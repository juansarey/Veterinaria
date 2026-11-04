"""Punto de entrada único de la capa de servicios para la interfaz."""

from veterinaria.servicios.atencion_servicio import AtencionServicio
from veterinaria.servicios.clinica_servicio import ClinicaServicio
from veterinaria.servicios.laboratorio_servicio import LaboratorioServicio
from veterinaria.servicios.reporte_servicio import ReporteServicio


class Servicios:
    """Agrupa los servicios sobre un mismo archivo SQLite."""

    def __init__(self, ruta_bd):
        self.clinica = ClinicaServicio(ruta_bd)
        self.atencion = AtencionServicio(ruta_bd)
        self.laboratorio = LaboratorioServicio(ruta_bd)
        self.reportes = ReporteServicio(ruta_bd)
