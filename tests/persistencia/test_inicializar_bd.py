from contextlib import closing
import sqlite3

import pytest

from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd


def test_crea_solamente_las_tablas_de_persistencia_1_a_8():
    with closing(abrir_conexion(":memory:")) as conexion:
        inicializar_bd(conexion)
        tablas = conexion.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        assert {fila["name"] for fila in tablas} == {
            "cliente",
            "mascota",
            "vacuna",
            "aplicacion_vacuna",
            "historia_clinica",
            "clinica",
            "veterinario",
            "atencion",
            "agenda_medica",
            "agenda_medica_dia",
            "turno",
            "orden_derivacion_laboratorio",
            "muestra_biologica",
            "historial_estado_muestra",
            "conservadora_isotermica",
            "remito_biologico",
            "precinto_sanitario",
            "envio",
            "recepcion",
            "resultado_analisis",
            "comprobante_atencion",
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


def test_inicializar_dos_veces_conserva_datos_de_persistencia_6(
    conexion, conservadora_isotermica_dao, conservadora_isotermica
):
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    conexion.commit()
    inicializar_bd(conexion)
    recuperada = conservadora_isotermica_dao.obtener_por_id(120)
    assert recuperada.codigo == "CONS-120"


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
    ("aplicacion_vacuna", {
        ("id_mascota", "mascota", "id_mascota"),
        ("id_vacuna", "vacuna", "id_vacuna"),
    }),
    ("orden_derivacion_laboratorio", {
        ("id_atencion", "atencion", "id_atencion"),
    }),
    ("muestra_biologica", {
        ("id_orden", "orden_derivacion_laboratorio", "id_orden"),
        ("id_remito", "remito_biologico", "id_remito"),
    }),
    ("historial_estado_muestra", {
        ("id_muestra", "muestra_biologica", "id_muestra"),
    }),
    ("remito_biologico", {
        ("id_conservadora", "conservadora_isotermica", "id_conservadora"),
        ("id_clinica_origen", "clinica", "id_clinica"),
    }),
    ("precinto_sanitario", {
        ("id_remito", "remito_biologico", "id_remito"),
    }),
    ("envio", {
        ("id_remito", "remito_biologico", "id_remito"),
    }),
    ("recepcion", {
        ("id_envio", "envio", "id_envio"),
    }),
    ("resultado_analisis", {
        ("id_muestra", "muestra_biologica", "id_muestra"),
    }),
    ("comprobante_atencion", {
        ("id_atencion", "atencion", "id_atencion"),
    }),
])
def test_fk_de_persistencia_2_a_8_sin_cascadas(
    conexion, tabla, referencias
):
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
    ("vacuna", [
        ("id_vacuna", "INTEGER", 0, 1),
        ("nombre", "VARCHAR(100)", 1, 0),
        ("especie", "VARCHAR(50)", 1, 0),
        ("obligatoria", "INTEGER", 1, 0),
    ]),
    ("aplicacion_vacuna", [
        ("id_aplicacion", "INTEGER", 0, 1),
        ("id_mascota", "INTEGER", 1, 0),
        ("id_vacuna", "INTEGER", 1, 0),
        ("fecha_aplicacion", "TEXT", 1, 0),
        ("fecha_proxima_dosis", "TEXT", 0, 0),
    ]),
    ("orden_derivacion_laboratorio", [
        ("id_orden", "INTEGER", 0, 1),
        ("id_atencion", "INTEGER", 1, 0),
        ("fecha_emision", "TEXT", 1, 0),
        ("estudio_solicitado", "VARCHAR(200)", 1, 0),
        ("estado", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("muestra_biologica", [
        ("id_muestra", "INTEGER", 0, 1),
        ("id_orden", "INTEGER", 1, 0),
        ("id_remito", "INTEGER", 0, 0),
        ("tipo_muestra", "VARCHAR(80)", 1, 0),
        ("fecha_extraccion", "TEXT", 1, 0),
        ("estado_actual", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("historial_estado_muestra", [
        ("id_historial", "INTEGER", 0, 1),
        ("id_muestra", "INTEGER", 1, 0),
        ("estado", "TEXT", 1, 0),
        ("fecha_hora", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("conservadora_isotermica", [
        ("id_conservadora", "INTEGER", 0, 1),
        ("codigo", "VARCHAR(50)", 1, 0),
        ("estado", "TEXT", 1, 0),
    ]),
    ("remito_biologico", [
        ("id_remito", "INTEGER", 0, 1),
        ("id_conservadora", "INTEGER", 1, 0),
        ("id_clinica_origen", "INTEGER", 1, 0),
        ("fecha_emision", "TEXT", 1, 0),
        ("estado", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("precinto_sanitario", [
        ("id_precinto", "INTEGER", 0, 1),
        ("id_remito", "INTEGER", 1, 0),
        ("codigo", "VARCHAR(50)", 1, 0),
        ("estado", "TEXT", 1, 0),
    ]),
    ("envio", [
        ("id_envio", "INTEGER", 0, 1),
        ("id_remito", "INTEGER", 1, 0),
        ("fecha_hora_salida", "TEXT", 0, 0),
        ("fecha_hora_llegada", "TEXT", 0, 0),
        ("estado", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("recepcion", [
        ("id_recepcion", "INTEGER", 0, 1),
        ("id_envio", "INTEGER", 1, 0),
        ("fecha_hora", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("resultado_analisis", [
        ("id_resultado", "INTEGER", 0, 1),
        ("id_muestra", "INTEGER", 1, 0),
        ("fecha_resultado", "TEXT", 1, 0),
        ("resultado", "TEXT", 1, 0),
        ("observaciones", "TEXT", 0, 0),
    ]),
    ("comprobante_atencion", [
        ("id_comprobante", "INTEGER", 0, 1),
        ("id_atencion", "INTEGER", 1, 0),
        ("fecha_emision", "TEXT", 1, 0),
    ]),
])
def test_columnas_tipos_y_opcionalidad(conexion, tabla, esperado):
    filas = conexion.execute(
        "SELECT name, type, [notnull], pk FROM pragma_table_info(?)", (tabla,)
    ).fetchall()
    assert [tuple(fila) for fila in filas] == esperado


def test_cerrado_ya_no_es_un_estado_valido_de_remito(conexion):
    conexion.execute("""
        INSERT INTO clinica (id_clinica, nombre, direccion)
        VALUES (1, 'Centro', 'San Martín 100')
    """)
    conexion.execute("""
        INSERT INTO conservadora_isotermica
            (id_conservadora, codigo, estado)
        VALUES (1, 'CONS-1', 'EN_USO')
    """)
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            INSERT INTO remito_biologico
                (id_remito, id_conservadora, id_clinica_origen,
                 fecha_emision, estado)
            VALUES (1, 1, 1, '2026-11-02T10:00:00', 'CERRADO')
        """)


@pytest.mark.parametrize("tabla, columna", [
    ("resultado_analisis", "id_muestra"),
    ("comprobante_atencion", "id_atencion"),
])
def test_fk_de_persistencia_8_rechaza_null(conexion, tabla, columna):
    if tabla == "resultado_analisis":
        sql = """
            INSERT INTO resultado_analisis
                (id_resultado, id_muestra, fecha_resultado, resultado)
            VALUES (170, NULL, '2026-11-03T14:00:00', 'Sin alteraciones')
        """
    else:
        sql = """
            INSERT INTO comprobante_atencion
                (id_comprobante, id_atencion, fecha_emision)
            VALUES (180, NULL, '2026-11-03T10:30:00')
        """
    with pytest.raises(sqlite3.IntegrityError, match=columna):
        conexion.execute(sql)
