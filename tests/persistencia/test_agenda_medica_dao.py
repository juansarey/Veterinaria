from datetime import time
from enum import Enum
import sqlite3

import pytest

from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana


def _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)


def test_crear_y_recuperar_horario_y_varios_dias(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    recuperada = agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    )

    assert isinstance(recuperada, AgendaMedica)
    assert recuperada is not agenda_medica
    assert recuperada.hora_desde == agenda_medica.hora_desde
    assert recuperada.hora_hasta == agenda_medica.hora_hasta
    assert recuperada.dias_trabajo == agenda_medica.dias_trabajo
    assert all(isinstance(dia, DiaSemana) for dia in recuperada.dias_trabajo)

    fila = conexion.execute("""
        SELECT id_agenda, hora_desde, hora_hasta
        FROM agenda_medica WHERE id_veterinario = ?
    """, (veterinario.id_veterinario,)).fetchone()
    assert isinstance(fila["id_agenda"], int)
    assert fila["hora_desde"] == agenda_medica.hora_desde.isoformat()
    assert fila["hora_hasta"] == agenda_medica.hora_hasta.isoformat()
    nombres = conexion.execute("""
        SELECT dia FROM agenda_medica_dia
        WHERE id_agenda = ? ORDER BY dia
    """, (fila["id_agenda"],)).fetchall()
    assert {fila_dia["dia"] for fila_dia in nombres} == {
        "LUNES", "MARTES", "VIERNES"
    }


def test_inexistente_devuelve_none(agenda_medica_dao):
    assert agenda_medica_dao.obtener_por_veterinario(999) is None


def test_agenda_sin_dias_esta_permitida(
    clinica_dao, veterinario_dao, agenda_medica_dao, clinica, veterinario
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(
        AgendaMedica(set(), time(8), time(12)),
        veterinario.id_veterinario,
    )
    recuperada = agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    )
    assert recuperada.dias_trabajo == set()


def test_id_agenda_es_exclusivamente_tecnico(
    clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    recuperada = agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    )
    assert not hasattr(agenda_medica, "id_agenda")
    assert not hasattr(recuperada, "id_agenda")


def test_segunda_agenda_propaga_error(
    clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    with pytest.raises(sqlite3.IntegrityError):
        agenda_medica_dao.crear(
            AgendaMedica({DiaSemana.JUEVES}, time(14), time(18)),
            veterinario.id_veterinario,
        )


def test_veterinario_inexistente_propaga_error(
    agenda_medica_dao, agenda_medica
):
    with pytest.raises(sqlite3.IntegrityError):
        agenda_medica_dao.crear(agenda_medica, 999)


def test_veterinario_null_propaga_error(agenda_medica_dao, agenda_medica):
    with pytest.raises(sqlite3.IntegrityError):
        agenda_medica_dao.crear(agenda_medica, None)


def test_actualizar_reemplaza_horario_y_dias(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    nueva = AgendaMedica(
        {DiaSemana.MIERCOLES, DiaSemana.SABADO},
        time(10, 5, 30, 111111),
        time(18, 40, 20, 222222),
    )

    assert agenda_medica_dao.actualizar(nueva, veterinario.id_veterinario) is True
    recuperada = agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    )
    assert recuperada.hora_desde == nueva.hora_desde
    assert recuperada.hora_hasta == nueva.hora_hasta
    assert recuperada.dias_trabajo == nueva.dias_trabajo
    assert conexion.execute("""
        SELECT COUNT(*) FROM agenda_medica_dia AS d
        JOIN agenda_medica AS a ON a.id_agenda = d.id_agenda
        WHERE a.id_veterinario = ?
    """, (veterinario.id_veterinario,)).fetchone()[0] == 2


def test_actualizar_inexistente_devuelve_false(
    agenda_medica_dao, agenda_medica
):
    assert agenda_medica_dao.actualizar(agenda_medica, 999) is False


def test_rollback_ante_dia_invalido_conserva_agenda_completa(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    conexion.commit()
    DiaInvalido = Enum("DiaInvalido", {"INVALIDO": 99})
    invalida = AgendaMedica(
        {DiaSemana.DOMINGO, DiaInvalido.INVALIDO},
        time(14),
        time(19),
    )

    with pytest.raises(sqlite3.IntegrityError):
        agenda_medica_dao.actualizar(invalida, veterinario.id_veterinario)
    conexion.rollback()

    recuperada = agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    )
    assert recuperada.hora_desde == agenda_medica.hora_desde
    assert recuperada.hora_hasta == agenda_medica.hora_hasta
    assert recuperada.dias_trabajo == agenda_medica.dias_trabajo


def test_eliminar_borra_agenda_y_sus_dias(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    id_agenda = conexion.execute("""
        SELECT id_agenda FROM agenda_medica WHERE id_veterinario = ?
    """, (veterinario.id_veterinario,)).fetchone()[0]

    assert agenda_medica_dao.eliminar_por_veterinario(
        veterinario.id_veterinario
    ) is True
    assert agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    ) is None
    assert conexion.execute("""
        SELECT COUNT(*) FROM agenda_medica_dia WHERE id_agenda = ?
    """, (id_agenda,)).fetchone()[0] == 0


def test_eliminar_inexistente_devuelve_false(agenda_medica_dao):
    assert agenda_medica_dao.eliminar_por_veterinario(999) is False


def test_crear_no_hace_commit(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    conexion.commit()
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    conexion.rollback()
    assert agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    ) is None


def test_actualizar_y_eliminar_no_hacen_commit(
    conexion, clinica_dao, veterinario_dao, agenda_medica_dao,
    clinica, veterinario, agenda_medica
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    conexion.commit()
    original = agenda_medica_dao.obtener_por_veterinario(veterinario.id_veterinario)
    nueva = AgendaMedica({DiaSemana.DOMINGO}, time(14), time(18))

    agenda_medica_dao.actualizar(nueva, veterinario.id_veterinario)
    conexion.rollback()
    recuperada = agenda_medica_dao.obtener_por_veterinario(veterinario.id_veterinario)
    assert recuperada.dias_trabajo == original.dias_trabajo
    assert recuperada.hora_desde == original.hora_desde

    agenda_medica_dao.eliminar_por_veterinario(veterinario.id_veterinario)
    conexion.rollback()
    assert agenda_medica_dao.obtener_por_veterinario(
        veterinario.id_veterinario
    ) is not None


def test_enum_dia_invalido_es_rechazado_por_sqlite(
    conexion, clinica_dao, veterinario_dao, clinica, veterinario
):
    _persistir_veterinario(clinica_dao, veterinario_dao, clinica, veterinario)
    cursor = conexion.execute("""
        INSERT INTO agenda_medica (id_veterinario, hora_desde, hora_hasta)
        VALUES (?, ?, ?)
    """, (veterinario.id_veterinario, "08:00:00", "12:00:00"))
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            INSERT INTO agenda_medica_dia (id_agenda, dia) VALUES (?, ?)
        """, (cursor.lastrowid, "INVALIDO"))
