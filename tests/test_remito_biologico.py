from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.remito_biologico import (
    EstadoRemito,
    RemitoBiologico,
)


@pytest.fixture
def clinica():
    return Clinica(1, "Clínica Centro", "San Martín 100")


@pytest.fixture
def conservadora():
    return ConservadoraIsotermica(1, "CONS-001")


@pytest.fixture
def fecha_emision():
    return datetime(2026, 10, 12, 10)


@pytest.fixture
def remito(clinica, conservadora, fecha_emision):
    return RemitoBiologico(1, clinica, conservadora, fecha_emision)


@pytest.fixture
def muestra(fecha_emision):
    return MuestraBiologica(1, "Sangre", fecha_emision)


def test_remito_nace_generado_y_conserva_sus_datos(
    remito, clinica, conservadora, fecha_emision
):
    assert remito.estado == EstadoRemito.GENERADO
    assert remito.clinica_origen is clinica
    assert remito.conservadora is conservadora
    assert remito.fecha_emision == fecha_emision


def test_conservadora_queda_en_uso_al_crear_remito(remito, conservadora):
    assert conservadora.estado == EstadoConservadora.EN_USO
    assert conservadora.esta_disponible() is False


def test_rechaza_clinica_ausente_sin_ocupar_conservadora(
    conservadora, fecha_emision
):
    with pytest.raises(ValueError, match="clínica"):
        RemitoBiologico(1, None, conservadora, fecha_emision)

    assert conservadora.esta_disponible() is True


def test_rechaza_conservadora_ausente(clinica, fecha_emision):
    with pytest.raises(ValueError, match="conservadora"):
        RemitoBiologico(1, clinica, None, fecha_emision)


def test_rechaza_conservadora_en_uso(clinica, conservadora, fecha_emision):
    conservadora.marcar_en_uso()

    with pytest.raises(ValueError, match="disponible"):
        RemitoBiologico(1, clinica, conservadora, fecha_emision)


def test_muestras_inicialmente_vacias(remito):
    assert remito.obtener_muestras() == []


def test_muestras_devueltas_son_una_copia(remito, muestra, fecha_emision):
    remito.agregar_muestra(muestra, fecha_emision)
    remito.obtener_muestras().clear()

    assert remito.obtener_muestras() == [muestra]


def test_agrega_y_empaqueta_muestra_extraida(remito, muestra, fecha_emision):
    fecha_empaquetado = fecha_emision + timedelta(hours=1)

    assert remito.agregar_muestra(
        muestra, fecha_empaquetado, "Acondicionada"
    ) is True
    assert remito.obtener_muestras() == [muestra]
    assert muestra.estado.obtener_nombre() == "EMPAQUETADA"

    registro = muestra.obtener_historial()[-1]
    assert registro.nombre_estado == "EMPAQUETADA"
    assert registro.fecha_hora == fecha_empaquetado
    assert registro.observaciones == "Acondicionada"


def test_no_agrega_dos_veces_la_misma_instancia(remito, muestra, fecha_emision):
    remito.agregar_muestra(muestra, fecha_emision)
    historial_antes = muestra.obtener_historial()

    assert remito.agregar_muestra(muestra, fecha_emision) is False
    assert remito.obtener_muestras() == [muestra]
    assert muestra.obtener_historial() == historial_antes


def test_no_agrega_muestra_que_no_esta_extraida(remito, muestra, fecha_emision):
    muestra.empaquetar(fecha_emision)
    historial_antes = muestra.obtener_historial()

    assert remito.agregar_muestra(muestra, fecha_emision) is False
    assert remito.obtener_muestras() == []
    assert muestra.obtener_historial() == historial_antes


def test_no_agrega_muestra_con_fecha_anterior(remito, muestra, fecha_emision):
    fecha_anterior = fecha_emision - timedelta(seconds=1)
    historial_antes = muestra.obtener_historial()

    assert remito.agregar_muestra(muestra, fecha_anterior) is False
    assert remito.obtener_muestras() == []
    assert muestra.estado.obtener_nombre() == "EXTRAIDA"
    assert muestra.obtener_historial() == historial_antes


def test_misma_muestra_no_se_agrega_a_dos_remitos(
    remito, muestra, clinica, fecha_emision
):
    otra_conservadora = ConservadoraIsotermica(2, "CONS-002")
    otro_remito = RemitoBiologico(
        2, clinica, otra_conservadora, fecha_emision
    )

    assert remito.agregar_muestra(muestra, fecha_emision) is True
    assert otro_remito.agregar_muestra(muestra, fecha_emision) is False
    assert otro_remito.obtener_muestras() == []


def test_precinto_inicialmente_ausente(remito):
    assert remito.obtener_precinto() is None


def test_no_asigna_precinto_ausente(remito):
    assert remito.asignar_precinto(None) is False
    assert remito.obtener_precinto() is None


def test_asigna_un_precinto(remito):
    precinto = PrecintoSanitario(1, "PREC-001")

    assert remito.asignar_precinto(precinto) is True
    assert remito.obtener_precinto() is precinto


def test_no_reemplaza_precinto_existente(remito):
    original = PrecintoSanitario(1, "PREC-001")
    otro = PrecintoSanitario(2, "PREC-002")
    remito.asignar_precinto(original)

    assert remito.asignar_precinto(otro) is False
    assert remito.obtener_precinto() is original


def test_permite_asignar_precinto_a_remito_vacio(remito):
    precinto = PrecintoSanitario(1, "PREC-001")

    assert remito.asignar_precinto(precinto) is True
    assert remito.puede_despacharse() is False


def test_permite_asignar_precinto_roto(remito):
    precinto = PrecintoSanitario(1, "PREC-001")
    precinto.marcar_roto()

    assert remito.asignar_precinto(precinto) is True
    assert remito.obtener_precinto() is precinto
    assert remito.puede_despacharse() is False


def test_permite_agregar_muestra_despues_de_asignar_precinto(
    remito, muestra, fecha_emision
):
    remito.asignar_precinto(PrecintoSanitario(1, "PREC-001"))

    assert remito.agregar_muestra(muestra, fecha_emision) is True
    assert remito.obtener_muestras() == [muestra]


def test_no_puede_despacharse_sin_muestras(remito):
    remito.asignar_precinto(PrecintoSanitario(1, "PREC-001"))
    assert remito.puede_despacharse() is False


def test_no_puede_despacharse_sin_precinto(remito, muestra, fecha_emision):
    remito.agregar_muestra(muestra, fecha_emision)
    assert remito.puede_despacharse() is False


def test_no_puede_despacharse_con_precinto_roto(
    remito, muestra, fecha_emision
):
    precinto = PrecintoSanitario(1, "PREC-001")
    precinto.marcar_roto()
    remito.agregar_muestra(muestra, fecha_emision)
    remito.asignar_precinto(precinto)

    assert remito.puede_despacharse() is False
    assert muestra.estado.obtener_nombre() == "EMPAQUETADA"


def test_puede_despacharse_con_requisitos_completos(
    remito, muestra, fecha_emision
):
    remito.agregar_muestra(muestra, fecha_emision)
    remito.asignar_precinto(PrecintoSanitario(1, "PREC-001"))

    assert remito.puede_despacharse() is True


def test_puede_despacharse_es_solo_consulta(
    remito, muestra, conservadora, fecha_emision
):
    precinto = PrecintoSanitario(1, "PREC-001")
    remito.agregar_muestra(muestra, fecha_emision)
    remito.asignar_precinto(precinto)
    historial_antes = muestra.obtener_historial()

    assert remito.puede_despacharse() is True
    assert remito.puede_despacharse() is True
    assert remito.estado == EstadoRemito.GENERADO
    assert remito.obtener_muestras() == [muestra]
    assert muestra.obtener_historial() == historial_antes
    assert remito.obtener_precinto() is precinto
    assert precinto.esta_intacto() is True
    assert conservadora.estado == EstadoConservadora.EN_USO
