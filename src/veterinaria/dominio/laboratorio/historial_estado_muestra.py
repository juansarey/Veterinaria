from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HistorialEstadoMuestra:
    nombre_estado: str
    fecha_hora: datetime
    observaciones: str = ""
