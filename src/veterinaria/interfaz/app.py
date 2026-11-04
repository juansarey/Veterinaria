"""Ventana principal: menú lateral con cinco secciones y área de contenido."""

import webbrowser
from pathlib import Path

import flet as ft

from veterinaria.interfaz.componentes import COLOR
from veterinaria.interfaz.seccion_atencion import SeccionAtencion
from veterinaria.interfaz.seccion_laboratorio import SeccionLaboratorio
from veterinaria.interfaz.seccion_personas import SeccionPersonas
from veterinaria.interfaz.seccion_reportes import SeccionReportes
from veterinaria.interfaz.seccion_turnos import SeccionTurnos

SECCIONES = [SeccionPersonas, SeccionTurnos, SeccionAtencion, SeccionLaboratorio, SeccionReportes]


class AplicacionVeterinaria:
    """Coordina las secciones. No conoce SQL ni reglas de negocio: sólo servicios."""

    def __init__(self, page: ft.Page, servicios, ruta_bd):
        self.page = page
        self.servicios = servicios
        self.ruta_bd = ruta_bd
        self.pantallas = [clase(self) for clase in SECCIONES]
        self.contenido = ft.Container(expand=True, padding=ft.Padding.all(20))
        self.riel = ft.NavigationRail(
            selected_index=0, label_type=ft.NavigationRailLabelType.ALL, min_width=104,
            bgcolor=ft.Colors.WHITE, on_change=self._cambio,
            leading=ft.Container(ft.Column([ft.Icon(ft.Icons.PETS, size=34, color=COLOR),
                                            ft.Text("VetRed", weight=ft.FontWeight.BOLD, color=COLOR)],
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                                 padding=ft.Padding.only(top=16, bottom=12)),
            destinations=[ft.NavigationRailDestination(icon=p.icono, label=p.nombre) for p in self.pantallas],
        )

    def iniciar(self):
        self.page.title = "Red de Clínicas Veterinarias y Laboratorio Central"
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
        # Siempre claro: los fondos de la interfaz son claros y, con el tema del sistema en
        # modo oscuro, los textos saldrían en color claro y no se leerían.
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("es", "AR")], current_locale=ft.Locale("es", "AR"))
        self.page.bgcolor = "#F4F7FA"
        self.page.padding = 0
        self.page.add(ft.Row(expand=True, spacing=0, controls=[
            self.riel, ft.VerticalDivider(width=1), self.contenido]))
        self.ir_a(0)

    def _cambio(self, e):
        self.ir_a(self.riel.selected_index)

    def ir_a(self, indice: int):
        pantalla = self.pantallas[indice]
        pantalla.refrescar()                 # datos frescos cada vez que se entra a una sección
        self.contenido.content = pantalla.vista
        self.actualizar()

    # ------------------------------------------------------------- utilidades
    def actualizar(self):
        self.page.update()

    def ok(self, mensaje: str):
        self._aviso(mensaje, ft.Colors.GREEN_700)

    def error(self, mensaje: str):
        self._aviso(mensaje, ft.Colors.RED_700)

    def _aviso(self, mensaje: str, color):
        self.page.show_dialog(ft.SnackBar(ft.Text(mensaje, color=ft.Colors.WHITE), bgcolor=color,
                                          duration=4500))

    def abrir_archivo(self, ruta):
        """Abre un PDF/CSV exportado con el programa predeterminado."""
        try:
            webbrowser.open(Path(ruta).resolve().as_uri())
        except Exception:                    # abrir el archivo es una comodidad, no un requisito
            pass
