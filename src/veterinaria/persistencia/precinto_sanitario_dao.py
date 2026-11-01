"""Persistencia de precintos sin agregar una relación inversa al dominio."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.transporte.precinto_sanitario import (
    EstadoPrecinto,
    PrecintoSanitario,
)


class PrecintoSanitarioDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, precinto: PrecintoSanitario, id_remito: int) -> None:
        if precinto.id_precinto is None:
            raise ValueError("El precinto requiere un id_precinto explícito.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO precinto_sanitario
                    (id_precinto, id_remito, codigo, estado)
                VALUES (?, ?, ?, ?)
            """, (
                precinto.id_precinto,
                id_remito,
                precinto.codigo,
                precinto.estado.name,
            ))

    def obtener_por_id(self, id_precinto: int) -> PrecintoSanitario | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_precinto, codigo, estado
                FROM precinto_sanitario
                WHERE id_precinto = ?
            """, (id_precinto,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_remito(self, id_remito: int) -> PrecintoSanitario | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_precinto, codigo, estado
                FROM precinto_sanitario
                WHERE id_remito = ?
            """, (id_remito,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def actualizar(self, precinto: PrecintoSanitario) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE precinto_sanitario
                SET codigo = ?, estado = ?
                WHERE id_precinto = ?
            """, (
                precinto.codigo,
                precinto.estado.name,
                precinto.id_precinto,
            ))
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> PrecintoSanitario:
        try:
            estado = EstadoPrecinto[fila["estado"]]
        except KeyError as error:
            raise ValueError(
                f"Estado de precinto desconocido: {fila['estado']!r}."
            ) from error

        precinto = PrecintoSanitario(fila["id_precinto"], fila["codigo"])
        precinto._estado = estado
        return precinto
