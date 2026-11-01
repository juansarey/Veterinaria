from contextlib import closing
import sqlite3

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd
from veterinaria.persistencia.mascota_dao import MascotaDAO


def test_abre_memoria_y_activa_fk():
    with closing(abrir_conexion(":memory:")) as conexion:
        assert isinstance(conexion, sqlite3.Connection)
        assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conexion.execute("SELECT 1 AS valor").fetchone()["valor"] == 1


def test_conexion_se_cierra_normalmente():
    conexion = abrir_conexion(":memory:")
    conexion.close()
    with pytest.raises(sqlite3.ProgrammingError):
        conexion.execute("SELECT 1")


@pytest.mark.parametrize("confirmar", [False, True])
def test_commit_explicito_controla_persistencia_en_archivo(
    tmp_path, cliente, mascota, confirmar
):
    ruta = tmp_path / "veterinaria.db"
    with closing(abrir_conexion(ruta)) as conexion:
        inicializar_bd(conexion)
        ClienteDAO(conexion).crear(cliente)
        MascotaDAO(conexion).crear(mascota)
        if confirmar:
            conexion.commit()

    with closing(abrir_conexion(ruta)) as conexion:
        assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (ClienteDAO(conexion).obtener_por_id(10) is not None) is confirmar
        assert (MascotaDAO(conexion).obtener_por_id(20) is not None) is confirmar


def test_error_en_mascota_permite_rollback_de_ambos_dao(
    conexion, cliente_dao, mascota_dao, cliente, mascota
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    inexistente = Cliente(999, "Otro", "Responsable", "999")
    with pytest.raises(sqlite3.IntegrityError):
        mascota_dao.crear(Mascota(21, "Sol", "Gato", inexistente))

    # El DAO propaga el error y deja la decisión de rollback al llamador.
    assert cliente_dao.obtener_por_id(10) is not None
    assert mascota_dao.obtener_por_id(20) is not None
    conexion.rollback()
    assert cliente_dao.listar() == []
    assert mascota_dao.listar() == []


@pytest.mark.parametrize("entidad", ["cliente", "mascota"])
@pytest.mark.parametrize("operacion", ["actualizar", "eliminar"])
def test_modificaciones_no_hacen_commit(
    conexion, cliente_dao, mascota_dao, cliente, mascota, entidad, operacion
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    conexion.commit()

    # Se necesita quitar la mascota antes de eliminar al cliente por la FK.
    if entidad == "cliente" and operacion == "eliminar":
        mascota_dao.eliminar(20)

    dao, objeto, identificador = (
        (cliente_dao, cliente, 10) if entidad == "cliente"
        else (mascota_dao, mascota, 20)
    )
    nombre_original = objeto.nombre
    if operacion == "actualizar":
        objeto.nombre = "Modificado"
        assert dao.actualizar(objeto) is True
    else:
        assert dao.eliminar(identificador) is True

    conexion.rollback()
    assert dao.obtener_por_id(identificador).nombre == nombre_original
    assert mascota_dao.obtener_por_id(20) is not None
