"""ABMC de veterinarios sin cargar automáticamente sus asociaciones."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.veterinario import Veterinario


class VeterinarioDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, veterinario: Veterinario, id_clinica: int) -> None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO veterinario
                    (id_veterinario, id_clinica, nombre, apellido,
                     matricula, especialidad)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                veterinario.id_veterinario,
                id_clinica,
                veterinario.nombre,
                veterinario.apellido,
                veterinario.matricula,
                veterinario.especialidad,
            ))

    def obtener_por_id(self, id_veterinario: int) -> Veterinario | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_veterinario, nombre, apellido, matricula, especialidad
                FROM veterinario
                WHERE id_veterinario = ?
            """, (id_veterinario,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[Veterinario]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_veterinario, nombre, apellido, matricula, especialidad
                FROM veterinario
                ORDER BY id_veterinario
            """)
            return [self._desde_fila(fila) for fila in cursor.fetchall()]

    def listar_por_clinica(self, id_clinica: int) -> list[Veterinario]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_veterinario, nombre, apellido, matricula, especialidad
                FROM veterinario
                WHERE id_clinica = ?
                ORDER BY id_veterinario
            """, (id_clinica,))
            return [self._desde_fila(fila) for fila in cursor.fetchall()]

    def actualizar(self, veterinario: Veterinario, id_clinica: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE veterinario
                SET id_clinica = ?, nombre = ?, apellido = ?,
                    matricula = ?, especialidad = ?
                WHERE id_veterinario = ?
            """, (
                id_clinica,
                veterinario.nombre,
                veterinario.apellido,
                veterinario.matricula,
                veterinario.especialidad,
                veterinario.id_veterinario,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_veterinario: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM veterinario WHERE id_veterinario = ?",
                (id_veterinario,),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> Veterinario:
        return Veterinario(
            fila["id_veterinario"],
            fila["nombre"],
            fila["apellido"],
            fila["matricula"],
            fila["especialidad"],
        )
