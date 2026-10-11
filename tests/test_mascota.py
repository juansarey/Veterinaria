from datetime import date

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota


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
