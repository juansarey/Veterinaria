from veterinaria.patrones.strategy.estrategia_reporte import EstrategiaReporte


class ReporteVacunasPendientes(EstrategiaReporte):
    def __init__(self, mascotas, vacunas, fecha_referencia):
        self.mascotas = mascotas
        self.vacunas = vacunas
        self.fecha_referencia = fecha_referencia

    def generar(self) -> list:
        filas = []
        for mascota in self.mascotas:
            pendientes = mascota.obtener_vacunas_pendientes(
                self.vacunas, self.fecha_referencia
            )
            responsable = mascota.responsable
            for vacuna in pendientes:
                filas.append({
                    "id_mascota": mascota.id_mascota,
                    "mascota": mascota.nombre,
                    "especie": mascota.especie,
                    "id_responsable": responsable.id_cliente,
                    "responsable": f"{responsable.nombre} {responsable.apellido}",
                    "id_vacuna": vacuna.id_vacuna,
                    "vacuna": vacuna.nombre,
                    "fecha_referencia": self.fecha_referencia,
                })
        return filas
