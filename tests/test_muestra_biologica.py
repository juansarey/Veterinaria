from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica


@pytest.fixture
def fecha_extraccion():
    return datetime(2026, 10, 12, 9)


@pytest.fixture
def muestra(fecha_extraccion):
    return MuestraBiologica(1, "Sangre", fecha_extraccion)


def avanzar_hasta_en_transito(muestra, fecha_extraccion):
    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))
    muestra.despachar(fecha_extraccion + timedelta(hours=2))


def avanzar_hasta_analizada(muestra, fecha_extraccion):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)
    muestra.recibir(fecha_extraccion + timedelta(hours=3))
    muestra.analizar(fecha_extraccion + timedelta(hours=4))


def test_estado_inicial_extraida(muestra):
    assert muestra.estado.obtener_nombre() == "EXTRAIDA"


def test_empaqueta_muestra_extraida(muestra, fecha_extraccion):
    assert muestra.empaquetar(fecha_extraccion + timedelta(hours=1)) is True
    assert muestra.estado.obtener_nombre() == "EMPAQUETADA"


def test_despacha_muestra_empaquetada(muestra, fecha_extraccion):
    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))

    assert muestra.despachar(fecha_extraccion + timedelta(hours=2)) is True
    assert muestra.estado.obtener_nombre() == "EN_TRANSITO"


def test_recibe_muestra_en_transito(muestra, fecha_extraccion):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)

    assert muestra.recibir(fecha_extraccion + timedelta(hours=3)) is True
    assert muestra.estado.obtener_nombre() == "RECIBIDA"


def test_analiza_muestra_recibida(muestra, fecha_extraccion):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)
    muestra.recibir(fecha_extraccion + timedelta(hours=3))

    assert muestra.analizar(fecha_extraccion + timedelta(hours=4)) is True
    assert muestra.estado.obtener_nombre() == "ANALIZADA"


def test_rechaza_muestra_en_transito(muestra, fecha_extraccion):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)

    assert muestra.rechazar(fecha_extraccion + timedelta(hours=3)) is True
    assert muestra.estado.obtener_nombre() == "RECHAZADA"


@pytest.mark.parametrize("estado", ["EXTRAIDA", "EMPAQUETADA", "RECIBIDA"])
def test_no_rechaza_desde_otros_estados(muestra, fecha_extraccion, estado):
    fecha = fecha_extraccion + timedelta(hours=1)

    if estado == "EMPAQUETADA":
        muestra.empaquetar(fecha)
        fecha += timedelta(hours=1)
    elif estado == "RECIBIDA":
        avanzar_hasta_en_transito(muestra, fecha_extraccion)
        muestra.recibir(fecha_extraccion + timedelta(hours=3))
        fecha = fecha_extraccion + timedelta(hours=4)

    assert muestra.estado.obtener_nombre() == estado
    assert muestra.rechazar(fecha) is False
    assert muestra.estado.obtener_nombre() == estado


def test_operacion_invalida_no_cambia_estado(muestra, fecha_extraccion):
    assert muestra.despachar(fecha_extraccion + timedelta(hours=1)) is False
    assert muestra.estado.obtener_nombre() == "EXTRAIDA"


@pytest.mark.parametrize(
    "operacion", ["empaquetar", "despachar", "recibir", "rechazar", "analizar"]
)
def test_analizada_es_estado_final(
    muestra, fecha_extraccion, operacion
):
    avanzar_hasta_analizada(muestra, fecha_extraccion)
    estado_anterior = muestra.estado

    resultado = getattr(muestra, operacion)(
        fecha_extraccion + timedelta(hours=5)
    )

    assert resultado is False
    assert muestra.estado is estado_anterior


@pytest.mark.parametrize(
    "operacion", ["empaquetar", "despachar", "recibir", "rechazar", "analizar"]
)
def test_rechazada_es_estado_final(
    muestra, fecha_extraccion, operacion
):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)
    muestra.rechazar(fecha_extraccion + timedelta(hours=3))
    estado_anterior = muestra.estado

    resultado = getattr(muestra, operacion)(
        fecha_extraccion + timedelta(hours=4)
    )

    assert resultado is False
    assert muestra.estado is estado_anterior


def test_estado_no_admite_asignacion_directa(muestra):
    estado_inicial = muestra.estado

    with pytest.raises(AttributeError):
        muestra.estado = object()

    assert muestra.estado is estado_inicial
