"""Administración de la agenda y las reservas de un veterinario."""

from .agenda_medica import AgendaMedica
from .turno import EstadoTurno, Turno


class Veterinario:
    def __init__(self, id_veterinario: int, nombre: str, apellido: str, matricula: str, especialidad: str = "",):
        self.id_veterinario = id_veterinario
        self.nombre = nombre
        self.apellido = apellido
        self.matricula = matricula
        self.especialidad = especialidad
        self._agenda: AgendaMedica | None = None
        self._turnos: list[Turno] = []

    def obtener_agenda(self) -> AgendaMedica | None:
        return self._agenda

    def obtener_turnos(self) -> list[Turno]:
        return self._turnos.copy()

    def asignar_agenda(self, agenda: AgendaMedica) -> None:
        self._agenda = agenda

    def puede_agendar(self, turno: Turno) -> bool:
        if any(registrado is turno for registrado in self._turnos):
            return False
        if self._agenda is None or not self._agenda.contiene(turno):
            return False
        return not any(
            otro.estado != EstadoTurno.CANCELADO and turno.se_superpone_con(otro)
            for otro in self._turnos
        )

    def agregar_turno(self, turno: Turno) -> None:
        if not self.puede_agendar(turno):
            raise ValueError(
                "No se puede registrar el turno: ya está asociado, está fuera de "
                "agenda o se superpone con un turno no cancelado."
            )
        self._turnos.append(turno)
