"""Carpeta y nombres de los archivos exportados (PDF / CSV)."""

from datetime import datetime
from pathlib import Path


def carpeta_exportacion(ruta_bd) -> Path:
    carpeta = Path(ruta_bd).resolve().parent / "exportaciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def nombre_archivo(base: str, extension: str) -> str:
    return f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
