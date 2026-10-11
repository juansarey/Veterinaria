from datetime import datetime

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    EstadoOrden,
    OrdenDerivacionLaboratorio,
)


@pytest.fixture
def orden():
    return OrdenDerivacionLaboratorio(
        1,
        datetime(2026, 10, 12, 10),
        "Hemograma",
    )


@pytest.fixture
def muestra():
    return MuestraBiologica(1, "Sangre", datetime(2026, 10, 12, 10, 30))


def test_estado_inicial_pendiente(orden):
    assert orden.estado == EstadoOrden.PENDIENTE


def test_muestras_inicialmente_vacias(orden):
    assert orden.obtener_muestras() == []


def test_agrega_muestra(orden, muestra):
    assert orden.agregar_muestra(muestra) is True
    assert orden.obtener_muestras() == [muestra]


def test_no_agrega_dos_veces_la_misma_muestra(orden, muestra):
    orden.agregar_muestra(muestra)

    assert orden.agregar_muestra(muestra) is False
    assert orden.obtener_muestras() == [muestra]


def test_muestras_devueltas_son_una_copia(orden, muestra):
    orden.agregar_muestra(muestra)
    orden.obtener_muestras().clear()

    assert orden.obtener_muestras() == [muestra]


def test_no_inicia_proceso_sin_muestras(orden):
    assert orden.iniciar_proceso() is False
    assert orden.estado == EstadoOrden.PENDIENTE


def test_inicia_proceso_con_una_muestra(orden, muestra):
    orden.agregar_muestra(muestra)

    assert orden.iniciar_proceso() is True
    assert orden.estado == EstadoOrden.EN_PROCESO
    assert orden.iniciar_proceso() is False


def test_no_completa_desde_pendiente(orden):
    assert orden.completar() is False
    assert orden.estado == EstadoOrden.PENDIENTE


def test_completa_desde_en_proceso(orden, muestra):
    orden.agregar_muestra(muestra)
    orden.iniciar_proceso()

    assert orden.completar() is True
    assert orden.estado == EstadoOrden.COMPLETADA
    assert orden.completar() is False


def test_completa_sin_inspeccionar_estado_de_la_muestra(orden, muestra):
    orden.agregar_muestra(muestra)
    orden.iniciar_proceso()

    assert muestra.estado.obtener_nombre() == "EXTRAIDA"
    assert orden.completar() is True


def test_muestra_rechazada_no_impide_completar_orden(orden, muestra):
    muestra.empaquetar(datetime(2026, 10, 12, 11))
    muestra.despachar(datetime(2026, 10, 12, 12))
    muestra.rechazar(datetime(2026, 10, 12, 13))
    orden.agregar_muestra(muestra)
    orden.iniciar_proceso()

    assert orden.completar() is True
    assert orden.estado == EstadoOrden.COMPLETADA


def test_cancela_desde_pendiente(orden):
    assert orden.cancelar() is True
    assert orden.estado == EstadoOrden.CANCELADA


def test_cancela_desde_en_proceso(orden, muestra):
    orden.agregar_muestra(muestra)
    orden.iniciar_proceso()

    assert orden.cancelar() is True
    assert orden.estado == EstadoOrden.CANCELADA


def test_no_cancela_orden_completada(orden, muestra):
    orden.agregar_muestra(muestra)
    orden.iniciar_proceso()
    orden.completar()

    assert orden.cancelar() is False
    assert orden.estado == EstadoOrden.COMPLETADA


def test_no_cancela_orden_cancelada(orden):
    orden.cancelar()

    assert orden.cancelar() is False
    assert orden.estado == EstadoOrden.CANCELADA


@pytest.mark.parametrize("estado_final", ["COMPLETADA", "CANCELADA"])
def test_no_agrega_muestras_a_orden_finalizada(orden, muestra, estado_final):
    orden.agregar_muestra(muestra)

    if estado_final == "COMPLETADA":
        orden.iniciar_proceso()
        orden.completar()
    else:
        orden.cancelar()

    nueva = MuestraBiologica(2, "Orina", datetime(2026, 10, 12, 11))
    assert orden.agregar_muestra(nueva) is False
    assert orden.obtener_muestras() == [muestra]


def test_estado_no_admite_asignacion_directa(orden):
    with pytest.raises(AttributeError):
        orden.estado = EstadoOrden.COMPLETADA

    assert orden.estado == EstadoOrden.PENDIENTE
