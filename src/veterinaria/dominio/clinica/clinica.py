"""Clínica y asociación de sus profesionales en memoria."""

from .veterinario import Veterinario


class Clinica:
    def __init__(self, id_clinica: int, nombre: str, direccion: str, telefono: str = ""):
        self.id_clinica = id_clinica
        self.nombre = nombre
        self.direccion = direccion
        self.telefono = telefono
        self._veterinarios = []

    def agregar_veterinario(self, veterinario):
        for veterinario_registrado in self._veterinarios:
            if veterinario_registrado is veterinario:
                return False

        self._veterinarios.append(veterinario)
        return True

    def obtener_veterinarios(self) -> list[Veterinario]:
        return self._veterinarios.copy()
