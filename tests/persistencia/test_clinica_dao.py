import sqlite3

import pytest

from veterinaria.dominio.clinica.clinica import Clinica


def test_crear_y_recuperar_conserva_datos(clinica_dao, clinica):
    clinica_dao.crear(clinica)
    recuperada = clinica_dao.obtener_por_id(30)
    assert isinstance(recuperada, Clinica)
    assert recuperada is not clinica
    assert vars(recuperada) == vars(clinica)
    assert recuperada.id_clinica == clinica.id_clinica == 30


def test_id_inexistente_devuelve_none(clinica_dao):
    assert clinica_dao.obtener_por_id(999) is None


def test_listar_vacio(clinica_dao):
    assert clinica_dao.listar() == []


def test_listar_varias_ordenadas_por_id(clinica_dao, clinica):
    otra = Clinica(10, "Clínica Norte", "Belgrano 200")
    clinica_dao.crear(clinica)
    clinica_dao.crear(otra)
    assert [c.id_clinica for c in clinica_dao.listar()] == [10, 30]


def test_actualizar_todos_los_campos(clinica_dao, clinica):
    clinica_dao.crear(clinica)
    actualizada = Clinica(30, "Clínica Sur", "Colón 500", "351-999999")
    assert clinica_dao.actualizar(actualizada) is True
    assert vars(clinica_dao.obtener_por_id(30)) == vars(actualizada)


def test_actualizar_inexistente_devuelve_false(clinica_dao, clinica):
    assert clinica_dao.actualizar(clinica) is False


def test_eliminar(clinica_dao, clinica):
    clinica_dao.crear(clinica)
    assert clinica_dao.eliminar(30) is True
    assert clinica_dao.obtener_por_id(30) is None


def test_eliminar_inexistente_devuelve_false(clinica_dao):
    assert clinica_dao.eliminar(999) is False


@pytest.mark.parametrize("campo", ["nombre", "direccion"])
def test_campos_obligatorios_rechazan_null(clinica_dao, clinica, campo):
    setattr(clinica, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        clinica_dao.crear(clinica)


def test_telefono_opcional_conserva_null(clinica_dao):
    clinica_dao.crear(Clinica(30, "Centro", "San Martín 100", None))
    assert clinica_dao.obtener_por_id(30).telefono is None


def test_pk_duplicada_propaga_error(clinica_dao, clinica):
    clinica_dao.crear(clinica)
    with pytest.raises(sqlite3.IntegrityError):
        clinica_dao.crear(Clinica(30, "Otra", "Otra dirección"))


def test_eliminar_con_veterinario_propaga_error(
    clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    with pytest.raises(sqlite3.IntegrityError):
        clinica_dao.eliminar(clinica.id_clinica)


def test_recuperar_no_carga_veterinarios(
    clinica_dao, veterinario_dao, clinica, veterinario
):
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    recuperada = clinica_dao.obtener_por_id(clinica.id_clinica)
    assert recuperada.obtener_veterinarios() == []


def test_crear_no_hace_commit(conexion, clinica_dao, clinica):
    clinica_dao.crear(clinica)
    conexion.rollback()
    assert clinica_dao.obtener_por_id(clinica.id_clinica) is None
