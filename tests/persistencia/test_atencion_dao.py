from datetime import datetime
from enum import Enum
import sqlite3

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    OrdenDerivacionLaboratorio,
)


def _persistir_dependencias(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, cliente, mascota, clinica, veterinario,
    historia_clinica
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)


def test_id_none_se_rechaza_sin_sql_y_conserva_transaccion(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    conexion.execute(
        "INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)",
        (999, "Trabajo pendiente", "Perro"),
    )
    assert conexion.in_transaction
    atencion.id_atencion = None
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        with pytest.raises(ValueError, match="id_atencion"):
            atencion_dao.crear(atencion, historia_clinica.id_historia)
    finally:
        conexion.set_trace_callback(None)

    assert sentencias == []
    assert conexion.in_transaction
    assert conexion.execute("SELECT COUNT(*) FROM atencion").fetchone()[0] == 0
    assert conexion.execute(
        "SELECT nombre FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone()[0] == "Trabajo pendiente"

    conexion.rollback()
    assert not conexion.in_transaction
    assert conexion.execute(
        "SELECT id_vacuna FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone() is None


def test_crear_y_recuperar_conserva_datos_tipo_fecha_y_veterinario(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    recuperada = atencion_dao.obtener_por_id(atencion.id_atencion)

    assert isinstance(recuperada, Atencion)
    assert recuperada is not atencion
    assert recuperada.id_atencion == atencion.id_atencion == 70
    assert recuperada.fecha_hora == atencion.fecha_hora
    assert recuperada.tipo == TipoAtencion.CONSULTA
    assert recuperada.motivo == atencion.motivo
    assert recuperada.diagnostico == atencion.diagnostico
    assert recuperada.observaciones == atencion.observaciones
    assert recuperada.veterinario.id_veterinario == veterinario.id_veterinario
    fila = conexion.execute("""
        SELECT id_historia, id_veterinario, fecha_hora, tipo
        FROM atencion WHERE id_atencion = ?
    """, (70,)).fetchone()
    assert fila["id_historia"] == historia_clinica.id_historia
    assert fila["id_veterinario"] == veterinario.id_veterinario
    assert fila["fecha_hora"] == atencion.fecha_hora.isoformat()
    assert fila["tipo"] == "CONSULTA"


def test_inexistente_devuelve_none(atencion_dao):
    assert atencion_dao.obtener_por_id(999) is None


def test_listados_vacios(atencion_dao):
    assert atencion_dao.listar() == []
    assert atencion_dao.listar(cargar_ordenes=True) == []
    assert atencion_dao.listar_por_historia(999) == []


def test_listar_y_listar_por_historia_ordenan_por_id(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    otro_cliente = Cliente(11, "Juan", "Díaz", "40111222")
    otra_mascota = Mascota(21, "Sol", "Gato", otro_cliente)
    otra_historia = HistoriaClinica(61, historia_clinica.fecha_apertura)
    cliente_dao.crear(otro_cliente)
    mascota_dao.crear(otra_mascota)
    historia_clinica_dao.crear(otra_historia, otra_mascota.id_mascota)

    for id_atencion, id_historia in [(90, 60), (10, 60), (50, 61)]:
        atencion_dao.crear(Atencion(
            id_atencion,
            datetime(2026, 11, 3, 10),
            TipoAtencion.CONTROL,
            "Control",
            veterinario,
        ), id_historia)

    assert [a.id_atencion for a in atencion_dao.listar()] == [10, 50, 90]
    assert [
        a.id_atencion
        for a in atencion_dao.listar_por_historia(60)
    ] == [10, 90]


@pytest.mark.parametrize("tipo", list(TipoAtencion))
def test_recupera_todos_los_tipos(
    tipo, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion = Atencion(
        70, datetime(2026, 11, 3, 10), tipo, "Control", veterinario
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    assert atencion_dao.obtener_por_id(70).tipo == tipo


def test_actualizar_datos_y_veterinario_sin_cambiar_historia(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    otro_veterinario = Veterinario(41, "Luis", "Díaz", "MP-200")
    veterinario_dao.crear(otro_veterinario, clinica.id_clinica)
    actualizada = Atencion(
        70,
        datetime(2026, 12, 4, 15, 16, 17, 222333),
        TipoAtencion.URGENCIA,
        "Dolor agudo",
        otro_veterinario,
        "Gastritis",
        "Medicación",
    )

    assert atencion_dao.actualizar(actualizada) is True
    recuperada = atencion_dao.obtener_por_id(70)
    assert recuperada.fecha_hora == actualizada.fecha_hora
    assert recuperada.tipo == TipoAtencion.URGENCIA
    assert recuperada.veterinario.id_veterinario == 41
    assert recuperada.motivo == "Dolor agudo"
    assert recuperada.diagnostico == "Gastritis"
    assert recuperada.observaciones == "Medicación"
    assert conexion.execute("""
        SELECT id_historia FROM atencion WHERE id_atencion = ?
    """, (70,)).fetchone()[0] == historia_clinica.id_historia


def test_actualizar_inexistente_devuelve_false(atencion_dao, atencion):
    assert atencion_dao.actualizar(atencion) is False


def test_actualizar_veterinario_inexistente_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    atencion.veterinario = Veterinario(999, "No", "Existe", "MP-X")
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.actualizar(atencion)


def test_eliminar(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    assert atencion_dao.eliminar(70) is True
    assert atencion_dao.obtener_por_id(70) is None


def test_eliminar_inexistente_devuelve_false(atencion_dao):
    assert atencion_dao.eliminar(999) is False


def test_pk_duplicada_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.crear(atencion, historia_clinica.id_historia)


@pytest.mark.parametrize("id_historia", [999, None])
def test_historia_inexistente_o_null_propaga_error(
    id_historia, cliente_dao, mascota_dao, clinica_dao,
    veterinario_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, atencion
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.crear(atencion, id_historia)


def test_veterinario_inexistente_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, historia_clinica_dao,
    atencion_dao, cliente, mascota, clinica, historia_clinica
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    inexistente = Veterinario(999, "No", "Existe", "MP-X")
    atencion = Atencion(
        70, datetime(2026, 11, 3, 10), TipoAtencion.CONSULTA,
        "Control", inexistente
    )
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.crear(atencion, historia_clinica.id_historia)


@pytest.mark.parametrize("campo", ["fecha_hora", "tipo"])
def test_campos_obligatorios_rechazan_null(
    campo, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    setattr(atencion, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.crear(atencion, historia_clinica.id_historia)


def test_tipo_invalido_es_rechazado_por_check(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    TipoInvalido = Enum("TipoInvalido", {"INVALIDO": "INVALIDO"})
    atencion.tipo = TipoInvalido.INVALIDO
    with pytest.raises(sqlite3.IntegrityError):
        atencion_dao.crear(atencion, historia_clinica.id_historia)


def test_campos_opcionales_none_conservan_null(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion = Atencion(
        70, datetime(2026, 11, 3, 10, 20, 30, 456789),
        TipoAtencion.CONTROL, None, veterinario, None, None
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    recuperada = atencion_dao.obtener_por_id(70)
    assert recuperada.motivo is None
    assert recuperada.diagnostico is None
    assert recuperada.observaciones is None
    fila = conexion.execute("""
        SELECT motivo, diagnostico, observaciones
        FROM atencion WHERE id_atencion = ?
    """, (70,)).fetchone()
    assert tuple(fila) == (None, None, None)


def test_veterinario_recuperado_es_basico_y_no_agrega_historia(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    recuperada = atencion_dao.obtener_por_id(70)
    assert vars(recuperada.veterinario) == vars(veterinario)
    assert recuperada.veterinario.obtener_agenda() is None
    assert recuperada.veterinario.obtener_turnos() == []
    assert not hasattr(recuperada.veterinario, "clinica")
    assert not hasattr(recuperada, "historia_clinica")


def test_recuperar_no_registra_atencion_ni_carga_ordenes(
    monkeypatch, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La recuperación no debe registrar la atención")

    monkeypatch.setattr(Mascota, "registrar_atencion", operacion_prohibida)
    monkeypatch.setattr(
        HistoriaClinica, "_agregar_atencion", operacion_prohibida
    )
    recuperada = atencion_dao.obtener_por_id(70)
    assert recuperada.obtener_ordenes_derivacion() == []


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        historia_clinica_dao, cliente, mascota, clinica, veterinario,
        historia_clinica
    )
    conexion.commit()
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    conexion.rollback()
    assert atencion_dao.obtener_por_id(70) is None

    atencion_dao.crear(atencion, historia_clinica.id_historia)
    conexion.commit()
    actualizada = Atencion(
        70, datetime(2026, 12, 4, 15), TipoAtencion.URGENCIA,
        "Urgencia", veterinario
    )
    atencion_dao.actualizar(actualizada)
    conexion.rollback()
    assert atencion_dao.obtener_por_id(70).tipo == TipoAtencion.CONSULTA

    atencion_dao.eliminar(70)
    conexion.rollback()
    assert atencion_dao.obtener_por_id(70) is not None


def test_listar_carga_ordenes_opcionalmente_sin_mezclarlas(
    conexion, monkeypatch, atencion_persistida, atencion_dao,
    orden_derivacion_laboratorio_dao,
):
    for id_atencion in (71, 72):
        atencion_dao.crear(Atencion(
            id_atencion, atencion_persistida.fecha_hora, TipoAtencion.CONTROL,
            "Control", atencion_persistida.veterinario,
        ), 60)
    for id_orden, id_atencion in ((102, 70), (100, 70), (101, 71)):
        orden_derivacion_laboratorio_dao.crear(OrdenDerivacionLaboratorio(
            id_orden, atencion_persistida.fecha_hora, f"Estudio {id_orden}",
        ), id_atencion)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("Leer no debe asociar órdenes por el dominio")

    monkeypatch.setattr(Atencion, "agregar_orden_derivacion", operacion_prohibida)
    monkeypatch.setattr(
        OrdenDerivacionLaboratorio, "iniciar_proceso", operacion_prohibida
    )
    assert all(a.obtener_ordenes_derivacion() == [] for a in atencion_dao.listar())
    assert all(
        a.obtener_ordenes_derivacion() == []
        for a in atencion_dao.listar(cargar_ordenes=False)
    )
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        for _ in range(2):
            atenciones = atencion_dao.listar(cargar_ordenes=True)
            assert [a.id_atencion for a in atenciones] == [70, 71, 72]
            assert [
                [o.id_orden for o in a.obtener_ordenes_derivacion()]
                for a in atenciones
            ] == [[100, 102], [101], []]
            assert atenciones[1].obtener_ordenes_derivacion()[0].estudio_solicitado == (
                "Estudio 101"
            )
    finally:
        conexion.set_trace_callback(None)
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in sentencias)
    assert conexion.execute(
        "SELECT COUNT(*) FROM orden_derivacion_laboratorio"
    ).fetchone()[0] == 3
    assert atencion_dao.obtener_por_id(70).obtener_ordenes_derivacion() == []
