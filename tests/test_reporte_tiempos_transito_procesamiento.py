from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.dominio.transporte.conservadora_isotermica import ConservadoraIsotermica
from veterinaria.dominio.transporte.envio import Envio
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico
from veterinaria.patrones.strategy.reporte_tiempos_transito_procesamiento import (
    ReporteTiemposTransitoProcesamiento,
)


FECHA = datetime(2026, 10, 12, 10)


def crear_envio(id_envio=1, cantidad=1):
    remito = RemitoBiologico(
        id_envio, Clinica(id_envio, "Centro", "San Martín 100"),
        ConservadoraIsotermica(id_envio, f"CONS-{id_envio}"), FECHA,
    )
    for i in range(cantidad):
        muestra = MuestraBiologica(id_envio * 10 + i, "Sangre", FECHA)
        assert remito.agregar_muestra(muestra, FECHA)
    assert remito.asignar_precinto(PrecintoSanitario(id_envio, f"PREC-{id_envio}"))
    return Envio(id_envio, remito)


def completar_transito(envio, duracion):
    assert envio.iniciar(FECHA)
    assert envio.registrar_llegada(FECHA + duracion)


def recibir(envio):
    fecha_recepcion = envio.fecha_hora_llegada + timedelta(minutes=15)
    assert Recepcion(envio.id_envio, envio, fecha_recepcion).procesar_recepcion()
    return fecha_recepcion


def analizar(muestra, fecha):
    assert ResultadoAnalisis(muestra.id_muestra, muestra, fecha, "Normal").registrar_resultado()


def test_lista_vacia_devuelve_resumen():
    assert ReporteTiemposTransitoProcesamiento([]).generar() == [{
        "cantidad_envios_con_transito": 0,
        "tiempo_promedio_transito": None,
        "cantidad_muestras_procesadas": 0,
        "tiempo_promedio_procesamiento": None,
    }]


@pytest.mark.parametrize("iniciado", [False, True])
def test_envio_incompleto_no_participa(iniciado):
    envio = crear_envio()
    if iniciado:
        assert envio.iniciar(FECHA)

    assert ReporteTiemposTransitoProcesamiento([envio]).generar() == [{
        "cantidad_envios_con_transito": 0,
        "tiempo_promedio_transito": None,
        "cantidad_muestras_procesadas": 0,
        "tiempo_promedio_procesamiento": None,
    }]


def test_un_envio_completo_sin_recepcion():
    envio = crear_envio()
    completar_transito(envio, timedelta(hours=2))

    assert ReporteTiemposTransitoProcesamiento([envio]).generar() == [{
        "cantidad_envios_con_transito": 1,
        "tiempo_promedio_transito": timedelta(hours=2),
        "cantidad_muestras_procesadas": 0,
        "tiempo_promedio_procesamiento": None,
    }]


def test_promedio_transito_cuenta_envios_no_muestras():
    primero = crear_envio(cantidad=3)
    segundo = crear_envio(2)
    pendiente = crear_envio(3)
    completar_transito(primero, timedelta(hours=1))
    completar_transito(segundo, timedelta(hours=4))

    fila = ReporteTiemposTransitoProcesamiento([primero, segundo, pendiente]).generar()[0]

    assert fila["cantidad_envios_con_transito"] == 2
    assert fila["tiempo_promedio_transito"] == timedelta(hours=2, minutes=30)


@pytest.mark.parametrize("rechazada", [False, True])
def test_recibida_sin_analisis_y_rechazada_no_participan(rechazada):
    envio = crear_envio()
    completar_transito(envio, timedelta(hours=1))
    if rechazada:
        assert envio.remito.obtener_precinto().marcar_roto()
    recibir(envio)

    fila = ReporteTiemposTransitoProcesamiento([envio]).generar()[0]

    assert fila["cantidad_envios_con_transito"] == 1
    assert fila["cantidad_muestras_procesadas"] == 0
    assert fila["tiempo_promedio_procesamiento"] is None


def test_una_muestra_analizada_usa_recepcion_y_no_llegada():
    envio = crear_envio()
    completar_transito(envio, timedelta(hours=1))
    fecha_recepcion = recibir(envio)
    analizar(envio.remito.obtener_muestras()[0], fecha_recepcion + timedelta(hours=3))

    fila = ReporteTiemposTransitoProcesamiento([envio]).generar()[0]

    assert fila["cantidad_muestras_procesadas"] == 1
    assert fila["tiempo_promedio_procesamiento"] == timedelta(hours=3)


def test_promedio_procesamiento_de_varias_muestras_ignora_incompletas():
    primero = crear_envio(cantidad=3)
    segundo = crear_envio(2)
    rechazado = crear_envio(3)
    for envio in (primero, segundo, rechazado):
        completar_transito(envio, timedelta(hours=1))
    primera_fecha = recibir(primero)
    segunda_fecha = recibir(segundo)
    assert rechazado.remito.obtener_precinto().marcar_roto()
    recibir(rechazado)
    muestras = primero.remito.obtener_muestras()
    analizar(muestras[0], primera_fecha)
    analizar(muestras[1], primera_fecha + timedelta(hours=2))
    analizar(segundo.remito.obtener_muestras()[0], segunda_fecha + timedelta(hours=7))

    fila = ReporteTiemposTransitoProcesamiento([primero, segundo, rechazado]).generar()[0]

    assert fila["cantidad_muestras_procesadas"] == 3
    assert fila["tiempo_promedio_procesamiento"] == timedelta(hours=3)


def test_duraciones_cero_son_validas():
    envio = crear_envio()
    completar_transito(envio, timedelta())
    fecha_recepcion = recibir(envio)
    analizar(envio.remito.obtener_muestras()[0], fecha_recepcion)

    assert ReporteTiemposTransitoProcesamiento([envio]).generar() == [{
        "cantidad_envios_con_transito": 1,
        "tiempo_promedio_transito": timedelta(),
        "cantidad_muestras_procesadas": 1,
        "tiempo_promedio_procesamiento": timedelta(),
    }]


def test_no_cuenta_dos_veces_el_mismo_envio():
    primero = crear_envio()
    segundo = crear_envio(2)
    completar_transito(primero, timedelta(hours=1))
    completar_transito(segundo, timedelta(hours=3))
    for envio, horas in ((primero, 2), (segundo, 6)):
        fecha_recepcion = recibir(envio)
        analizar(envio.remito.obtener_muestras()[0], fecha_recepcion + timedelta(hours=horas))

    fila = ReporteTiemposTransitoProcesamiento([primero, primero, segundo]).generar()[0]

    assert fila["cantidad_envios_con_transito"] == 2
    assert fila["tiempo_promedio_transito"] == timedelta(hours=2)
    assert fila["cantidad_muestras_procesadas"] == 2
    assert fila["tiempo_promedio_procesamiento"] == timedelta(hours=4)


def test_muestra_compartida_por_referencia_se_cuenta_una_vez():
    envio = crear_envio()
    completar_transito(envio, timedelta(hours=1))
    fecha_recepcion = recibir(envio)
    analizar(envio.remito.obtener_muestras()[0], fecha_recepcion + timedelta(hours=2))
    otro_envio = Envio(2, envio.remito)

    fila = ReporteTiemposTransitoProcesamiento([envio, otro_envio]).generar()[0]

    assert fila["cantidad_envios_con_transito"] == 1
    assert fila["cantidad_muestras_procesadas"] == 1
    assert fila["tiempo_promedio_procesamiento"] == timedelta(hours=2)


def test_no_modifica_envio_remito_estados_ni_historiales():
    envio = crear_envio(cantidad=2)
    completar_transito(envio, timedelta(hours=1))
    fecha_recepcion = recibir(envio)
    muestras = envio.remito.obtener_muestras()
    analizar(muestras[0], fecha_recepcion + timedelta(hours=2))
    historiales = [muestra.obtener_historial() for muestra in muestras]
    estados = [muestra.estado for muestra in muestras]
    datos_envio = vars(envio).copy()
    estado_remito = envio.remito.estado
    precinto = envio.remito.obtener_precinto()
    estado_precinto = precinto.estado
    estado_conservadora = envio.remito.conservadora.estado
    envios = [envio]
    reporte = ReporteTiemposTransitoProcesamiento(envios)

    resultado = reporte.generar()
    assert reporte.generar() == resultado
    resultado.clear()

    assert len(reporte.generar()) == 1
    assert vars(envio) == datos_envio
    assert envio.remito.estado == estado_remito
    assert envio.remito.obtener_muestras() == muestras
    assert envio.remito.obtener_precinto() is precinto
    assert precinto.estado == estado_precinto
    assert envio.remito.conservadora.estado == estado_conservadora
    assert [muestra.estado for muestra in muestras] == estados
    assert [muestra.obtener_historial() for muestra in muestras] == historiales
    assert envios == [envio]
