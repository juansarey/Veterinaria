from contextlib import closing

import pytest

from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd


def test_crea_solamente_las_tablas_de_persistencia_1_2_y_3():
    with closing(abrir_conexion(":memory:")) as conexion:
        inicializar_bd(conexion)
        tablas = conexion.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        assert {fila["name"] for fila in tablas} == {
            "cliente",
            "mascota",
            "historia_clinica",
            "clinica",
            "veterinario",
            "atencion",
            "agenda_medica",
            "agenda_medica_dia",
            "turno",
        }


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


@pytest.mark.parametrize("tabla, referencias", [
    ("veterinario", {("id_clinica", "clinica", "id_clinica")}),
    ("agenda_medica", {("id_veterinario", "veterinario", "id_veterinario")}),
    ("agenda_medica_dia", {("id_agenda", "agenda_medica", "id_agenda")}),
    ("turno", {
        ("id_mascota", "mascota", "id_mascota"),
        ("id_veterinario", "veterinario", "id_veterinario"),
    }),
    ("historia_clinica", {
        ("id_mascota", "mascota", "id_mascota"),
    }),
    ("atencion", {
        ("id_historia", "historia_clinica", "id_historia"),
        ("id_veterinario", "veterinario", "id_veterinario"),
    }),
])
def test_fk_de_persistencia_2_y_3_sin_cascadas(conexion, tabla, referencias):
    claves = conexion.execute(f"PRAGMA foreign_key_list({tabla})").fetchall()
    assert {
        (fila["from"], fila["table"], fila["to"])
        for fila in claves
    } == referencias
    assert all(fila["on_delete"] == "NO ACTION" for fila in claves)
    assert all(fila["on_update"] == "NO ACTION" for fila in claves)


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
    ("clinica", [
        ("id_clinica", "INTEGER", 0, 1),
        ("nombre", "VARCHAR(100)", 1, 0),
        ("direccion", "VARCHAR(200)", 1, 0),
        ("telefono", "VARCHAR(30)", 0, 0),
    ]),
    ("veterinario", [
        ("id_veterinario", "INTEGER", 0, 1),
        ("id_clinica", "INTEGER", 1, 0),
        ("nombre", "VARCHAR(80)", 1, 0),
        ("apellido", "VARCHAR(80)", 1, 0),
        ("matricula", "VARCHAR(30)", 1, 0),
        ("especialidad", "VARCHAR(100)", 0, 0),
    ]),
    ("agenda_medica", [
        ("id_agenda", "INTEGER", 0, 1),
        ("id_veterinario", "INTEGER", 1, 0),
        ("hora_desde", "TEXT", 1, 0),
        ("hora_hasta", "TEXT", 1, 0),
    ]),
    ("agenda_medica_dia", [
        ("id_agenda", "INTEGER", 1, 1),
        ("dia", "TEXT", 1, 2),
    ]),
    ("turno", [
        ("id_turno", "INTEGER", 0, 1),
        ("id_mascota", "INTEGER", 1, 0),
        ("id_veterinario", "INTEGER", 1, 0),
        ("fecha_hora_inicio", "TEXT", 1, 0),
        ("fecha_hora_fin", "TEXT", 1, 0),
        ("estado", "TEXT", 1, 0),
        ("motivo", "VARCHAR(200)", 0, 0),
    ]),
    ("historia_clinica", [
        ("id_historia", "INTEGER", 0, 1),
        ("id_mascota", "INTEGER", 1, 0),
        ("fecha_apertura", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("atencion", [
        ("id_atencion", "INTEGER", 0, 1),
        ("id_historia", "INTEGER", 1, 0),
        ("id_veterinario", "INTEGER", 1, 0),
        ("fecha_hora", "TEXT", 1, 0),
        ("tipo", "TEXT", 1, 0),
        ("motivo", "VARCHAR(200)", 0, 0),
        ("diagnostico", "TEXT", 0, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
])
def test_columnas_tipos_y_opcionalidad(conexion, tabla, esperado):
    filas = conexion.execute(
        "SELECT name, type, [notnull], pk FROM pragma_table_info(?)", (tabla,)
    ).fetchall()
    assert [tuple(fila) for fila in filas] == esperado
