"""Persistencia de agendas y sus días mediante una conexión compartida."""

from contextlib import closing
from datetime import time
from sqlite3 import Connection

from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana


class AgendaMedicaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, agenda: AgendaMedica, id_veterinario: int) -> None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO agenda_medica
                    (id_veterinario, hora_desde, hora_hasta)
                VALUES (?, ?, ?)
            """, (
                id_veterinario,
                agenda.hora_desde.isoformat(),
                agenda.hora_hasta.isoformat(),
            ))
            self._insertar_dias(cursor, cursor.lastrowid, agenda.dias_trabajo)

    def obtener_por_veterinario(
        self, id_veterinario: int
    ) -> AgendaMedica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_agenda, hora_desde, hora_hasta
                FROM agenda_medica
                WHERE id_veterinario = ?
            """, (id_veterinario,))
            fila = cursor.fetchone()
            if fila is None:
                return None

            cursor.execute("""
                SELECT dia
                FROM agenda_medica_dia
                WHERE id_agenda = ?
            """, (fila["id_agenda"],))
            dias = {
                DiaSemana[fila_dia["dia"]]
                for fila_dia in cursor.fetchall()
            }

        return AgendaMedica(
            dias,
            time.fromisoformat(fila["hora_desde"]),
            time.fromisoformat(fila["hora_hasta"]),
        )

    def actualizar(self, agenda: AgendaMedica, id_veterinario: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_agenda
                FROM agenda_medica
                WHERE id_veterinario = ?
            """, (id_veterinario,))
            fila = cursor.fetchone()
            if fila is None:
                return False

            id_agenda = fila["id_agenda"]
            cursor.execute("""
                UPDATE agenda_medica
                SET hora_desde = ?, hora_hasta = ?
                WHERE id_agenda = ?
            """, (
                agenda.hora_desde.isoformat(),
                agenda.hora_hasta.isoformat(),
                id_agenda,
            ))
            cursor.execute(
                "DELETE FROM agenda_medica_dia WHERE id_agenda = ?",
                (id_agenda,),
            )
            self._insertar_dias(cursor, id_agenda, agenda.dias_trabajo)
            return True

    def eliminar_por_veterinario(self, id_veterinario: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_agenda
                FROM agenda_medica
                WHERE id_veterinario = ?
            """, (id_veterinario,))
            fila = cursor.fetchone()
            if fila is None:
                return False

            cursor.execute(
                "DELETE FROM agenda_medica_dia WHERE id_agenda = ?",
                (fila["id_agenda"],),
            )
            cursor.execute(
                "DELETE FROM agenda_medica WHERE id_agenda = ?",
                (fila["id_agenda"],),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _insertar_dias(cursor, id_agenda: int, dias_trabajo) -> None:
        cursor.executemany("""
            INSERT INTO agenda_medica_dia (id_agenda, dia)
            VALUES (?, ?)
        """, (
            (id_agenda, dia.name)
            for dia in sorted(dias_trabajo, key=lambda dia: dia.value)
        ))
