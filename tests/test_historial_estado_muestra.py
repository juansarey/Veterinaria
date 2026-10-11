from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica


@pytest.fixture
def fecha_extraccion():
    return datetime(2026, 10, 12, 9)


@pytest.fixture
def muestra(fecha_extraccion):
    return MuestraBiologica(1, "Sangre", fecha_extraccion)


def test_crea_registro_inicial_extraida(muestra, fecha_extraccion):
    historial = muestra.obtener_historial()

    assert len(historial) == 1
    assert historial[0].nombre_estado == "EXTRAIDA"
    assert historial[0].fecha_hora == fecha_extraccion


def test_transicion_valida_agrega_un_registro(muestra, fecha_extraccion):
    fecha = fecha_extraccion + timedelta(hours=1)

    muestra.empaquetar(fecha, "Muestra acondicionada")
    historial = muestra.obtener_historial()

    assert len(historial) == 2
    assert historial[-1].nombre_estado == "EMPAQUETADA"
    assert historial[-1].fecha_hora == fecha
    assert historial[-1].observaciones == "Muestra acondicionada"


def test_secuencia_completa_conserva_todos_los_estados(muestra, fecha_extraccion):
    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))
    muestra.despachar(fecha_extraccion + timedelta(hours=2))
    muestra.recibir(fecha_extraccion + timedelta(hours=3))
    muestra.analizar(fecha_extraccion + timedelta(hours=4))

    assert [
        registro.nombre_estado for registro in muestra.obtener_historial()
    ] == ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA"]


def test_transicion_invalida_no_agrega_registro(muestra, fecha_extraccion):
    assert muestra.analizar(fecha_extraccion + timedelta(hours=1)) is False
    assert len(muestra.obtener_historial()) == 1


def test_transicion_no_modifica_registros_anteriores(muestra, fecha_extraccion):
    registro_inicial = muestra.obtener_historial()[0]

    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))

    assert muestra.obtener_historial()[0] is registro_inicial
    assert registro_inicial.nombre_estado == "EXTRAIDA"
    assert registro_inicial.fecha_hora == fecha_extraccion


def test_registro_historico_es_inmutable(muestra):
    registro = muestra.obtener_historial()[0]

    with pytest.raises(FrozenInstanceError):
        registro.nombre_estado = "EMPAQUETADA"


def test_historial_devuelto_es_una_copia(muestra):
    muestra.obtener_historial().clear()
    assert len(muestra.obtener_historial()) == 1


def test_fecha_anterior_no_cambia_estado_ni_historial(muestra, fecha_extraccion):
    fecha_anterior = fecha_extraccion - timedelta(seconds=1)

    assert muestra.empaquetar(fecha_anterior) is False
    assert muestra.estado.obtener_nombre() == "EXTRAIDA"
    assert len(muestra.obtener_historial()) == 1


def test_fecha_igual_al_ultimo_registro_esta_permitida(muestra, fecha_extraccion):
    assert muestra.empaquetar(fecha_extraccion) is True
    assert muestra.estado.obtener_nombre() == "EMPAQUETADA"
    assert len(muestra.obtener_historial()) == 2
