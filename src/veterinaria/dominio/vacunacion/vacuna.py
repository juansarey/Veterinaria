class Vacuna:
    def __init__(
        self,
        id_vacuna: int,
        nombre: str,
        especie: str,
        obligatoria: bool,
    ):
        self.id_vacuna = id_vacuna
        self.nombre = nombre
        self.especie = especie
        self.obligatoria = obligatoria

    def es_obligatoria(self):
        return self.obligatoria
