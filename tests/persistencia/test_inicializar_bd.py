from contextlib import closing

import pytest

from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd


def test_crea_solamente_las_dos_tablas_del_incremento():
    with closing(abrir_conexion(":memory:")) as conexion:
        inicializar_bd(conexion)
        tablas = conexion.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        assert {fila["name"] for fila in tablas} == {"cliente", "mascota"}


def test_inicializar_dos_veces_conserva_datos(
    conexion, cliente_dao, mascota_dao, cliente, mascota
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    conexion.commit()
    inicializar_bd(conexion)
    assert cliente_dao.obtener_por_id(10).nombre == cliente.nombre
    assert mascota_dao.obtener_por_id(20).nombre == mascota.nombre


def test_inicializacion_no_confirma_transaccion_pendiente(conexion, cliente_dao, cliente):
    cliente_dao.crear(cliente)
    inicializar_bd(conexion)
    conexion.rollback()
    assert cliente_dao.listar() == []


def test_fk_mascota_referencia_cliente_sin_cascadas(conexion):
    claves = conexion.execute("PRAGMA foreign_key_list(mascota)").fetchall()
    assert len(claves) == 1
    assert claves[0]["table"] == "cliente"
    assert claves[0]["from"] == "id_cliente"
    assert claves[0]["to"] == "id_cliente"
    assert claves[0]["on_delete"] == "NO ACTION"
    assert claves[0]["on_update"] == "NO ACTION"


@pytest.mark.parametrize("tabla, esperado", [
    ("cliente", [
        ("id_cliente", "INTEGER", 0, 1),
        ("nombre", "VARCHAR(80)", 1, 0),
        ("apellido", "VARCHAR(80)", 1, 0),
        ("dni", "VARCHAR(20)", 0, 0),
        ("telefono", "VARCHAR(30)", 0, 0),
        ("email", "VARCHAR(120)", 0, 0),
    ]),
    ("mascota", [
        ("id_mascota", "INTEGER", 0, 1),
        ("id_cliente", "INTEGER", 1, 0),
        ("nombre", "VARCHAR(80)", 1, 0),
        ("especie", "VARCHAR(50)", 1, 0),
        ("raza", "VARCHAR(80)", 0, 0),
        ("fecha_nacimiento", "TEXT", 0, 0),
        ("sexo", "VARCHAR(20)", 0, 0),
    ]),
])
def test_columnas_tipos_y_opcionalidad(conexion, tabla, esperado):
    filas = conexion.execute(
        "SELECT name, type, [notnull], pk FROM pragma_table_info(?)", (tabla,)
    ).fetchall()
    assert [tuple(fila) for fila in filas] == esperado
