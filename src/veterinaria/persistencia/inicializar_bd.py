"""Tablas del primer incremento de persistencia, según el DER."""

from contextlib import closing
from sqlite3 import Connection


def inicializar_bd(conexion: Connection) -> None:
    """Crea cliente y mascota sin confirmar transacciones del llamador."""
    with closing(conexion.cursor()) as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cliente (
                id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre VARCHAR(80) NOT NULL,
                apellido VARCHAR(80) NOT NULL,
                dni VARCHAR(20) UNIQUE,
                telefono VARCHAR(30),
                email VARCHAR(120)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mascota (
                id_mascota INTEGER PRIMARY KEY AUTOINCREMENT,
                id_cliente INTEGER NOT NULL REFERENCES cliente(id_cliente),
                nombre VARCHAR(80) NOT NULL,
                especie VARCHAR(50) NOT NULL,
                raza VARCHAR(80),
                fecha_nacimiento TEXT,
                sexo VARCHAR(20)
            )
        """)
