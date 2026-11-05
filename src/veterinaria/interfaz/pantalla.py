"""Clases base: una pantalla/pestaña y una sección con pestañas."""

import traceback
from threading import Lock

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
        self._bloqueo_accion = Lock()
        self.vista = self.construir()

    def construir(self) -> ft.Control:  # pragma: no cover - lo define cada pantalla
        raise NotImplementedError

    def refrescar(self):
        """Recarga selectores y tablas desde los servicios."""

    def ejecutar(self, accion, exito: str | None = None, campos=None, mensaje_error=None):
        """Ejecuta una operación mostrando los errores como avisos, sin cerrar la aplicación."""
        for control in (campos or {}).values():
            c.revisar_error(control)
        try:
            resultado = accion()
        except ErrorNegocio as error:
            control = (campos or {}).get(error.campo)
            if control is not None:
                c.establecer_error(control, str(error))
            self.app.error(mensaje_error or str(error))
            self.app.actualizar()
            if control is not None:
                c.enfocar_control(self.app.page, control)
            return None
        except OSError:
            traceback.print_exc()
            self.app.error(mensaje_error or "No se pudo completar la operación. Revise los permisos y la ubicación "
                           "del archivo y vuelva a intentar.")
            self.app.actualizar()
            return None
        except Exception:      # el detalle técnico queda en consola
            traceback.print_exc()
            self.app.error(mensaje_error or "No se pudo completar esta acción. Vuelva a intentar; "
                           "si el problema continúa, consulte el diagnóstico de la aplicación.")
            self.app.actualizar()
            return None
        for control in (campos or {}).values():
            c.establecer_error(control, None)
        actualizado = True
        try:
            self.refrescar()
        except Exception:
            traceback.print_exc()
            actualizado = False
        if exito:
            self.app.ok(exito)
        if not actualizado:
            self.app.error("La operación se completó, pero no se pudo actualizar la vista. "
                           "Vuelva a abrir esta sección; no repita el registro.")
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
                    ft.Container(h.vista, padding=ft.Padding.only(top=12), expand=True) for h in self.hijas]),
            ]))
        return ft.Column(expand=True, spacing=8, controls=[c.titulo(self.nombre, self.subtitulo), tabs])

    def refrescar(self):
        for hija in self.hijas:
            hija.refrescar()

    def _cambio(self, e):
        self.hijas[e.control.selected_index].refrescar()
        self.app.actualizar()
