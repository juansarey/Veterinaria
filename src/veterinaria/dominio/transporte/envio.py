from enum import Enum


class EstadoEnvio(Enum):
    PENDIENTE = "PENDIENTE"
    EN_TRANSITO = "EN_TRANSITO"
    ENTREGADO = "ENTREGADO"


class Envio:
    def __init__(self, id_envio: int, remito, observaciones: str = ""):
        if remito is None:
            raise ValueError("Un envío debe tener un remito.")

        self.id_envio = id_envio
        self.remito = remito
        self.observaciones = observaciones
        self.fecha_hora_salida = None
        self.fecha_hora_llegada = None
        self._estado = EstadoEnvio.PENDIENTE

    @property
    def estado(self):
        return self._estado

    def iniciar(self, fecha_hora):
        if self._estado != EstadoEnvio.PENDIENTE:
            return False

        if not self.remito.despachar(fecha_hora, self.observaciones):
            return False

        self.fecha_hora_salida = fecha_hora
        self._estado = EstadoEnvio.EN_TRANSITO
        return True

    def registrar_llegada(self, fecha_hora):
        if self._estado != EstadoEnvio.EN_TRANSITO:
            return False

        if fecha_hora < self.fecha_hora_salida:
            return False

        self.fecha_hora_llegada = fecha_hora
        self._estado = EstadoEnvio.ENTREGADO
        return True
