from datetime import date
import sqlite3

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna


def test_id_none_se_rechaza_sin_sql_y_conserva_transaccion(
    conexion, cliente_dao, mascota_dao, cliente, mascota
):
    cliente_dao.crear(cliente)
    conexion.execute(
        "INSERT INTO vacuna (id_vacuna, nombre, especie) VALUES (?, ?, ?)",
        (999, "Trabajo pendiente", "Perro"),
    )
    assert conexion.in_transaction
    mascota.id_mascota = None
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        with pytest.raises(ValueError, match="id_mascota"):
            mascota_dao.crear(mascota)
    finally:
        conexion.set_trace_callback(None)

    assert sentencias == []
    assert conexion.in_transaction
    assert conexion.execute("SELECT COUNT(*) FROM mascota").fetchone()[0] == 0
    assert conexion.execute(
        "SELECT nombre FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone()[0] == "Trabajo pendiente"

    conexion.rollback()
    assert not conexion.in_transaction
    assert conexion.execute(
        "SELECT id_vacuna FROM vacuna WHERE id_vacuna = ?", (999,)
    ).fetchone() is None


def test_crear_y_recuperar_datos_y_responsable(
    conexion, cliente_dao, mascota_dao, cliente, mascota
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    recuperada = mascota_dao.obtener_por_id(20)
    assert isinstance(recuperada, Mascota)
    assert recuperada is not mascota
    assert recuperada.id_mascota == mascota.id_mascota == 20
    assert recuperada.nombre == mascota.nombre
    assert recuperada.especie == mascota.especie
    assert recuperada.raza == mascota.raza
    assert recuperada.sexo == mascota.sexo
    assert recuperada.fecha_nacimiento == date(2020, 5, 10)
    assert type(recuperada.fecha_nacimiento) is date
    assert recuperada.responsable is not cliente
    assert isinstance(recuperada.responsable, Cliente)
    assert vars(recuperada.responsable) == vars(cliente)
    assert recuperada.responsable.id_cliente == 10
    assert recuperada.obtener_historia_clinica() is None
    assert recuperada.obtener_aplicaciones_vacuna() == []
    fila = conexion.execute("""
        SELECT id_cliente, fecha_nacimiento, typeof(fecha_nacimiento) AS tipo
        FROM mascota WHERE id_mascota = ?
    """, (20,)).fetchone()
    assert tuple(fila) == (10, "2020-05-10", "text")


def test_id_inexistente_devuelve_none(mascota_dao):
    assert mascota_dao.obtener_por_id(999) is None


def test_listar_vacio(mascota_dao):
    assert mascota_dao.listar() == []
    assert mascota_dao.listar(cargar_aplicaciones=True) == []


def test_listar_varias_con_sus_responsables(cliente_dao, mascota_dao, cliente, mascota):
    otro = Cliente(11, "Juan", "Pérez", "40000111")
    cliente_dao.crear(cliente)
    cliente_dao.crear(otro)
    mascota_dao.crear(mascota)
    mascota_dao.crear(Mascota(21, "Sol", "Gato", otro))
    assert [
        (m.id_mascota, m.nombre, m.responsable.id_cliente)
        for m in mascota_dao.listar()
    ] == [(20, "Luna", 10), (21, "Sol", 11)]


def test_actualizar_campos_y_responsable(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    otro = Cliente(11, "Juan", "Pérez", "40000111")
    cliente_dao.crear(otro)
    actualizada = Mascota(20, "Sol", "Gato", otro, "Siamés", date(2021, 2, 3), "Macho")
    assert mascota_dao.actualizar(actualizada) is True
    recuperada = mascota_dao.obtener_por_id(20)
    assert (recuperada.nombre, recuperada.especie, recuperada.raza, recuperada.sexo) == (
        "Sol", "Gato", "Siamés", "Macho"
    )
    assert recuperada.fecha_nacimiento == date(2021, 2, 3)
    assert vars(recuperada.responsable) == vars(otro)


def test_actualizar_inexistente_devuelve_false(mascota_dao, mascota):
    assert mascota_dao.actualizar(mascota) is False


def test_eliminar_no_elimina_responsable(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    assert mascota_dao.eliminar(20) is True
    assert mascota_dao.obtener_por_id(20) is None
    assert cliente_dao.obtener_por_id(10) is not None


def test_eliminar_inexistente_devuelve_false(mascota_dao):
    assert mascota_dao.eliminar(999) is False


def test_fk_inexistente_propaga_error(mascota_dao, mascota):
    with pytest.raises(sqlite3.IntegrityError):
        mascota_dao.crear(mascota)


def test_actualizar_fk_inexistente_propaga_error(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    actualizada = Mascota(
        mascota.id_mascota, mascota.nombre, mascota.especie,
        Cliente(999, "Otro", "Responsable", "999"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        mascota_dao.actualizar(actualizada)
    assert mascota_dao.obtener_por_id(20).responsable.id_cliente == 10


def test_pk_duplicada_propaga_error(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    with pytest.raises(sqlite3.IntegrityError):
        mascota_dao.crear(mascota)


def test_id_cliente_null_rechazado_por_sqlite(conexion):
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            INSERT INTO mascota (id_mascota, id_cliente, nombre, especie)
            VALUES (?, ?, ?, ?)
        """, (20, None, "Luna", "Perro"))


@pytest.mark.parametrize("campo", ["nombre", "especie"])
def test_campos_obligatorios_rechazan_null(cliente_dao, mascota_dao, cliente, mascota, campo):
    cliente_dao.crear(cliente)
    setattr(mascota, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        mascota_dao.crear(mascota)


def test_opcionales_null_se_conservan(cliente_dao, mascota_dao, cliente):
    cliente_dao.crear(cliente)
    mascota_dao.crear(Mascota(20, "Luna", "Perro", cliente, None, None, None))
    recuperada = mascota_dao.obtener_por_id(20)
    assert recuperada.raza is None
    assert recuperada.fecha_nacimiento is None
    assert recuperada.sexo is None


def test_actualizar_fecha_a_null(conexion, cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    mascota.fecha_nacimiento = None
    assert mascota_dao.actualizar(mascota) is True
    assert mascota_dao.obtener_por_id(20).fecha_nacimiento is None
    assert conexion.execute(
        "SELECT fecha_nacimiento FROM mascota WHERE id_mascota = ?", (20,)
    ).fetchone()[0] is None


def test_texto_con_apostrofe_y_sql_es_literal(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota.nombre = "L'Una'); DROP TABLE mascota; --"
    mascota_dao.crear(mascota)
    assert mascota_dao.obtener_por_id(20).nombre == mascota.nombre
    assert mascota_dao.obtener_por_id("20 OR 1=1") is None
    assert mascota_dao.eliminar("20 OR 1=1") is False
    assert len(mascota_dao.listar()) == 1


def test_listar_carga_aplicaciones_opcionalmente_sin_mezclarlas(
    conexion, monkeypatch, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota,
):
    cliente_dao.crear(cliente)
    for actual in (mascota, Mascota(21, "Sol", "Gato", cliente),
                   Mascota(22, "Toby", "Perro", cliente)):
        mascota_dao.crear(actual)
    canina = Vacuna(80, "Antirrábica", "Perro", True)
    felina = Vacuna(81, "Triple felina", "Gato", True)
    vacuna_dao.crear(canina)
    vacuna_dao.crear(felina)
    for id_aplicacion, vacuna, id_mascota in (
        (92, canina, 20), (90, canina, 20), (91, felina, 21),
    ):
        aplicacion_vacuna_dao.crear(
            AplicacionVacuna(id_aplicacion, vacuna, date(2026, 1, 1)),
            id_mascota,
        )

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("Leer no debe registrar aplicaciones")

    monkeypatch.setattr(Mascota, "agregar_aplicacion_vacuna", operacion_prohibida)
    assert all(m.obtener_aplicaciones_vacuna() == [] for m in mascota_dao.listar())
    assert all(
        m.obtener_aplicaciones_vacuna() == []
        for m in mascota_dao.listar(cargar_aplicaciones=False)
    )
    sentencias = []
    conexion.set_trace_callback(sentencias.append)
    try:
        for _ in range(2):
            mascotas = mascota_dao.listar(cargar_aplicaciones=True)
            assert [m.id_mascota for m in mascotas] == [20, 21, 22]
            assert [
                [a.id_aplicacion for a in m.obtener_aplicaciones_vacuna()]
                for m in mascotas
            ] == [[90, 92], [91], []]
            assert [
                [a.vacuna.id_vacuna for a in m.obtener_aplicaciones_vacuna()]
                for m in mascotas
            ] == [[80, 80], [81], []]
            assert mascotas[1].obtener_aplicaciones_vacuna()[0].vacuna.nombre == (
                "Triple felina"
            )
    finally:
        conexion.set_trace_callback(None)
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in sentencias)
    assert conexion.execute(
        "SELECT COUNT(*) FROM aplicacion_vacuna"
    ).fetchone()[0] == 3
    assert mascota_dao.obtener_por_id(20).obtener_aplicaciones_vacuna() == []
