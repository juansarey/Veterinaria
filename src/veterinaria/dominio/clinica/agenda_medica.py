from datetime import time
from enum import Enum


class DiaSemana(Enum):
    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6


class AgendaMedica:
    def __init__(self, dias_trabajo: set[DiaSemana], hora_desde: time, hora_hasta: time):
        
        if hora_hasta <= hora_desde:
            raise ValueError("hora_hasta debe ser mayor que hora_desde.")

        self._dias_trabajo = dias_trabajo.copy()
        self._hora_desde = hora_desde
        self._hora_hasta = hora_hasta

    @property
    def dias_trabajo(self):
        return self._dias_trabajo.copy()

    @property
    def hora_desde(self):
        return self._hora_desde

    @property
    def hora_hasta(self):
        return self._hora_hasta

    def contiene(self, turno):
        inicio = turno.fecha_hora_inicio
        fin = turno.fecha_hora_fin

        dia_turno = DiaSemana(inicio.weekday())

        return (
            inicio.date() == fin.date()
            and dia_turno in self.dias_trabajo
            and inicio.time() >= self.hora_desde
            and fin.time() <= self.hora_hasta
        )
