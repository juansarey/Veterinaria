from datetime import date


class AplicacionVacuna:
    def __init__(
        self,
        id_aplicacion: int,
        vacuna,
        fecha_aplicacion: date,
        fecha_proxima_dosis: date | None = None,
    ):
        if vacuna is None:
            raise ValueError("Una aplicación debe corresponder a una vacuna.")

        if (
            fecha_proxima_dosis is not None
            and fecha_proxima_dosis <= fecha_aplicacion
        ):
            raise ValueError(
                "La fecha de la próxima dosis debe ser posterior a la aplicación."
            )

        self.id_aplicacion = id_aplicacion
        self.vacuna = vacuna
        self.fecha_aplicacion = fecha_aplicacion
        self.fecha_proxima_dosis = fecha_proxima_dosis

    def esta_vigente(self, fecha_referencia):
        if fecha_referencia < self.fecha_aplicacion:
            return False

        if self.fecha_proxima_dosis is None:
            return True

        return fecha_referencia < self.fecha_proxima_dosis

    def esta_vencida(self, fecha_referencia):
        if fecha_referencia < self.fecha_aplicacion:
            return False

        if self.fecha_proxima_dosis is None:
            return False

        return fecha_referencia >= self.fecha_proxima_dosis
