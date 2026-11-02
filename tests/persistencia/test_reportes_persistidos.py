from contextlib import closing
from datetime import date, timedelta

from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
)
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico
from veterinaria.patrones.strategy.generador_reportes import GeneradorReportes
from veterinaria.patrones.strategy.reporte_atenciones_derivaciones import (
    ReporteAtencionesDerivaciones,
)
from veterinaria.patrones.strategy.reporte_muestras_rechazadas import (
    ReporteMuestrasRechazadas,
)
from veterinaria.patrones.strategy.reporte_tiempos_transito_procesamiento import (
    ReporteTiemposTransitoProcesamiento,
)
from veterinaria.patrones.strategy.reporte_vacunas_pendientes import (
    ReporteVacunasPendientes,
)
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.conservadora_isotermica_dao import (
    ConservadoraIsotermicaDAO,
)
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO
from veterinaria.persistencia.vacuna_dao import VacunaDAO


def test_atenciones_y_derivaciones_tras_reabrir(circuito_persistido):
    ruta = circuito_persistido()
    with closing(abrir_conexion(ruta)) as conexion:
        atenciones = AtencionDAO(conexion).listar(cargar_ordenes=True)
        assert [o.id_orden for o in atenciones[0].obtener_ordenes_derivacion()] == [100]
        filas = GeneradorReportes(
            ReporteAtencionesDerivaciones(atenciones)
        ).generar_reporte()
        assert len(filas) == 1
        assert filas[0]["id_atencion"] == 70
        assert filas[0]["id_veterinario"] == 40
        assert filas[0]["cantidad_derivaciones"] == 1
        assert filas[0]["derivaciones"] == [{
            "id_orden": 100,
            "estudio_solicitado": "Hemograma completo",
            "estado": "COMPLETADA",
        }]


def test_muestras_rechazadas_tras_reabrir(circuito_persistido):
    ruta = circuito_persistido(precinto_roto=True)
    with closing(abrir_conexion(ruta)) as conexion:
        remitos = RemitoBiologicoDAO(conexion).listar()
        historial = remitos[0].obtener_muestras()[0].obtener_historial()
        filas = GeneradorReportes(ReporteMuestrasRechazadas(remitos)).generar_reporte()
        assert len(filas) == 1
        assert filas[0]["id_muestra"] == 110
        assert filas[0]["id_remito"] == 130
        assert filas[0]["id_clinica"] == 30
        assert filas[0]["estado"] == "RECHAZADA"
        assert filas[0]["estado_precinto"] == "ROTO"
        assert filas[0]["fecha_rechazo"] == historial[-1].fecha_hora
        assert remitos[0].obtener_muestras()[0].obtener_historial() == historial


def test_vacunas_pendientes_sin_falsos_positivos_tras_reabrir(circuito_persistido):
    ruta = circuito_persistido()
    with closing(abrir_conexion(ruta)) as conexion:
        responsable = ClienteDAO(conexion).obtener_por_id(10)
        MascotaDAO(conexion).crear(Mascota(21, "Toby", "Perro", responsable))
        conexion.commit()
    with closing(abrir_conexion(ruta)) as conexion:
        mascotas = MascotaDAO(conexion).listar(cargar_aplicaciones=True)
        vacunas = VacunaDAO(conexion).listar()
        assert [m.id_mascota for m in mascotas] == [20, 21]
        assert [len(m.obtener_aplicaciones_vacuna()) for m in mascotas] == [1, 0]
        filas = GeneradorReportes(ReporteVacunasPendientes(
            mascotas, vacunas, date(2026, 11, 3)
        )).generar_reporte()
        assert [(f["id_mascota"], f["id_vacuna"]) for f in filas] == [(21, 80)]
        assert filas[0]["id_responsable"] == 10
        assert filas[0]["mascota"] == "Toby"


def test_tiempos_compuestos_con_dao_tras_reabrir(circuito_persistido):
    ruta = circuito_persistido()
    # Un remito sin envío permite comprobar el descarte de consultas sin resultado.
    with closing(abrir_conexion(ruta)) as conexion:
        conservadora = ConservadoraIsotermica(121, "CONS-121")
        ConservadoraIsotermicaDAO(conexion).crear(conservadora)
        existente = RemitoBiologicoDAO(conexion).obtener_por_id(130)
        remito_sin_envio = RemitoBiologico(
            131, ClinicaDAO(conexion).obtener_por_id(30), conservadora,
            existente.fecha_emision,
        )
        RemitoBiologicoDAO(conexion).crear(remito_sin_envio)
        conexion.commit()
    with closing(abrir_conexion(ruta)) as conexion:
        remitos = RemitoBiologicoDAO(conexion).listar()
        envio_dao = EnvioDAO(conexion)
        envios = []
        for remito in remitos:
            envio = envio_dao.obtener_por_remito(remito.id_remito)
            if envio is not None:
                envios.append(envio)
        assert len(remitos) == 2
        assert [e.id_envio for e in envios] == [150]
        filas = GeneradorReportes(
            ReporteTiemposTransitoProcesamiento(envios)
        ).generar_reporte()
        assert filas == [{
            "cantidad_envios_con_transito": 1,
            "tiempo_promedio_transito": timedelta(hours=1),
            "cantidad_muestras_procesadas": 1,
            "tiempo_promedio_procesamiento": timedelta(minutes=90),
        }]
