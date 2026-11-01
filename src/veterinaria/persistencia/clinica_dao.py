"""ABMC de clínicas sobre una conexión compartida, sin commit automático."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.clinica import Clinica


class ClinicaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, clinica: Clinica) -> None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO clinica (id_clinica, nombre, direccion, telefono)
                VALUES (?, ?, ?, ?)
            """, (
                clinica.id_clinica,
                clinica.nombre,
                clinica.direccion,
                clinica.telefono,
            ))

    def obtener_por_id(self, id_clinica: int) -> Clinica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_clinica, nombre, direccion, telefono
                FROM clinica
                WHERE id_clinica = ?
            """, (id_clinica,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[Clinica]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_clinica, nombre, direccion, telefono
                FROM clinica
                ORDER BY id_clinica
            """)
            return [self._desde_fila(fila) for fila in cursor.fetchall()]

    def actualizar(self, clinica: Clinica) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE clinica
                SET nombre = ?, direccion = ?, telefono = ?
                WHERE id_clinica = ?
            """, (
                clinica.nombre,
                clinica.direccion,
                clinica.telefono,
                clinica.id_clinica,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_clinica: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM clinica WHERE id_clinica = ?", (id_clinica,)
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> Clinica:
        return Clinica(
            fila["id_clinica"],
            fila["nombre"],
            fila["direccion"],
            fila["telefono"],
        )
