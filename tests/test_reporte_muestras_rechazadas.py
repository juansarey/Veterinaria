from datetime import datetime, timedelta

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.conservadora_isotermica import ConservadoraIsotermica
from veterinaria.dominio.transporte.envio import Envio
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico
from veterinaria.patrones.strategy.reporte_muestras_rechazadas import (
    ReporteMuestrasRechazadas,
)


FECHA = datetime(2026, 10, 12, 10)


def crear_remito(id_remito=1, cantidad=1, con_precinto=True):
    remito = RemitoBiologico(
        id_remito, Clinica(id_remito, f"Clínica {id_remito}", "San Martín 100"),
        ConservadoraIsotermica(id_remito, f"CONS-{id_remito}"), FECHA,
    )
    for i in range(cantidad):
        muestra = MuestraBiologica(id_remito * 10 + i, "Sangre", FECHA)
        assert remito.agregar_muestra(muestra, FECHA)
    if con_precinto:
        assert remito.asignar_precinto(PrecintoSanitario(id_remito, f"PREC-{id_remito}"))
    return remito


def test_lista_vacia():
    assert ReporteMuestrasRechazadas([]).generar() == []


def test_remito_sin_rechazadas():
    assert ReporteMuestrasRechazadas([crear_remito()]).generar() == []


def test_rechazo_por_recepcion_incluye_fecha_y_contexto():
    remito = crear_remito()
    envio = Envio(1, remito)
    assert envio.iniciar(FECHA)
    llegada = FECHA + timedelta(hours=1)
    rechazo = llegada + timedelta(minutes=15)
    assert envio.registrar_llegada(llegada)
    assert remito.obtener_precinto().marcar_roto()
    assert Recepcion(1, envio, rechazo).procesar_recepcion()

    assert ReporteMuestrasRechazadas([remito]).generar() == [{
        "id_muestra": 10,
        "tipo_muestra": "Sangre",
        "estado": "RECHAZADA",
        "fecha_rechazo": rechazo,
        "id_remito": 1,
        "id_clinica": 1,
        "clinica_origen": "Clínica 1",
        "estado_precinto": "ROTO",
    }]


def test_varios_remitos_filtran_por_estado_de_muestra():
    primero = crear_remito(cantidad=3)
    segundo = crear_remito(2)
    for remito in (primero, segundo):
        assert remito.despachar(FECHA)
    rechazada, recibida, en_transito = primero.obtener_muestras()
    assert rechazada.rechazar(FECHA)
    assert recibida.recibir(FECHA)
    assert segundo.obtener_muestras()[0].rechazar(FECHA)

    filas = ReporteMuestrasRechazadas([primero, segundo]).generar()

    assert [fila["id_muestra"] for fila in filas] == [10, 20]
    assert [fila["id_remito"] for fila in filas] == [1, 2]
    assert [fila["clinica_origen"] for fila in filas] == ["Clínica 1", "Clínica 2"]
    assert all(fila["estado_precinto"] == "INTACTO" for fila in filas)
    assert en_transito.estado.obtener_nombre() == "EN_TRANSITO"


def test_precinto_roto_sin_rechazo_no_genera_filas():
    remito = crear_remito()
    assert remito.despachar(FECHA)
    assert remito.obtener_precinto().marcar_roto()

    assert ReporteMuestrasRechazadas([remito]).generar() == []


def test_precinto_ausente_se_informa_como_none():
    remito = crear_remito(con_precinto=False)
    muestra = remito.obtener_muestras()[0]
    assert muestra.despachar(FECHA)
    assert muestra.rechazar(FECHA)

    assert ReporteMuestrasRechazadas([remito]).generar()[0]["estado_precinto"] is None


def test_no_modifica_muestra_historial_remito_ni_precinto():
    remito = crear_remito()
    assert remito.despachar(FECHA)
    precinto = remito.obtener_precinto()
    assert precinto.marcar_roto()
    muestra = remito.obtener_muestras()[0]
    assert muestra.rechazar(FECHA)
    historial = muestra.obtener_historial()
    estado_muestra = muestra.estado
    estado_remito = remito.estado
    estado_precinto = precinto.estado
    estado_conservadora = remito.conservadora.estado
    remitos = [remito]
    reporte = ReporteMuestrasRechazadas(remitos)

    filas = reporte.generar()
    filas[0]["estado"] = "MODIFICADO"

    assert reporte.generar()[0]["estado"] == "RECHAZADA"
    assert muestra.estado is estado_muestra
    assert muestra.obtener_historial() == historial
    assert remito.estado == estado_remito
    assert remito.obtener_muestras() == [muestra]
    assert remito.obtener_precinto() is precinto
    assert precinto.estado == estado_precinto
    assert remito.conservadora.estado == estado_conservadora
    assert remitos == [remito]
