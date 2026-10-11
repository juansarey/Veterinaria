from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)
from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito, RemitoBiologico


@pytest.fixture
def fecha():
    return datetime(2026, 10, 12, 10)


@pytest.fixture
def envio(fecha):
    remito = RemitoBiologico(
        1, Clinica(1, "Centro", "San Martín 100"),
        ConservadoraIsotermica(1, "CONS-001"), fecha,
    )
    for id_muestra in (1, 2):
        remito.agregar_muestra(
            MuestraBiologica(id_muestra, "Sangre", fecha), fecha
        )
    remito.asignar_precinto(PrecintoSanitario(1, "PREC-001"))
    return Envio(1, remito)


@pytest.fixture
def recepcion(envio, fecha):
    envio.iniciar(fecha)
    llegada = fecha + timedelta(hours=1)
    envio.registrar_llegada(llegada)
    return Recepcion(1, envio, llegada, "Verificación sanitaria")


def test_recepcion_conserva_datos_aunque_envio_este_pendiente(envio, fecha):
    recepcion = Recepcion(1, envio, fecha)

    assert recepcion.id_recepcion == 1
    assert recepcion.envio is envio
    assert recepcion.fecha_hora == fecha
    assert recepcion.observaciones == ""


def test_envio_obligatorio(fecha):
    with pytest.raises(ValueError, match="envío"):
        Recepcion(1, None, fecha)


@pytest.mark.parametrize("roto", [False, True])
def test_verificar_precinto_es_consulta(recepcion, roto):
    remito = recepcion.envio.remito
    precinto = remito.obtener_precinto()
    if roto:
        precinto.marcar_roto()
    estado_precinto = precinto.estado
    muestras = remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]

    assert recepcion.verificar_precinto() is (not roto)
    assert precinto.estado == estado_precinto
    assert remito.estado == EstadoRemito.DESPACHADO
    assert all(m.estado.obtener_nombre() == "EN_TRANSITO" for m in muestras)
    assert [m.obtener_historial() for m in muestras] == historiales


def test_verificar_precinto_ausente(fecha):
    remito = RemitoBiologico(
        1, Clinica(1, "Centro", "San Martín 100"),
        ConservadoraIsotermica(1, "CONS-001"), fecha,
    )
    recepcion = Recepcion(1, Envio(1, remito), fecha)

    assert recepcion.verificar_precinto() is False
    assert remito.obtener_precinto() is None


@pytest.mark.parametrize("en_transito", [False, True])
def test_no_procesa_envio_no_entregado(envio, fecha, en_transito):
    if en_transito:
        envio.iniciar(fecha)
    recepcion = Recepcion(1, envio, fecha)
    muestras = envio.remito.obtener_muestras()
    estados = [m.estado for m in muestras]
    historiales = [m.obtener_historial() for m in muestras]
    estado_remito = envio.remito.estado
    estado_envio = envio.estado

    assert recepcion.procesar_recepcion() is False
    assert envio.estado == estado_envio
    assert envio.remito.estado == estado_remito
    assert [m.estado for m in muestras] == estados
    assert [m.obtener_historial() for m in muestras] == historiales


@pytest.mark.parametrize("roto", [False, True])
@pytest.mark.parametrize("horas", [0, 1])
def test_procesa_todas_las_muestras_segun_precinto(recepcion, roto, horas):
    remito = recepcion.envio.remito
    if roto:
        remito.obtener_precinto().marcar_roto()
    recepcion.fecha_hora += timedelta(hours=horas)
    muestras = remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]
    esperado = "RECHAZADA" if roto else "RECIBIDA"

    assert recepcion.procesar_recepcion() is True
    assert remito.estado == EstadoRemito.RECIBIDO
    assert recepcion.envio.estado == EstadoEnvio.ENTREGADO
    assert remito.conservadora.estado == EstadoConservadora.EN_USO
    for muestra, anterior in zip(muestras, historiales):
        assert muestra.estado.obtener_nombre() == esperado
        historial = muestra.obtener_historial()
        assert len(historial) == len(anterior) + 1
        assert all(a is b for a, b in zip(historial[:-1], anterior))
        assert historial[-1].nombre_estado == esperado
        assert historial[-1].fecha_hora == recepcion.fecha_hora
        assert historial[-1].observaciones == recepcion.observaciones


def test_muestras_rechazadas_no_pueden_analizarse(recepcion):
    remito = recepcion.envio.remito
    remito.obtener_precinto().marcar_roto()
    recepcion.procesar_recepcion()

    for muestra in remito.obtener_muestras():
        historial = muestra.obtener_historial()
        assert muestra.analizar(recepcion.fecha_hora) is False
        assert muestra.estado.obtener_nombre() == "RECHAZADA"
        assert muestra.obtener_historial() == historial


@pytest.mark.parametrize("problema", ["sin_llegada", "fecha_anterior", "sin_precinto"])
def test_recepcion_invalida_no_modifica_muestras(recepcion, problema, monkeypatch):
    envio = recepcion.envio
    remito = envio.remito
    if problema == "sin_llegada":
        envio.fecha_hora_llegada = None
    elif problema == "fecha_anterior":
        recepcion.fecha_hora -= timedelta(seconds=1)
    else:
        # Simula un dato ausente que el flujo normal de despacho impide.
        monkeypatch.setattr(remito, "obtener_precinto", lambda: None)
    muestras = remito.obtener_muestras()
    estados = [m.estado for m in muestras]
    historiales = [m.obtener_historial() for m in muestras]

    assert recepcion.procesar_recepcion() is False
    assert envio.estado == EstadoEnvio.ENTREGADO
    assert remito.estado == EstadoRemito.DESPACHADO
    assert [m.estado for m in muestras] == estados
    assert [m.obtener_historial() for m in muestras] == historiales


@pytest.mark.parametrize("roto", [False, True])
@pytest.mark.parametrize("operacion_previa", ["recibir", "rechazar"])
def test_muestra_posterior_invalida_impide_recepcion_parcial(
    recepcion, roto, operacion_previa
):
    remito = recepcion.envio.remito
    if roto:
        remito.obtener_precinto().marcar_roto()
    muestras = remito.obtener_muestras()
    getattr(muestras[-1], operacion_previa)(recepcion.fecha_hora)
    estados = [m.estado for m in muestras]
    historiales = [m.obtener_historial() for m in muestras]

    assert recepcion.procesar_recepcion() is False
    assert remito.estado == EstadoRemito.DESPACHADO
    assert [m.estado for m in muestras] == estados
    assert [m.obtener_historial() for m in muestras] == historiales


def test_fecha_anterior_al_historial_no_procesa_recepcion(recepcion, fecha):
    # Una llegada alterada no debe permitir retroceder la fecha de las muestras.
    recepcion.envio.fecha_hora_llegada = fecha - timedelta(hours=1)
    recepcion.fecha_hora = fecha - timedelta(seconds=1)
    remito = recepcion.envio.remito
    muestras = remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]

    assert recepcion.procesar_recepcion() is False
    assert remito.estado == EstadoRemito.DESPACHADO
    assert all(m.estado.obtener_nombre() == "EN_TRANSITO" for m in muestras)
    assert [m.obtener_historial() for m in muestras] == historiales


@pytest.mark.parametrize("otra_instancia", [False, True])
def test_no_procesa_dos_veces(recepcion, otra_instancia):
    assert recepcion.procesar_recepcion() is True
    muestras = recepcion.envio.remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]
    if otra_instancia:
        recepcion = Recepcion(2, recepcion.envio, recepcion.fecha_hora)

    assert recepcion.procesar_recepcion() is False
    assert recepcion.envio.remito.estado == EstadoRemito.RECIBIDO
    assert [m.obtener_historial() for m in muestras] == historiales
