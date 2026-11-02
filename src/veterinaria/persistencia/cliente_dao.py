"""ABMC de clientes sobre una conexión compartida, sin commit automático."""

from contextlib import closing
from sqlite3 import Connection, Row

from veterinaria.dominio.clinica.cliente import Cliente


class ClienteDAO:
    def __init__(self, conexion: Connection):
        self._conexion = conexion

    def crear(self, cliente: Cliente) -> None:
        if cliente.id_cliente is None:
            raise ValueError("Cliente requiere un id_cliente explícito.")

        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO cliente
                    (id_cliente, nombre, apellido, dni, telefono, email)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cliente.id_cliente, cliente.nombre, cliente.apellido,
                cliente.dni, cliente.telefono, cliente.email,
            ))

    def obtener_por_id(self, id_cliente: int) -> Cliente | None:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_cliente, nombre, apellido, dni, telefono, email
                FROM cliente WHERE id_cliente = ?
            """, (id_cliente,))
            fila = cursor.fetchone()
        return self._desde_fila(fila) if fila is not None else None

    def listar(self) -> list[Cliente]:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                SELECT id_cliente, nombre, apellido, dni, telefono, email
                FROM cliente ORDER BY id_cliente
            """)
            return [self._desde_fila(fila) for fila in cursor.fetchall()]

    def actualizar(self, cliente: Cliente) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute("""
                UPDATE cliente
                SET nombre = ?, apellido = ?, dni = ?, telefono = ?, email = ?
                WHERE id_cliente = ?
            """, (
                cliente.nombre, cliente.apellido, cliente.dni,
                cliente.telefono, cliente.email, cliente.id_cliente,
            ))
            return cursor.rowcount == 1

    def eliminar(self, id_cliente: int) -> bool:
        with closing(self._conexion.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM cliente WHERE id_cliente = ?", (id_cliente,)
            )
            return cursor.rowcount == 1

    @staticmethod
    def _desde_fila(fila: Row) -> Cliente:
        return Cliente(
            fila["id_cliente"], fila["nombre"], fila["apellido"],
            fila["dni"], fila["telefono"], fila["email"],
        )
