from datetime import datetime, timedelta
import sqlite3

import pytest

from veterinaria.dominio.laboratorio.historial_estado_muestra import (
    HistorialEstadoMuestra,
)
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito


def _fixture(request, nombre):
    return request.getfixturevalue(nombre)


def _crear_envio_persistido(request):
    cliente = _fixture(request, "cliente")
    mascota = _fixture(request, "mascota")
    clinica = _fixture(request, "clinica")
    veterinario = _fixture(request, "veterinario")
    historia = _fixture(request, "historia_clinica")
    atencion = _fixture(request, "atencion")
    orden = _fixture(request, "orden_derivacion_laboratorio")
    primera = _fixture(request, "muestra_biologica")
    segunda = MuestraBiologica(
        111, "Orina", primera.fecha_extraccion, "Frasco estéril"
    )
    remito = _fixture(request, "remito_biologico")
    precinto = _fixture(request, "precinto_sanitario")

    _fixture(request, "cliente_dao").crear(cliente)
    _fixture(request, "mascota_dao").crear(mascota)
    _fixture(request, "clinica_dao").crear(clinica)
    _fixture(request, "veterinario_dao").crear(
        veterinario, clinica.id_clinica
    )
    _fixture(request, "historia_clinica_dao").crear(
        historia, mascota.id_mascota
    )
    _fixture(request, "atencion_dao").crear(atencion, historia.id_historia)
    _fixture(request, "orden_derivacion_laboratorio_dao").crear(
        orden, atencion.id_atencion
    )
    muestra_dao = _fixture(request, "muestra_biologica_dao")
    for muestra in (primera, segunda):
        muestra_dao.crear(muestra, orden.id_orden)

    _fixture(request, "conservadora_isotermica_dao").crear(
        remito.conservadora
    )
    remito_dao = _fixture(request, "remito_biologico_dao")
    remito_dao.crear(remito)
    for muestra in (primera, segunda):
        assert remito.agregar_muestra(
            muestra, datetime(2026, 11, 3, 12, 45), "Acondicionada"
        )
        assert remito_dao.guardar_muestra_asociada(remito, muestra)

    assert remito.asignar_precinto(precinto)
    _fixture(request, "precinto_sanitario_dao").crear(
        precinto, remito.id_remito
    )
    envio = Envio(150, remito, "Traslado central")
    _fixture(request, "envio_dao").crear(envio)
    return envio


def _crear_recepcion_procesada(request, precinto_roto=False):
    envio = _crear_envio_persistido(request)
    salida = datetime(2026, 11, 3, 13, 15, 30, 123456)
    llegada = salida + timedelta(hours=1, microseconds=333333)
    assert envio.iniciar(salida)
    assert _fixture(request, "envio_dao").guardar_despacho(envio)
    assert envio.registrar_llegada(llegada)
    if precinto_roto:
        assert envio.remito.obtener_precinto().marcar_roto()
    recepcion = Recepcion(
        160,
        envio,
        llegada + timedelta(minutes=5, microseconds=222222),
        "Control de ingreso",
    )
    assert recepcion.procesar_recepcion()
    return recepcion


def test_obtener_inexistente_por_id_y_envio(recepcion_dao):
    assert recepcion_dao.obtener_por_id(999) is None
    assert recepcion_dao.obtener_por_envio(999) is None


def test_guardar_recepcion_intacta_persiste_toda_la_cadena(
    request, conexion
):
    recepcion = _crear_recepcion_procesada(request)
    _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)

    fila = conexion.execute(
        "SELECT * FROM recepcion WHERE id_recepcion = 160"
    ).fetchone()
    assert fila["id_envio"] == 150
    assert fila["fecha_hora"] == recepcion.fecha_hora.isoformat()
    assert fila["observaciones"] == "Control de ingreso"
    envio = conexion.execute(
        "SELECT * FROM envio WHERE id_envio = 150"
    ).fetchone()
    assert envio["estado"] == "ENTREGADO"
    assert envio["fecha_hora_llegada"] == (
        recepcion.envio.fecha_hora_llegada.isoformat()
    )
    assert conexion.execute("""
        SELECT estado FROM precinto_sanitario WHERE id_precinto = 140
    """).fetchone()[0] == "INTACTO"
    assert conexion.execute("""
        SELECT estado FROM remito_biologico WHERE id_remito = 130
    """).fetchone()[0] == "RECIBIDO"
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"RECIBIDA"}
    assert [
        fila[0]
        for fila in conexion.execute("""
            SELECT estado FROM historial_estado_muestra
            WHERE id_muestra = 110 ORDER BY id_historial
        """).fetchall()
    ] == ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA"]


def test_guardar_recepcion_rota_persiste_precinto_y_rechazo(
    request, conexion
):
    recepcion = _crear_recepcion_procesada(request, precinto_roto=True)
    _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)
    assert conexion.execute("""
        SELECT estado FROM precinto_sanitario WHERE id_precinto = 140
    """).fetchone()[0] == "ROTO"
    assert conexion.execute("""
        SELECT estado FROM remito_biologico WHERE id_remito = 130
    """).fetchone()[0] == "RECIBIDO"
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"RECHAZADA"}
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado FROM historial_estado_muestra
            WHERE id_muestra IN (110, 111)
              AND id_historial IN (
                  SELECT MAX(id_historial) FROM historial_estado_muestra
                  GROUP BY id_muestra
              )
        """).fetchall()
    } == {"RECHAZADA"}


def test_guardar_recepcion_no_ejecuta_operaciones_de_dominio(
    request, monkeypatch
):
    recepcion = _crear_recepcion_procesada(request)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La persistencia no debe transicionar objetos")

    monkeypatch.setattr(Recepcion, "procesar_recepcion", operacion_prohibida)
    monkeypatch.setattr(
        recepcion.envio.remito.obtener_precinto(),
        "marcar_roto",
        operacion_prohibida,
    )
    monkeypatch.setattr(
        recepcion.envio.remito, "marcar_recibido", operacion_prohibida
    )
    for muestra in recepcion.envio.remito.obtener_muestras():
        monkeypatch.setattr(muestra, "recibir", operacion_prohibida)
        monkeypatch.setattr(muestra, "rechazar", operacion_prohibida)
        monkeypatch.setattr(muestra, "_cambiar_estado", operacion_prohibida)
    _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)


def test_obtener_por_id_y_envio_reconstruye_sin_procesar_ni_escribir(
    request, conexion, monkeypatch
):
    recepcion = _crear_recepcion_procesada(request)
    dao = _fixture(request, "recepcion_dao")
    dao.guardar_recepcion(recepcion)
    cantidad_antes = conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra
    """).fetchone()[0]

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar operaciones de dominio")

    monkeypatch.setattr(Recepcion, "procesar_recepcion", operacion_prohibida)
    monkeypatch.setattr(Recepcion, "verificar_precinto", operacion_prohibida)
    por_id = dao.obtener_por_id(160)
    por_envio = dao.obtener_por_envio(150)
    for recuperada in (por_id, por_envio):
        assert recuperada is not recepcion
        assert recuperada.id_recepcion == 160
        assert recuperada.envio.id_envio == 150
        assert recuperada.envio.estado is EstadoEnvio.ENTREGADO
        assert recuperada.envio.remito.estado is EstadoRemito.RECIBIDO
        assert recuperada.envio.remito.obtener_precinto().esta_intacto()
        assert {
            muestra.estado.obtener_nombre()
            for muestra in recuperada.envio.remito.obtener_muestras()
        } == {"RECIBIDA"}
    cantidad_despues = conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra
    """).fetchone()[0]
    assert cantidad_despues == cantidad_antes


def test_id_none_es_rechazado(request):
    recepcion = _crear_recepcion_procesada(request)
    recepcion.id_recepcion = None
    with pytest.raises(ValueError, match="id_recepcion"):
        _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)


def test_envio_inexistente_propaga_integrity_error(
    recepcion_dao, remito_biologico, precinto_sanitario
):
    assert remito_biologico.asignar_precinto(precinto_sanitario)
    recepcion = Recepcion(
        160,
        Envio(999, remito_biologico),
        datetime(2026, 11, 3, 14),
    )
    with pytest.raises(sqlite3.IntegrityError):
        recepcion_dao.guardar_recepcion(recepcion)


def test_segunda_recepcion_del_mismo_envio_es_rechazada(request):
    recepcion = _crear_recepcion_procesada(request)
    dao = _fixture(request, "recepcion_dao")
    dao.guardar_recepcion(recepcion)
    segunda = Recepcion(
        161, recepcion.envio, recepcion.fecha_hora, "Segundo registro"
    )
    with pytest.raises(sqlite3.IntegrityError):
        dao.guardar_recepcion(segunda)


def test_guardar_recepcion_dos_veces_no_duplica_historial(request, conexion):
    recepcion = _crear_recepcion_procesada(request)
    dao = _fixture(request, "recepcion_dao")
    dao.guardar_recepcion(recepcion)
    cantidades = conexion.execute("""
        SELECT id_muestra, COUNT(*) AS cantidad
        FROM historial_estado_muestra
        GROUP BY id_muestra ORDER BY id_muestra
    """).fetchall()
    with pytest.raises(sqlite3.IntegrityError):
        dao.guardar_recepcion(recepcion)
    assert [fila["cantidad"] for fila in cantidades] == [4, 4]
    cantidades_despues = conexion.execute("""
        SELECT id_muestra, COUNT(*) AS cantidad
        FROM historial_estado_muestra
        GROUP BY id_muestra ORDER BY id_muestra
    """).fetchall()
    assert [fila["cantidad"] for fila in cantidades_despues] == [4, 4]


def test_rollback_externo_revierte_recepcion_fallida_completa(
    request, conexion
):
    recepcion = _crear_recepcion_procesada(request, precinto_roto=True)
    conexion.commit()
    segunda = recepcion.envio.remito.obtener_muestras()[1]
    inicial = segunda.obtener_historial()[0]
    segunda._historial[0] = HistorialEstadoMuestra(
        inicial.nombre_estado,
        inicial.fecha_hora,
        "Historial divergente",
    )

    with pytest.raises(ValueError, match="historial persistido difiere"):
        _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)
    conexion.rollback()

    assert conexion.execute(
        "SELECT COUNT(*) FROM recepcion"
    ).fetchone()[0] == 0
    envio = conexion.execute(
        "SELECT estado, fecha_hora_llegada FROM envio WHERE id_envio = 150"
    ).fetchone()
    assert tuple(envio) == ("EN_TRANSITO", None)
    assert conexion.execute("""
        SELECT estado FROM precinto_sanitario WHERE id_precinto = 140
    """).fetchone()[0] == "INTACTO"
    assert conexion.execute("""
        SELECT estado FROM remito_biologico WHERE id_remito = 130
    """).fetchone()[0] == "DESPACHADO"
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"EN_TRANSITO"}
    assert [
        fila[0]
        for fila in conexion.execute("""
            SELECT COUNT(*) FROM historial_estado_muestra
            GROUP BY id_muestra ORDER BY id_muestra
        """).fetchall()
    ] == [3, 3]


def test_guardar_recepcion_no_hace_commit(request, conexion):
    recepcion = _crear_recepcion_procesada(request)
    conexion.commit()
    _fixture(request, "recepcion_dao").guardar_recepcion(recepcion)
    conexion.rollback()
    assert conexion.execute(
        "SELECT COUNT(*) FROM recepcion"
    ).fetchone()[0] == 0
    assert conexion.execute("""
        SELECT estado FROM envio WHERE id_envio = 150
    """).fetchone()[0] == "EN_TRANSITO"


def test_foreign_keys_continua_activo(conexion):
    assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_no_existen_operaciones_publicas_crud_adicionales(recepcion_dao):
    assert not hasattr(recepcion_dao, "crear")
    assert not hasattr(recepcion_dao, "actualizar")
    assert not hasattr(recepcion_dao, "listar")
    assert not hasattr(recepcion_dao, "eliminar")


def test_relaciones_del_dominio_continuan_unidireccionales(request):
    recepcion = _crear_recepcion_procesada(request)
    assert recepcion.envio.remito is not None
    assert not hasattr(recepcion.envio, "recepcion")
    assert not hasattr(recepcion.envio.remito, "envio")
