"""Conexiones SQLite sin estado global."""

import sqlite3
from os import PathLike


def abrir_conexion(ruta: str | PathLike[str]) -> sqlite3.Connection:
    """Abre una conexión con FK activas; quien la utiliza debe cerrarla."""
    conexion = sqlite3.connect(ruta)
    conexion.execute("PRAGMA foreign_keys = ON").close()
    conexion.row_factory = sqlite3.Row
    return conexion
