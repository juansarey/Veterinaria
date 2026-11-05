"""Ventana principal: menú lateral con cinco secciones y área de contenido."""

import webbrowser
from pathlib import Path
from threading import Timer

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.componentes import COLOR
from veterinaria.interfaz.seccion_atencion import PestanaAtenciones, SeccionAtencion
from veterinaria.interfaz.seccion_laboratorio import PestanaEmpaquetado, SeccionLaboratorio
from veterinaria.interfaz.seccion_personas import SeccionPersonas
from veterinaria.interfaz.seccion_reportes import SeccionReportes
from veterinaria.interfaz.seccion_turnos import PestanaAgenda, SeccionTurnos

SECCIONES = [SeccionPersonas, SeccionTurnos, SeccionAtencion, SeccionLaboratorio, SeccionReportes]


class AplicacionVeterinaria:
    """Coordina las secciones. No conoce SQL ni reglas de negocio: sólo servicios."""

    def __init__(self, page: ft.Page, servicios, ruta_bd):
        self.page = page
        self.servicios = servicios
        self.ruta_bd = ruta_bd
        self.pantallas = [clase(self) for clase in SECCIONES]
        # Las cinco secciones quedan montadas y sólo se alterna su visibilidad. Si se cambiara
        # contenido.content, Flet volvería a montar la sección y enviaría además los cambios hechos
        # mientras estaba oculta: las filas nuevas aparecían duplicadas (p. ej. en Seguimiento).
        for pantalla in self.pantallas:
            pantalla.vista.visible = False
        self.contenido = ft.Container(expand=True, padding=ft.Padding.all(20), content=ft.Column(
            [p.vista for p in self.pantallas], expand=True, spacing=0))
        self.pantalla_actual = None
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
        for otra in self.pantallas:
            otra.vista.visible = otra is pantalla
        self.pantalla_actual = pantalla
        self.actualizar()

    # ------------------------------------------------------------- utilidades
    def refrescar_selectores_profesionales(self):
        """Actualiza sólo las opciones afectadas por una baja, sin reiniciar formularios."""
        vets = self.servicios.clinica.listar_veterinarios()
        clinicas = self.servicios.clinica.listar_clinicas()
        for seccion in self.pantallas:
            for hija in getattr(seccion, "hijas", []):
                if isinstance(hija, PestanaAgenda):
                    c.cargar_selector(hija.vet, vets)
                    c.cargar_selector(hija.filtro_vet, vets)
                    hija._tabla()
                elif isinstance(hija, PestanaAtenciones):
                    c.cargar_selector(hija.vet, vets)
                elif isinstance(hija, PestanaEmpaquetado):
                    c.cargar_selector(hija.clinica, clinicas)
        self.actualizar()

    def actualizar(self):
        self.page.update()

    def ok(self, mensaje: str):
        self._aviso(mensaje, ft.Colors.GREEN_700)

    def error(self, mensaje: str):
        self._aviso(mensaje, ft.Colors.RED_700, duracion=10000)

    def _aviso(self, mensaje: str, color, duracion=4500):
        """Notificación arriba a la derecha (capa superior de la página); reemplaza a la anterior
        y se cierra sola tras ``duracion`` milisegundos o con su botón."""
        self._quitar_de_capa(getattr(self, "_aviso_actual", None))
        icono = ft.Icons.CHECK_CIRCLE if color == ft.Colors.GREEN_700 else ft.Icons.ERROR
        aviso = ft.Container(
            ft.Row([ft.Icon(icono, color=ft.Colors.WHITE, size=22),
                    ft.Text(mensaje, color=ft.Colors.WHITE, size=14, expand=True, no_wrap=False),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=ft.Colors.WHITE, icon_size=18,
                                  tooltip="Cerrar", on_click=lambda e: self._cerrar_aviso(aviso))],
                   spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            data=mensaje, bgcolor=color, border_radius=10, width=400, top=20, right=20,
            padding=ft.Padding.only(left=16, top=8, right=6, bottom=8),
            shadow=ft.BoxShadow(blur_radius=12, spread_radius=1, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)))
        self._aviso_actual = aviso
        self.page.overlay.append(aviso)
        self.actualizar()
        temporizador = Timer(duracion / 1000, lambda: self._cerrar_aviso(aviso))
        temporizador.daemon = True
        temporizador.start()

    def _quitar_de_capa(self, aviso) -> bool:
        for i, control in enumerate(self.page.overlay):
            if control is aviso:
                del self.page.overlay[i]
                return True
        return False

    def _cerrar_aviso(self, aviso):
        if self._quitar_de_capa(aviso):
            try:
                self.actualizar()
            except Exception:  # la ventana pudo cerrarse mientras corría el temporizador
                pass

    def abrir_archivo(self, ruta):
        """Abre un PDF/CSV exportado con el programa predeterminado."""
        try:
            webbrowser.open(Path(ruta).resolve().as_uri())
        except Exception:                    # abrir el archivo es una comodidad, no un requisito
            pass
