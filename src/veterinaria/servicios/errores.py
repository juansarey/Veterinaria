"""Errores de la capa de servicios, pensados para mostrarse al usuario."""


class ErrorNegocio(Exception):
    """Una regla de negocio o validación impidió la operación."""
