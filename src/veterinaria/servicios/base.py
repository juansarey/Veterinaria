"""Infraestructura común de los servicios: conexión, transacciones e IDs."""

import sqlite3
import re
import unicodedata
from contextlib import contextmanager
from datetime import datetime

from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.inicializar_bd import inicializar_bd
from veterinaria.servicios.errores import ErrorNegocio

# Nombres fijos de tabla/columna; nunca provienen del usuario.
_TABLAS_ID = {
    "cliente": "id_cliente",
    "mascota": "id_mascota",
    "clinica": "id_clinica",
    "veterinario": "id_veterinario",
    "turno": "id_turno",
    "historia_clinica": "id_historia",
    "atencion": "id_atencion",
    "vacuna": "id_vacuna",
    "aplicacion_vacuna": "id_aplicacion",
    "orden_derivacion_laboratorio": "id_orden",
    "muestra_biologica": "id_muestra",
    "conservadora_isotermica": "id_conservadora",
    "precinto_sanitario": "id_precinto",
    "remito_biologico": "id_remito",
    "envio": "id_envio",
    "recepcion": "id_recepcion",
    "resultado_analisis": "id_resultado",
    "comprobante_atencion": "id_comprobante",
}


class ServicioBase:
    """Abre la conexión, confirma o revierte cada operación y genera IDs.

    Cada método público de un servicio es una unidad de trabajo: abre una
    conexión, ejecuta dominio + DAO y hace commit; ante cualquier error hace
    rollback y lo informa como ``ErrorNegocio``. Los objetos de dominio se
    vuelven a leer en cada operación, por lo que un rollback nunca deja
    objetos Python inconsistentes.
    """

    def __init__(self, ruta_bd):
        self._ruta = str(ruta_bd)
        if self._ruta == ":memory:":
            raise ValueError("Los servicios requieren una base en archivo.")
        con = abrir_conexion(self._ruta)
        try:
            inicializar_bd(con)
            con.commit()
        finally:
            con.close()

    @contextmanager
    def _tx(self):
        con = abrir_conexion(self._ruta)
        try:
            yield con
            con.commit()
        except ErrorNegocio:
            con.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            con.rollback()
            raise ErrorNegocio(_traducir_integridad(exc)) from exc
        except ValueError as exc:
            con.rollback()
            raise ErrorNegocio(str(exc)) from exc
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def _lectura(self):
        con = abrir_conexion(self._ruta)
        try:
            yield con
        finally:
            con.close()

    @staticmethod
    def _siguiente_id(con, tabla: str) -> int:
        columna = _TABLAS_ID[tabla]
        fila = con.execute(
            f"SELECT COALESCE(MAX({columna}), 0) + 1 FROM {tabla}"
        ).fetchone()
        return int(fila[0])


def _traducir_integridad(exc: sqlite3.IntegrityError) -> str:
    texto = str(exc)
    if "UNIQUE" in texto:
        return "Ya existe un registro con ese valor único (por ejemplo DNI, matrícula o código)."
    if "FOREIGN KEY" in texto:
        return "El registro está relacionado con otros datos y no puede modificarse o eliminarse así."
    if "NOT NULL" in texto:
        return "Falta completar un dato obligatorio."
    return f"No se pudo guardar por una restricción de integridad: {texto}"


def validar_texto(valor, campo: str, maximo: int | None = None, obligatorio=False) -> str:
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ErrorNegocio(f"El campo «{campo}» debe ser texto.", campo)
    texto = valor.strip()
    if obligatorio and not texto:
        raise ErrorNegocio(f"El campo «{campo}» es obligatorio.", campo)
    if maximo is not None and len(texto) > maximo:
        raise ErrorNegocio(f"«{campo}» admite como máximo {maximo} caracteres.", campo)
    return texto


def requerir_texto(valor, campo: str, maximo: int | None = None) -> str:
    return validar_texto(valor, campo, maximo, obligatorio=True)


def validar_nombre_persona(valor, campo: str) -> str:
    texto = unicodedata.normalize("NFC", requerir_texto(valor, campo))
    texto = re.sub(" +", " ", texto)
    validar_texto(texto, campo, 80)
    letra_anterior = False
    for caracter in texto:
        categoria = unicodedata.category(caracter)
        if categoria.startswith("L"):
            letra_anterior = True
        elif categoria.startswith("M") and letra_anterior:
            continue
        elif caracter in " -‐‑'’" and letra_anterior:
            letra_anterior = False
        else:
            raise ErrorNegocio(
                f"«{campo}» sólo admite letras, espacios, guiones y apóstrofes entre letras.", campo)
    if not letra_anterior:
        raise ErrorNegocio(f"«{campo}» debe terminar en una letra.", campo)
    return texto


def validar_dni(valor) -> str:
    texto = requerir_texto(valor, "DNI")
    if re.fullmatch(r"[0-9]{7,8}", texto) is None:
        raise ErrorNegocio("DNI: ingrese 7 u 8 dígitos, sin puntos ni espacios internos.", "DNI")
    return texto


def validar_telefono(valor) -> str:
    texto = validar_texto(valor, "Teléfono", 30)
    if texto and (re.fullmatch(r"\+?[0-9 ()-]+", texto) is None
                  or not any(c in "0123456789" for c in texto)):
        raise ErrorNegocio(
            "Teléfono: use números y, si corresponde, +, espacios, paréntesis o guiones.", "Teléfono")
    return texto


def validar_email(valor) -> str:
    texto = validar_texto(valor, "Email", 120)
    if not texto:
        return texto
    valido = texto.count("@") == 1 and not any(
        c.isspace() or unicodedata.category(c).startswith("C") for c in texto)
    if valido:
        usuario, dominio = texto.split("@")
        try:
            etiquetas = dominio.encode("idna").decode("ascii").split(".")
        except UnicodeError:
            etiquetas = []
        valido = (bool(usuario) and not usuario.startswith(".") and not usuario.endswith(".")
                  and ".." not in usuario and not any(c in '<>()[]\\,;:"' for c in usuario)
                  and bool(etiquetas) and all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", e)
                                              for e in etiquetas))
    if not valido:
        raise ErrorNegocio("Ingrese un correo con formato usuario@dominio, sin espacios.", "Email")
    return texto


def fmt_fecha_hora(valor) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if isinstance(valor, datetime) else (
        valor.strftime("%d/%m/%Y") if valor is not None else ""
    )


def ahora() -> datetime:
    """Fecha y hora actuales al minuto, igual que las que se ingresan en la interfaz."""
    return datetime.now().replace(second=0, microsecond=0)
