"""Reservas y transiciones de estado de los turnos."""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class EstadoTurno(Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    ATENDIDO = "ATENDIDO"
    CANCELADO = "CANCELADO"


class Turno:
    """Intervalo fijo en fecha y hora local, inicialmente pendiente."""

    def __init__(
        self,
        id_turno: int,
        fecha_hora_inicio: datetime,
        fecha_hora_fin: datetime,
        mascota,
        motivo: str = "",
    ):
        if fecha_hora_fin <= fecha_hora_inicio:
            raise ValueError("La fecha/hora de fin debe ser posterior al inicio.")
        if mascota is None:
            raise ValueError("Un turno debe corresponder a una mascota.")
        self.id_turno = id_turno
        self.motivo = motivo
        self.mascota = mascota
        self._fecha_hora_inicio = fecha_hora_inicio
        self._fecha_hora_fin = fecha_hora_fin
        self._estado = EstadoTurno.PENDIENTE

    @property
    def fecha_hora_inicio(self) -> datetime:
        return self._fecha_hora_inicio

    @property
    def fecha_hora_fin(self) -> datetime:
        return self._fecha_hora_fin

    @property
    def estado(self) -> EstadoTurno:
        return self._estado

    def confirmar(self):
        if self.estado != EstadoTurno.PENDIENTE:
            raise ValueError("Sólo se puede confirmar un turno PENDIENTE.")
        self._estado = EstadoTurno.CONFIRMADO

    def cancelar(self):
        if self.estado not in (EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO):
            raise ValueError("Sólo se puede cancelar un turno PENDIENTE o CONFIRMADO.")
        self._estado = EstadoTurno.CANCELADO

    def marcar_atendido(self):
        if self.estado != EstadoTurno.CONFIRMADO:
            raise ValueError("Sólo se puede atender un turno CONFIRMADO.")
        self._estado = EstadoTurno.ATENDIDO

    def se_superpone_con(self, otro: Turno) -> bool:
        """Compara intervalos; el veterinario decide qué estados bloquean."""
        return (
            self.fecha_hora_inicio < otro.fecha_hora_fin
            and self.fecha_hora_fin > otro.fecha_hora_inicio
        )
