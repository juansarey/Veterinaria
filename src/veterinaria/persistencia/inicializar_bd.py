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
            CREATE TABLE IF NOT EXISTS vacuna (
                id_vacuna INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre VARCHAR(100) NOT NULL,
                especie VARCHAR(50) NOT NULL,
                obligatoria INTEGER NOT NULL DEFAULT 0
                    CHECK (obligatoria IN (0, 1))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aplicacion_vacuna (
                id_aplicacion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_mascota INTEGER NOT NULL REFERENCES mascota(id_mascota),
                id_vacuna INTEGER NOT NULL REFERENCES vacuna(id_vacuna),
                fecha_aplicacion TEXT NOT NULL,
                fecha_proxima_dosis TEXT
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orden_derivacion_laboratorio (
                id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
                id_atencion INTEGER NOT NULL REFERENCES atencion(id_atencion),
                fecha_emision TEXT NOT NULL,
                estudio_solicitado VARCHAR(200) NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN (
                    'PENDIENTE', 'EN_PROCESO', 'COMPLETADA', 'CANCELADA'
                )),
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conservadora_isotermica (
                id_conservadora INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo VARCHAR(50) NOT NULL UNIQUE,
                estado TEXT NOT NULL CHECK (estado IN (
                    'DISPONIBLE', 'EN_USO'
                ))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS remito_biologico (
                id_remito INTEGER PRIMARY KEY AUTOINCREMENT,
                id_conservadora INTEGER NOT NULL
                    REFERENCES conservadora_isotermica(id_conservadora),
                id_clinica_origen INTEGER NOT NULL
                    REFERENCES clinica(id_clinica),
                fecha_emision TEXT NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN (
                    'GENERADO', 'DESPACHADO', 'RECIBIDO'
                )),
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS muestra_biologica (
                id_muestra INTEGER PRIMARY KEY AUTOINCREMENT,
                id_orden INTEGER NOT NULL
                    REFERENCES orden_derivacion_laboratorio(id_orden),
                id_remito INTEGER REFERENCES remito_biologico(id_remito),
                tipo_muestra VARCHAR(80) NOT NULL,
                fecha_extraccion TEXT NOT NULL,
                estado_actual TEXT NOT NULL CHECK (estado_actual IN (
                    'EXTRAIDA', 'EMPAQUETADA', 'EN_TRANSITO',
                    'RECIBIDA', 'ANALIZADA', 'RECHAZADA'
                )),
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS precinto_sanitario (
                id_precinto INTEGER PRIMARY KEY AUTOINCREMENT,
                id_remito INTEGER NOT NULL UNIQUE
                    REFERENCES remito_biologico(id_remito),
                codigo VARCHAR(50) NOT NULL UNIQUE,
                estado TEXT NOT NULL CHECK (estado IN (
                    'INTACTO', 'ROTO'
                ))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_estado_muestra (
                id_historial INTEGER PRIMARY KEY AUTOINCREMENT,
                id_muestra INTEGER NOT NULL
                    REFERENCES muestra_biologica(id_muestra),
                estado TEXT NOT NULL CHECK (estado IN (
                    'EXTRAIDA', 'EMPAQUETADA', 'EN_TRANSITO',
                    'RECIBIDA', 'ANALIZADA', 'RECHAZADA'
                )),
                fecha_hora TEXT NOT NULL,
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS envio (
                id_envio INTEGER PRIMARY KEY AUTOINCREMENT,
                id_remito INTEGER NOT NULL UNIQUE
                    REFERENCES remito_biologico(id_remito),
                fecha_hora_salida TEXT,
                fecha_hora_llegada TEXT,
                estado TEXT NOT NULL CHECK (estado IN (
                    'PENDIENTE', 'EN_TRANSITO', 'ENTREGADO'
                )),
                observaciones TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recepcion (
                id_recepcion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_envio INTEGER NOT NULL UNIQUE
                    REFERENCES envio(id_envio),
                fecha_hora TEXT NOT NULL,
                observaciones TEXT
            )
        """)
