from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.conservadora_isotermica import ConservadoraIsotermica
from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito, RemitoBiologico


@pytest.fixture
def fecha():
    return datetime(2026, 10, 12, 10)


@pytest.fixture
def remito(fecha):
    return RemitoBiologico(
        1, Clinica(1, "Centro", "San Martín 100"),
        ConservadoraIsotermica(1, "CONS-001"), fecha,
    )


@pytest.fixture
def envio(remito, fecha):
    for id_muestra in (1, 2):
        remito.agregar_muestra(
            MuestraBiologica(id_muestra, "Sangre", fecha), fecha
        )
    remito.asignar_precinto(PrecintoSanitario(1, "PREC-001"))
    return Envio(1, remito, "Traslado al laboratorio")


def test_envio_nace_pendiente_y_conserva_datos(remito):
    envio = Envio(1, remito)

    assert envio.id_envio == 1
    assert envio.remito is remito
    assert envio.observaciones == ""
    assert envio.estado == EstadoEnvio.PENDIENTE
    assert envio.fecha_hora_salida is None
    assert envio.fecha_hora_llegada is None


def test_remito_obligatorio():
    with pytest.raises(ValueError, match="remito"):
        Envio(1, None)


def test_iniciar_sin_preparacion_no_modifica_envio(remito, fecha):
    envio = Envio(1, remito)

    assert envio.iniciar(fecha) is False
    assert envio.estado == EstadoEnvio.PENDIENTE
    assert envio.fecha_hora_salida is None
    assert envio.fecha_hora_llegada is None
    assert remito.estado == EstadoRemito.GENERADO


def test_iniciar_despacha_remito_y_muestras(envio, fecha):
    salida = fecha + timedelta(hours=1)
    muestras = envio.remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]

    assert envio.iniciar(salida) is True
    assert envio.estado == EstadoEnvio.EN_TRANSITO
    assert envio.fecha_hora_salida == salida
    assert envio.fecha_hora_llegada is None
    assert envio.remito.estado == EstadoRemito.DESPACHADO
    for muestra, anterior in zip(muestras, historiales):
        assert muestra.estado.obtener_nombre() == "EN_TRANSITO"
        historial = muestra.obtener_historial()
        assert historial[:-1] == anterior
        assert historial[-1].fecha_hora == salida
        assert historial[-1].observaciones == envio.observaciones


def test_fecha_invalida_de_despacho_no_modifica_envio_ni_muestras(envio, fecha):
    muestras = envio.remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]

    assert envio.iniciar(fecha - timedelta(seconds=1)) is False
    assert envio.estado == EstadoEnvio.PENDIENTE
    assert envio.fecha_hora_salida is None
    assert envio.remito.estado == EstadoRemito.GENERADO
    assert [m.obtener_historial() for m in muestras] == historiales
    assert all(m.estado.obtener_nombre() == "EMPAQUETADA" for m in muestras)


@pytest.mark.parametrize("entregado", [False, True])
def test_no_inicia_dos_veces(envio, fecha, entregado):
    envio.iniciar(fecha)
    if entregado:
        envio.registrar_llegada(fecha)
    estado = envio.estado
    historiales = [m.obtener_historial() for m in envio.remito.obtener_muestras()]

    assert envio.iniciar(fecha + timedelta(hours=1)) is False
    assert envio.estado == estado
    assert envio.fecha_hora_salida == fecha
    assert [m.obtener_historial() for m in envio.remito.obtener_muestras()] == historiales


def test_no_registra_llegada_si_esta_pendiente(envio, fecha):
    assert envio.registrar_llegada(fecha) is False
    assert envio.estado == EstadoEnvio.PENDIENTE
    assert envio.fecha_hora_llegada is None


def test_llegada_anterior_a_salida_no_modifica_envio(envio, fecha):
    envio.iniciar(fecha)

    assert envio.registrar_llegada(fecha - timedelta(seconds=1)) is False
    assert envio.estado == EstadoEnvio.EN_TRANSITO
    assert envio.fecha_hora_salida == fecha
    assert envio.fecha_hora_llegada is None


@pytest.mark.parametrize("horas", [0, 1])
def test_llegada_igual_o_posterior_no_procesa_muestras(envio, fecha, horas):
    envio.iniciar(fecha)
    llegada = fecha + timedelta(hours=horas)
    muestras = envio.remito.obtener_muestras()
    historiales = [m.obtener_historial() for m in muestras]

    assert envio.registrar_llegada(llegada) is True
    assert envio.estado == EstadoEnvio.ENTREGADO
    assert envio.fecha_hora_llegada == llegada
    assert envio.remito.estado == EstadoRemito.DESPACHADO
    assert all(m.estado.obtener_nombre() == "EN_TRANSITO" for m in muestras)
    assert [m.obtener_historial() for m in muestras] == historiales


def test_no_registra_llegada_dos_veces(envio, fecha):
    envio.iniciar(fecha)
    envio.registrar_llegada(fecha)

    assert envio.registrar_llegada(fecha + timedelta(hours=1)) is False
    assert envio.estado == EstadoEnvio.ENTREGADO
    assert envio.fecha_hora_llegada == fecha
