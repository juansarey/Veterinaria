class Mascota:
    def __init__(
        self,
        id_mascota: int,
        nombre: str,
        especie: str,
        responsable,
        raza: str = "",
        fecha_nacimiento=None,
        sexo: str = "",
    ):
        if responsable is None:
            raise ValueError("Una mascota debe tener un responsable.")

        self.id_mascota = id_mascota
        self.nombre = nombre
        self.especie = especie
        self.responsable = responsable
        self.raza = raza
        self.fecha_nacimiento = fecha_nacimiento
        self.sexo = sexo
        self._historia_clinica = None

    def obtener_historia_clinica(self):
        return self._historia_clinica

    def asignar_historia_clinica(self, historia):
        if self._historia_clinica is not None:
            return False

        self._historia_clinica = historia
        return True
