from datetime import date

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd
from veterinaria.persistencia.mascota_dao import MascotaDAO


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
def cliente():
    return Cliente(10, "Laura", "García", "30111222", "351-123456", "laura@test.com")


@pytest.fixture
def mascota(cliente):
    return Mascota(20, "Luna", "Perro", cliente, "Mestiza", date(2020, 5, 10), "Hembra")
