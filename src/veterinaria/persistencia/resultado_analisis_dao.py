"""Persistencia del resultado y la muestra ya analizada por el dominio."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO


class ResultadoAnalisisDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._muestra_dao = MuestraBiologicaDAO(conexion)

    def guardar_resultado(self, resultado: ResultadoAnalisis) -> None:
        """Guarda después de registrar_resultado() exitoso; transacción externa."""
        if resultado.id_resultado is None:
            raise ValueError("El resultado requiere un id_resultado explícito.")
        if resultado.muestra.estado.obtener_nombre() != "ANALIZADA":
            raise ValueError("La muestra del resultado debe estar ANALIZADA.")

        fecha = resultado.fecha_resultado
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO resultado_analisis
                    (id_resultado, id_muestra, fecha_resultado,
                     resultado, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, (
                resultado.id_resultado,
                resultado.muestra.id_muestra,
                fecha.isoformat() if fecha is not None else None,
                resultado.resultado,
                resultado.observaciones,
            ))

        if not self._muestra_dao.actualizar(resultado.muestra):
            raise ValueError("La muestra del resultado no existe en persistencia.")

    def obtener_por_id(self, id_resultado: int) -> ResultadoAnalisis | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_resultado, id_muestra, fecha_resultado,
                       resultado, observaciones
                FROM resultado_analisis
                WHERE id_resultado = ?
            """, (id_resultado,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def obtener_por_muestra(self, id_muestra: int) -> ResultadoAnalisis | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_resultado, id_muestra, fecha_resultado,
                       resultado, observaciones
                FROM resultado_analisis
                WHERE id_muestra = ?
            """, (id_muestra,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def _desde_fila(self, fila: Row) -> ResultadoAnalisis:
        muestra = self._muestra_dao.obtener_por_id(fila["id_muestra"])
        if muestra is None:
            raise ValueError("El resultado referencia una muestra inexistente.")
        return ResultadoAnalisis(
            fila["id_resultado"],
            muestra,
            datetime.fromisoformat(fila["fecha_resultado"]),
            fila["resultado"],
            fila["observaciones"],
        )
