from datetime import datetime, time

import pytest

from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana
from veterinaria.dominio.clinica.turno import Turno


@pytest.fixture
def agenda():
    return AgendaMedica(
        {
            DiaSemana.LUNES,
            DiaSemana.MARTES,
            DiaSemana.JUEVES,
            DiaSemana.VIERNES,
        },
        time(8),
        time(13),
    )


@pytest.mark.parametrize("hora_hasta", [time(9), time(8)])
def test_rechaza_franja_sin_duracion_positiva(hora_hasta):
    with pytest.raises(ValueError, match="hora_hasta"):
        AgendaMedica({DiaSemana.LUNES}, time(9), hora_hasta)


@pytest.mark.parametrize(
    "inicio,fin,esperado",
    [
        (datetime(2026, 10, 12, 9), datetime(2026, 10, 12, 9, 30), True),
        (datetime(2026, 10, 14, 9), datetime(2026, 10, 14, 9, 30), False),
        (datetime(2026, 10, 16, 12, 30), datetime(2026, 10, 16, 13), True),
        (datetime(2026, 10, 16, 12, 30), datetime(2026, 10, 16, 13, 30), False),
        (datetime(2026, 10, 12, 7, 30), datetime(2026, 10, 12, 8, 30), False),
        (datetime(2026, 10, 12, 8), datetime(2026, 10, 12, 13), True),
        (datetime(2026, 10, 17, 9), datetime(2026, 10, 17, 9, 30), False),
        (datetime(2026, 10, 12, 10), datetime(2026, 10, 13, 11), False),
    ],
)
def test_contencion_completa_en_una_fecha(agenda, inicio, fin, esperado):
    assert agenda.contiene(Turno(1, inicio, fin)) is esperado


@pytest.mark.parametrize(
    "atributo,valor",
    [
        ("dias_trabajo", {DiaSemana.DOMINGO}),
        ("hora_desde", time(8)),
        ("hora_hasta", time(13)),
    ],
)
def test_franja_no_admite_modificacion_directa(agenda, atributo, valor):
    anterior = getattr(agenda, atributo)
    with pytest.raises(AttributeError):
        setattr(agenda, atributo, valor)
    assert getattr(agenda, atributo) == anterior


def test_dias_de_trabajo_devueltos_son_una_copia(agenda):
    dias_antes = agenda.dias_trabajo
    agenda.dias_trabajo.clear()
    assert agenda.dias_trabajo == dias_antes
