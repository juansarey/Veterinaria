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
        self._aplicaciones_vacuna = []

    def obtener_historia_clinica(self):
        return self._historia_clinica

    def asignar_historia_clinica(self, historia):
        if self._historia_clinica is not None:
            return False

        self._historia_clinica = historia
        return True

    def agregar_aplicacion_vacuna(self, aplicacion):
        for aplicacion_registrada in self._aplicaciones_vacuna:
            if aplicacion_registrada is aplicacion:
                return False

        self._aplicaciones_vacuna.append(aplicacion)
        return True

    def obtener_aplicaciones_vacuna(self):
        return self._aplicaciones_vacuna.copy()

    def obtener_vacunas_pendientes(self, vacunas, fecha_referencia):
        pendientes = []

        for vacuna in vacunas:
            if not vacuna.es_obligatoria():
                continue

            if vacuna.especie != self.especie:
                continue

            tiene_aplicacion_vigente = False

            for aplicacion in self._aplicaciones_vacuna:
                if aplicacion.vacuna.id_vacuna == vacuna.id_vacuna:
                    if aplicacion.esta_vigente(fecha_referencia):
                        tiene_aplicacion_vigente = True
                        break

            if not tiene_aplicacion_vigente:
                pendientes.append(vacuna)

        return pendientes

    def vacunas_obligatorias_al_dia(self, vacunas, fecha_referencia):
        return self.obtener_vacunas_pendientes(vacunas, fecha_referencia) == []

    def registrar_atencion(self, atencion, vacunas):
        if self._historia_clinica is None:
            return False

        fecha_referencia = atencion.fecha_hora.date()

        if not self.vacunas_obligatorias_al_dia(vacunas, fecha_referencia):
            return False

        return self._historia_clinica._agregar_atencion(atencion)
