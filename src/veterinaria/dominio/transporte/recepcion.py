from .envio import EstadoEnvio
from .remito_biologico import EstadoRemito


class Recepcion:
    def __init__(
        self, id_recepcion: int, envio, fecha_hora, observaciones: str = ""
    ):
        if envio is None:
            raise ValueError("Una recepción debe tener un envío.")

        self.id_recepcion = id_recepcion
        self.envio = envio
        self.fecha_hora = fecha_hora
        self.observaciones = observaciones

    def verificar_precinto(self):
        precinto = self.envio.remito.obtener_precinto()
        return precinto is not None and precinto.esta_intacto()

    def procesar_recepcion(self):
        if self.envio.estado != EstadoEnvio.ENTREGADO:
            return False

        if self.envio.fecha_hora_llegada is None:
            return False

        if self.fecha_hora < self.envio.fecha_hora_llegada:
            return False

        remito = self.envio.remito
        if remito.estado != EstadoRemito.DESPACHADO:
            return False

        if remito.obtener_precinto() is None:
            return False

        muestras = remito.obtener_muestras()
        # Validar el lote completo antes de cambiar cualquier muestra.
        for muestra in muestras:
            if muestra.estado.obtener_nombre() != "EN_TRANSITO":
                return False

            if self.fecha_hora < muestra.obtener_historial()[-1].fecha_hora:
                return False

        precinto_intacto = self.verificar_precinto()
        for muestra in muestras:
            if precinto_intacto:
                muestra.recibir(self.fecha_hora, self.observaciones)
            else:
                muestra.rechazar(self.fecha_hora, self.observaciones)

        return remito.marcar_recibido()
