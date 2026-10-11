from datetime import timedelta

from veterinaria.patrones.strategy.estrategia_reporte import EstrategiaReporte


class ReporteTiemposTransitoProcesamiento(EstrategiaReporte):
    def __init__(self, envios):
        self.envios = envios

    def generar(self) -> list:
        tiempos_transito = []
        tiempos_procesamiento = []
        envios_visitados = set()
        muestras_visitadas = set()

        for envio in self.envios:
            # Evitar ponderar un objeto varias veces por referencias repetidas.
            if envio in envios_visitados:
                continue
            envios_visitados.add(envio)

            if (
                envio.fecha_hora_salida is not None
                and envio.fecha_hora_llegada is not None
            ):
                tiempos_transito.append(
                    envio.fecha_hora_llegada - envio.fecha_hora_salida
                )

            for muestra in envio.remito.obtener_muestras():
                if muestra in muestras_visitadas:
                    continue
                muestras_visitadas.add(muestra)

                fechas = {
                    registro.nombre_estado: registro.fecha_hora
                    for registro in muestra.obtener_historial()
                }
                if "RECIBIDA" in fechas and "ANALIZADA" in fechas:
                    tiempos_procesamiento.append(
                        fechas["ANALIZADA"] - fechas["RECIBIDA"]
                    )

        return [{
            "cantidad_envios_con_transito": len(tiempos_transito),
            "tiempo_promedio_transito": (
                sum(tiempos_transito, timedelta()) / len(tiempos_transito)
                if tiempos_transito else None
            ),
            "cantidad_muestras_procesadas": len(tiempos_procesamiento),
            "tiempo_promedio_procesamiento": (
                sum(tiempos_procesamiento, timedelta()) / len(tiempos_procesamiento)
                if tiempos_procesamiento else None
            ),
        }]
