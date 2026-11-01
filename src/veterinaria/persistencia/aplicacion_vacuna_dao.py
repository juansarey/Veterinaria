"""Persistencia de aplicaciones sin cargar ni modificar su mascota."""

from contextlib import closing
from datetime import date
from sqlite3 import Connection, Row

from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.persistencia.vacuna_dao import VacunaDAO


class AplicacionVacunaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._vacuna_dao = VacunaDAO(conexion)

    def crear(self, aplicacion: AplicacionVacuna, id_mascota: int) -> None:
        if aplicacion.id_aplicacion is None:
            raise ValueError(
                "AplicacionVacuna requiere un id_aplicacion explícito."
            )

        fecha = aplicacion.fecha_aplicacion
        proxima = aplicacion.fecha_proxima_dosis
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO aplicacion_vacuna
                    (id_aplicacion, id_mascota, id_vacuna,
                     fecha_aplicacion, fecha_proxima_dosis)
                VALUES (?, ?, ?, ?, ?)
            """, (
                aplicacion.id_aplicacion,
                id_mascota,
                aplicacion.vacuna.id_vacuna,
                fecha.isoformat() if fecha is not None else None,
                proxima.isoformat() if proxima is not None else None,
            ))

    def obtener_por_id(self, id_aplicacion: int) -> AplicacionVacuna | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_aplicacion, id_vacuna,
                       fecha_aplicacion, fecha_proxima_dosis
                FROM aplicacion_vacuna
                WHERE id_aplicacion = ?
            """, (id_aplicacion,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar_por_mascota(self, id_mascota: int) -> list[AplicacionVacuna]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_aplicacion, id_vacuna,
                       fecha_aplicacion, fecha_proxima_dosis
                FROM aplicacion_vacuna
                WHERE id_mascota = ?
                ORDER BY id_aplicacion
            """, (id_mascota,))
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, aplicacion: AplicacionVacuna) -> bool:
        fecha = aplicacion.fecha_aplicacion
        proxima = aplicacion.fecha_proxima_dosis
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE aplicacion_vacuna
                SET fecha_aplicacion = ?, fecha_proxima_dosis = ?
                WHERE id_aplicacion = ?
            """, (
                fecha.isoformat() if fecha is not None else None,
                proxima.isoformat() if proxima is not None else None,
                aplicacion.id_aplicacion,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_aplicacion: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM aplicacion_vacuna WHERE id_aplicacion = ?",
                (id_aplicacion,),
            )
            return cursor.rowcount == 1

    def _desde_fila(self, fila: Row) -> AplicacionVacuna:
        vacuna = self._vacuna_dao.obtener_por_id(fila["id_vacuna"])
        proxima = fila["fecha_proxima_dosis"]
        return AplicacionVacuna(
            fila["id_aplicacion"],
            vacuna,
            date.fromisoformat(fila["fecha_aplicacion"]),
            date.fromisoformat(proxima) if proxima is not None else None,
        )
