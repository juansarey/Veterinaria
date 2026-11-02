import sqlite3

import pytest

from veterinaria.dominio.clinica.veterinario import Veterinario


def _persistir_clinica(clinica_dao, clinica):
    clinica_dao.crear(clinica)


def test_id_none_se_rechaza_sin_sql_y_conserva_transaccion(
    conexion, clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    conexion.execute(
        "INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)",
        (999, "Trabajo pendiente", "Perro"),
    )
    assert conexion.in_transaction
    veterinario.id_veterinario = None
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        with pytest.raises(ValueError, match="id_veterinario"):
            veterinario_dao.crear(veterinario, clinica.id_clinica)
    finally:
        conexion.set_trace_callback(None)

    assert sentencias == []
    assert conexion.in_transaction
    assert conexion.execute("SELECT COUNT(*) FROM veterinario").fetchone()[0] == 0
    assert conexion.execute(
        "SELECT nombre FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone()[0] == "Trabajo pendiente"

    conexion.rollback()
    assert not conexion.in_transaction
    assert conexion.execute(
        "SELECT id_vacuna FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone() is None


def test_crear_y_recuperar_conserva_datos(
    clinica_dao, veterinario_dao, clinica, veterinario
):
    _persistir_clinica(clinica_dao, clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    recuperado = veterinario_dao.obtener_por_id(40)
    assert isinstance(recuperado, Veterinario)
    assert recuperado is not veterinario
    assert vars(recuperado) == vars(veterinario)
    assert recuperado.id_veterinario == veterinario.id_veterinario == 40


def test_id_inexistente_devuelve_none(veterinario_dao):
    assert veterinario_dao.obtener_por_id(999) is None


def test_listar_vacio(veterinario_dao):
    assert veterinario_dao.listar() == []


def test_listar_y_listar_por_clinica(
    clinica_dao, veterinario_dao, clinica, veterinario
):
    otra_clinica_id = 31
    clinica_dao.crear(clinica)
    clinica_dao.crear(type(clinica)(otra_clinica_id, "Norte", "Belgrano 200"))
    otro = Veterinario(10, "Luis", "Gómez", "MP-200")
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    veterinario_dao.crear(otro, otra_clinica_id)

    assert [v.id_veterinario for v in veterinario_dao.listar()] == [10, 40]
    assert [
        v.id_veterinario
        for v in veterinario_dao.listar_por_clinica(clinica.id_clinica)
    ] == [40]
    assert veterinario_dao.listar_por_clinica(999) == []


def test_actualizar_datos_y_clinica(
    conexion, clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    otra = type(clinica)(31, "Norte", "Belgrano 200")
    clinica_dao.crear(otra)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    actualizado = Veterinario(40, "Laura", "Díaz", "MP-101", "Cirugía")

    assert veterinario_dao.actualizar(actualizado, otra.id_clinica) is True
    assert vars(veterinario_dao.obtener_por_id(40)) == vars(actualizado)
    assert conexion.execute("""
        SELECT id_clinica FROM veterinario WHERE id_veterinario = ?
    """, (40,)).fetchone()[0] == otra.id_clinica


def test_actualizar_inexistente_devuelve_false(veterinario_dao, veterinario):
    assert veterinario_dao.actualizar(veterinario, 30) is False


def test_eliminar(clinica_dao, veterinario_dao, clinica, veterinario):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    assert veterinario_dao.eliminar(40) is True
    assert veterinario_dao.obtener_por_id(40) is None


def test_eliminar_inexistente_devuelve_false(veterinario_dao):
    assert veterinario_dao.eliminar(999) is False


def test_clinica_inexistente_propaga_error(veterinario_dao, veterinario):
    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.crear(veterinario, 999)


def test_clinica_null_propaga_error(veterinario_dao, veterinario):
    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.crear(veterinario, None)


def test_actualizar_con_clinica_inexistente_propaga_error(
    clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.actualizar(veterinario, 999)


@pytest.mark.parametrize("id_veterinario, matricula", [(40, "OTRA"), (41, "MP-100")])
def test_pk_o_matricula_duplicada_propaga_error(
    clinica_dao, veterinario_dao, clinica, veterinario,
    id_veterinario, matricula
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    duplicado = Veterinario(id_veterinario, "Otro", "Profesional", matricula)
    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.crear(duplicado, clinica.id_clinica)


@pytest.mark.parametrize("campo", ["nombre", "apellido", "matricula"])
def test_campos_obligatorios_rechazan_null(
    clinica_dao, veterinario_dao, clinica, veterinario, campo
):
    clinica_dao.crear(clinica)
    setattr(veterinario, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.crear(veterinario, clinica.id_clinica)


def test_especialidad_opcional_conserva_null(
    clinica_dao, veterinario_dao, clinica
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(
        Veterinario(40, "Ana", "Pérez", "MP-100", None),
        clinica.id_clinica,
    )
    assert veterinario_dao.obtener_por_id(40).especialidad is None


def test_recuperar_no_agrega_clinica_agenda_ni_turnos(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    agenda_medica_dao, turno_dao, cliente, mascota, clinica,
    veterinario, agenda_medica, turno
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    turno_dao.crear(turno, veterinario.id_veterinario)
    recuperado = veterinario_dao.obtener_por_id(veterinario.id_veterinario)

    assert not hasattr(recuperado, "clinica")
    assert recuperado.obtener_agenda() is None
    assert recuperado.obtener_turnos() == []


@pytest.mark.parametrize("dependencia", ["agenda", "turno"])
def test_eliminar_con_dependencias_propaga_error(
    dependencia, cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    agenda_medica_dao, turno_dao, cliente, mascota, clinica,
    veterinario, agenda_medica, turno
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    if dependencia == "agenda":
        agenda_medica_dao.crear(agenda_medica, veterinario.id_veterinario)
    else:
        cliente_dao.crear(cliente)
        mascota_dao.crear(mascota)
        turno_dao.crear(turno, veterinario.id_veterinario)

    with pytest.raises(sqlite3.IntegrityError):
        veterinario_dao.eliminar(veterinario.id_veterinario)


def test_crear_no_hace_commit(
    conexion, clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    conexion.commit()
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    conexion.rollback()
    assert veterinario_dao.obtener_por_id(veterinario.id_veterinario) is None
