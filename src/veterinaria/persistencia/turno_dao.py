"""ABMC de turnos y restauración controlada de su estado persistido."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.turno import EstadoTurno, Turno
from veterinaria.persistencia.mascota_dao import MascotaDAO


class TurnoDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._mascota_dao = MascotaDAO(conexion)

    def crear(self, turno: Turno, id_veterinario: int) -> None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO turno
                    (id_turno, id_mascota, id_veterinario,
                     fecha_hora_inicio, fecha_hora_fin, estado, motivo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                turno.id_turno,
                turno.mascota.id_mascota,
                id_veterinario,
                turno.fecha_hora_inicio.isoformat(),
                turno.fecha_hora_fin.isoformat(),
                turno.estado.name,
                turno.motivo,
            ))

    def obtener_por_id(self, id_turno: int) -> Turno | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_turno, id_mascota, fecha_hora_inicio,
                       fecha_hora_fin, estado, motivo
                FROM turno
                WHERE id_turno = ?
            """, (id_turno,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[Turno]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_turno, id_mascota, fecha_hora_inicio,
                       fecha_hora_fin, estado, motivo
                FROM turno
                ORDER BY id_turno
            """)
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def listar_por_veterinario(self, id_veterinario: int) -> list[Turno]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_turno, id_mascota, fecha_hora_inicio,
                       fecha_hora_fin, estado, motivo
                FROM turno
                WHERE id_veterinario = ?
                ORDER BY id_turno
            """, (id_veterinario,))
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, turno: Turno, id_veterinario: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE turno
                SET id_mascota = ?, id_veterinario = ?,
                    fecha_hora_inicio = ?, fecha_hora_fin = ?,
                    estado = ?, motivo = ?
                WHERE id_turno = ?
            """, (
                turno.mascota.id_mascota,
                id_veterinario,
                turno.fecha_hora_inicio.isoformat(),
                turno.fecha_hora_fin.isoformat(),
                turno.estado.name,
                turno.motivo,
                turno.id_turno,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_turno: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("DELETE FROM turno WHERE id_turno = ?", (id_turno,))
            return cursor.rowcount == 1

    def _desde_fila(self, fila: Row) -> Turno:
        mascota = self._mascota_dao.obtener_por_id(fila["id_mascota"])
        turno = Turno(
            fila["id_turno"],
            datetime.fromisoformat(fila["fecha_hora_inicio"]),
            datetime.fromisoformat(fila["fecha_hora_fin"]),
            mascota,
            fila["motivo"],
        )
        turno._estado = EstadoTurno[fila["estado"]]
        return turno
