from veterinaria.patrones.strategy.estrategia_reporte import EstrategiaReporte


class ReporteAtencionesDerivaciones(EstrategiaReporte):
    def __init__(self, atenciones):
        self.atenciones = atenciones

    def generar(self) -> list:
        filas = []
        for atencion in self.atenciones:
            derivaciones = [
                {
                    "id_orden": orden.id_orden,
                    "estudio_solicitado": orden.estudio_solicitado,
                    "estado": orden.estado.value,
                }
                for orden in atencion.obtener_ordenes_derivacion()
            ]
            veterinario = atencion.veterinario
            filas.append({
                "id_atencion": atencion.id_atencion,
                "fecha_hora": atencion.fecha_hora,
                "tipo": atencion.tipo.value,
                "id_veterinario": veterinario.id_veterinario,
                "veterinario": f"{veterinario.nombre} {veterinario.apellido}",
                "cantidad_derivaciones": len(derivaciones),
                "derivaciones": derivaciones,
            })
        return filas
