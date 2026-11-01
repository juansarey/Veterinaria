from datetime import datetime
import sqlite3

import pytest

from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico


def test_crear_y_obtener_conserva_id_codigo_y_estado(
    conexion, conservadora_isotermica_dao, conservadora_isotermica,
):
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    recuperada = conservadora_isotermica_dao.obtener_por_id(120)
    assert isinstance(recuperada, ConservadoraIsotermica)
    assert recuperada is not conservadora_isotermica
    assert recuperada.id_conservadora == 120
    assert recuperada.codigo == "CONS-120"
    assert recuperada.estado is EstadoConservadora.DISPONIBLE
    assert tuple(conexion.execute("""
        SELECT codigo, estado FROM conservadora_isotermica
        WHERE id_conservadora = 120
    """).fetchone()) == ("CONS-120", "DISPONIBLE")


def test_obtener_inexistente_y_listar_vacio(conservadora_isotermica_dao):
    assert conservadora_isotermica_dao.obtener_por_id(999) is None
    assert conservadora_isotermica_dao.listar() == []


def test_listar_ordena_por_id_y_conserva_estados(conservadora_isotermica_dao):
    for id_conservadora in (130, 110, 120):
        conservadora = ConservadoraIsotermica(
            id_conservadora, f"CONS-{id_conservadora}"
        )
        if id_conservadora == 120:
            assert conservadora.marcar_en_uso()
        conservadora_isotermica_dao.crear(conservadora)
    recuperadas = conservadora_isotermica_dao.listar()
    assert [c.id_conservadora for c in recuperadas] == [110, 120, 130]
    assert [c.estado for c in recuperadas] == [
        EstadoConservadora.DISPONIBLE,
        EstadoConservadora.EN_USO,
        EstadoConservadora.DISPONIBLE,
    ]


@pytest.mark.parametrize("estado", list(EstadoConservadora))
def test_reconstruye_estado_sin_ejecutar_operaciones(
    estado, monkeypatch, conservadora_isotermica_dao,
):
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    if estado is EstadoConservadora.EN_USO:
        assert conservadora.marcar_en_uso()
    conservadora_isotermica_dao.crear(conservadora)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar transiciones")

    monkeypatch.setattr(
        ConservadoraIsotermica, "marcar_en_uso", operacion_prohibida
    )
    monkeypatch.setattr(ConservadoraIsotermica, "liberar", operacion_prohibida)
    recuperada = conservadora_isotermica_dao.obtener_por_id(120)
    assert recuperada.estado is estado


def test_id_none_es_rechazado(conservadora_isotermica_dao):
    with pytest.raises(ValueError, match="id_conservadora"):
        conservadora_isotermica_dao.crear(
            ConservadoraIsotermica(None, "CONS-X")
        )


def test_codigo_null_y_codigo_duplicado_propagan_integrity_error(
    conservadora_isotermica_dao,
):
    conservadora_isotermica_dao.crear(ConservadoraIsotermica(120, "CONS-120"))
    with pytest.raises(sqlite3.IntegrityError):
        conservadora_isotermica_dao.crear(ConservadoraIsotermica(121, None))
    with pytest.raises(sqlite3.IntegrityError):
        conservadora_isotermica_dao.crear(
            ConservadoraIsotermica(122, "CONS-120")
        )


def test_actualizar_codigo_y_estado(conservadora_isotermica_dao):
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    conservadora_isotermica_dao.crear(conservadora)
    conservadora.codigo = "CONS-ACTUALIZADA"
    assert conservadora.marcar_en_uso()
    assert conservadora_isotermica_dao.actualizar(conservadora) is True
    recuperada = conservadora_isotermica_dao.obtener_por_id(120)
    assert recuperada.codigo == "CONS-ACTUALIZADA"
    assert recuperada.estado is EstadoConservadora.EN_USO


def test_actualizar_inexistente_devuelve_false(
    conservadora_isotermica_dao, conservadora_isotermica,
):
    assert conservadora_isotermica_dao.actualizar(
        conservadora_isotermica
    ) is False


def test_estado_fuera_del_enum_es_rechazado_por_check(
    conexion, conservadora_isotermica_dao, conservadora_isotermica,
):
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            UPDATE conservadora_isotermica SET estado = 'INVALIDO'
            WHERE id_conservadora = 120
        """)


def test_eliminar_libre_y_eliminar_inexistente(
    conservadora_isotermica_dao, conservadora_isotermica,
):
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    assert conservadora_isotermica_dao.eliminar(120) is True
    assert conservadora_isotermica_dao.eliminar(120) is False


def test_eliminar_referenciada_por_remito_es_bloqueado(
    clinica_dao, conservadora_isotermica_dao, remito_biologico_dao,
    clinica, conservadora_isotermica,
):
    clinica_dao.crear(clinica)
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    remito = RemitoBiologico(
        130, clinica, conservadora_isotermica,
        datetime(2026, 11, 3, 12),
    )
    remito_biologico_dao.crear(remito)
    with pytest.raises(sqlite3.IntegrityError):
        conservadora_isotermica_dao.eliminar(120)


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    conexion, conservadora_isotermica_dao, conservadora_isotermica,
):
    conservadora_isotermica_dao.crear(conservadora_isotermica)
    conexion.rollback()
    assert conservadora_isotermica_dao.obtener_por_id(120) is None

    conservadora_isotermica_dao.crear(conservadora_isotermica)
    conexion.commit()
    conservadora_isotermica.codigo = "CAMBIO"
    conservadora_isotermica_dao.actualizar(conservadora_isotermica)
    conexion.rollback()
    assert conservadora_isotermica_dao.obtener_por_id(120).codigo == "CONS-120"

    conservadora_isotermica_dao.eliminar(120)
    conexion.rollback()
    assert conservadora_isotermica_dao.obtener_por_id(120) is not None
