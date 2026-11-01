from datetime import date, datetime
import sqlite3

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica


def _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)


def test_crear_y_recuperar_conserva_datos_y_fecha_iso(
    conexion, cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    recuperada = historia_clinica_dao.obtener_por_id(
        historia_clinica.id_historia
    )

    assert isinstance(recuperada, HistoriaClinica)
    assert recuperada is not historia_clinica
    assert recuperada.id_historia == historia_clinica.id_historia == 60
    assert recuperada.fecha_apertura == historia_clinica.fecha_apertura
    assert recuperada.observaciones == historia_clinica.observaciones
    fila = conexion.execute("""
        SELECT id_mascota, fecha_apertura
        FROM historia_clinica WHERE id_historia = ?
    """, (60,)).fetchone()
    assert fila["id_mascota"] == mascota.id_mascota
    assert fila["fecha_apertura"] == historia_clinica.fecha_apertura.isoformat()


def test_obtener_por_mascota(
    cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    recuperada = historia_clinica_dao.obtener_por_mascota(mascota.id_mascota)
    assert recuperada.id_historia == historia_clinica.id_historia


def test_inexistentes_devuelven_none(historia_clinica_dao):
    assert historia_clinica_dao.obtener_por_id(999) is None
    assert historia_clinica_dao.obtener_por_mascota(999) is None


def test_actualizar_fecha_y_observaciones_sin_cambiar_mascota(
    conexion, cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    actualizada = HistoriaClinica(60, date(2026, 2, 3), "Antecedente nuevo")

    assert historia_clinica_dao.actualizar(actualizada) is True
    recuperada = historia_clinica_dao.obtener_por_id(60)
    assert recuperada.fecha_apertura == actualizada.fecha_apertura
    assert recuperada.observaciones == actualizada.observaciones
    assert conexion.execute("""
        SELECT id_mascota FROM historia_clinica WHERE id_historia = ?
    """, (60,)).fetchone()[0] == mascota.id_mascota


def test_actualizar_inexistente_devuelve_false(
    historia_clinica_dao, historia_clinica
):
    assert historia_clinica_dao.actualizar(historia_clinica) is False


def test_eliminar(
    cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    assert historia_clinica_dao.eliminar(60) is True
    assert historia_clinica_dao.obtener_por_id(60) is None


def test_eliminar_inexistente_devuelve_false(historia_clinica_dao):
    assert historia_clinica_dao.eliminar(999) is False


def test_pk_duplicada_propaga_error(
    cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    with pytest.raises(sqlite3.IntegrityError):
        historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)


@pytest.mark.parametrize("id_mascota", [999, None])
def test_mascota_inexistente_o_null_propaga_error(
    historia_clinica_dao, historia_clinica, id_mascota
):
    with pytest.raises(sqlite3.IntegrityError):
        historia_clinica_dao.crear(historia_clinica, id_mascota)


def test_segunda_historia_para_misma_mascota_propaga_error(
    cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    segunda = HistoriaClinica(61, date(2026, 3, 4))
    with pytest.raises(sqlite3.IntegrityError):
        historia_clinica_dao.crear(segunda, mascota.id_mascota)


def test_fecha_apertura_null_propaga_error(
    cliente_dao, mascota_dao, historia_clinica_dao, cliente, mascota
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    with pytest.raises(sqlite3.IntegrityError):
        historia_clinica_dao.crear(
            HistoriaClinica(60, None), mascota.id_mascota
        )


def test_observaciones_none_conserva_null(
    conexion, cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia = HistoriaClinica(60, date(2026, 1, 2), None)
    historia_clinica_dao.crear(historia, mascota.id_mascota)
    assert historia_clinica_dao.obtener_por_id(60).observaciones is None
    assert conexion.execute("""
        SELECT observaciones FROM historia_clinica WHERE id_historia = ?
    """, (60,)).fetchone()[0] is None


def test_recuperar_no_carga_atenciones_ni_agrega_mascota(
    cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    recuperada = historia_clinica_dao.obtener_por_id(60)
    assert recuperada.obtener_atenciones() == []
    assert not hasattr(recuperada, "mascota")


def test_eliminar_con_atenciones_propaga_error(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    atencion = Atencion(
        70, datetime(2026, 3, 4, 10), TipoAtencion.CONSULTA,
        "Control", veterinario
    )
    atencion_dao.crear(atencion, historia_clinica.id_historia)

    with pytest.raises(sqlite3.IntegrityError):
        historia_clinica_dao.eliminar(historia_clinica.id_historia)


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, cliente_dao, mascota_dao, historia_clinica_dao,
    cliente, mascota, historia_clinica
):
    _persistir_mascota(cliente_dao, mascota_dao, cliente, mascota)
    conexion.commit()
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    conexion.rollback()
    assert historia_clinica_dao.obtener_por_id(60) is None

    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    conexion.commit()
    actualizada = HistoriaClinica(60, date(2026, 5, 6), "Actualizada")
    historia_clinica_dao.actualizar(actualizada)
    conexion.rollback()
    assert historia_clinica_dao.obtener_por_id(60).fecha_apertura == date(
        2026, 1, 2
    )

    historia_clinica_dao.eliminar(60)
    conexion.rollback()
    assert historia_clinica_dao.obtener_por_id(60) is not None
