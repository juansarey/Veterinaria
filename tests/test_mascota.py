from datetime import date

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna


@pytest.fixture
def responsable():
    return Cliente(1, "Laura", "García", "30111222")


def test_guarda_sus_datos_y_conserva_el_responsable(responsable):
    mascota = Mascota(
        1,
        "Luna",
        "Perro",
        responsable,
        "Mestiza",
        date(2020, 5, 10),
        "Hembra",
    )

    assert mascota.id_mascota == 1
    assert mascota.nombre == "Luna"
    assert mascota.especie == "Perro"
    assert mascota.responsable is responsable
    assert mascota.raza == "Mestiza"
    assert mascota.fecha_nacimiento == date(2020, 5, 10)
    assert mascota.sexo == "Hembra"


def test_rechaza_responsable_ausente():
    with pytest.raises(ValueError, match="responsable"):
        Mascota(1, "Luna", "Perro", None)


def test_historia_clinica_inicialmente_ausente(responsable):
    mascota = Mascota(1, "Luna", "Perro", responsable)
    assert mascota.obtener_historia_clinica() is None


def test_primera_asignacion_de_historia_devuelve_true(responsable):
    mascota = Mascota(1, "Luna", "Perro", responsable)
    historia = HistoriaClinica(1, date(2026, 10, 10))

    assert mascota.asignar_historia_clinica(historia) is True
    assert mascota.obtener_historia_clinica() is historia


def test_segunda_asignacion_no_reemplaza_la_historia(responsable):
    mascota = Mascota(1, "Luna", "Perro", responsable)
    original = HistoriaClinica(1, date(2026, 10, 10))
    otra = HistoriaClinica(2, date(2026, 10, 11))
    mascota.asignar_historia_clinica(original)

    assert mascota.asignar_historia_clinica(otra) is False
    assert mascota.obtener_historia_clinica() is original


@pytest.fixture
def mascota(responsable):
    return Mascota(1, "Luna", "Perro", responsable)


@pytest.fixture
def antirrabica():
    return Vacuna(1, "Antirrábica", "Perro", True)


def test_aplicaciones_inicialmente_vacias(mascota):
    assert mascota.obtener_aplicaciones_vacuna() == []


def test_agrega_aplicacion_de_vacuna(mascota, antirrabica):
    aplicacion = AplicacionVacuna(
        1, antirrabica, date(2026, 1, 1), date(2027, 1, 1)
    )

    assert mascota.agregar_aplicacion_vacuna(aplicacion) is True
    assert mascota.obtener_aplicaciones_vacuna() == [aplicacion]


def test_no_agrega_dos_veces_la_misma_aplicacion(mascota, antirrabica):
    aplicacion = AplicacionVacuna(1, antirrabica, date(2026, 1, 1))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.agregar_aplicacion_vacuna(aplicacion) is False
    assert mascota.obtener_aplicaciones_vacuna() == [aplicacion]


def test_aplicaciones_devueltas_son_una_copia(mascota, antirrabica):
    aplicacion = AplicacionVacuna(1, antirrabica, date(2026, 1, 1))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    mascota.obtener_aplicaciones_vacuna().clear()

    assert mascota.obtener_aplicaciones_vacuna() == [aplicacion]


def test_vacuna_obligatoria_faltante_esta_pendiente(mascota, antirrabica):
    assert mascota.obtener_vacunas_pendientes(
        [antirrabica], date(2026, 10, 12)
    ) == [antirrabica]
    assert not mascota.vacunas_obligatorias_al_dia(
        [antirrabica], date(2026, 10, 12)
    )


def test_vacuna_obligatoria_vencida_esta_pendiente(mascota, antirrabica):
    aplicacion = AplicacionVacuna(
        1, antirrabica, date(2025, 1, 1), date(2026, 1, 1)
    )
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.obtener_vacunas_pendientes(
        [antirrabica], date(2026, 10, 12)
    ) == [antirrabica]


def test_vacuna_obligatoria_vigente_no_esta_pendiente(mascota, antirrabica):
    aplicacion = AplicacionVacuna(
        1, antirrabica, date(2026, 1, 1), date(2027, 1, 1)
    )
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.obtener_vacunas_pendientes(
        [antirrabica], date(2026, 10, 12)
    ) == []
    assert mascota.vacunas_obligatorias_al_dia(
        [antirrabica], date(2026, 10, 12)
    )


def test_varias_vacunas_obligatorias_deben_estar_vigentes(mascota, antirrabica):
    sextuple = Vacuna(2, "Sextuple", "Perro", True)
    aplicacion = AplicacionVacuna(1, antirrabica, date(2026, 1, 1))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.obtener_vacunas_pendientes(
        [antirrabica, sextuple], date(2026, 10, 12)
    ) == [sextuple]


def test_vacuna_opcional_no_genera_pendiente(mascota):
    opcional = Vacuna(3, "Bordetella", "Perro", False)

    assert mascota.obtener_vacunas_pendientes(
        [opcional], date(2026, 10, 12)
    ) == []


def test_vacuna_de_otra_especie_no_genera_pendiente(mascota):
    felina = Vacuna(4, "Triple felina", "Gato", True)

    assert mascota.obtener_vacunas_pendientes([felina], date(2026, 10, 12)) == []


def test_aplicacion_vigente_cubre_otra_vencida_de_la_misma_vacuna(
    mascota, antirrabica
):
    vencida = AplicacionVacuna(
        1, antirrabica, date(2024, 1, 1), date(2025, 1, 1)
    )
    vigente = AplicacionVacuna(
        2, antirrabica, date(2026, 1, 1), date(2027, 1, 1)
    )
    mascota.agregar_aplicacion_vacuna(vencida)
    mascota.agregar_aplicacion_vacuna(vigente)

    assert mascota.obtener_vacunas_pendientes(
        [antirrabica], date(2026, 10, 12)
    ) == []


def test_compara_vacunas_por_id(mascota, antirrabica):
    misma_vacuna = Vacuna(1, "Antirrábica actualizada", "Perro", True)
    aplicacion = AplicacionVacuna(1, antirrabica, date(2026, 1, 1))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.obtener_vacunas_pendientes(
        [misma_vacuna], date(2026, 10, 12)
    ) == []
