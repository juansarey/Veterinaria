"""ABMC de mascotas y recuperación de su responsable."""

from contextlib import closing
from datetime import date
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.persistencia.aplicacion_vacuna_dao import AplicacionVacunaDAO
from veterinaria.persistencia.cliente_dao import ClienteDAO


class MascotaDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion
        self._cliente_dao = ClienteDAO(conexion)
        self._aplicacion_dao = AplicacionVacunaDAO(conexion)

    def crear(self, mascota: Mascota) -> None:
        fecha = mascota.fecha_nacimiento
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO mascota
                    (id_mascota, id_cliente, nombre, especie, raza,
                     fecha_nacimiento, sexo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                mascota.id_mascota, mascota.responsable.id_cliente,
                mascota.nombre, mascota.especie, mascota.raza,
                fecha.isoformat() if fecha is not None else None, mascota.sexo,
            ))

    def obtener_por_id(self, id_mascota: int) -> Mascota | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_mascota, id_cliente, nombre, especie, raza,
                       fecha_nacimiento, sexo
                FROM mascota WHERE id_mascota = ?
            """, (id_mascota,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self, *, cargar_aplicaciones: bool = False) -> list[Mascota]:
        """Recupera opcionalmente aplicaciones sin volver a registrarlas."""
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_mascota, id_cliente, nombre, especie, raza,
                       fecha_nacimiento, sexo
                FROM mascota ORDER BY id_mascota
            """)
            filas = cursor.fetchall()
        mascotas = [self._desde_fila(fila) for fila in filas]
        if cargar_aplicaciones:
            for mascota in mascotas:
                mascota._aplicaciones_vacuna = (
                    self._aplicacion_dao.listar_por_mascota(mascota.id_mascota)
                )
        return mascotas

    def actualizar(self, mascota: Mascota) -> bool:
        fecha = mascota.fecha_nacimiento
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE mascota
                SET id_cliente = ?, nombre = ?, especie = ?, raza = ?,
                    fecha_nacimiento = ?, sexo = ?
                WHERE id_mascota = ?
            """, (
                mascota.responsable.id_cliente, mascota.nombre, mascota.especie,
                mascota.raza, fecha.isoformat() if fecha is not None else None,
                mascota.sexo, mascota.id_mascota,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_mascota: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM mascota WHERE id_mascota = ?", (id_mascota,)
            )
            return cursor.rowcount == 1

    def _desde_fila(self, fila: Row) -> Mascota:
        responsable = self._cliente_dao.obtener_por_id(fila["id_cliente"])
        fecha = fila["fecha_nacimiento"]
        return Mascota(
            fila["id_mascota"], fila["nombre"], fila["especie"], responsable,
            fila["raza"], date.fromisoformat(fecha) if fecha is not None else None,
            fila["sexo"],
        )
