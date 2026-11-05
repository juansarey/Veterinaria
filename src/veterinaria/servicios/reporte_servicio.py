"""Reportes (patrón Strategy) compuestos con datos persistidos.

Cada método devuelve un diccionario genérico listo para mostrar o exportar::

    {"titulo": str, "columnas": [(clave, encabezado), ...], "filas": [dict, ...],
     "grafico": {"titulo": str, "eje": str, "datos": {etiqueta: valor}}}

El gráfico lo dibuja el exportador en el PDF (Matplotlib); la vista en pantalla lo ignora.
"""
from collections import Counter

from datetime import date, datetime, timedelta

from veterinaria.patrones.strategy.generador_reportes import GeneradorReportes
from veterinaria.patrones.strategy.reporte_atenciones_derivaciones import (
    ReporteAtencionesDerivaciones,
)
from veterinaria.patrones.strategy.reporte_muestras_rechazadas import ReporteMuestrasRechazadas
from veterinaria.patrones.strategy.reporte_tiempos_transito_procesamiento import (
    ReporteTiemposTransitoProcesamiento,
)
from veterinaria.patrones.strategy.reporte_vacunas_pendientes import ReporteVacunasPendientes
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO
from veterinaria.persistencia.vacuna_dao import VacunaDAO
from veterinaria.servicios.atencion_servicio import AtencionServicio
from veterinaria.servicios.base import ServicioBase, fmt_fecha_hora
from veterinaria.servicios.clinica_servicio import ClinicaServicio


def formatear_duracion(valor: timedelta | None) -> str:
    if valor is None:
        return "Sin datos"
    minutos_totales = int(valor.total_seconds() // 60)
    dias, resto = divmod(minutos_totales, 1440)
    horas, minutos = divmod(resto, 60)
    partes = ([f"{dias} d"] if dias else []) + ([f"{horas} h"] if horas else [])
    partes.append(f"{minutos} min")
    return " ".join(partes)


def grafico(titulo: str, eje: str, datos: dict) -> dict:
    return {"titulo": titulo, "eje": eje, "datos": dict(datos)}


def _horas(valor: timedelta | None) -> float:
    return round(valor.total_seconds() / 3600, 1) if valor else 0.0


class ReporteServicio(ServicioBase):
    def _generar(self, estrategia) -> list:
        return GeneradorReportes(estrategia).generar_reporte()

    # 1 ---------------------------------------------------- atenciones y derivaciones
    def atenciones_derivaciones(self) -> dict:
        mascota_de = {a["id"]: a["mascota"] for a in AtencionServicio(self._ruta).listar_atenciones()}
        clinica_de = {v["id"]: v["clinica"] for v in ClinicaServicio(self._ruta).listar_veterinarios()}
        with self._lectura() as con:
            filas = self._generar(
                ReporteAtencionesDerivaciones(AtencionDAO(con).listar(cargar_ordenes=True))
            )
        salida = [{
            "fecha": fmt_fecha_hora(f["fecha_hora"]), "tipo": f["tipo"],
            "mascota": mascota_de.get(f["id_atencion"], ""),
            "veterinario": f["veterinario"],
            "clinica": clinica_de.get(f["id_veterinario"], ""),
            "derivaciones": f["cantidad_derivaciones"],
            "estudios": "; ".join(d["estudio_solicitado"] for d in f["derivaciones"]) or "—",
            "_orden": f["fecha_hora"],
        } for f in filas]
        salida.sort(key=lambda f: f["_orden"])
        return {
            "titulo": "Atenciones clínicas y derivaciones realizadas",
            "columnas": [("fecha", "Fecha"), ("tipo", "Tipo"), ("mascota", "Mascota"),
                         ("veterinario", "Veterinario"), ("clinica", "Clínica"),
                         ("derivaciones", "Derivaciones"), ("estudios", "Estudios solicitados")],
            "filas": salida,
            "grafico": grafico("Atenciones por tipo", "Atenciones", Counter(f["tipo"] for f in salida)),
        }

    # 2 ------------------------------------------------------------ muestras rechazadas
    def muestras_rechazadas(self) -> dict:
        with self._lectura() as con:
            filas = self._generar(ReporteMuestrasRechazadas(RemitoBiologicoDAO(con).listar()))
        return {
            "titulo": "Muestras biológicas rechazadas por fallas en el transporte",
            "columnas": [("id_muestra", "Muestra"), ("tipo_muestra", "Tipo"),
                         ("fecha_rechazo", "Fecha de rechazo"), ("id_remito", "Remito"),
                         ("clinica_origen", "Clínica de origen"),
                         ("estado_precinto", "Precinto")],
            "filas": [{**f, "fecha_rechazo": fmt_fecha_hora(f["fecha_rechazo"])} for f in filas],
            "grafico": grafico("Muestras rechazadas por clínica de origen", "Muestras",
                               Counter(f["clinica_origen"] for f in filas)),
        }

    # 3 --------------------------------------------------------------- vacunas pendientes
    def vacunas_pendientes(self, fecha_referencia: date | None = None) -> dict:
        ref = fecha_referencia or date.today()
        with self._lectura() as con:
            filas = self._generar(ReporteVacunasPendientes(
                MascotaDAO(con).listar(cargar_aplicaciones=True), VacunaDAO(con).listar(), ref))
        return {
            "titulo": f"Vacunas obligatorias pendientes al {ref.strftime('%d/%m/%Y')}",
            "columnas": [("id_mascota", "ID mascota"), ("mascota", "Mascota"), ("especie", "Especie"),
                         ("responsable", "Responsable"), ("vacuna", "Vacuna pendiente")],
            "filas": filas,
            "grafico": grafico("Mascotas con cada vacuna pendiente", "Mascotas",
                               Counter(f"{f['vacuna']} ({f['especie']})" for f in filas)),
        }

    # 4 ------------------------------------------------ tiempos de tránsito y procesamiento
    def tiempos(self) -> dict:
        with self._lectura() as con:
            envio_dao = EnvioDAO(con)
            envios = [e for r in RemitoBiologicoDAO(con).listar()
                      if (e := envio_dao.obtener_por_remito(r.id_remito)) is not None]
            resumen = self._generar(ReporteTiemposTransitoProcesamiento(envios))
        r = resumen[0] if isinstance(resumen, list) and resumen else resumen
        return {
            "titulo": "Tiempo promedio de tránsito y procesamiento de muestras",
            "columnas": [("indicador", "Indicador"), ("cantidad", "Casos"),
                         ("promedio", "Tiempo promedio")],
            "filas": [
                {"indicador": "Tránsito (llegada - salida)",
                 "cantidad": r["cantidad_envios_con_transito"],
                 "promedio": formatear_duracion(r["tiempo_promedio_transito"])},
                {"indicador": "Procesamiento (resultado - recepción)",
                 "cantidad": r["cantidad_muestras_procesadas"],
                 "promedio": formatear_duracion(r["tiempo_promedio_procesamiento"])},
            ],
            "grafico": grafico("Tiempo promedio de cada etapa", "Horas", {
                "Tránsito": _horas(r["tiempo_promedio_transito"]),
                "Procesamiento": _horas(r["tiempo_promedio_procesamiento"])}),
        }

    def todos(self, fecha_referencia: date | None = None) -> dict[str, dict]:
        return {
            "atenciones": self.atenciones_derivaciones(),
            "rechazadas": self.muestras_rechazadas(),
            "vacunas": self.vacunas_pendientes(fecha_referencia),
            "tiempos": self.tiempos(),
        }
