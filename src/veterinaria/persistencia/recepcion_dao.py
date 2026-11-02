"""Persistencia coordinada de la recepción y su cadena de custodia."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO
from veterinaria.persistencia.precinto_sanitario_dao import PrecintoSanitarioDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO


class RecepcionDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._envio_dao = EnvioDAO(conexion)
        self._precinto_dao = PrecintoSanitarioDAO(conexion)
        self._remito_dao = RemitoBiologicoDAO(conexion)
        self._muestra_dao = MuestraBiologicaDAO(conexion)

    def obtener_por_id(self, id_recepcion: int) -> Recepcion | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_recepcion, id_envio, fecha_hora, observaciones
                FROM recepcion
                WHERE id_recepcion = ?
            """, (id_recepcion,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_envio(self, id_envio: int) -> Recepcion | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_recepcion, id_envio, fecha_hora, observaciones
                FROM recepcion
                WHERE id_envio = ?
            """, (id_envio,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def guardar_recepcion(self, recepcion: Recepcion) -> None:
        if recepcion.id_recepcion is None:
            raise ValueError("La recepción requiere un id_recepcion explícito.")

        envio = recepcion.envio
        remito = envio.remito
        precinto = remito.obtener_precinto()
        if precinto is None:
            raise ValueError("La recepción requiere un precinto sanitario.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO recepcion
                    (id_recepcion, id_envio, fecha_hora, observaciones)
                VALUES (?, ?, ?, ?)
            """, (
                recepcion.id_recepcion,
                envio.id_envio,
                recepcion.fecha_hora.isoformat(),
                recepcion.observaciones,
            ))

        if not self._envio_dao.actualizar(envio):
            raise ValueError("El envío de la recepción no existe en persistencia.")
        if not self._precinto_dao.actualizar(precinto):
            raise ValueError("El precinto del remito no existe en persistencia.")
        if not self._remito_dao.actualizar(remito):
            raise ValueError("El remito del envío no existe en persistencia.")

        for muestra in remito.obtener_muestras():
            if not self._muestra_dao.actualizar(muestra):
                raise ValueError(
                    "Una muestra del remito no existe en persistencia."
                )

    def _desde_fila(self, fila: Row) -> Recepcion:
        envio = self._envio_dao.obtener_por_id(fila["id_envio"])
        if envio is None:
            raise ValueError("La recepción referencia un envío inexistente.")
        return Recepcion(
            fila["id_recepcion"],
            envio,
            datetime.fromisoformat(fila["fecha_hora"]),
            fila["observaciones"],
        )
