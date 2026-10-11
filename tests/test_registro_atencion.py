from datetime import date, datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna


@pytest.fixture
def mascota():
    responsable = Cliente(1, "Laura", "García", "30111222")
    paciente = Mascota(1, "Luna", "Perro", responsable)
    paciente.asignar_historia_clinica(HistoriaClinica(1, date(2026, 1, 1)))
    return paciente


@pytest.fixture
def vacuna():
    return Vacuna(1, "Antirrábica", "Perro", True)


def crear_atencion(id_atencion=1, fecha=datetime(2026, 10, 12, 9)):
    veterinario = Veterinario(1, "Ana", "Pérez", "MP-100")
    return Atencion(
        id_atencion,
        fecha,
        TipoAtencion.CONSULTA,
        "Control general",
        veterinario,
    )


def test_registra_atencion_con_vacunas_obligatorias_al_dia(mascota, vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2026, 1, 1), date(2027, 1, 1)
    )
    atencion = crear_atencion()
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.registrar_atencion(atencion, [vacuna]) is True
    assert mascota.obtener_historia_clinica().obtener_atenciones() == [atencion]


def test_rechaza_atencion_si_falta_vacuna_obligatoria(mascota, vacuna):
    atencion = crear_atencion()

    assert mascota.registrar_atencion(atencion, [vacuna]) is False
    assert mascota.obtener_historia_clinica().obtener_atenciones() == []


def test_rechaza_atencion_si_vacuna_obligatoria_esta_vencida(mascota, vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2025, 1, 1), date(2026, 1, 1)
    )
    atencion = crear_atencion()
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.registrar_atencion(atencion, [vacuna]) is False
    assert mascota.obtener_historia_clinica().obtener_atenciones() == []


def test_rechaza_atencion_si_no_existe_historia_clinica(vacuna):
    responsable = Cliente(1, "Laura", "García", "30111222")
    mascota = Mascota(1, "Luna", "Perro", responsable)

    assert mascota.registrar_atencion(crear_atencion(), [vacuna]) is False


def test_atencion_repetida_devuelve_false(mascota):
    atencion = crear_atencion()

    assert mascota.registrar_atencion(atencion, []) is True
    assert mascota.registrar_atencion(atencion, []) is False
    assert mascota.obtener_historia_clinica().obtener_atenciones() == [atencion]


@pytest.mark.parametrize("motivo", ["faltante", "vencida"])
def test_rechazo_no_modifica_historia(mascota, vacuna, motivo):
    anterior = crear_atencion(1, datetime(2026, 10, 11, 9))
    mascota.registrar_atencion(anterior, [])

    if motivo == "vencida":
        aplicacion = AplicacionVacuna(
            1, vacuna, date(2025, 1, 1), date(2026, 1, 1)
        )
        mascota.agregar_aplicacion_vacuna(aplicacion)

    rechazada = crear_atencion(2)
    assert mascota.registrar_atencion(rechazada, [vacuna]) is False
    assert mascota.obtener_historia_clinica().obtener_atenciones() == [anterior]


def test_aplicacion_posterior_no_valida_fecha_de_atencion(mascota, vacuna):
    aplicacion = AplicacionVacuna(1, vacuna, date(2026, 10, 13))
    atencion = crear_atencion(fecha=datetime(2026, 10, 12, 9))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.registrar_atencion(atencion, [vacuna]) is False
    assert mascota.obtener_historia_clinica().obtener_atenciones() == []


def test_evalua_vigencia_en_fecha_de_atencion(mascota, vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2025, 1, 1), date(2025, 12, 31)
    )
    atencion = crear_atencion(fecha=datetime(2025, 6, 1, 9))
    mascota.agregar_aplicacion_vacuna(aplicacion)

    assert mascota.registrar_atencion(atencion, [vacuna]) is True
    assert mascota.obtener_historia_clinica().obtener_atenciones() == [atencion]
