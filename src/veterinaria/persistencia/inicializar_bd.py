"""Tablas de los incrementos de persistencia implementados, según el DER."""

from contextlib import closing
from sqlite3 import Connection


def inicializar_bd(conexion: Connection) -> None:
    """Crea las tablas implementadas sin confirmar transacciones del llamador."""
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historia_clinica (
                id_historia INTEGER PRIMARY KEY AUTOINCREMENT,
                id_mascota INTEGER NOT NULL UNIQUE
                    REFERENCES mascota(id_mascota),
                fecha_apertura TEXT NOT NULL,
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clinica (
                id_clinica INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre VARCHAR(100) NOT NULL,
                direccion VARCHAR(200) NOT NULL,
                telefono VARCHAR(30)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS veterinario (
                id_veterinario INTEGER PRIMARY KEY AUTOINCREMENT,
                id_clinica INTEGER NOT NULL REFERENCES clinica(id_clinica),
                nombre VARCHAR(80) NOT NULL,
                apellido VARCHAR(80) NOT NULL,
                matricula VARCHAR(30) NOT NULL UNIQUE,
                especialidad VARCHAR(100)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS atencion (
                id_atencion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_historia INTEGER NOT NULL
                    REFERENCES historia_clinica(id_historia),
                id_veterinario INTEGER NOT NULL
                    REFERENCES veterinario(id_veterinario),
                fecha_hora TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN (
                    'CONSULTA', 'CONTROL', 'URGENCIA'
                )),
                motivo VARCHAR(200),
                diagnostico TEXT,
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agenda_medica (
                id_agenda INTEGER PRIMARY KEY AUTOINCREMENT,
                id_veterinario INTEGER NOT NULL UNIQUE
                    REFERENCES veterinario(id_veterinario),
                hora_desde TEXT NOT NULL,
                hora_hasta TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agenda_medica_dia (
                id_agenda INTEGER NOT NULL REFERENCES agenda_medica(id_agenda),
                dia TEXT NOT NULL CHECK (dia IN (
                    'LUNES', 'MARTES', 'MIERCOLES', 'JUEVES',
                    'VIERNES', 'SABADO', 'DOMINGO'
                )),
                PRIMARY KEY (id_agenda, dia)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS turno (
                id_turno INTEGER PRIMARY KEY AUTOINCREMENT,
                id_mascota INTEGER NOT NULL REFERENCES mascota(id_mascota),
                id_veterinario INTEGER NOT NULL
                    REFERENCES veterinario(id_veterinario),
                fecha_hora_inicio TEXT NOT NULL,
                fecha_hora_fin TEXT NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN (
                    'PENDIENTE', 'CONFIRMADO', 'ATENDIDO', 'CANCELADO'
                )),
                motivo VARCHAR(200)
            )
        """)
