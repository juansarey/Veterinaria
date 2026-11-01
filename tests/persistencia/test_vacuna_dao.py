import sqlite3

import pytest

from veterinaria.dominio.vacunacion.vacuna import Vacuna


def test_crear_y_recuperar_conserva_datos_e_id_explicito(
    conexion, vacuna_dao, vacuna
):
    vacuna_dao.crear(vacuna)
    recuperada = vacuna_dao.obtener_por_id(vacuna.id_vacuna)

    assert isinstance(recuperada, Vacuna)
    assert recuperada is not vacuna
    assert vars(recuperada) == vars(vacuna)
    fila = conexion.execute("""
        SELECT id_vacuna, obligatoria FROM vacuna WHERE id_vacuna = ?
    """, (vacuna.id_vacuna,)).fetchone()
    assert fila["id_vacuna"] == 80
    assert fila["obligatoria"] == 1


def test_id_inexistente_devuelve_none(vacuna_dao):
    assert vacuna_dao.obtener_por_id(999) is None


def test_listar_vacio(vacuna_dao):
    assert vacuna_dao.listar() == []


def test_listar_varias_ordenadas_por_id(vacuna_dao, vacuna):
    vacuna_dao.crear(vacuna)
    vacuna_dao.crear(Vacuna(10, "Triple felina", "Gato", False))
    vacuna_dao.crear(Vacuna(50, "Séxtuple", "Perro", True))
    assert [v.id_vacuna for v in vacuna_dao.listar()] == [10, 50, 80]


def test_actualizar_datos(vacuna_dao, vacuna):
    vacuna_dao.crear(vacuna)
    actualizada = Vacuna(80, "Rabia actualizada", "Canino", False)
    assert vacuna_dao.actualizar(actualizada) is True
    assert vars(vacuna_dao.obtener_por_id(80)) == vars(actualizada)


def test_actualizar_inexistente_devuelve_false(vacuna_dao, vacuna):
    assert vacuna_dao.actualizar(vacuna) is False


def test_eliminar(vacuna_dao, vacuna):
    vacuna_dao.crear(vacuna)
    assert vacuna_dao.eliminar(80) is True
    assert vacuna_dao.obtener_por_id(80) is None


def test_eliminar_inexistente_devuelve_false(vacuna_dao):
    assert vacuna_dao.eliminar(999) is False


def test_pk_duplicada_propaga_error(vacuna_dao, vacuna):
    vacuna_dao.crear(vacuna)
    with pytest.raises(sqlite3.IntegrityError):
        vacuna_dao.crear(vacuna)


def test_id_none_es_rechazado(vacuna_dao):
    with pytest.raises(ValueError, match="id_vacuna"):
        vacuna_dao.crear(Vacuna(None, "Rabia", "Perro", True))


@pytest.mark.parametrize("campo", ["nombre", "especie", "obligatoria"])
def test_campos_obligatorios_rechazan_null(vacuna_dao, vacuna, campo):
    setattr(vacuna, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        vacuna_dao.crear(vacuna)


@pytest.mark.parametrize("obligatoria,almacenado", [(True, 1), (False, 0)])
def test_booleano_se_almacena_como_cero_o_uno(
    conexion, vacuna_dao, obligatoria, almacenado
):
    vacuna_dao.crear(Vacuna(80, "Antirrábica", "Perro", obligatoria))
    fila = conexion.execute("""
        SELECT obligatoria FROM vacuna WHERE id_vacuna = ?
    """, (80,)).fetchone()
    assert fila["obligatoria"] == almacenado
    assert vacuna_dao.obtener_por_id(80).obligatoria is obligatoria


def test_default_de_obligatoria_es_cero(conexion, vacuna_dao):
    conexion.execute("""
        INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)
    """, (80, "Antirrábica", "Perro"))
    assert vacuna_dao.obtener_por_id(80).obligatoria is False


def test_check_rechaza_booleano_fuera_de_cero_y_uno(vacuna_dao, vacuna):
    vacuna.obligatoria = 2
    with pytest.raises(sqlite3.IntegrityError):
        vacuna_dao.crear(vacuna)


def test_eliminar_vacuna_utilizada_propaga_error(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna, aplicacion_vacuna
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    vacuna_dao.crear(vacuna)
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    with pytest.raises(sqlite3.IntegrityError):
        vacuna_dao.eliminar(vacuna.id_vacuna)


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, vacuna_dao, vacuna
):
    vacuna_dao.crear(vacuna)
    conexion.rollback()
    assert vacuna_dao.obtener_por_id(80) is None

    vacuna_dao.crear(vacuna)
    conexion.commit()
    vacuna_dao.actualizar(Vacuna(80, "Actualizada", "Gato", False))
    conexion.rollback()
    recuperada = vacuna_dao.obtener_por_id(80)
    assert recuperada.nombre == vacuna.nombre
    assert recuperada.obligatoria is True

    vacuna_dao.eliminar(80)
    conexion.rollback()
    assert vacuna_dao.obtener_por_id(80) is not None
