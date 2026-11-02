import sqlite3

import pytest

from veterinaria.dominio.clinica.cliente import Cliente


def test_id_none_se_rechaza_sin_sql_y_conserva_transaccion(
    conexion, cliente_dao, cliente
):
    conexion.execute(
        "INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)",
        (999, "Trabajo pendiente", "Perro"),
    )
    assert conexion.in_transaction
    cliente.id_cliente = None
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        with pytest.raises(ValueError, match="id_cliente"):
            cliente_dao.crear(cliente)
    finally:
        conexion.set_trace_callback(None)

    assert sentencias == []
    assert conexion.in_transaction
    assert conexion.execute("SELECT COUNT(*) FROM cliente").fetchone()[0] == 0
    assert conexion.execute(
        "SELECT nombre FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone()[0] == "Trabajo pendiente"

    conexion.rollback()
    assert not conexion.in_transaction
    assert conexion.execute(
        "SELECT id_vacuna FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone() is None


def test_crear_y_recuperar_conserva_todos_los_datos(cliente_dao, cliente):
    cliente_dao.crear(cliente)
    recuperado = cliente_dao.obtener_por_id(10)
    assert isinstance(recuperado, Cliente)
    assert recuperado is not cliente
    assert vars(recuperado) == vars(cliente)
    assert cliente.id_cliente == 10


def test_id_inexistente_devuelve_none(cliente_dao):
    assert cliente_dao.obtener_por_id(999) is None


def test_listar_vacio(cliente_dao):
    assert cliente_dao.listar() == []


def test_listar_varios(cliente_dao, cliente):
    otro = Cliente(5, "Juan", "Pérez", "40000111")
    cliente_dao.crear(cliente)
    cliente_dao.crear(otro)
    assert [vars(c) for c in cliente_dao.listar()] == [vars(otro), vars(cliente)]


def test_actualizar_todos_los_campos(cliente_dao, cliente):
    cliente_dao.crear(cliente)
    actualizado = Cliente(10, "Ana", "D'Angelo", "40000000", "555", "ana@test.com")
    assert cliente_dao.actualizar(actualizado) is True
    assert vars(cliente_dao.obtener_por_id(10)) == vars(actualizado)


def test_actualizar_inexistente_devuelve_false(cliente_dao, cliente):
    assert cliente_dao.actualizar(cliente) is False


def test_eliminar(cliente_dao, cliente):
    cliente_dao.crear(cliente)
    assert cliente_dao.eliminar(10) is True
    assert cliente_dao.obtener_por_id(10) is None


def test_eliminar_inexistente_devuelve_false(cliente_dao):
    assert cliente_dao.eliminar(999) is False


@pytest.mark.parametrize("id_cliente, dni", [(10, "otro"), (11, "30111222")])
def test_rechaza_pk_o_dni_duplicado(cliente_dao, cliente, id_cliente, dni):
    cliente_dao.crear(cliente)
    with pytest.raises(sqlite3.IntegrityError):
        cliente_dao.crear(Cliente(id_cliente, "Otro", "Cliente", dni))


def test_actualizar_dni_duplicado_propaga_error(cliente_dao, cliente):
    cliente_dao.crear(cliente)
    otro = Cliente(11, "Otro", "Cliente", "otro")
    cliente_dao.crear(otro)
    otro.dni = cliente.dni
    with pytest.raises(sqlite3.IntegrityError):
        cliente_dao.actualizar(otro)
    assert cliente_dao.obtener_por_id(11).dni == "otro"


def test_texto_con_apostrofe_y_sql_se_guarda_literalmente(cliente_dao, cliente):
    cliente.apellido = "D'Angelo'); DROP TABLE cliente; --"
    cliente_dao.crear(cliente)
    assert cliente_dao.obtener_por_id(10).apellido == cliente.apellido
    assert cliente_dao.obtener_por_id("10 OR 1=1") is None
    assert cliente_dao.eliminar("10 OR 1=1") is False
    assert len(cliente_dao.listar()) == 1


@pytest.mark.parametrize("campo", ["nombre", "apellido"])
def test_campos_obligatorios_rechazan_null(cliente_dao, cliente, campo):
    setattr(cliente, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        cliente_dao.crear(cliente)


def test_opcionales_null_y_varios_dni_null_permitidos(cliente_dao):
    for identificador in (10, 11):
        cliente_dao.crear(Cliente(identificador, "Ana", "Pérez", None, None, None))
    for cliente in cliente_dao.listar():
        assert cliente.dni is None
        assert cliente.telefono is None
        assert cliente.email is None


def test_no_agrega_unique_a_telefono_o_email(cliente_dao):
    for identificador in (10, 11):
        cliente_dao.crear(Cliente(identificador, "Ana", "Pérez", None, "555", "a@b.com"))
    assert len(cliente_dao.listar()) == 2


def test_eliminar_cliente_con_mascota_propaga_error(
    cliente_dao, mascota_dao, cliente, mascota
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    with pytest.raises(sqlite3.IntegrityError):
        cliente_dao.eliminar(10)
    assert cliente_dao.obtener_por_id(10) is not None
    assert mascota_dao.obtener_por_id(20) is not None
