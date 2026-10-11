from veterinaria.patrones.strategy.estrategia_reporte import EstrategiaReporte


class ReporteMuestrasRechazadas(EstrategiaReporte):
    def __init__(self, remitos):
        self.remitos = remitos

    def generar(self) -> list:
        filas = []
        for remito in self.remitos:
            for muestra in remito.obtener_muestras():
                estado = muestra.estado.obtener_nombre()
                if estado != "RECHAZADA":
                    continue

                fecha_rechazo = next(
                    registro.fecha_hora
                    for registro in muestra.obtener_historial()
                    if registro.nombre_estado == "RECHAZADA"
                )
                precinto = remito.obtener_precinto()
                filas.append({
                    "id_muestra": muestra.id_muestra,
                    "tipo_muestra": muestra.tipo_muestra,
                    "estado": estado,
                    "fecha_rechazo": fecha_rechazo,
                    "id_remito": remito.id_remito,
                    "id_clinica": remito.clinica_origen.id_clinica,
                    "clinica_origen": remito.clinica_origen.nombre,
                    "estado_precinto": (
                        precinto.estado.value if precinto is not None else None
                    ),
                })
        return filas
