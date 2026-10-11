from datetime import datetime

from veterinaria.patrones.state.estado_muestra import EstadoExtraida

from .historial_estado_muestra import HistorialEstadoMuestra


class MuestraBiologica:
    def __init__(
        self,
        id_muestra: int,
        tipo_muestra: str,
        fecha_extraccion: datetime,
        observaciones: str = "",
    ):
        self.id_muestra = id_muestra
        self.tipo_muestra = tipo_muestra
        self.fecha_extraccion = fecha_extraccion
        self.observaciones = observaciones
        self._estado = EstadoExtraida()
        self._historial = [
            HistorialEstadoMuestra(
                self._estado.obtener_nombre(),
                fecha_extraccion,
            )
        ]

    @property
    def estado(self):
        return self._estado

    def empaquetar(self, fecha_hora, observaciones=""):
        return self._estado.empaquetar(self, fecha_hora, observaciones)

    def despachar(self, fecha_hora, observaciones=""):
        return self._estado.despachar(self, fecha_hora, observaciones)

    def recibir(self, fecha_hora, observaciones=""):
        return self._estado.recibir(self, fecha_hora, observaciones)

    def rechazar(self, fecha_hora, observaciones=""):
        return self._estado.rechazar(self, fecha_hora, observaciones)

    def analizar(self, fecha_hora, observaciones=""):
        return self._estado.analizar(self, fecha_hora, observaciones)

    def obtener_historial(self):
        return self._historial.copy()

    def _cambiar_estado(self, nuevo_estado, fecha_hora, observaciones=""):
        ultimo_registro = self._historial[-1]

        if fecha_hora < ultimo_registro.fecha_hora:
            return False

        self._estado = nuevo_estado
        self._historial.append(
            HistorialEstadoMuestra(
                nuevo_estado.obtener_nombre(),
                fecha_hora,
                observaciones,
            )
        )
        return True
