"""Persistencia de comprobantes ya emitidos mediante su construcción."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.comprobante_atencion import ComprobanteAtencion
from veterinaria.persistencia.atencion_dao import AtencionDAO


class ComprobanteAtencionDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._atencion_dao = AtencionDAO(conexion)

    def crear(self, comprobante: ComprobanteAtencion) -> None:
        if comprobante.id_comprobante is None:
            raise ValueError("El comprobante requiere un id_comprobante explícito.")

        fecha = comprobante.fecha_emision
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO comprobante_atencion
                    (id_comprobante, id_atencion, fecha_emision)
                VALUES (?, ?, ?)
            """, (
                comprobante.id_comprobante,
                comprobante.atencion.id_atencion,
                fecha.isoformat() if fecha is not None else None,
            ))

    def obtener_por_id(self, id_comprobante: int) -> ComprobanteAtencion | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_comprobante, id_atencion, fecha_emision
                FROM comprobante_atencion
                WHERE id_comprobante = ?
            """, (id_comprobante,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_atencion(self, id_atencion: int) -> ComprobanteAtencion | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_comprobante, id_atencion, fecha_emision
                FROM comprobante_atencion
                WHERE id_atencion = ?
            """, (id_atencion,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def _desde_fila(self, fila: Row) -> ComprobanteAtencion:
        atencion = self._atencion_dao.obtener_por_id(fila["id_atencion"])
        if atencion is None:
            raise ValueError("El comprobante referencia una atención inexistente.")
        return ComprobanteAtencion(
            fila["id_comprobante"],
            atencion,
            datetime.fromisoformat(fila["fecha_emision"]),
        )
