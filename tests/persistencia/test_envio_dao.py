from datetime import datetime, timedelta
import sqlite3

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito


def _fixture(request, nombre):
    return request.getfixturevalue(nombre)


def _crear_envio_persistido(request, cantidad_muestras=2):
    cliente = _fixture(request, "cliente")
    mascota = _fixture(request, "mascota")
    clinica = _fixture(request, "clinica")
    veterinario = _fixture(request, "veterinario")
    historia = _fixture(request, "historia_clinica")
    atencion = _fixture(request, "atencion")
    orden = _fixture(request, "orden_derivacion_laboratorio")
    muestra_inicial = _fixture(request, "muestra_biologica")
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

    muestras = [muestra_inicial]
    muestras.extend(
        MuestraBiologica(
            110 + indice,
            f"Muestra {indice}",
            muestra_inicial.fecha_extraccion,
        )
        for indice in range(1, cantidad_muestras)
    )
    muestra_dao = _fixture(request, "muestra_biologica_dao")
    for muestra in muestras:
        muestra_dao.crear(muestra, orden.id_orden)

    _fixture(request, "conservadora_isotermica_dao").crear(
        remito.conservadora
    )
    remito_dao = _fixture(request, "remito_biologico_dao")
    remito_dao.crear(remito)
    fecha_empaquetado = datetime(2026, 11, 3, 12, 45, 15, 123456)
    for muestra in muestras:
        assert remito.agregar_muestra(
            muestra, fecha_empaquetado, "Acondicionada"
        )
        assert remito_dao.guardar_muestra_asociada(remito, muestra)

    assert remito.asignar_precinto(precinto)
    _fixture(request, "precinto_sanitario_dao").crear(
        precinto, remito.id_remito
    )

    envio = Envio(150, remito, "Traslado central")
    _fixture(request, "envio_dao").crear(envio)
    return envio


def test_crear_pendiente_con_id_fechas_null_y_remito(request, conexion):
    envio = _crear_envio_persistido(request)
    fila = conexion.execute(
        "SELECT * FROM envio WHERE id_envio = ?", (envio.id_envio,)
    ).fetchone()
    assert fila["id_envio"] == 150
    assert fila["id_remito"] == 130
    assert fila["fecha_hora_salida"] is None
    assert fila["fecha_hora_llegada"] is None
    assert fila["estado"] == "PENDIENTE"
    assert fila["observaciones"] == "Traslado central"


def test_id_none_es_rechazado(envio_dao, remito_biologico):
    with pytest.raises(ValueError, match="id_envio"):
        envio_dao.crear(Envio(None, remito_biologico))


def test_remito_inexistente_propaga_integrity_error(
    envio_dao, remito_biologico
):
    with pytest.raises(sqlite3.IntegrityError):
        envio_dao.crear(Envio(150, remito_biologico))


def test_segundo_envio_para_el_mismo_remito_es_rechazado(request):
    envio = _crear_envio_persistido(request)
    with pytest.raises(sqlite3.IntegrityError):
        _fixture(request, "envio_dao").crear(Envio(151, envio.remito))


def test_obtener_inexistente_por_id_y_remito(envio_dao):
    assert envio_dao.obtener_por_id(999) is None
    assert envio_dao.obtener_por_remito(999) is None


def test_obtener_por_id_y_remito_reconstruye_agregado_completo(request):
    envio = _crear_envio_persistido(request)
    dao = _fixture(request, "envio_dao")
    por_id = dao.obtener_por_id(150)
    por_remito = dao.obtener_por_remito(130)
    for recuperado in (por_id, por_remito):
        assert recuperado is not envio
        assert recuperado.id_envio == 150
        assert recuperado.remito.id_remito == 130
        assert recuperado.remito.obtener_precinto().id_precinto == 140
        assert [
            muestra.id_muestra
            for muestra in recuperado.remito.obtener_muestras()
        ] == [110, 111]
        assert all(
            len(muestra.obtener_historial()) == 2
            for muestra in recuperado.remito.obtener_muestras()
        )


@pytest.mark.parametrize(
    "estado,salida,llegada",
    [
        (EstadoEnvio.PENDIENTE, None, None),
        (
            EstadoEnvio.EN_TRANSITO,
            datetime(2026, 11, 3, 13, 1, 2, 345678),
            None,
        ),
        (
            EstadoEnvio.ENTREGADO,
            datetime(2026, 11, 3, 13, 1, 2, 345678),
            datetime(2026, 11, 3, 14, 2, 3, 456789),
        ),
    ],
)
def test_reconstruye_estados_y_fechas_sin_operaciones_de_dominio(
    estado, salida, llegada, request, conexion, monkeypatch
):
    _crear_envio_persistido(request)
    conexion.execute("""
        UPDATE envio
        SET estado = ?, fecha_hora_salida = ?, fecha_hora_llegada = ?
        WHERE id_envio = 150
    """, (
        estado.name,
        salida.isoformat() if salida is not None else None,
        llegada.isoformat() if llegada is not None else None,
    ))

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar operaciones de dominio")

    monkeypatch.setattr(Envio, "iniciar", operacion_prohibida)
    monkeypatch.setattr(Envio, "registrar_llegada", operacion_prohibida)
    recuperado = _fixture(request, "envio_dao").obtener_por_id(150)
    assert recuperado.estado is estado
    assert recuperado.fecha_hora_salida == salida
    assert recuperado.fecha_hora_llegada == llegada


def test_actualizar_no_cambia_id_remito(request, conexion):
    envio = _crear_envio_persistido(request)
    envio.remito.id_remito = 999
    envio.observaciones = "Actualizado"
    assert _fixture(request, "envio_dao").actualizar(envio)
    fila = conexion.execute(
        "SELECT id_remito, observaciones FROM envio WHERE id_envio = 150"
    ).fetchone()
    assert fila["id_remito"] == 130
    assert fila["observaciones"] == "Actualizado"


def test_actualizar_inexistente_devuelve_false(envio_dao, remito_biologico):
    assert envio_dao.actualizar(Envio(999, remito_biologico)) is False


def test_guardar_despacho_persiste_envio_remito_muestras_e_historial(
    request, conexion
):
    envio = _crear_envio_persistido(request)
    salida = datetime(2026, 11, 3, 13, 15, 30, 654321)
    assert envio.iniciar(salida)
    assert _fixture(request, "envio_dao").guardar_despacho(envio)

    fila_envio = conexion.execute(
        "SELECT * FROM envio WHERE id_envio = 150"
    ).fetchone()
    assert fila_envio["estado"] == "EN_TRANSITO"
    assert fila_envio["fecha_hora_salida"] == salida.isoformat()
    assert fila_envio["fecha_hora_llegada"] is None
    assert conexion.execute("""
        SELECT estado FROM remito_biologico WHERE id_remito = 130
    """).fetchone()[0] == "DESPACHADO"
    assert {
        fila["estado_actual"]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"EN_TRANSITO"}
    assert [
        fila["estado"]
        for fila in conexion.execute("""
            SELECT estado FROM historial_estado_muestra
            WHERE id_muestra = 110 ORDER BY id_historial
        """).fetchall()
    ] == ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO"]


def test_guardar_despacho_no_ejecuta_operaciones_de_dominio(
    request, monkeypatch
):
    envio = _crear_envio_persistido(request)
    assert envio.iniciar(datetime(2026, 11, 3, 13))

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La persistencia no debe transicionar objetos")

    monkeypatch.setattr(Envio, "iniciar", operacion_prohibida)
    monkeypatch.setattr(envio.remito, "despachar", operacion_prohibida)
    for muestra in envio.remito.obtener_muestras():
        monkeypatch.setattr(muestra, "despachar", operacion_prohibida)
        monkeypatch.setattr(muestra, "_cambiar_estado", operacion_prohibida)
    assert _fixture(request, "envio_dao").guardar_despacho(envio)


def test_guardar_despacho_dos_veces_no_duplica_historial(request, conexion):
    envio = _crear_envio_persistido(request)
    assert envio.iniciar(datetime(2026, 11, 3, 13))
    dao = _fixture(request, "envio_dao")
    assert dao.guardar_despacho(envio)
    assert dao.guardar_despacho(envio)
    cantidades = conexion.execute("""
        SELECT id_muestra, COUNT(*) AS cantidad
        FROM historial_estado_muestra
        GROUP BY id_muestra
        ORDER BY id_muestra
    """).fetchall()
    assert [fila["cantidad"] for fila in cantidades] == [3, 3]


def test_actualizar_persiste_llegada_sin_procesar_muestras(request, conexion):
    envio = _crear_envio_persistido(request)
    salida = datetime(2026, 11, 3, 13)
    llegada = salida + timedelta(hours=1, microseconds=123456)
    assert envio.iniciar(salida)
    dao = _fixture(request, "envio_dao")
    assert dao.guardar_despacho(envio)
    assert envio.registrar_llegada(llegada)
    assert dao.actualizar(envio)
    fila = conexion.execute(
        "SELECT estado, fecha_hora_llegada FROM envio WHERE id_envio = 150"
    ).fetchone()
    assert tuple(fila) == ("ENTREGADO", llegada.isoformat())
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"EN_TRANSITO"}


def test_guardar_despacho_no_hace_commit_y_rollback_externo_revierte(
    request, conexion
):
    envio = _crear_envio_persistido(request)
    conexion.commit()
    assert envio.iniciar(datetime(2026, 11, 3, 13))
    assert _fixture(request, "envio_dao").guardar_despacho(envio)
    conexion.rollback()
    assert conexion.execute("""
        SELECT estado FROM envio WHERE id_envio = 150
    """).fetchone()[0] == "PENDIENTE"
    assert conexion.execute("""
        SELECT estado FROM remito_biologico WHERE id_remito = 130
    """).fetchone()[0] == "GENERADO"
    assert {
        fila[0]
        for fila in conexion.execute("""
            SELECT estado_actual FROM muestra_biologica
            WHERE id_remito = 130
        """).fetchall()
    } == {"EMPAQUETADA"}


def test_no_existen_listar_ni_eliminar(envio_dao):
    assert not hasattr(envio_dao, "listar")
    assert not hasattr(envio_dao, "eliminar")
