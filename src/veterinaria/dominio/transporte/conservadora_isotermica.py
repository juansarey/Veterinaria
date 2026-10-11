from enum import Enum


class EstadoConservadora(Enum):
    DISPONIBLE = "DISPONIBLE"
    EN_USO = "EN_USO"


class ConservadoraIsotermica:
    def __init__(self, id_conservadora: int, codigo: str):
        self.id_conservadora = id_conservadora
        self.codigo = codigo
        self._estado = EstadoConservadora.DISPONIBLE

    @property
    def estado(self):
        return self._estado

    def esta_disponible(self):
        return self._estado == EstadoConservadora.DISPONIBLE

    def marcar_en_uso(self):
        if not self.esta_disponible():
            return False

        self._estado = EstadoConservadora.EN_USO
        return True

    def liberar(self):
        if self._estado != EstadoConservadora.EN_USO:
            return False

        self._estado = EstadoConservadora.DISPONIBLE
        return True
