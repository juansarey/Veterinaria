from datetime import date
import sqlite3

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna


def _persistir_dependencias(
    cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    vacuna_dao.crear(vacuna)


def test_crear_y_recuperar_conserva_datos_fechas_y_vacuna(
    conexion, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    recuperada = aplicacion_vacuna_dao.obtener_por_id(90)

    assert isinstance(recuperada, AplicacionVacuna)
    assert recuperada is not aplicacion_vacuna
    assert recuperada.id_aplicacion == aplicacion_vacuna.id_aplicacion == 90
    assert recuperada.fecha_aplicacion == aplicacion_vacuna.fecha_aplicacion
    assert recuperada.fecha_proxima_dosis == aplicacion_vacuna.fecha_proxima_dosis
    assert vars(recuperada.vacuna) == vars(vacuna)
    fila = conexion.execute("""
        SELECT id_mascota, id_vacuna, fecha_aplicacion, fecha_proxima_dosis
        FROM aplicacion_vacuna WHERE id_aplicacion = ?
    """, (90,)).fetchone()
    assert fila["id_mascota"] == mascota.id_mascota
    assert fila["id_vacuna"] == vacuna.id_vacuna
    assert fila["fecha_aplicacion"] == date(2026, 2, 3).isoformat()
    assert fila["fecha_proxima_dosis"] == date(2027, 2, 3).isoformat()


def test_inexistente_devuelve_none(aplicacion_vacuna_dao):
    assert aplicacion_vacuna_dao.obtener_por_id(999) is None


def test_listar_por_mascota_vacio(aplicacion_vacuna_dao):
    assert aplicacion_vacuna_dao.listar_por_mascota(999) == []


def test_listar_por_mascota_filtra_y_ordena_por_id(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    otra_mascota = Mascota(21, "Sol", "Gato", cliente)
    mascota_dao.crear(otra_mascota)
    for id_aplicacion, id_mascota in [(110, 20), (10, 20), (50, 21)]:
        aplicacion_vacuna_dao.crear(
            AplicacionVacuna(
                id_aplicacion, vacuna, date(2026, 1, id_aplicacion // 10)
            ),
            id_mascota,
        )

    assert [
        a.id_aplicacion
        for a in aplicacion_vacuna_dao.listar_por_mascota(20)
    ] == [10, 110]
    assert [
        a.id_aplicacion
        for a in aplicacion_vacuna_dao.listar_por_mascota(21)
    ] == [50]


def test_pk_duplicada_propaga_error(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    with pytest.raises(sqlite3.IntegrityError):
        aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)


def test_id_none_es_rechazado(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion = AplicacionVacuna(None, vacuna, date(2026, 1, 1))
    with pytest.raises(ValueError, match="id_aplicacion"):
        aplicacion_vacuna_dao.crear(aplicacion, mascota.id_mascota)


@pytest.mark.parametrize("id_mascota", [999, None])
def test_mascota_inexistente_o_null_propaga_error(
    id_mascota, vacuna_dao, aplicacion_vacuna_dao, vacuna, aplicacion_vacuna
):
    vacuna_dao.crear(vacuna)
    with pytest.raises(sqlite3.IntegrityError):
        aplicacion_vacuna_dao.crear(aplicacion_vacuna, id_mascota)


def test_vacuna_inexistente_propaga_error(
    cliente_dao, mascota_dao, aplicacion_vacuna_dao,
    cliente, mascota
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    inexistente = Vacuna(999, "No persistida", "Perro", True)
    aplicacion = AplicacionVacuna(90, inexistente, date(2026, 1, 1))
    with pytest.raises(sqlite3.IntegrityError):
        aplicacion_vacuna_dao.crear(aplicacion, mascota.id_mascota)


def test_fecha_aplicacion_null_propaga_error(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion = AplicacionVacuna(90, vacuna, None)
    with pytest.raises(sqlite3.IntegrityError):
        aplicacion_vacuna_dao.crear(aplicacion, mascota.id_mascota)


def test_fecha_proxima_dosis_none_conserva_null(
    conexion, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota, vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion = AplicacionVacuna(90, vacuna, date(2026, 1, 1), None)
    aplicacion_vacuna_dao.crear(aplicacion, mascota.id_mascota)
    assert aplicacion_vacuna_dao.obtener_por_id(90).fecha_proxima_dosis is None
    assert conexion.execute("""
        SELECT fecha_proxima_dosis
        FROM aplicacion_vacuna WHERE id_aplicacion = ?
    """, (90,)).fetchone()[0] is None


def test_recuperar_no_agrega_mascota_ni_carga_aplicaciones_en_mascota(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    recuperada = aplicacion_vacuna_dao.obtener_por_id(90)
    mascota_recuperada = mascota_dao.obtener_por_id(mascota.id_mascota)
    assert not hasattr(recuperada, "mascota")
    assert mascota_recuperada.obtener_aplicaciones_vacuna() == []


def test_recuperar_no_ejecuta_agregar_aplicacion_vacuna(
    monkeypatch, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La recuperación no debe modificar la mascota")

    monkeypatch.setattr(
        Mascota, "agregar_aplicacion_vacuna", operacion_prohibida
    )
    assert aplicacion_vacuna_dao.obtener_por_id(90).id_aplicacion == 90


def test_actualizar_fechas_conserva_mascota_y_vacuna_originales(
    conexion, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    otra_vacuna = Vacuna(81, "Séxtuple", "Perro", True)
    vacuna_dao.crear(otra_vacuna)
    actualizada = AplicacionVacuna(
        90, otra_vacuna, date(2026, 3, 4), date(2027, 3, 4)
    )

    assert aplicacion_vacuna_dao.actualizar(actualizada) is True
    fila = conexion.execute("""
        SELECT id_mascota, id_vacuna, fecha_aplicacion, fecha_proxima_dosis
        FROM aplicacion_vacuna WHERE id_aplicacion = ?
    """, (90,)).fetchone()
    assert fila["id_mascota"] == mascota.id_mascota
    assert fila["id_vacuna"] == vacuna.id_vacuna
    assert fila["fecha_aplicacion"] == date(2026, 3, 4).isoformat()
    assert fila["fecha_proxima_dosis"] == date(2027, 3, 4).isoformat()
    recuperada = aplicacion_vacuna_dao.obtener_por_id(90)
    assert recuperada.vacuna.id_vacuna == vacuna.id_vacuna


def test_actualizar_inexistente_devuelve_false(
    aplicacion_vacuna_dao, aplicacion_vacuna
):
    assert aplicacion_vacuna_dao.actualizar(aplicacion_vacuna) is False


def test_eliminar(
    cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    assert aplicacion_vacuna_dao.eliminar(90) is True
    assert aplicacion_vacuna_dao.obtener_por_id(90) is None


def test_eliminar_inexistente_devuelve_false(aplicacion_vacuna_dao):
    assert aplicacion_vacuna_dao.eliminar(999) is False


@pytest.mark.parametrize("padre", ["mascota", "vacuna"])
def test_eliminar_padre_referenciado_propaga_error(
    padre, cliente_dao, mascota_dao, vacuna_dao, aplicacion_vacuna_dao,
    cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    with pytest.raises(sqlite3.IntegrityError):
        if padre == "mascota":
            mascota_dao.eliminar(mascota.id_mascota)
        else:
            vacuna_dao.eliminar(vacuna.id_vacuna)


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, cliente_dao, mascota_dao, vacuna_dao,
    aplicacion_vacuna_dao, cliente, mascota, vacuna, aplicacion_vacuna
):
    _persistir_dependencias(
        cliente_dao, mascota_dao, vacuna_dao, cliente, mascota, vacuna
    )
    conexion.commit()
    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    conexion.rollback()
    assert aplicacion_vacuna_dao.obtener_por_id(90) is None

    aplicacion_vacuna_dao.crear(aplicacion_vacuna, mascota.id_mascota)
    conexion.commit()
    actualizada = AplicacionVacuna(
        90, vacuna, date(2026, 4, 5), date(2027, 4, 5)
    )
    aplicacion_vacuna_dao.actualizar(actualizada)
    conexion.rollback()
    assert aplicacion_vacuna_dao.obtener_por_id(90).fecha_aplicacion == date(
        2026, 2, 3
    )

    aplicacion_vacuna_dao.eliminar(90)
    conexion.rollback()
    assert aplicacion_vacuna_dao.obtener_por_id(90) is not None
