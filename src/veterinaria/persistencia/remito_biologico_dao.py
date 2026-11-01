"""Persistencia del agregado RemitoBiologico sin repetir reglas de negocio."""

from contextlib import closing
from datetime import datetime
from sqlite3 import Connection, Row

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.remito_biologico import (
    EstadoRemito,
    RemitoBiologico,
)
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.conservadora_isotermica_dao import (
    ConservadoraIsotermicaDAO,
)
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO
from veterinaria.persistencia.precinto_sanitario_dao import PrecintoSanitarioDAO


class RemitoBiologicoDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._clinica_dao = ClinicaDAO(conexion)
        self._conservadora_dao = ConservadoraIsotermicaDAO(conexion)
        self._precinto_dao = PrecintoSanitarioDAO(conexion)
        self._muestra_dao = MuestraBiologicaDAO(conexion)

    def crear(self, remito: RemitoBiologico) -> None:
        if remito.id_remito is None:
            raise ValueError("El remito requiere un id_remito explícito.")

        fecha = remito.fecha_emision
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO remito_biologico
                    (id_remito, id_conservadora, id_clinica_origen,
                     fecha_emision, estado, observaciones)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                remito.id_remito,
                remito.conservadora.id_conservadora,
                remito.clinica_origen.id_clinica,
                fecha.isoformat() if fecha is not None else None,
                remito.estado.name,
                remito.observaciones,
            ))
        self._conservadora_dao.actualizar(remito.conservadora)

    def obtener_por_id(self, id_remito: int) -> RemitoBiologico | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_remito, id_conservadora, id_clinica_origen,
                       fecha_emision, estado, observaciones
                FROM remito_biologico
                WHERE id_remito = ?
            """, (id_remito,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[RemitoBiologico]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_remito, id_conservadora, id_clinica_origen,
                       fecha_emision, estado, observaciones
                FROM remito_biologico
                ORDER BY id_remito
            """)
            filas = cursor.fetchall()
        return [self._desde_fila(fila) for fila in filas]

    def actualizar(self, remito: RemitoBiologico) -> bool:
        fecha = remito.fecha_emision
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE remito_biologico
                SET fecha_emision = ?, estado = ?, observaciones = ?
                WHERE id_remito = ?
            """, (
                fecha.isoformat() if fecha is not None else None,
                remito.estado.name,
                remito.observaciones,
                remito.id_remito,
            ))
            return cursor.rowcount == 1

    def guardar_muestra_asociada(
        self, remito: RemitoBiologico, muestra: MuestraBiologica
    ) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "SELECT 1 FROM remito_biologico WHERE id_remito = ?",
                (remito.id_remito,),
            )
            if cursor.fetchone() is None:
                raise ValueError("El remito no existe en persistencia.")

            cursor.execute("""
                SELECT id_remito FROM muestra_biologica WHERE id_muestra = ?
            """, (muestra.id_muestra,))
            fila_muestra = cursor.fetchone()
            if fila_muestra is None:
                raise ValueError("La muestra no existe en persistencia.")

            if not any(
                registrada is muestra for registrada in remito.obtener_muestras()
            ):
                raise ValueError("La muestra no pertenece al remito en el dominio.")

            id_remito_actual = fila_muestra["id_remito"]
            if id_remito_actual not in (None, remito.id_remito):
                raise ValueError("La muestra ya pertenece a otro remito.")

        if not self._muestra_dao.actualizar(muestra):
            raise ValueError("La muestra no existe en persistencia.")

        if id_remito_actual is None:
            with closing(self._conexion.cursor()) as cursor:
                cursor.execute("""
                    UPDATE muestra_biologica
                    SET id_remito = ?
                    WHERE id_muestra = ? AND id_remito IS NULL
                """, (remito.id_remito, muestra.id_muestra))
                if cursor.rowcount != 1:
                    raise ValueError("No se pudo asociar la muestra al remito.")
        return True

    def _desde_fila(self, fila: Row) -> RemitoBiologico:
        try:
            estado = EstadoRemito[fila["estado"]]
        except KeyError as error:
            raise ValueError(
                f"Estado de remito desconocido: {fila['estado']!r}."
            ) from error

        clinica = self._clinica_dao.obtener_por_id(fila["id_clinica_origen"])
        conservadora = self._conservadora_dao.obtener_por_id(
            fila["id_conservadora"]
        )
        if clinica is None or conservadora is None:
            raise ValueError("El remito referencia asociaciones inexistentes.")

        remito = RemitoBiologico.__new__(RemitoBiologico)
        remito.id_remito = fila["id_remito"]
        remito.clinica_origen = clinica
        remito.conservadora = conservadora
        remito.fecha_emision = datetime.fromisoformat(fila["fecha_emision"])
        remito.observaciones = fila["observaciones"]
        remito._estado = estado
        remito._precinto = self._precinto_dao.obtener_por_remito(
            fila["id_remito"]
        )
        remito._muestras = self._muestra_dao.listar_por_remito(
            fila["id_remito"]
        )
        return remito
