from enum import Enum


class TipoAtencion(Enum):
    CONSULTA = "CONSULTA"
    CONTROL = "CONTROL"
    URGENCIA = "URGENCIA"


class Atencion:
    def __init__(
        self,
        id_atencion: int,
        fecha_hora,
        tipo: TipoAtencion,
        motivo: str,
        veterinario,
        diagnostico: str = "",
        observaciones: str = "",
    ):
        if veterinario is None:
            raise ValueError("Una atención debe tener un veterinario.")

        self.id_atencion = id_atencion
        self.fecha_hora = fecha_hora
        self.tipo = tipo
        self.motivo = motivo
        self.diagnostico = diagnostico
        self.observaciones = observaciones
        self.veterinario = veterinario

    def registrar_diagnostico(self, diagnostico):
        self.diagnostico = diagnostico
