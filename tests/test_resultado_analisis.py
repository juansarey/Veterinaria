from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis


@pytest.fixture
def fecha_extraccion():
    return datetime(2026, 10, 12, 9)


@pytest.fixture
def muestra(fecha_extraccion):
    return MuestraBiologica(1, "Sangre", fecha_extraccion)


def avanzar_hasta_en_transito(muestra, fecha_extraccion):
    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))
    muestra.despachar(fecha_extraccion + timedelta(hours=2))


def avanzar_hasta_recibida(muestra, fecha_extraccion):
    avanzar_hasta_en_transito(muestra, fecha_extraccion)
    muestra.recibir(fecha_extraccion + timedelta(hours=3))


def preparar_estado(muestra, fecha_extraccion, estado):
    if estado == "EXTRAIDA":
        return

    muestra.empaquetar(fecha_extraccion + timedelta(hours=1))
    if estado == "EMPAQUETADA":
        return

    muestra.despachar(fecha_extraccion + timedelta(hours=2))
    if estado == "EN_TRANSITO":
        return

    if estado == "RECHAZADA":
        muestra.rechazar(fecha_extraccion + timedelta(hours=3))
        return

    muestra.recibir(fecha_extraccion + timedelta(hours=3))
    muestra.analizar(fecha_extraccion + timedelta(hours=4))


def test_conserva_datos_del_resultado(muestra, fecha_extraccion):
    fecha_resultado = fecha_extraccion + timedelta(hours=4)
    resultado = ResultadoAnalisis(
        1,
        muestra,
        fecha_resultado,
        "Hemograma dentro de parámetros",
        "Validado por laboratorio",
    )

    assert resultado.id_resultado == 1
    assert resultado.muestra is muestra
    assert resultado.fecha_resultado == fecha_resultado
    assert resultado.resultado == "Hemograma dentro de parámetros"
    assert resultado.observaciones == "Validado por laboratorio"


def test_muestra_obligatoria(fecha_extraccion):
    with pytest.raises(ValueError, match="muestra"):
        ResultadoAnalisis(1, None, fecha_extraccion, "Resultado")


def test_fecha_resultado_obligatoria(muestra):
    with pytest.raises(ValueError, match="fecha"):
        ResultadoAnalisis(1, muestra, None, "Resultado")


def test_contenido_resultado_obligatorio(muestra, fecha_extraccion):
    with pytest.raises(ValueError, match="resultado"):
        ResultadoAnalisis(1, muestra, fecha_extraccion, None)


def test_permite_resultado_vacio(muestra, fecha_extraccion):
    resultado = ResultadoAnalisis(1, muestra, fecha_extraccion, "")

    assert resultado.resultado == ""


def test_registra_resultado_y_analiza_muestra_recibida(
    muestra, fecha_extraccion
):
    avanzar_hasta_recibida(muestra, fecha_extraccion)
    historial_anterior = muestra.obtener_historial()
    fecha_resultado = fecha_extraccion + timedelta(hours=4)
    resultado = ResultadoAnalisis(
        1,
        muestra,
        fecha_resultado,
        "Sin alteraciones",
        "Procesamiento finalizado",
    )

    assert resultado.registrar_resultado() is True
    assert muestra.estado.obtener_nombre() == "ANALIZADA"

    historial = muestra.obtener_historial()
    assert len(historial) == len(historial_anterior) + 1
    assert all(
        actual is anterior
        for actual, anterior in zip(historial[:-1], historial_anterior)
    )
    assert historial[-1].nombre_estado == "ANALIZADA"
    assert historial[-1].fecha_hora == fecha_resultado
    assert historial[-1].observaciones == "Procesamiento finalizado"


def test_fecha_igual_al_ultimo_historial_esta_permitida(
    muestra, fecha_extraccion
):
    avanzar_hasta_recibida(muestra, fecha_extraccion)
    fecha_recepcion = muestra.obtener_historial()[-1].fecha_hora
    resultado = ResultadoAnalisis(
        1, muestra, fecha_recepcion, "Sin alteraciones"
    )

    assert resultado.registrar_resultado() is True
    assert muestra.estado.obtener_nombre() == "ANALIZADA"
    assert muestra.obtener_historial()[-1].fecha_hora == fecha_recepcion


def test_fecha_anterior_no_modifica_estado_ni_historial(
    muestra, fecha_extraccion
):
    avanzar_hasta_recibida(muestra, fecha_extraccion)
    estado_anterior = muestra.estado
    historial_anterior = muestra.obtener_historial()
    resultado = ResultadoAnalisis(
        1,
        muestra,
        historial_anterior[-1].fecha_hora - timedelta(seconds=1),
        "Sin alteraciones",
    )

    assert resultado.registrar_resultado() is False
    assert muestra.estado is estado_anterior
    assert muestra.obtener_historial() == historial_anterior


@pytest.mark.parametrize(
    "estado", ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECHAZADA", "ANALIZADA"]
)
def test_no_registra_resultado_en_estado_invalido(
    muestra, fecha_extraccion, estado
):
    preparar_estado(muestra, fecha_extraccion, estado)
    estado_anterior = muestra.estado
    historial_anterior = muestra.obtener_historial()
    resultado = ResultadoAnalisis(
        1,
        muestra,
        fecha_extraccion + timedelta(hours=5),
        "Sin alteraciones",
    )

    assert muestra.estado.obtener_nombre() == estado
    assert resultado.registrar_resultado() is False
    assert muestra.estado is estado_anterior
    assert muestra.obtener_historial() == historial_anterior


def test_segunda_llamada_no_modifica_muestra(muestra, fecha_extraccion):
    avanzar_hasta_recibida(muestra, fecha_extraccion)
    resultado = ResultadoAnalisis(
        1,
        muestra,
        fecha_extraccion + timedelta(hours=4),
        "Sin alteraciones",
    )
    assert resultado.registrar_resultado() is True
    estado_anterior = muestra.estado
    historial_anterior = muestra.obtener_historial()

    assert resultado.registrar_resultado() is False
    assert muestra.estado is estado_anterior
    assert muestra.obtener_historial() == historial_anterior


def test_otro_resultado_no_reanaliza_muestra_analizada(
    muestra, fecha_extraccion
):
    avanzar_hasta_recibida(muestra, fecha_extraccion)
    primer_resultado = ResultadoAnalisis(
        1,
        muestra,
        fecha_extraccion + timedelta(hours=4),
        "Primer resultado",
    )
    segundo_resultado = ResultadoAnalisis(
        2,
        muestra,
        fecha_extraccion + timedelta(hours=5),
        "Segundo resultado",
    )
    assert primer_resultado.registrar_resultado() is True
    estado_anterior = muestra.estado
    historial_anterior = muestra.obtener_historial()

    assert segundo_resultado.registrar_resultado() is False
    assert muestra.estado is estado_anterior
    assert muestra.obtener_historial() == historial_anterior
