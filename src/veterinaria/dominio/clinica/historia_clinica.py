class HistoriaClinica:
    def __init__(self, id_historia: int, fecha_apertura, observaciones: str = ""):
        self.id_historia = id_historia
        self.fecha_apertura = fecha_apertura
        self.observaciones = observaciones
        self._atenciones = []

    def _agregar_atencion(self, atencion):
        for atencion_registrada in self._atenciones:
            if atencion_registrada is atencion:
                return False

        self._atenciones.append(atencion)
        return True

    def obtener_atenciones(self):
        return self._atenciones.copy()
