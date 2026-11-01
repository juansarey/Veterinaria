from datetime import datetime
import sqlite3

import pytest

from veterinaria.dominio.transporte.precinto_sanitario import (
    EstadoPrecinto,
    PrecintoSanitario,
)
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico


def _crear_remito(
    clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
    clinica, conservadora_isotermica, id_remito=130,
):
    if clinica_dao.obtener_por_id(clinica.id_clinica) is None:
        clinica_dao.crear(clinica)
    if conservadora_isotermica_dao.obtener_por_id(
        conservadora_isotermica.id_conservadora
    ) is None:
        conservadora_isotermica_dao.crear(conservadora_isotermica)
    remito = RemitoBiologico(
        id_remito, clinica, conservadora_isotermica,
        datetime(2026, 11, 3, 12, 30, 45, 123456),
    )
    remito_biologico_dao.crear(remito)
    return remito


def test_crear_y_obtener_por_id_y_remito_conserva_datos(
    conexion, clinica_dao, conservadora_isotermica_dao,
    remito_biologico_dao, precinto_sanitario_dao, clinica,
    conservadora_isotermica, precinto_sanitario,
):
    remito = _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    assert remito.asignar_precinto(precinto_sanitario)
    precinto_sanitario_dao.crear(precinto_sanitario, remito.id_remito)
    por_id = precinto_sanitario_dao.obtener_por_id(140)
    por_remito = precinto_sanitario_dao.obtener_por_remito(130)
    assert por_id.id_precinto == por_remito.id_precinto == 140
    assert por_id.codigo == por_remito.codigo == "PREC-140"
    assert por_id.estado is por_remito.estado is EstadoPrecinto.INTACTO
    assert conexion.execute("""
        SELECT id_remito FROM precinto_sanitario WHERE id_precinto = 140
    """).fetchone()[0] == 130
    assert not hasattr(por_id, "remito")


def test_obtener_inexistentes_devuelve_none(precinto_sanitario_dao):
    assert precinto_sanitario_dao.obtener_por_id(999) is None
    assert precinto_sanitario_dao.obtener_por_remito(999) is None


@pytest.mark.parametrize("estado", list(EstadoPrecinto))
def test_reconstruye_estado_sin_marcar_roto(
    estado, monkeypatch, clinica_dao, conservadora_isotermica_dao,
    remito_biologico_dao, precinto_sanitario_dao, clinica,
    conservadora_isotermica,
):
    remito = _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    precinto = PrecintoSanitario(140, "PREC-140")
    if estado is EstadoPrecinto.ROTO:
        assert precinto.marcar_roto()
    precinto_sanitario_dao.crear(precinto, remito.id_remito)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe romper el precinto")

    monkeypatch.setattr(PrecintoSanitario, "marcar_roto", operacion_prohibida)
    assert precinto_sanitario_dao.obtener_por_id(140).estado is estado


def test_id_none_es_rechazado(precinto_sanitario_dao):
    with pytest.raises(ValueError, match="id_precinto"):
        precinto_sanitario_dao.crear(PrecintoSanitario(None, "PREC-X"), 130)


def test_remito_inexistente_propaga_integrity_error(
    precinto_sanitario_dao, precinto_sanitario,
):
    with pytest.raises(sqlite3.IntegrityError):
        precinto_sanitario_dao.crear(precinto_sanitario, 999)


def test_codigo_unico_y_un_precinto_por_remito(
    clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
    precinto_sanitario_dao, clinica, conservadora_isotermica,
):
    remito = _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    precinto_sanitario_dao.crear(PrecintoSanitario(140, "PREC-140"), 130)
    with pytest.raises(sqlite3.IntegrityError):
        precinto_sanitario_dao.crear(PrecintoSanitario(141, "PREC-141"), 130)

    otra_conservadora = type(conservadora_isotermica)(121, "CONS-121")
    conservadora_isotermica_dao.crear(otra_conservadora)
    _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, otra_conservadora, 131,
    )
    with pytest.raises(sqlite3.IntegrityError):
        precinto_sanitario_dao.crear(PrecintoSanitario(142, "PREC-140"), 131)
    assert remito.id_remito == 130


def test_codigo_null_propaga_integrity_error(
    clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
    precinto_sanitario_dao, clinica, conservadora_isotermica,
):
    _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    with pytest.raises(sqlite3.IntegrityError):
        precinto_sanitario_dao.crear(PrecintoSanitario(140, None), 130)


def test_actualizar_codigo_y_estado_sin_cambiar_remito(
    conexion, clinica_dao, conservadora_isotermica_dao,
    remito_biologico_dao, precinto_sanitario_dao, clinica,
    conservadora_isotermica,
):
    _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    precinto = PrecintoSanitario(140, "PREC-140")
    precinto_sanitario_dao.crear(precinto, 130)
    precinto.codigo = "PREC-ACTUALIZADO"
    assert precinto.marcar_roto()
    assert precinto_sanitario_dao.actualizar(precinto) is True
    fila = conexion.execute("""
        SELECT id_remito, codigo, estado FROM precinto_sanitario
        WHERE id_precinto = 140
    """).fetchone()
    assert tuple(fila) == (130, "PREC-ACTUALIZADO", "ROTO")


def test_actualizar_inexistente_devuelve_false(
    precinto_sanitario_dao, precinto_sanitario,
):
    assert precinto_sanitario_dao.actualizar(precinto_sanitario) is False


def test_estado_fuera_del_enum_es_rechazado_por_check(
    conexion, clinica_dao, conservadora_isotermica_dao,
    remito_biologico_dao, precinto_sanitario_dao, clinica,
    conservadora_isotermica, precinto_sanitario,
):
    _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    precinto_sanitario_dao.crear(precinto_sanitario, 130)
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            UPDATE precinto_sanitario SET estado = 'INVALIDO'
            WHERE id_precinto = 140
        """)


def test_no_existe_eliminar_publico(precinto_sanitario_dao):
    assert not hasattr(precinto_sanitario_dao, "eliminar")


def test_crear_y_actualizar_no_hacen_commit(
    conexion, clinica_dao, conservadora_isotermica_dao,
    remito_biologico_dao, precinto_sanitario_dao, clinica,
    conservadora_isotermica, precinto_sanitario,
):
    remito = _crear_remito(
        clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
        clinica, conservadora_isotermica,
    )
    conexion.commit()
    precinto_sanitario_dao.crear(precinto_sanitario, remito.id_remito)
    conexion.rollback()
    assert precinto_sanitario_dao.obtener_por_id(140) is None

    precinto_sanitario_dao.crear(precinto_sanitario, remito.id_remito)
    conexion.commit()
    precinto_sanitario.codigo = "CAMBIO"
    precinto_sanitario_dao.actualizar(precinto_sanitario)
    conexion.rollback()
    assert precinto_sanitario_dao.obtener_por_id(140).codigo == "PREC-140"
