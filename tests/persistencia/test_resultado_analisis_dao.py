from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.persistencia.inicializar_bd import inicializar_bd


@pytest.fixture
def resultado(muestra_recibida_persistida):
    muestra = muestra_recibida_persistida
    return ResultadoAnalisis(
        170,
        muestra,
        muestra.fecha_extraccion + timedelta(minutes=4),
        "Hemograma dentro de parámetros",
        "Validado por laboratorio",
    )


def test_guardar_persiste_resultado_muestra_e_historial(
    conexion, resultado_analisis_dao, resultado,
):
    historial_previo = resultado.muestra.obtener_historial()
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    fila = conexion.execute("""
        SELECT * FROM resultado_analisis WHERE id_resultado = 170
    """).fetchone()
    assert fila["id_resultado"] == resultado.id_resultado == 170
    assert fila["id_muestra"] == resultado.muestra.id_muestra == 110
    assert fila["fecha_resultado"] == resultado.fecha_resultado.isoformat()
    assert fila["fecha_resultado"].endswith(".654321")
    assert fila["resultado"] == resultado.resultado
    assert fila["observaciones"] == resultado.observaciones
    assert conexion.execute("""
        SELECT estado_actual FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] == "ANALIZADA"
    recuperado = resultado_analisis_dao.obtener_por_id(170)
    historial = recuperado.muestra.obtener_historial()
    assert historial[:-1] == historial_previo
    assert len(historial) == 5
    assert [registro.nombre_estado for registro in historial] == [
        "EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA",
    ]
    assert historial[-1].fecha_hora == resultado.fecha_resultado
    assert historial[-1].observaciones == resultado.observaciones


def test_id_none_es_rechazado(resultado_analisis_dao, resultado):
    assert resultado.registrar_resultado()
    resultado.id_resultado = None
    with pytest.raises(ValueError, match="id_resultado"):
        resultado_analisis_dao.guardar_resultado(resultado)


def test_muestra_inexistente_propaga_integrity_error(
    conexion, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado.muestra.id_muestra = 999
    with pytest.raises(sqlite3.IntegrityError):
        resultado_analisis_dao.guardar_resultado(resultado)
    assert conexion.execute(
        "SELECT COUNT(*) FROM resultado_analisis"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("otro_id", [False, True], ids=["pk", "unique_muestra"])
def test_segunda_insercion_falla_sin_duplicar_historial(
    otro_id, conexion, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    if otro_id:
        resultado.id_resultado = 171
    with pytest.raises(sqlite3.IntegrityError):
        resultado_analisis_dao.guardar_resultado(resultado)
    assert conexion.execute(
        "SELECT COUNT(*) FROM resultado_analisis"
    ).fetchone()[0] == 1
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0] == 5


@pytest.mark.parametrize("consulta", ["id", "muestra"])
def test_obtener_reconstruye_resultado_y_muestra_completos(
    consulta, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    if consulta == "id":
        recuperado = resultado_analisis_dao.obtener_por_id(170)
    else:
        recuperado = resultado_analisis_dao.obtener_por_muestra(110)
    assert isinstance(recuperado, ResultadoAnalisis)
    assert recuperado is not resultado
    assert recuperado.id_resultado == 170
    assert recuperado.fecha_resultado == resultado.fecha_resultado
    assert recuperado.resultado == resultado.resultado
    assert recuperado.observaciones == resultado.observaciones
    assert recuperado.muestra is not resultado.muestra
    assert recuperado.muestra.id_muestra == 110
    assert recuperado.muestra.tipo_muestra == resultado.muestra.tipo_muestra
    assert recuperado.muestra.fecha_extraccion == resultado.muestra.fecha_extraccion
    assert recuperado.muestra.observaciones == resultado.muestra.observaciones
    assert recuperado.muestra.estado.obtener_nombre() == "ANALIZADA"
    assert recuperado.muestra.obtener_historial() == (
        resultado.muestra.obtener_historial()
    )
    assert not hasattr(recuperado.muestra, "resultado_analisis")
    assert not hasattr(recuperado.muestra, "resultado")


def test_obtener_inexistentes_devuelve_none(resultado_analisis_dao):
    assert resultado_analisis_dao.obtener_por_id(999) is None
    assert resultado_analisis_dao.obtener_por_muestra(999) is None


def test_obtener_por_muestra_sin_resultado_devuelve_none(
    resultado_analisis_dao, muestra_recibida_persistida,
):
    assert resultado_analisis_dao.obtener_por_muestra(110) is None


def test_lectura_no_ejecuta_negocio_ni_escribe(
    conexion, monkeypatch, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    historial = resultado.muestra.obtener_historial()

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar operaciones de negocio")

    monkeypatch.setattr(ResultadoAnalisis, "registrar_resultado", operacion_prohibida)
    for nombre in (
        "empaquetar", "despachar", "recibir", "rechazar", "analizar",
        "_cambiar_estado",
    ):
        monkeypatch.setattr(MuestraBiologica, nombre, operacion_prohibida)
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        for recuperado in (
            resultado_analisis_dao.obtener_por_id(170),
            resultado_analisis_dao.obtener_por_muestra(110),
        ):
            assert recuperado.muestra.obtener_historial() == historial
    finally:
        conexion.set_trace_callback(None)
    assert sentencias
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in sentencias)
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0] == 5


def test_guardar_no_ejecuta_transiciones(
    monkeypatch, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("Guardar no debe volver a analizar")

    monkeypatch.setattr(ResultadoAnalisis, "registrar_resultado", operacion_prohibida)
    monkeypatch.setattr(MuestraBiologica, "analizar", operacion_prohibida)
    monkeypatch.setattr(MuestraBiologica, "_cambiar_estado", operacion_prohibida)
    resultado_analisis_dao.guardar_resultado(resultado)


@pytest.mark.parametrize("contenido", ["", "Sin alteraciones"])
def test_contenido_vacio_y_observaciones_none(
    contenido, conexion, resultado_analisis_dao, resultado,
):
    resultado.resultado = contenido
    resultado.observaciones = None
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    recuperado = resultado_analisis_dao.obtener_por_id(170)
    assert recuperado.resultado == contenido
    assert recuperado.observaciones is None
    assert conexion.execute("""
        SELECT observaciones FROM resultado_analisis WHERE id_resultado = 170
    """).fetchone()[0] is None


@pytest.mark.parametrize("campo", ["fecha_resultado", "resultado"])
def test_campos_obligatorios_propagan_integrity_error(
    campo, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    setattr(resultado, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        resultado_analisis_dao.guardar_resultado(resultado)


@pytest.mark.parametrize(
    "estado", ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "RECHAZADA"]
)
def test_guardar_rechaza_muestra_no_analizada_sin_modificarla(
    estado, conexion, resultado_analisis_dao, muestra_biologica,
):
    muestra = muestra_biologica
    fecha = muestra.fecha_extraccion
    if estado != "EXTRAIDA":
        assert muestra.empaquetar(fecha)
    if estado in {"EN_TRANSITO", "RECIBIDA", "RECHAZADA"}:
        assert muestra.despachar(fecha)
    if estado == "RECIBIDA":
        assert muestra.recibir(fecha)
    if estado == "RECHAZADA":
        assert muestra.rechazar(fecha)
    resultado = ResultadoAnalisis(170, muestra, fecha, "Sin alteraciones")
    historial = muestra.obtener_historial()
    with pytest.raises(ValueError, match="ANALIZADA"):
        resultado_analisis_dao.guardar_resultado(resultado)
    assert muestra.estado.obtener_nombre() == estado
    assert muestra.obtener_historial() == historial
    assert conexion.execute(
        "SELECT COUNT(*) FROM resultado_analisis"
    ).fetchone()[0] == 0


def test_muestra_rechazada_no_registra_resultado(
    conexion, resultado_analisis_dao, muestra_biologica_dao,
    muestra_biologica, atencion_persistida,
    orden_derivacion_laboratorio_dao, orden_derivacion_laboratorio,
):
    orden = orden_derivacion_laboratorio
    orden_derivacion_laboratorio_dao.crear(orden, atencion_persistida.id_atencion)
    muestra = muestra_biologica
    fecha = muestra.fecha_extraccion
    assert muestra.empaquetar(fecha)
    assert muestra.despachar(fecha)
    assert muestra.rechazar(fecha, "Precinto roto")
    muestra_biologica_dao.crear(muestra, orden.id_orden)
    resultado = ResultadoAnalisis(170, muestra, fecha, "Resultado inválido")
    historial = muestra.obtener_historial()
    registrado = resultado.registrar_resultado()
    assert registrado is False
    if registrado:
        resultado_analisis_dao.guardar_resultado(resultado)
    assert resultado_analisis_dao.obtener_por_muestra(muestra.id_muestra) is None
    recuperada = muestra_biologica_dao.obtener_por_id(muestra.id_muestra)
    assert recuperada.estado.obtener_nombre() == "RECHAZADA"
    assert recuperada.obtener_historial() == historial


def test_actualizar_muestra_dos_veces_no_duplica_analizada(
    conexion, resultado_analisis_dao, muestra_biologica_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    for _ in range(2):
        assert muestra_biologica_dao.actualizar(resultado.muestra)
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra
        WHERE id_muestra = 110 AND estado = 'ANALIZADA'
    """).fetchone()[0] == 1


def test_rollback_externo_revierte_resultado_estado_e_historial(
    conexion, resultado_analisis_dao, muestra_biologica_dao, resultado,
):
    conexion.commit()
    assert resultado.registrar_resultado()
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        resultado_analisis_dao.guardar_resultado(resultado)
    finally:
        conexion.set_trace_callback(None)
    assert not any(
        sql.strip().upper().startswith(("COMMIT", "ROLLBACK"))
        for sql in sentencias
    )
    conexion.rollback()
    assert resultado_analisis_dao.obtener_por_id(170) is None
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    assert recuperada.estado.obtener_nombre() == "RECIBIDA"
    assert len(recuperada.obtener_historial()) == 4
    assert all(h.nombre_estado != "ANALIZADA" for h in recuperada.obtener_historial())
    assert resultado.muestra.estado.obtener_nombre() == "ANALIZADA"


def test_fallo_intermedio_no_revierte_y_permite_rollback_externo(
    conexion, resultado_analisis_dao, muestra_biologica_dao, resultado,
):
    conexion.commit()
    conexion.execute(
        "UPDATE clinica SET nombre = 'Cambio pendiente' WHERE id_clinica = 30"
    )
    assert resultado.registrar_resultado()
    muestra = resultado.muestra
    muestra._historial[0] = replace(
        muestra.obtener_historial()[0], observaciones="Prefijo alterado"
    )
    with pytest.raises(ValueError, match="historial persistido difiere"):
        resultado_analisis_dao.guardar_resultado(resultado)
    assert conexion.execute(
        "SELECT COUNT(*) FROM resultado_analisis"
    ).fetchone()[0] == 1
    assert conexion.execute(
        "SELECT nombre FROM clinica WHERE id_clinica = 30"
    ).fetchone()[0] == "Cambio pendiente"
    conexion.rollback()
    assert resultado_analisis_dao.obtener_por_id(170) is None
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    assert recuperada.estado.obtener_nombre() == "RECIBIDA"
    assert len(recuperada.obtener_historial()) == 4
    assert conexion.execute(
        "SELECT nombre FROM clinica WHERE id_clinica = 30"
    ).fetchone()[0] != "Cambio pendiente"


def test_inicializar_de_nuevo_conserva_resultado(
    conexion, resultado_analisis_dao, resultado,
):
    assert resultado.registrar_resultado()
    resultado_analisis_dao.guardar_resultado(resultado)
    conexion.commit()
    inicializar_bd(conexion)
    assert resultado_analisis_dao.obtener_por_id(170).resultado == resultado.resultado
    assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_api_publica_minima(resultado_analisis_dao):
    for nombre in ("crear", "actualizar", "eliminar", "listar"):
        assert not hasattr(resultado_analisis_dao, nombre)
