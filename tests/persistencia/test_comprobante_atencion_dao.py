from datetime import datetime
import sqlite3

import pytest

from veterinaria.dominio.clinica.atencion import Atencion
from veterinaria.dominio.clinica.comprobante_atencion import ComprobanteAtencion
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.persistencia.inicializar_bd import inicializar_bd


@pytest.fixture
def comprobante(atencion_persistida):
    return ComprobanteAtencion(
        180, atencion_persistida, datetime(2026, 11, 3, 10, 30, 45, 123456)
    )


def test_crear_conserva_id_atencion_y_fecha_iso(
    conexion, comprobante_atencion_dao, comprobante,
):
    comprobante_atencion_dao.crear(comprobante)
    fila = conexion.execute("""
        SELECT * FROM comprobante_atencion WHERE id_comprobante = 180
    """).fetchone()
    assert tuple(fila) == (180, 70, "2026-11-03T10:30:45.123456")


def test_id_none_es_rechazado(comprobante_atencion_dao, comprobante):
    comprobante.id_comprobante = None
    with pytest.raises(ValueError, match="id_comprobante"):
        comprobante_atencion_dao.crear(comprobante)


def test_atencion_inexistente_propaga_integrity_error(
    comprobante_atencion_dao, atencion,
):
    comprobante = ComprobanteAtencion(180, atencion, atencion.fecha_hora)
    with pytest.raises(sqlite3.IntegrityError):
        comprobante_atencion_dao.crear(comprobante)


@pytest.mark.parametrize("otro_id", [False, True], ids=["pk", "unique_atencion"])
def test_segunda_insercion_propaga_integrity_error(
    otro_id, conexion, comprobante_atencion_dao, comprobante,
):
    comprobante_atencion_dao.crear(comprobante)
    if otro_id:
        comprobante.id_comprobante = 181
    with pytest.raises(sqlite3.IntegrityError):
        comprobante_atencion_dao.crear(comprobante)
    assert conexion.execute(
        "SELECT COUNT(*) FROM comprobante_atencion"
    ).fetchone()[0] == 1


@pytest.mark.parametrize("consulta", ["id", "atencion"])
def test_obtener_reconstruye_comprobante_atencion_y_veterinario(
    consulta, comprobante_atencion_dao, comprobante,
):
    comprobante_atencion_dao.crear(comprobante)
    if consulta == "id":
        recuperado = comprobante_atencion_dao.obtener_por_id(180)
    else:
        recuperado = comprobante_atencion_dao.obtener_por_atencion(70)
    assert isinstance(recuperado, ComprobanteAtencion)
    assert recuperado is not comprobante
    assert recuperado.id_comprobante == 180
    assert recuperado.fecha_emision == comprobante.fecha_emision
    atencion = recuperado.atencion
    original = comprobante.atencion
    assert atencion is not original
    for nombre in (
        "id_atencion", "fecha_hora", "tipo", "motivo", "diagnostico",
        "observaciones",
    ):
        assert getattr(atencion, nombre) == getattr(original, nombre)
    assert vars(atencion.veterinario) == vars(original.veterinario)
    assert atencion.obtener_ordenes_derivacion() == []
    assert not hasattr(atencion, "comprobante")
    assert not hasattr(atencion, "comprobante_atencion")


def test_obtener_inexistentes_devuelve_none(comprobante_atencion_dao):
    assert comprobante_atencion_dao.obtener_por_id(999) is None
    assert comprobante_atencion_dao.obtener_por_atencion(999) is None


def test_atencion_sin_comprobante_devuelve_none(
    comprobante_atencion_dao, atencion_persistida,
):
    assert comprobante_atencion_dao.obtener_por_atencion(70) is None


def test_creacion_y_lectura_no_modifican_atencion_ni_ejecutan_negocio(
    conexion, monkeypatch, comprobante_atencion_dao, comprobante,
):
    atencion = comprobante.atencion
    atributos = vars(atencion).copy()
    fila_antes = tuple(conexion.execute(
        "SELECT * FROM atencion WHERE id_atencion = 70"
    ).fetchone())

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("El comprobante no debe registrar atenciones")

    monkeypatch.setattr(Mascota, "registrar_atencion", operacion_prohibida)
    monkeypatch.setattr(HistoriaClinica, "_agregar_atencion", operacion_prohibida)
    monkeypatch.setattr(Atencion, "agregar_orden_derivacion", operacion_prohibida)
    comprobante_atencion_dao.crear(comprobante)
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        assert comprobante_atencion_dao.obtener_por_id(180).atencion.id_atencion == 70
        assert comprobante_atencion_dao.obtener_por_atencion(70).id_comprobante == 180
    finally:
        conexion.set_trace_callback(None)
    assert sentencias
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in sentencias)
    assert vars(atencion) == atributos
    assert tuple(conexion.execute(
        "SELECT * FROM atencion WHERE id_atencion = 70"
    ).fetchone()) == fila_antes


def test_fecha_obligatoria_propaga_integrity_error(
    comprobante_atencion_dao, comprobante,
):
    comprobante.fecha_emision = None
    with pytest.raises(sqlite3.IntegrityError):
        comprobante_atencion_dao.crear(comprobante)


def test_rollback_externo_revierte_comprobante_sin_borrar_atencion(
    conexion, comprobante_atencion_dao, atencion_dao, comprobante,
):
    conexion.commit()
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        comprobante_atencion_dao.crear(comprobante)
    finally:
        conexion.set_trace_callback(None)
    assert not any(
        sql.strip().upper().startswith(("COMMIT", "ROLLBACK"))
        for sql in sentencias
    )
    conexion.rollback()
    assert comprobante_atencion_dao.obtener_por_id(180) is None
    assert atencion_dao.obtener_por_id(70) is not None


def test_error_no_hace_rollback_de_escrituras_del_llamador(
    conexion, comprobante_atencion_dao, comprobante,
):
    comprobante_atencion_dao.crear(comprobante)
    conexion.commit()
    conexion.execute(
        "UPDATE clinica SET nombre = 'Cambio pendiente' WHERE id_clinica = 30"
    )
    with pytest.raises(sqlite3.IntegrityError):
        comprobante_atencion_dao.crear(comprobante)
    assert conexion.execute(
        "SELECT nombre FROM clinica WHERE id_clinica = 30"
    ).fetchone()[0] == "Cambio pendiente"
    conexion.rollback()
    assert conexion.execute(
        "SELECT nombre FROM clinica WHERE id_clinica = 30"
    ).fetchone()[0] != "Cambio pendiente"


def test_inicializar_de_nuevo_conserva_comprobante(
    conexion, comprobante_atencion_dao, comprobante,
):
    comprobante_atencion_dao.crear(comprobante)
    conexion.commit()
    inicializar_bd(conexion)
    assert comprobante_atencion_dao.obtener_por_id(180).fecha_emision == (
        comprobante.fecha_emision
    )
    assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_api_publica_minima(comprobante_atencion_dao):
    for nombre in ("actualizar", "eliminar", "listar"):
        assert not hasattr(comprobante_atencion_dao, nombre)
