"""ABMC de vacunas sobre una conexión compartida, sin commit automático."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.vacunacion.vacuna import Vacuna


class VacunaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, vacuna: Vacuna) -> None:
        if vacuna.id_vacuna is None:
            raise ValueError("Vacuna requiere un id_vacuna explícito.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO vacuna (id_vacuna, nombre, especie, obligatoria)
                VALUES (?, ?, ?, ?)
            """, (
                vacuna.id_vacuna,
                vacuna.nombre,
                vacuna.especie,
                vacuna.obligatoria,
            ))

    def obtener_por_id(self, id_vacuna: int) -> Vacuna | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_vacuna, nombre, especie, obligatoria
                FROM vacuna
                WHERE id_vacuna = ?
            """, (id_vacuna,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[Vacuna]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_vacuna, nombre, especie, obligatoria
                FROM vacuna
                ORDER BY id_vacuna
            """)
            return [self._desde_fila(fila) for fila in cursor.fetchall()]

    def actualizar(self, vacuna: Vacuna) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE vacuna
                SET nombre = ?, especie = ?, obligatoria = ?
                WHERE id_vacuna = ?
            """, (
                vacuna.nombre,
                vacuna.especie,
                vacuna.obligatoria,
                vacuna.id_vacuna,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_vacuna: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM vacuna WHERE id_vacuna = ?", (id_vacuna,)
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> Vacuna:
        return Vacuna(
            fila["id_vacuna"],
            fila["nombre"],
            fila["especie"],
            bool(fila["obligatoria"]),
        )
