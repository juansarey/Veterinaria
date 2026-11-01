from datetime import date, datetime, time

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana
from veterinaria.dominio.clinica.turno import Turno
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.persistencia.agenda_medica_dao import AgendaMedicaDAO
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.persistencia.turno_dao import TurnoDAO
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO


@pytest.fixture
def conexion():
    conexion = abrir_conexion(":memory:")
    try:
        inicializar_bd(conexion)
        yield conexion
    finally:
        conexion.close()


@pytest.fixture
def cliente_dao(conexion):
    return ClienteDAO(conexion)


@pytest.fixture
def mascota_dao(conexion):
    return MascotaDAO(conexion)


@pytest.fixture
def clinica_dao(conexion):
    return ClinicaDAO(conexion)


@pytest.fixture
def veterinario_dao(conexion):
    return VeterinarioDAO(conexion)


@pytest.fixture
def agenda_medica_dao(conexion):
    return AgendaMedicaDAO(conexion)


@pytest.fixture
def turno_dao(conexion):
    return TurnoDAO(conexion)


@pytest.fixture
def cliente():
    return Cliente(10, "Laura", "García", "30111222", "351-123456", "laura@test.com")


@pytest.fixture
def mascota(cliente):
    return Mascota(20, "Luna", "Perro", cliente, "Mestiza", date(2020, 5, 10), "Hembra")


@pytest.fixture
def clinica():
    return Clinica(30, "Centro Veterinario", "San Martín 100", "351-555555")


@pytest.fixture
def veterinario():
    return Veterinario(40, "Ana", "Pérez", "MP-100", "Clínica general")


@pytest.fixture
def agenda_medica():
    return AgendaMedica(
        {DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.VIERNES},
        time(8, 30, 15, 123456),
        time(13, 45, 30, 654321),
    )


@pytest.fixture
def turno(mascota):
    return Turno(
        50,
        datetime(2026, 11, 2, 9, 15, 10, 123456),
        datetime(2026, 11, 2, 10, 30, 20, 654321),
        mascota,
        "Control anual",
    )
