"""Persistencia de envíos sin ejecutar nuevamente reglas de despacho."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO


class EnvioDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._remito_dao = RemitoBiologicoDAO(conexion)
        self._muestra_dao = MuestraBiologicaDAO(conexion)

    def crear(self, envio: Envio) -> None:
        if envio.id_envio is None:
            raise ValueError("El envío requiere un id_envio explícito.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO envio
                    (id_envio, id_remito, fecha_hora_salida,
                     fecha_hora_llegada, estado, observaciones)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                envio.id_envio,
                envio.remito.id_remito,
                self._fecha_iso(envio.fecha_hora_salida),
                self._fecha_iso(envio.fecha_hora_llegada),
                envio.estado.name,
                envio.observaciones,
            ))

    def obtener_por_id(self, id_envio: int) -> Envio | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_envio, id_remito, fecha_hora_salida,
                       fecha_hora_llegada, estado, observaciones
                FROM envio
                WHERE id_envio = ?
            """, (id_envio,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_remito(self, id_remito: int) -> Envio | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_envio, id_remito, fecha_hora_salida,
                       fecha_hora_llegada, estado, observaciones
                FROM envio
                WHERE id_remito = ?
            """, (id_remito,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def actualizar(self, envio: Envio) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE envio
                SET fecha_hora_salida = ?, fecha_hora_llegada = ?,
                    estado = ?, observaciones = ?
                WHERE id_envio = ?
            """, (
                self._fecha_iso(envio.fecha_hora_salida),
                self._fecha_iso(envio.fecha_hora_llegada),
                envio.estado.name,
                envio.observaciones,
                envio.id_envio,
            ))
            return cursor.rowcount == 1

    def guardar_despacho(self, envio: Envio) -> bool:
        if not self.actualizar(envio):
            return False

        if not self._remito_dao.actualizar(envio.remito):
            raise ValueError("El remito del envío no existe en persistencia.")

        for muestra in envio.remito.obtener_muestras():
            if not self._muestra_dao.actualizar(muestra):
                raise ValueError(
                    "Una muestra del remito no existe en persistencia."
                )
        return True

    def _desde_fila(self, fila: Row) -> Envio:
        try:
            estado = EstadoEnvio[fila["estado"]]
        except KeyError as error:
            raise ValueError(
                f"Estado de envío desconocido: {fila['estado']!r}."
            ) from error

        remito = self._remito_dao.obtener_por_id(fila["id_remito"])
        if remito is None:
            raise ValueError("El envío referencia un remito inexistente.")

        envio = Envio(fila["id_envio"], remito, fila["observaciones"])
        envio.fecha_hora_salida = self._fecha_desde_sql(
            fila["fecha_hora_salida"]
        )
        envio.fecha_hora_llegada = self._fecha_desde_sql(
            fila["fecha_hora_llegada"]
        )
        envio._estado = estado
        return envio

    @staticmethod
    def _fecha_iso(fecha: datetime | None) -> str | None:
        return fecha.isoformat() if fecha is not None else None

    @staticmethod
    def _fecha_desde_sql(fecha: str | None) -> datetime | None:
        return datetime.fromisoformat(fecha) if fecha is not None else None
