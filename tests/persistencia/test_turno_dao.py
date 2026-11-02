from datetime import datetime
import sqlite3

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.turno import EstadoTurno, Turno
from veterinaria.dominio.clinica.veterinario import Veterinario


def _persistir_dependencias(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    cliente, mascota, clinica, veterinario
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)


def test_id_none_se_rechaza_sin_sql_y_conserva_transaccion(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    conexion.execute(
        "INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)",
        (999, "Trabajo pendiente", "Perro"),
    )
    assert conexion.in_transaction
    turno.id_turno = None
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        with pytest.raises(ValueError, match="id_turno"):
            turno_dao.crear(turno, veterinario.id_veterinario)
    finally:
        conexion.set_trace_callback(None)

    assert sentencias == []
    assert conexion.in_transaction
    assert conexion.execute("SELECT COUNT(*) FROM turno").fetchone()[0] == 0
    assert conexion.execute(
        "SELECT nombre FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone()[0] == "Trabajo pendiente"

    conexion.rollback()
    assert not conexion.in_transaction
    assert conexion.execute(
        "SELECT id_vacuna FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone() is None


def test_crear_y_recuperar_conserva_datos_mascota_y_responsable(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    recuperado = turno_dao.obtener_por_id(turno.id_turno)

    assert isinstance(recuperado, Turno)
    assert recuperado is not turno
    assert recuperado.id_turno == turno.id_turno == 50
    assert recuperado.fecha_hora_inicio == turno.fecha_hora_inicio
    assert recuperado.fecha_hora_fin == turno.fecha_hora_fin
    assert recuperado.motivo == turno.motivo
    assert recuperado.estado == EstadoTurno.PENDIENTE
    assert recuperado.mascota.id_mascota == mascota.id_mascota
    assert vars(recuperado.mascota.responsable) == vars(cliente)

    fila = conexion.execute("""
        SELECT fecha_hora_inicio, fecha_hora_fin, estado
        FROM turno WHERE id_turno = ?
    """, (turno.id_turno,)).fetchone()
    assert fila["fecha_hora_inicio"] == turno.fecha_hora_inicio.isoformat()
    assert fila["fecha_hora_fin"] == turno.fecha_hora_fin.isoformat()
    assert fila["estado"] == "PENDIENTE"


def test_id_inexistente_devuelve_none(turno_dao):
    assert turno_dao.obtener_por_id(999) is None


def test_listar_vacio(turno_dao):
    assert turno_dao.listar() == []
    assert turno_dao.listar_por_veterinario(999) == []


def test_listar_y_listar_por_veterinario(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    otro_veterinario = Veterinario(41, "Luis", "Gómez", "MP-200")
    veterinario_dao.crear(otro_veterinario, clinica.id_clinica)
    otro_turno = Turno(
        10,
        datetime(2026, 11, 3, 11),
        datetime(2026, 11, 3, 12),
        mascota,
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    turno_dao.crear(otro_turno, otro_veterinario.id_veterinario)

    assert [t.id_turno for t in turno_dao.listar()] == [10, 50]
    assert [
        t.id_turno
        for t in turno_dao.listar_por_veterinario(veterinario.id_veterinario)
    ] == [50]


@pytest.mark.parametrize("estado", list(EstadoTurno))
def test_recupera_todos_los_estados_sin_ejecutar_transiciones(
    monkeypatch, estado, cliente_dao, mascota_dao, clinica_dao,
    veterinario_dao, turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    if estado == EstadoTurno.CONFIRMADO:
        turno.confirmar()
    elif estado == EstadoTurno.ATENDIDO:
        turno.confirmar()
        turno.marcar_atendido()
    elif estado == EstadoTurno.CANCELADO:
        turno.cancelar()
    turno_dao.crear(turno, veterinario.id_veterinario)

    def transicion_prohibida(*args, **kwargs):
        raise AssertionError("La recuperación no debe ejecutar transiciones")

    monkeypatch.setattr(Turno, "confirmar", transicion_prohibida)
    monkeypatch.setattr(Turno, "cancelar", transicion_prohibida)
    monkeypatch.setattr(Turno, "marcar_atendido", transicion_prohibida)
    assert turno_dao.obtener_por_id(turno.id_turno).estado == estado


def test_motivo_opcional_conserva_null(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno = Turno(
        50,
        datetime(2026, 11, 2, 9),
        datetime(2026, 11, 2, 10),
        mascota,
        None,
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    assert turno_dao.obtener_por_id(50).motivo is None


def test_veterinario_inexistente_propaga_error(
    cliente_dao, mascota_dao, turno_dao, cliente, mascota, turno
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    with pytest.raises(sqlite3.IntegrityError):
        turno_dao.crear(turno, 999)


def test_veterinario_null_propaga_error(
    cliente_dao, mascota_dao, turno_dao, cliente, mascota, turno
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    with pytest.raises(sqlite3.IntegrityError):
        turno_dao.crear(turno, None)


def test_mascota_inexistente_propaga_error(
    clinica_dao, veterinario_dao, turno_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    responsable = Cliente(999, "No", "Persistido", "999")
    mascota = Mascota(999, "Sol", "Gato", responsable)
    turno = Turno(
        50,
        datetime(2026, 11, 2, 9),
        datetime(2026, 11, 2, 10),
        mascota,
    )
    with pytest.raises(sqlite3.IntegrityError):
        turno_dao.crear(turno, veterinario.id_veterinario)


def test_pk_duplicada_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    with pytest.raises(sqlite3.IntegrityError):
        turno_dao.crear(turno, veterinario.id_veterinario)


def test_actualizar_todos_los_datos_y_contextos(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    otro_cliente = Cliente(11, "Juan", "Gómez", "40111222")
    otra_mascota = Mascota(21, "Sol", "Gato", otro_cliente)
    otro_veterinario = Veterinario(41, "Luis", "Díaz", "MP-200")
    cliente_dao.crear(otro_cliente)
    mascota_dao.crear(otra_mascota)
    veterinario_dao.crear(otro_veterinario, clinica.id_clinica)
    actualizado = Turno(
        50,
        datetime(2026, 12, 1, 14, 1, 2, 333333),
        datetime(2026, 12, 1, 15, 3, 4, 444444),
        otra_mascota,
        "Urgencia",
    )
    actualizado.confirmar()

    assert turno_dao.actualizar(actualizado, otro_veterinario.id_veterinario) is True
    recuperado = turno_dao.obtener_por_id(50)
    assert recuperado.mascota.id_mascota == 21
    assert recuperado.fecha_hora_inicio == actualizado.fecha_hora_inicio
    assert recuperado.fecha_hora_fin == actualizado.fecha_hora_fin
    assert recuperado.estado == EstadoTurno.CONFIRMADO
    assert recuperado.motivo == "Urgencia"
    assert conexion.execute("""
        SELECT id_veterinario FROM turno WHERE id_turno = ?
    """, (50,)).fetchone()[0] == otro_veterinario.id_veterinario


def test_actualizar_inexistente_devuelve_false(turno_dao, turno):
    assert turno_dao.actualizar(turno, 40) is False


def test_actualizar_fk_invalida_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    with pytest.raises(sqlite3.IntegrityError):
        turno_dao.actualizar(turno, 999)


def test_eliminar(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    assert turno_dao.eliminar(50) is True
    assert turno_dao.obtener_por_id(50) is None


def test_eliminar_inexistente_devuelve_false(turno_dao):
    assert turno_dao.eliminar(999) is False


def test_turno_recuperado_no_conoce_veterinario(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    turno_dao.crear(turno, veterinario.id_veterinario)
    assert not hasattr(turno_dao.obtener_por_id(50), "veterinario")


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    turno_dao, cliente, mascota, clinica, veterinario, turno
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    conexion.commit()
    turno_dao.crear(turno, veterinario.id_veterinario)
    conexion.rollback()
    assert turno_dao.obtener_por_id(50) is None

    turno_dao.crear(turno, veterinario.id_veterinario)
    conexion.commit()
    actualizado = Turno(
        50,
        datetime(2026, 11, 3, 11),
        datetime(2026, 11, 3, 12),
        mascota,
    )
    turno_dao.actualizar(actualizado, veterinario.id_veterinario)
    conexion.rollback()
    assert turno_dao.obtener_por_id(50).fecha_hora_inicio == turno.fecha_hora_inicio

    turno_dao.eliminar(50)
    conexion.rollback()
    assert turno_dao.obtener_por_id(50) is not None


def test_enum_invalido_es_rechazado_por_sqlite(
    conexion, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    cliente, mascota, clinica, veterinario
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
        cliente, mascota, clinica, veterinario
    )
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            INSERT INTO turno (
                id_turno, id_mascota, id_veterinario,
                fecha_hora_inicio, fecha_hora_fin, estado
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            50,
            mascota.id_mascota,
            veterinario.id_veterinario,
            "2026-11-02T09:00:00",
            "2026-11-02T10:00:00",
            "INVALIDO",
        ))
