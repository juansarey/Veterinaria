"""Persistencia de muestras y administración interna de su historial."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.laboratorio.historial_estado_muestra import (
    HistorialEstadoMuestra,
)
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.patrones.state.estado_muestra import (
    EstadoAnalizada,
    EstadoEmpaquetada,
    EstadoEnTransito,
    EstadoExtraida,
    EstadoRecibida,
    EstadoRechazada,
)


_CLASES_ESTADO = {
    "EXTRAIDA": EstadoExtraida,
    "EMPAQUETADA": EstadoEmpaquetada,
    "EN_TRANSITO": EstadoEnTransito,
    "RECIBIDA": EstadoRecibida,
    "ANALIZADA": EstadoAnalizada,
    "RECHAZADA": EstadoRechazada,
}


class MuestraBiologicaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, muestra: MuestraBiologica, id_orden: int) -> None:
        if muestra.id_muestra is None:
            raise ValueError("La muestra requiere un id_muestra explícito.")

        historial = muestra.obtener_historial()
        nombre_estado = muestra.estado.obtener_nombre()
        self._validar_consistencia(nombre_estado, historial)

        fecha = muestra.fecha_extraccion
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO muestra_biologica
                    (id_muestra, id_orden, id_remito, tipo_muestra,
                     fecha_extraccion, estado_actual, observaciones)
                VALUES (?, ?, NULL, ?, ?, ?, ?)
            """, (
                muestra.id_muestra,
                id_orden,
                muestra.tipo_muestra,
                fecha.isoformat() if fecha is not None else None,
                nombre_estado,
                muestra.observaciones,
            ))
            self._insertar_historial(cursor, muestra.id_muestra, historial)

    def obtener_por_id(self, id_muestra: int) -> MuestraBiologica | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_muestra, tipo_muestra, fecha_extraccion,
                       estado_actual, observaciones
                FROM muestra_biologica
                WHERE id_muestra = ?
            """, (id_muestra,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            historial = self._obtener_historial(cursor, id_muestra)
        return self._desde_fila(fila, historial)

    def listar_por_orden(self, id_orden: int) -> list[MuestraBiologica]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_muestra, tipo_muestra, fecha_extraccion,
                       estado_actual, observaciones
                FROM muestra_biologica
                WHERE id_orden = ?
                ORDER BY id_muestra
            """, (id_orden,))
            filas = cursor.fetchall()
            muestras = [
                self._desde_fila(
                    fila,
                    self._obtener_historial(cursor, fila["id_muestra"]),
                )
                for fila in filas
            ]
        return muestras

    def actualizar(self, muestra: MuestraBiologica) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT estado_actual
                FROM muestra_biologica
                WHERE id_muestra = ?
            """, (muestra.id_muestra,))
            fila = cursor.fetchone()
            if fila is None:
                return False

            historial_persistido = self._obtener_historial(
                cursor, muestra.id_muestra
            )
            historial_objeto = muestra.obtener_historial()
            self._validar_consistencia(
                fila["estado_actual"], historial_persistido
            )
            nombre_estado = muestra.estado.obtener_nombre()
            self._validar_consistencia(nombre_estado, historial_objeto)
            self._validar_prefijo(historial_persistido, historial_objeto)

            fecha = muestra.fecha_extraccion
            cursor.execute("""
                UPDATE muestra_biologica
                SET tipo_muestra = ?, fecha_extraccion = ?,
                    estado_actual = ?, observaciones = ?
                WHERE id_muestra = ?
            """, (
                muestra.tipo_muestra,
                fecha.isoformat() if fecha is not None else None,
                nombre_estado,
                muestra.observaciones,
                muestra.id_muestra,
            ))
            nuevos = historial_objeto[len(historial_persistido):]
            self._insertar_historial(cursor, muestra.id_muestra, nuevos)
            return True

    @staticmethod
    def _obtener_historial(
        cursor, id_muestra: int
    ) -> list[HistorialEstadoMuestra]:
        cursor.execute("""
            SELECT estado, fecha_hora, observaciones
            FROM historial_estado_muestra
            WHERE id_muestra = ?
            ORDER BY fecha_hora, id_historial
        """, (id_muestra,))
        return [
            HistorialEstadoMuestra(
                fila["estado"],
                datetime.fromisoformat(fila["fecha_hora"]),
                fila["observaciones"],
            )
            for fila in cursor.fetchall()
        ]

    @staticmethod
    def _insertar_historial(cursor, id_muestra: int, historial) -> None:
        cursor.executemany("""
            INSERT INTO historial_estado_muestra
                (id_muestra, estado, fecha_hora, observaciones)
            VALUES (?, ?, ?, ?)
        """, [
            (
                id_muestra,
                registro.nombre_estado,
                registro.fecha_hora.isoformat(),
                registro.observaciones,
            )
            for registro in historial
        ])

    @staticmethod
    def _validar_consistencia(
        estado_actual: str,
        historial: list[HistorialEstadoMuestra],
    ) -> None:
        if estado_actual not in _CLASES_ESTADO:
            raise ValueError(f"Estado de muestra desconocido: {estado_actual!r}.")
        if not historial:
            raise ValueError("El historial de la muestra no puede estar vacío.")
        for registro in historial:
            if registro.nombre_estado not in _CLASES_ESTADO:
                raise ValueError(
                    "Estado desconocido en el historial de la muestra: "
                    f"{registro.nombre_estado!r}."
                )
        if historial[0].nombre_estado != "EXTRAIDA":
            raise ValueError("El historial de la muestra debe comenzar en EXTRAIDA.")
        if any(
            actual.fecha_hora < anterior.fecha_hora
            for anterior, actual in zip(historial, historial[1:])
        ):
            raise ValueError(
                "Las fechas del historial deben estar en orden no decreciente."
            )
        if historial[-1].nombre_estado != estado_actual:
            raise ValueError(
                "El último estado del historial no coincide con el estado actual."
            )

    @staticmethod
    def _validar_prefijo(
        persistido: list[HistorialEstadoMuestra],
        objeto: list[HistorialEstadoMuestra],
    ) -> None:
        if len(persistido) > len(objeto):
            raise ValueError(
                "El historial persistido no es prefijo del historial del objeto."
            )
        for guardado, actual in zip(persistido, objeto):
            if guardado != actual:
                raise ValueError(
                    "El historial persistido difiere del historial del objeto."
                )

    @staticmethod
    def _desde_fila(
        fila: Row,
        historial: list[HistorialEstadoMuestra],
    ) -> MuestraBiologica:
        estado_actual = fila["estado_actual"]
        MuestraBiologicaDAO._validar_consistencia(estado_actual, historial)
        estado_recuperado = _CLASES_ESTADO[estado_actual]()
        muestra = MuestraBiologica(
            fila["id_muestra"],
            fila["tipo_muestra"],
            datetime.fromisoformat(fila["fecha_extraccion"]),
            fila["observaciones"],
        )
        muestra._estado = estado_recuperado
        muestra._historial = historial
        return muestra
