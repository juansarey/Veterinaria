"""Persistencia de conservadoras isotérmicas sobre una conexión compartida."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)


class ConservadoraIsotermicaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, conservadora: ConservadoraIsotermica) -> None:
        if conservadora.id_conservadora is None:
            raise ValueError("La conservadora requiere un id_conservadora explícito.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO conservadora_isotermica
                    (id_conservadora, codigo, estado)
                VALUES (?, ?, ?)
            """, (
                conservadora.id_conservadora,
                conservadora.codigo,
                conservadora.estado.name,
            ))

    def obtener_por_id(
        self, id_conservadora: int
    ) -> ConservadoraIsotermica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_conservadora, codigo, estado
                FROM conservadora_isotermica
                WHERE id_conservadora = ?
            """, (id_conservadora,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[ConservadoraIsotermica]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_conservadora, codigo, estado
                FROM conservadora_isotermica
                ORDER BY id_conservadora
            """)
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, conservadora: ConservadoraIsotermica) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE conservadora_isotermica
                SET codigo = ?, estado = ?
                WHERE id_conservadora = ?
            """, (
                conservadora.codigo,
                conservadora.estado.name,
                conservadora.id_conservadora,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_conservadora: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM conservadora_isotermica WHERE id_conservadora = ?",
                (id_conservadora,),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> ConservadoraIsotermica:
        try:
            estado = EstadoConservadora[fila["estado"]]
        except KeyError as error:
            raise ValueError(
                f"Estado de conservadora desconocido: {fila['estado']!r}."
            ) from error

        conservadora = ConservadoraIsotermica(
            fila["id_conservadora"], fila["codigo"]
        )
        conservadora._estado = estado
        return conservadora
