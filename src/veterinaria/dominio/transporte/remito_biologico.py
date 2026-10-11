from enum import Enum


class EstadoRemito(Enum):
    GENERADO = "GENERADO"
    DESPACHADO = "DESPACHADO"
    RECIBIDO = "RECIBIDO"
    CERRADO = "CERRADO"


class RemitoBiologico:
    def __init__(
        self,
        id_remito: int,
        clinica_origen,
        conservadora,
        fecha_emision,
        observaciones: str = "",
    ):
        if clinica_origen is None:
            raise ValueError("Un remito debe tener una clínica de origen.")

        if conservadora is None:
            raise ValueError("Un remito debe tener una conservadora.")

        if not conservadora.esta_disponible():
            raise ValueError("La conservadora debe estar disponible.")

        self.id_remito = id_remito
        self.clinica_origen = clinica_origen
        self.conservadora = conservadora
        self.fecha_emision = fecha_emision
        self.observaciones = observaciones
        self._estado = EstadoRemito.GENERADO
        self._precinto = None
        self._muestras = []

        conservadora.marcar_en_uso()

    @property
    def estado(self):
        return self._estado

    def agregar_muestra(self, muestra, fecha_hora, observaciones=""):
        if self._estado != EstadoRemito.GENERADO:
            return False

        for muestra_registrada in self._muestras:
            if muestra_registrada is muestra:
                return False

        if not muestra.empaquetar(fecha_hora, observaciones):
            return False

        self._muestras.append(muestra)
        return True

    def obtener_muestras(self):
        return self._muestras.copy()

    def asignar_precinto(self, precinto):
        if precinto is None:
            return False

        if self._precinto is not None:
            return False

        self._precinto = precinto
        return True

    def obtener_precinto(self):
        return self._precinto

    def puede_despacharse(self):
        if self._estado != EstadoRemito.GENERADO:
            return False

        if self.conservadora is None:
            return False

        if not self._muestras:
            return False

        if self._precinto is None:
            return False

        return self._precinto.esta_intacto()
