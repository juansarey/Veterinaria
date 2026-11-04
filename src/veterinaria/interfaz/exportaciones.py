"""Carpeta y nombres de los archivos exportados (PDF / CSV)."""

from datetime import datetime
from itertools import count
from pathlib import Path


def carpeta_exportacion(ruta_bd) -> Path:
    carpeta = Path(ruta_bd).resolve().parent / "exportaciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def nombre_archivo(base: str, extension: str) -> str:
    return f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"


def exportar_con_nombre_unico(ruta_bd, base: str, extension: str, exportar) -> Path:
    """Reintenta con sufijos; el exportador crea cada archivo en modo exclusivo."""
    carpeta = carpeta_exportacion(ruta_bd)
    nombre = Path(nombre_archivo(base, extension))
    for numero in count():
        ruta = carpeta / (nombre.name if numero == 0 else
                          f"{nombre.stem}_{numero}{nombre.suffix}")
        try:
            exportar(ruta)
        except FileExistsError:
            continue
        return ruta
