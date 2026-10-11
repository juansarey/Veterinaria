from datetime import date, datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.veterinario import Veterinario


@pytest.fixture
def historia():
    return HistoriaClinica(1, date(2026, 10, 10), "Sin antecedentes")


@pytest.fixture
def atencion():
    veterinario = Veterinario(1, "Ana", "Pérez", "MP-100")
    return Atencion(
        1,
        datetime(2026, 10, 12, 9),
        TipoAtencion.CONSULTA,
        "Control general",
        veterinario,
    )


def test_inicialmente_no_tiene_atenciones(historia):
    assert historia.obtener_atenciones() == []


def test_agrega_atencion(historia, atencion):
    assert historia.agregar_atencion(atencion) is True
    assert historia.obtener_atenciones() == [atencion]


def test_no_agrega_dos_veces_la_misma_instancia(historia, atencion):
    historia.agregar_atencion(atencion)
    assert historia.agregar_atencion(atencion) is False
    assert historia.obtener_atenciones() == [atencion]


def test_atenciones_devuelve_una_copia(historia, atencion):
    historia.agregar_atencion(atencion)
    historia.obtener_atenciones().clear()
    assert historia.obtener_atenciones() == [atencion]
