"""ABMC de historias clínicas sin cargar automáticamente sus atenciones."""

from contextlib import closing
from datetime import date
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica


class HistoriaClinicaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, historia: HistoriaClinica, id_mascota: int) -> None:
        fecha = historia.fecha_apertura
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO historia_clinica
                    (id_historia, id_mascota, fecha_apertura, observaciones)
                VALUES (?, ?, ?, ?)
            """, (
                historia.id_historia,
                id_mascota,
                fecha.isoformat() if fecha is not None else None,
                historia.observaciones,
            ))

    def obtener_por_id(self, id_historia: int) -> HistoriaClinica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_historia, fecha_apertura, observaciones
                FROM historia_clinica
                WHERE id_historia = ?
            """, (id_historia,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_mascota(self, id_mascota: int) -> HistoriaClinica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_historia, fecha_apertura, observaciones
                FROM historia_clinica
                WHERE id_mascota = ?
            """, (id_mascota,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def actualizar(self, historia: HistoriaClinica) -> bool:
        fecha = historia.fecha_apertura
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE historia_clinica
                SET fecha_apertura = ?, observaciones = ?
                WHERE id_historia = ?
            """, (
                fecha.isoformat() if fecha is not None else None,
                historia.observaciones,
                historia.id_historia,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_historia: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM historia_clinica WHERE id_historia = ?",
                (id_historia,),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> HistoriaClinica:
        return HistoriaClinica(
            fila["id_historia"],
            date.fromisoformat(fila["fecha_apertura"]),
            fila["observaciones"],
        )
