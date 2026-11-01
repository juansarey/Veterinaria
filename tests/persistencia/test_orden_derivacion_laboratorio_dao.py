from datetime import datetime
import sqlite3

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    EstadoOrden,
    OrdenDerivacionLaboratorio,
)


def _persistir_atencion(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion,
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    atencion_dao.crear(atencion, historia_clinica.id_historia)


def _persistir_dependencias(request):
    _persistir_atencion(*[
        request.getfixturevalue(nombre)
        for nombre in (
            "cliente_dao", "mascota_dao", "clinica_dao",
            "veterinario_dao", "historia_clinica_dao", "atencion_dao",
            "cliente", "mascota", "clinica", "veterinario",
            "historia_clinica", "atencion",
        )
    ])


def test_crear_y_recuperar_conserva_datos_estado_fecha_y_microsegundos(
    request, conexion, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )

    recuperada = orden_derivacion_laboratorio_dao.obtener_por_id(100)
    assert isinstance(recuperada, OrdenDerivacionLaboratorio)
    assert recuperada is not orden_derivacion_laboratorio
    assert recuperada.id_orden == 100
    assert recuperada.fecha_emision == orden_derivacion_laboratorio.fecha_emision
    assert recuperada.estudio_solicitado == "Hemograma completo"
    assert recuperada.estado is EstadoOrden.PENDIENTE
    assert recuperada.observaciones == "Procesar con prioridad"
    fila = conexion.execute("""
        SELECT id_atencion, fecha_emision, estado
        FROM orden_derivacion_laboratorio WHERE id_orden = 100
    """).fetchone()
    assert fila["id_atencion"] == atencion.id_atencion
    assert fila["fecha_emision"] == "2026-11-03T11:22:33.456789"
    assert fila["estado"] == "PENDIENTE"


def test_obtener_inexistente_y_listar_sin_resultados(
    orden_derivacion_laboratorio_dao,
):
    assert orden_derivacion_laboratorio_dao.obtener_por_id(999) is None
    assert orden_derivacion_laboratorio_dao.listar_por_atencion(999) == []


def test_listar_por_atencion_filtra_y_ordena_por_id(
    request, orden_derivacion_laboratorio_dao, atencion,
):
    _persistir_dependencias(request)
    for id_orden in (130, 100, 120):
        orden_derivacion_laboratorio_dao.crear(
            OrdenDerivacionLaboratorio(
                id_orden, datetime(2026, 11, 3, 12), f"Estudio {id_orden}"
            ),
            atencion.id_atencion,
        )
    assert [
        orden.id_orden
        for orden in orden_derivacion_laboratorio_dao.listar_por_atencion(
            atencion.id_atencion
        )
    ] == [100, 120, 130]


@pytest.mark.parametrize("estado", list(EstadoOrden))
def test_reconstruye_todos_los_estados_sin_transiciones_y_sin_muestras(
    estado, monkeypatch, request, conexion,
    orden_derivacion_laboratorio_dao, orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    conexion.execute("""
        UPDATE orden_derivacion_laboratorio SET estado = ? WHERE id_orden = 100
    """, (estado.name,))

    def transicion_prohibida(*args, **kwargs):
        raise AssertionError("La reconstrucción no debe ejecutar transiciones")

    monkeypatch.setattr(
        OrdenDerivacionLaboratorio, "iniciar_proceso", transicion_prohibida
    )
    monkeypatch.setattr(
        OrdenDerivacionLaboratorio, "completar", transicion_prohibida
    )
    monkeypatch.setattr(
        OrdenDerivacionLaboratorio, "cancelar", transicion_prohibida
    )
    recuperada = orden_derivacion_laboratorio_dao.obtener_por_id(100)
    assert recuperada.estado is estado
    assert recuperada.obtener_muestras() == []


def test_atencion_inexistente_propaga_integrity_error(
    orden_derivacion_laboratorio_dao, orden_derivacion_laboratorio,
):
    with pytest.raises(sqlite3.IntegrityError):
        orden_derivacion_laboratorio_dao.crear(
            orden_derivacion_laboratorio, 999
        )


def test_id_none_es_rechazado(orden_derivacion_laboratorio_dao):
    orden = OrdenDerivacionLaboratorio(
        None, datetime(2026, 11, 3), "Hemograma"
    )
    with pytest.raises(ValueError, match="id_orden"):
        orden_derivacion_laboratorio_dao.crear(orden, 70)


def test_pk_duplicada_propaga_integrity_error(
    request, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    with pytest.raises(sqlite3.IntegrityError):
        orden_derivacion_laboratorio_dao.crear(
            orden_derivacion_laboratorio, atencion.id_atencion
        )


@pytest.mark.parametrize("campo", ["fecha_emision", "estudio_solicitado"])
def test_campos_obligatorios_rechazan_null(
    campo, request, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    setattr(orden_derivacion_laboratorio, campo, None)
    with pytest.raises(sqlite3.IntegrityError):
        orden_derivacion_laboratorio_dao.crear(
            orden_derivacion_laboratorio, atencion.id_atencion
        )


def test_actualizar_campos_autorizados_sin_cambiar_atencion(
    request, conexion, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    orden_derivacion_laboratorio.fecha_emision = datetime(
        2026, 12, 4, 15, 16, 17, 222333
    )
    orden_derivacion_laboratorio.estudio_solicitado = "Cultivo"
    orden_derivacion_laboratorio.observaciones = None
    muestra = MuestraBiologica(999, "Sangre", datetime(2026, 11, 3, 12))
    assert orden_derivacion_laboratorio.agregar_muestra(muestra)
    assert orden_derivacion_laboratorio.iniciar_proceso()

    assert orden_derivacion_laboratorio_dao.actualizar(
        orden_derivacion_laboratorio
    ) is True
    fila = conexion.execute("""
        SELECT * FROM orden_derivacion_laboratorio WHERE id_orden = 100
    """).fetchone()
    assert fila["id_atencion"] == atencion.id_atencion
    assert fila["fecha_emision"] == "2026-12-04T15:16:17.222333"
    assert fila["estudio_solicitado"] == "Cultivo"
    assert fila["estado"] == "EN_PROCESO"
    assert fila["observaciones"] is None


def test_actualizar_inexistente_devuelve_false(
    orden_derivacion_laboratorio_dao, orden_derivacion_laboratorio,
):
    assert orden_derivacion_laboratorio_dao.actualizar(
        orden_derivacion_laboratorio
    ) is False


def test_eliminar_y_eliminar_inexistente(
    request, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    assert orden_derivacion_laboratorio_dao.eliminar(100) is True
    assert orden_derivacion_laboratorio_dao.eliminar(100) is False


def test_eliminar_orden_con_muestra_es_bloqueado(
    request, orden_derivacion_laboratorio_dao, muestra_biologica_dao,
    orden_derivacion_laboratorio, muestra_biologica, atencion,
):
    _persistir_dependencias(request)
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    muestra_biologica_dao.crear(muestra_biologica, 100)
    with pytest.raises(sqlite3.IntegrityError):
        orden_derivacion_laboratorio_dao.eliminar(100)


def test_crear_actualizar_y_eliminar_no_hacen_commit(
    request, conexion, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, atencion,
):
    _persistir_dependencias(request)
    conexion.commit()
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    conexion.rollback()
    assert orden_derivacion_laboratorio_dao.obtener_por_id(100) is None

    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion.id_atencion
    )
    conexion.commit()
    orden_derivacion_laboratorio.estudio_solicitado = "Cultivo"
    orden_derivacion_laboratorio_dao.actualizar(
        orden_derivacion_laboratorio
    )
    conexion.rollback()
    assert orden_derivacion_laboratorio_dao.obtener_por_id(
        100
    ).estudio_solicitado == "Hemograma completo"

    orden_derivacion_laboratorio_dao.eliminar(100)
    conexion.rollback()
    assert orden_derivacion_laboratorio_dao.obtener_por_id(100) is not None
