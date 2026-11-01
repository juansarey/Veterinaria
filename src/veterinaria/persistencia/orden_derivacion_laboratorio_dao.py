"""Persistencia de órdenes sin cargar automáticamente sus muestras."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    EstadoOrden,
    OrdenDerivacionLaboratorio,
)


class OrdenDerivacionLaboratorioDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(
        self, orden: OrdenDerivacionLaboratorio, id_atencion: int
    ) -> None:
        if orden.id_orden is None:
            raise ValueError("La orden requiere un id_orden explícito.")

        fecha = orden.fecha_emision
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO orden_derivacion_laboratorio
                    (id_orden, id_atencion, fecha_emision,
                     estudio_solicitado, estado, observaciones)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                orden.id_orden,
                id_atencion,
                fecha.isoformat() if fecha is not None else None,
                orden.estudio_solicitado,
                orden.estado.name,
                orden.observaciones,
            ))

    def obtener_por_id(
        self, id_orden: int
    ) -> OrdenDerivacionLaboratorio | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_orden, fecha_emision, estudio_solicitado,
                       estado, observaciones
                FROM orden_derivacion_laboratorio
                WHERE id_orden = ?
            """, (id_orden,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar_por_atencion(
        self, id_atencion: int
    ) -> list[OrdenDerivacionLaboratorio]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_orden, fecha_emision, estudio_solicitado,
                       estado, observaciones
                FROM orden_derivacion_laboratorio
                WHERE id_atencion = ?
                ORDER BY id_orden
            """, (id_atencion,))
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, orden: OrdenDerivacionLaboratorio) -> bool:
        fecha = orden.fecha_emision
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE orden_derivacion_laboratorio
                SET fecha_emision = ?, estudio_solicitado = ?,
                    estado = ?, observaciones = ?
                WHERE id_orden = ?
            """, (
                fecha.isoformat() if fecha is not None else None,
                orden.estudio_solicitado,
                orden.estado.name,
                orden.observaciones,
                orden.id_orden,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_orden: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM orden_derivacion_laboratorio WHERE id_orden = ?",
                (id_orden,),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> OrdenDerivacionLaboratorio:
        try:
            estado = EstadoOrden[fila["estado"]]
        except KeyError as error:
            raise ValueError(
                f"Estado de orden desconocido: {fila['estado']!r}."
            ) from error

        orden = OrdenDerivacionLaboratorio(
            fila["id_orden"],
            datetime.fromisoformat(fila["fecha_emision"]),
            fila["estudio_solicitado"],
            fila["observaciones"],
        )
        orden._estado = estado
        return orden
