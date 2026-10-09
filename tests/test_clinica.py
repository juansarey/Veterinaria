import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.clinica.veterinario import Veterinario


@pytest.fixture
def clinica():
    return Clinica(1, "Centro Veterinario", "San Martín 100", "011-12345678")


@pytest.fixture
def veterinario():
    return Veterinario(1, "Ana", "Pérez", "MP-100")


def test_asocia_veterinarios_a_la_clinica(clinica, veterinario):
    otro = Veterinario(2, "Luis", "Gómez", "MP-101")
    assert clinica.obtener_veterinarios() == []

    clinica.agregar_veterinario(veterinario)
    clinica.agregar_veterinario(otro)

    assert clinica.obtener_veterinarios() == [veterinario, otro]


def test_devuelve_copia_de_veterinarios(clinica, veterinario):
    clinica.agregar_veterinario(veterinario)
    copia = clinica.obtener_veterinarios()
    copia.clear()
    assert clinica.obtener_veterinarios() == [veterinario]


def test_informa_si_pudo_registrar_el_veterinario(clinica, veterinario):
    assert clinica.agregar_veterinario(veterinario) is True
    assert clinica.agregar_veterinario(veterinario) is False
    assert clinica.obtener_veterinarios() == [veterinario]


def test_no_controla_asociacion_del_mismo_veterinario_a_otra_clinica(
    clinica, veterinario
):
    otra = Clinica(2, "Clínica Norte", "Belgrano 200")
    clinica.agregar_veterinario(veterinario)
    otra.agregar_veterinario(veterinario)
    assert clinica.obtener_veterinarios() == [veterinario]
    assert otra.obtener_veterinarios() == [veterinario]
