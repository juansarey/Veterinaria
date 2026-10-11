from enum import Enum


class EstadoOrden(Enum):
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADA = "COMPLETADA"
    CANCELADA = "CANCELADA"


class OrdenDerivacionLaboratorio:
    def __init__(
        self,
        id_orden: int,
        fecha_emision,
        estudio_solicitado: str,
        observaciones: str = "",
    ):
        self.id_orden = id_orden
        self.fecha_emision = fecha_emision
        self.estudio_solicitado = estudio_solicitado
        self.observaciones = observaciones
        self._estado = EstadoOrden.PENDIENTE
        self._muestras = []

    @property
    def estado(self):
        return self._estado

    def agregar_muestra(self, muestra):
        if self._estado not in (EstadoOrden.PENDIENTE, EstadoOrden.EN_PROCESO):
            return False

        for muestra_registrada in self._muestras:
            if muestra_registrada is muestra:
                return False

        self._muestras.append(muestra)
        return True

    def obtener_muestras(self):
        return self._muestras.copy()

    def iniciar_proceso(self):
        if self._estado != EstadoOrden.PENDIENTE:
            return False

        if not self._muestras:
            return False

        self._estado = EstadoOrden.EN_PROCESO
        return True

    def completar(self):
        if self._estado != EstadoOrden.EN_PROCESO:
            return False

        self._estado = EstadoOrden.COMPLETADA
        return True

    def cancelar(self):
        if self._estado not in (EstadoOrden.PENDIENTE, EstadoOrden.EN_PROCESO):
            return False

        self._estado = EstadoOrden.CANCELADA
        return True
