from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta
import sqlite3

import pytest

from veterinaria.dominio.laboratorio.historial_estado_muestra import (
    HistorialEstadoMuestra,
)
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.patrones.state.estado_muestra import (
    EstadoAnalizada,
    EstadoEmpaquetada,
    EstadoEnTransito,
    EstadoExtraida,
    EstadoRecibida,
    EstadoRechazada,
)


def _persistir_dependencias(request):
    nombres = (
        "cliente_dao", "mascota_dao", "clinica_dao", "veterinario_dao",
        "historia_clinica_dao", "atencion_dao",
        "orden_derivacion_laboratorio_dao", "cliente", "mascota", "clinica",
        "veterinario", "historia_clinica", "atencion",
        "orden_derivacion_laboratorio",
    )
    (
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, atencion_dao, orden_dao, cliente, mascota,
        clinica, veterinario, historia, atencion, orden,
    ) = [request.getfixturevalue(nombre) for nombre in nombres]
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    historia_clinica_dao.crear(historia, mascota.id_mascota)
    atencion_dao.crear(atencion, historia.id_historia)
    orden_dao.crear(orden, atencion.id_atencion)
    return orden


def _avanzar_hasta(muestra, estado):
    fecha = muestra.fecha_extraccion
    if estado in {
        "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA", "RECHAZADA"
    }:
        assert muestra.empaquetar(fecha + timedelta(minutes=1), "Empaquetada")
    if estado in {"EN_TRANSITO", "RECIBIDA", "ANALIZADA", "RECHAZADA"}:
        assert muestra.despachar(fecha + timedelta(minutes=2), "Despachada")
    if estado in {"RECIBIDA", "ANALIZADA"}:
        assert muestra.recibir(fecha + timedelta(minutes=3), "Recibida")
    if estado == "ANALIZADA":
        assert muestra.analizar(fecha + timedelta(minutes=4), "Analizada")
    if estado == "RECHAZADA":
        assert muestra.rechazar(fecha + timedelta(minutes=3), "Precinto roto")


def test_crear_extraida_persiste_una_historia_id_remito_null_y_microsegundos(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    fila = conexion.execute("""
        SELECT * FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()
    historiales = conexion.execute("""
        SELECT estado, fecha_hora, observaciones
        FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchall()
    assert fila["id_orden"] == orden.id_orden
    assert fila["id_remito"] is None
    assert fila["estado_actual"] == "EXTRAIDA"
    assert fila["fecha_extraccion"] == "2026-11-03T11:45:12.654321"
    assert [tuple(historial) for historial in historiales] == [(
        "EXTRAIDA", "2026-11-03T11:45:12.654321", ""
    )]


def test_crear_con_orden_inexistente_propaga_integrity_error(
    muestra_biologica_dao, muestra_biologica,
):
    with pytest.raises(sqlite3.IntegrityError):
        muestra_biologica_dao.crear(muestra_biologica, 999)


def test_id_none_es_rechazado(muestra_biologica_dao):
    muestra = MuestraBiologica(None, "Sangre", datetime(2026, 11, 3))
    with pytest.raises(ValueError, match="id_muestra"):
        muestra_biologica_dao.crear(muestra, 100)


def test_pk_duplicada_propaga_integrity_error(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    with pytest.raises(sqlite3.IntegrityError):
        muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)


@pytest.mark.parametrize("campo", ["tipo_muestra", "fecha_extraccion"])
def test_campos_obligatorios_rechazan_null(
    campo, request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    setattr(muestra_biologica, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)


def test_obtener_inexistente_y_listar_orden_inexistente(
    muestra_biologica_dao,
):
    assert muestra_biologica_dao.obtener_por_id(999) is None
    assert muestra_biologica_dao.listar_por_orden(999) == []


def test_listar_por_orden_ordena_por_id(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    for id_muestra in (130, 110, 120):
        muestra_biologica_dao.crear(MuestraBiologica(
            id_muestra, "Sangre", muestra_biologica.fecha_extraccion
        ), orden.id_orden)
    assert [
        muestra.id_muestra
        for muestra in muestra_biologica_dao.listar_por_orden(orden.id_orden)
    ] == [110, 120, 130]


@pytest.mark.parametrize("nombre, clase", [
    ("EXTRAIDA", EstadoExtraida),
    ("EMPAQUETADA", EstadoEmpaquetada),
    ("EN_TRANSITO", EstadoEnTransito),
    ("RECIBIDA", EstadoRecibida),
    ("ANALIZADA", EstadoAnalizada),
    ("RECHAZADA", EstadoRechazada),
])
def test_reconstruye_cada_state_con_historial_completo_e_inmutable(
    nombre, clase, request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    _avanzar_hasta(muestra_biologica, nombre)
    esperado = muestra_biologica.obtener_historial()
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)

    recuperada = muestra_biologica_dao.obtener_por_id(110)
    assert isinstance(recuperada.estado, clase)
    assert recuperada.obtener_historial() == esperado
    with pytest.raises(FrozenInstanceError):
        recuperada.obtener_historial()[0].observaciones = "alterada"


def test_historial_con_fechas_iguales_conserva_orden_de_insercion(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    fecha = muestra_biologica.fecha_extraccion
    assert muestra_biologica.empaquetar(fecha, "primero")
    assert muestra_biologica.despachar(fecha, "segundo")
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    assert [h.nombre_estado for h in recuperada.obtener_historial()] == [
        "EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO"
    ]
    assert [h.fecha_hora for h in recuperada.obtener_historial()] == [fecha] * 3


def test_leer_no_inserta_no_transiciona_ni_duplica_extraida(
    monkeypatch, request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    cantidad_antes = conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0]

    def transicion_prohibida(*args, **kwargs):
        raise AssertionError("Leer no debe ejecutar transiciones")

    for metodo in ("empaquetar", "despachar", "recibir", "rechazar", "analizar"):
        monkeypatch.setattr(MuestraBiologica, metodo, transicion_prohibida)
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    cantidad_despues = conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0]
    assert cantidad_antes == cantidad_despues == 1
    assert [h.nombre_estado for h in recuperada.obtener_historial()] == ["EXTRAIDA"]


def test_actualizar_inserta_solo_el_nuevo_historial_y_conserva_fks(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    assert muestra_biologica.empaquetar(
        datetime(2026, 11, 3, 12, 1, 2, 123456), "Preparada"
    )
    muestra_biologica.tipo_muestra = "Plasma"
    muestra_biologica.fecha_extraccion = datetime(
        2026, 11, 3, 11, 46, 12, 111222
    )
    muestra_biologica.observaciones = None
    assert muestra_biologica_dao.actualizar(muestra_biologica) is True
    fila = conexion.execute("""
        SELECT * FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()
    estados = conexion.execute("""
        SELECT estado FROM historial_estado_muestra
        WHERE id_muestra = 110 ORDER BY id_historial
    """).fetchall()
    assert fila["id_orden"] == orden.id_orden
    assert fila["id_remito"] is None
    assert fila["tipo_muestra"] == "Plasma"
    assert fila["fecha_extraccion"] == "2026-11-03T11:46:12.111222"
    assert fila["estado_actual"] == "EMPAQUETADA"
    assert fila["observaciones"] is None
    assert [fila[0] for fila in estados] == ["EXTRAIDA", "EMPAQUETADA"]


def test_guardar_dos_veces_no_duplica_historial(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    assert muestra_biologica.empaquetar(datetime(2026, 11, 3, 12))
    assert muestra_biologica_dao.actualizar(muestra_biologica)
    assert muestra_biologica_dao.actualizar(muestra_biologica)
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0] == 2


def test_actualizar_inserta_varias_transiciones_pendientes(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    assert muestra_biologica.empaquetar(datetime(2026, 11, 3, 12))
    assert muestra_biologica.despachar(datetime(2026, 11, 3, 12, 30))
    assert muestra_biologica_dao.actualizar(muestra_biologica)
    estados = conexion.execute("""
        SELECT estado FROM historial_estado_muestra
        WHERE id_muestra = 110 ORDER BY id_historial
    """).fetchall()
    assert [fila[0] for fila in estados] == [
        "EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO"
    ]


def test_actualizar_inexistente_devuelve_false(
    muestra_biologica_dao, muestra_biologica,
):
    assert muestra_biologica_dao.actualizar(muestra_biologica) is False


def test_bd_con_mas_historial_que_objeto_falla_antes_de_escribir(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.execute("""
        INSERT INTO historial_estado_muestra
            (id_muestra, estado, fecha_hora, observaciones)
        VALUES (110, 'EMPAQUETADA', '2026-11-03T12:00:00', '')
    """)
    conexion.execute("""
        UPDATE muestra_biologica SET estado_actual = 'EMPAQUETADA'
        WHERE id_muestra = 110
    """)
    muestra_biologica.tipo_muestra = "No debe persistirse"
    with pytest.raises(ValueError, match="prefijo"):
        muestra_biologica_dao.actualizar(muestra_biologica)
    assert conexion.execute("""
        SELECT tipo_muestra FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] == "Sangre"


@pytest.mark.parametrize("diferencia", ["estado", "fecha", "observaciones"])
def test_historial_del_objeto_diferente_falla_antes_de_escribir(
    diferencia, request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    assert muestra_biologica.empaquetar(
        datetime(2026, 11, 3, 12), "Empaquetada"
    )
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    historial = muestra_biologica.obtener_historial()
    original = historial[1]
    if diferencia == "estado":
        alterado = HistorialEstadoMuestra(
            "EN_TRANSITO", original.fecha_hora, original.observaciones
        )
        vars(muestra_biologica)["_estado"] = EstadoEnTransito()
    elif diferencia == "fecha":
        alterado = HistorialEstadoMuestra(
            original.nombre_estado,
            original.fecha_hora + timedelta(seconds=1),
            original.observaciones,
        )
    else:
        alterado = HistorialEstadoMuestra(
            original.nombre_estado, original.fecha_hora, "observación distinta"
        )
    vars(muestra_biologica)["_historial"] = [historial[0], alterado]
    muestra_biologica.tipo_muestra = "No debe persistirse"
    with pytest.raises(ValueError, match="difiere"):
        muestra_biologica_dao.actualizar(muestra_biologica)
    assert conexion.execute("""
        SELECT tipo_muestra FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] == "Sangre"


def test_actualizar_rechaza_historial_vacio(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    vars(muestra_biologica)["_historial"] = []
    with pytest.raises(ValueError, match="vacío"):
        muestra_biologica_dao.actualizar(muestra_biologica)


def test_actualizar_rechaza_ultimo_historial_distinto_del_estado(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    vars(muestra_biologica)["_historial"].append(HistorialEstadoMuestra(
        "EMPAQUETADA", datetime(2026, 11, 3, 12)
    ))
    with pytest.raises(ValueError, match="no coincide"):
        muestra_biologica_dao.actualizar(muestra_biologica)


def test_actualizar_rechaza_estado_desconocido(
    request, muestra_biologica_dao, muestra_biologica,
):
    class EstadoDesconocido:
        def obtener_nombre(self):
            return "DESCONOCIDO"

    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    vars(muestra_biologica)["_estado"] = EstadoDesconocido()
    with pytest.raises(ValueError, match="desconocido"):
        muestra_biologica_dao.actualizar(muestra_biologica)


def test_actualizar_rechaza_fechas_decrecientes(
    request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    vars(muestra_biologica)["_estado"] = EstadoEmpaquetada()
    vars(muestra_biologica)["_historial"].append(HistorialEstadoMuestra(
        "EMPAQUETADA",
        muestra_biologica.fecha_extraccion - timedelta(seconds=1),
    ))
    with pytest.raises(ValueError, match="no decreciente"):
        muestra_biologica_dao.actualizar(muestra_biologica)


def test_recuperar_rechaza_estado_desconocido(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.execute("PRAGMA ignore_check_constraints = ON")
    conexion.execute("""
        UPDATE muestra_biologica SET estado_actual = 'DESCONOCIDO'
        WHERE id_muestra = 110
    """)
    with pytest.raises(ValueError, match="desconocido"):
        muestra_biologica_dao.obtener_por_id(110)


def test_recuperar_rechaza_historial_vacio_y_estado_final_inconsistente(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.execute("DELETE FROM historial_estado_muestra WHERE id_muestra = 110")
    with pytest.raises(ValueError, match="vacío"):
        muestra_biologica_dao.obtener_por_id(110)
    conexion.execute("""
        INSERT INTO historial_estado_muestra
            (id_muestra, estado, fecha_hora, observaciones)
        VALUES (110, 'EXTRAIDA', '2026-11-03T11:45:12.654321', '')
    """)
    conexion.execute("""
        UPDATE muestra_biologica SET estado_actual = 'EMPAQUETADA'
        WHERE id_muestra = 110
    """)
    with pytest.raises(ValueError, match="no coincide"):
        muestra_biologica_dao.obtener_por_id(110)


@pytest.mark.parametrize("estado_historial, mensaje", [
    ("EMPAQUETADA", "comenzar en EXTRAIDA"),
    ("DESCONOCIDO", "desconocido"),
])
def test_recuperar_rechaza_inicio_o_estado_historico_invalido(
    estado_historial, mensaje, request, conexion,
    muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.execute("PRAGMA ignore_check_constraints = ON")
    conexion.execute("DELETE FROM historial_estado_muestra WHERE id_muestra = 110")
    conexion.execute("""
        INSERT INTO historial_estado_muestra
            (id_muestra, estado, fecha_hora, observaciones)
        VALUES (110, ?, '2026-11-03T11:45:12.654321', '')
    """, (estado_historial,))
    conexion.execute("""
        UPDATE muestra_biologica SET estado_actual = ? WHERE id_muestra = 110
    """, (estado_historial,))
    with pytest.raises(ValueError, match=mensaje):
        muestra_biologica_dao.obtener_por_id(110)


@pytest.mark.parametrize("estado", ["RECHAZADA", "ANALIZADA", "RECIBIDA", "EXTRAIDA"])
def test_state_recuperado_conserva_comportamiento(
    estado, request, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    _avanzar_hasta(muestra_biologica, estado)
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    cantidad = len(recuperada.obtener_historial())
    fecha = datetime(2026, 11, 3, 13)
    if estado == "RECHAZADA":
        assert recuperada.analizar(fecha) is False
        assert len(recuperada.obtener_historial()) == cantidad
    elif estado == "ANALIZADA":
        assert recuperada.analizar(fecha) is False
        assert recuperada.recibir(fecha) is False
        assert len(recuperada.obtener_historial()) == cantidad
    elif estado == "RECIBIDA":
        assert recuperada.analizar(fecha) is True
        assert recuperada.obtener_historial()[-1].nombre_estado == "ANALIZADA"
    else:
        assert recuperada.empaquetar(fecha) is True
        assert recuperada.obtener_historial()[-1].nombre_estado == "EMPAQUETADA"


def test_crear_y_actualizar_no_hacen_commit_ni_rollback(
    request, conexion, muestra_biologica_dao, muestra_biologica,
):
    orden = _persistir_dependencias(request)
    conexion.commit()
    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.rollback()
    assert muestra_biologica_dao.obtener_por_id(110) is None

    muestra_biologica_dao.crear(muestra_biologica, orden.id_orden)
    conexion.commit()
    assert muestra_biologica.empaquetar(datetime(2026, 11, 3, 12))
    muestra_biologica_dao.actualizar(muestra_biologica)
    conexion.rollback()
    recuperada = muestra_biologica_dao.obtener_por_id(110)
    assert recuperada.estado.obtener_nombre() == "EXTRAIDA"
    assert len(recuperada.obtener_historial()) == 1


def test_no_existen_operaciones_publicas_de_eliminacion(
    muestra_biologica_dao,
):
    assert not hasattr(muestra_biologica_dao, "eliminar")
    assert not hasattr(muestra_biologica_dao, "eliminar_historial")
