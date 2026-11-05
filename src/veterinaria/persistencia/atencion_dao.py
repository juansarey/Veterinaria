"""ABMC de atenciones y recuperación de su veterinario indispensable."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.persistencia.orden_derivacion_laboratorio_dao import (
    OrdenDerivacionLaboratorioDAO,
)
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO


class AtencionDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._veterinario_dao = VeterinarioDAO(conexion)
        self._orden_dao = OrdenDerivacionLaboratorioDAO(conexion)

    def crear(self, atencion: Atencion, id_historia: int) -> None:
        if atencion.id_atencion is None:
            raise ValueError("Atencion requiere un id_atencion explícito.")

        fecha_hora = atencion.fecha_hora
        tipo = atencion.tipo
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO atencion
                    (id_atencion, id_historia, id_veterinario, fecha_hora,
                     tipo, motivo, diagnostico, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                atencion.id_atencion,
                id_historia,
                atencion.veterinario.id_veterinario,
                fecha_hora.isoformat() if fecha_hora is not None else None,
                tipo.name if tipo is not None else None,
                atencion.motivo,
                atencion.diagnostico,
                atencion.observaciones,
            ))

    def obtener_por_id(self, id_atencion: int) -> Atencion | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_atencion, id_veterinario, fecha_hora, tipo,
                       motivo, diagnostico, observaciones
                FROM atencion
                WHERE id_atencion = ?
            """, (id_atencion,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self, *, cargar_ordenes: bool = False) -> list[Atencion]:
        """Recupera opcionalmente órdenes sin volver a asociarlas por dominio."""
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_atencion, id_veterinario, fecha_hora, tipo,
                       motivo, diagnostico, observaciones
                FROM atencion
                ORDER BY id_atencion
            """)
            filas = cursor.fetchall()
        atenciones = [self._desde_fila(fila) for fila in filas]
        if cargar_ordenes:
            for atencion in atenciones:
                atencion._ordenes_derivacion = (
                    self._orden_dao.listar_por_atencion(atencion.id_atencion)
                )
        return atenciones

    def existe_por_veterinario(self, id_veterinario: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "SELECT 1 FROM atencion WHERE id_veterinario = ? LIMIT 1",
                (id_veterinario,),
            )
            return cursor.fetchone() is not None

    def listar_por_historia(self, id_historia: int) -> list[Atencion]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_atencion, id_veterinario, fecha_hora, tipo,
                       motivo, diagnostico, observaciones
                FROM atencion
                WHERE id_historia = ?
                ORDER BY id_atencion
            """, (id_historia,))
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, atencion: Atencion) -> bool:
        fecha_hora = atencion.fecha_hora
        tipo = atencion.tipo
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE atencion
                SET id_veterinario = ?, fecha_hora = ?, tipo = ?,
                    motivo = ?, diagnostico = ?, observaciones = ?
                WHERE id_atencion = ?
            """, (
                atencion.veterinario.id_veterinario,
                fecha_hora.isoformat() if fecha_hora is not None else None,
                tipo.name if tipo is not None else None,
                atencion.motivo,
                atencion.diagnostico,
                atencion.observaciones,
                atencion.id_atencion,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_atencion: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM atencion WHERE id_atencion = ?", (id_atencion,)
            )
            return cursor.rowcount == 1

    def _desde_fila(self, fila: Row) -> Atencion:
        veterinario = self._veterinario_dao.obtener_por_id(
            fila["id_veterinario"]
        )
        return Atencion(
            fila["id_atencion"],
            datetime.fromisoformat(fila["fecha_hora"]),
            TipoAtencion[fila["tipo"]],
            fila["motivo"],
            veterinario,
            fila["diagnostico"],
            fila["observaciones"],
        )
