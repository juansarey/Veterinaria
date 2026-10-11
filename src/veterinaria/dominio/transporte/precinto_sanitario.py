from enum import Enum


class EstadoPrecinto(Enum):
    INTACTO = "INTACTO"
    ROTO = "ROTO"


class PrecintoSanitario:
    def __init__(self, id_precinto: int, codigo: str):
        self.id_precinto = id_precinto
        self.codigo = codigo
        self._estado = EstadoPrecinto.INTACTO

    @property
    def estado(self):
        return self._estado

    def esta_intacto(self):
        return self._estado == EstadoPrecinto.INTACTO

    def marcar_roto(self):
        if self._estado == EstadoPrecinto.ROTO:
            return False

        self._estado = EstadoPrecinto.ROTO
        return True
