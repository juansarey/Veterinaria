"""Clases base: una pantalla/pestaña y una sección con pestañas."""

import traceback

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.servicios.errores import ErrorNegocio


class Pantalla:
    """Una pantalla (o pestaña) = una clase que guarda referencias a sus controles.

    Recoge datos, invoca a un servicio y muestra el resultado; no contiene reglas de
    negocio ni SQL (guía de Flet, sección 9).
    """

    nombre = ""
    icono = ft.Icons.CIRCLE

    def __init__(self, app):
        self.app = app
        self.srv = app.servicios
        self.vista = self.construir()

    def construir(self) -> ft.Control:  # pragma: no cover - lo define cada pantalla
        raise NotImplementedError

    def refrescar(self):
        """Recarga selectores y tablas desde los servicios."""

    def ejecutar(self, accion, exito: str | None = None):
        """Ejecuta una operación mostrando los errores como avisos, sin cerrar la aplicación."""
        try:
            resultado = accion()
        except ErrorNegocio as error:
            self.app.error(str(error))
            self.app.actualizar()
            return None
        except Exception as error:      # error inesperado: se informa y la aplicación sigue
            traceback.print_exc()
            self.app.error(f"Error inesperado: {error}")
            self.app.actualizar()
            return None
        self.refrescar()
        if exito:
            self.app.ok(exito)
        self.app.actualizar()
        return True if resultado is None else resultado


class Seccion(Pantalla):
    """Una entrada del menú lateral con varias pestañas."""

    subtitulo = ""
    PESTANAS: list[type[Pantalla]] = []

    def construir(self):
        self.hijas = [clase(self.app) for clase in self.PESTANAS]
        tabs = ft.Tabs(
            length=len(self.hijas), selected_index=0, expand=True, on_change=self._cambio,
            content=ft.Column(expand=True, controls=[
                ft.TabBar(tabs=[ft.Tab(label=h.nombre, icon=h.icono) for h in self.hijas]),
                ft.TabBarView(expand=True, controls=[
                    ft.Container(h.vista, padding=ft.Padding.only(top=12)) for h in self.hijas]),
            ]))
        return ft.Column(expand=True, spacing=8, controls=[c.titulo(self.nombre, self.subtitulo), tabs])

    def refrescar(self):
        for hija in self.hijas:
            hija.refrescar()

    def _cambio(self, e):
        self.hijas[e.control.selected_index].refrescar()
        self.app.actualizar()
