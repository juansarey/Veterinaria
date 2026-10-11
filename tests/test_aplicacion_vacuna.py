from datetime import date

import pytest

from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna


@pytest.fixture
def vacuna():
    return Vacuna(1, "Antirrábica", "Perro", True)


def test_conserva_la_vacuna(vacuna):
    aplicacion = AplicacionVacuna(1, vacuna, date(2026, 1, 1))
    assert aplicacion.vacuna is vacuna


def test_rechaza_vacuna_ausente():
    with pytest.raises(ValueError, match="vacuna"):
        AplicacionVacuna(1, None, date(2026, 1, 1))


@pytest.mark.parametrize("fecha_proxima", [date(2026, 1, 1), date(2025, 12, 31)])
def test_rechaza_fecha_proxima_no_posterior(vacuna, fecha_proxima):
    with pytest.raises(ValueError, match="posterior"):
        AplicacionVacuna(1, vacuna, date(2026, 1, 1), fecha_proxima)


def test_aplicacion_futura_no_esta_vigente_ni_vencida(vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2026, 6, 1), date(2027, 6, 1)
    )

    assert not aplicacion.esta_vigente(date(2026, 5, 31))
    assert not aplicacion.esta_vencida(date(2026, 5, 31))


def test_aplicacion_esta_vigente_antes_de_proxima_dosis(vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2026, 1, 1), date(2027, 1, 1)
    )

    assert aplicacion.esta_vigente(date(2026, 12, 31))
    assert not aplicacion.esta_vencida(date(2026, 12, 31))


def test_aplicacion_esta_vencida_despues_de_proxima_dosis(vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2026, 1, 1), date(2027, 1, 1)
    )

    assert not aplicacion.esta_vigente(date(2027, 1, 2))
    assert aplicacion.esta_vencida(date(2027, 1, 2))


def test_fecha_de_proxima_dosis_ya_se_considera_vencida(vacuna):
    aplicacion = AplicacionVacuna(
        1, vacuna, date(2026, 1, 1), date(2027, 1, 1)
    )

    assert not aplicacion.esta_vigente(date(2027, 1, 1))
    assert aplicacion.esta_vencida(date(2027, 1, 1))


def test_sin_proxima_dosis_permanece_vigente(vacuna):
    aplicacion = AplicacionVacuna(1, vacuna, date(2026, 1, 1))

    assert aplicacion.esta_vigente(date(2030, 1, 1))
    assert not aplicacion.esta_vencida(date(2030, 1, 1))
