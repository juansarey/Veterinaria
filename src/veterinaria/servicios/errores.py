"""Errores de la capa de servicios, pensados para mostrarse al usuario."""


class ErrorNegocio(Exception):
    """Una regla de negocio o validación impidió la operación."""

    def __init__(self, mensaje, campo: str | None = None):
        super().__init__(mensaje)
        self.campo = campo
