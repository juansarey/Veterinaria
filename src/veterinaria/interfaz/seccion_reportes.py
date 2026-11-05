"""Reportes de gestión (Strategy) con vista previa y exportación a PDF y CSV."""

from datetime import date

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.exportaciones import exportar_con_nombre_unico
from veterinaria.interfaz.pantalla import Pantalla
from veterinaria.servicios.exportador import exportar_csv, exportar_pdf

REPORTES = {
    "atenciones": "Atenciones y derivaciones",
    "rechazadas": "Muestras rechazadas por fallas de transporte",
    "vacunas": "Vacunas pendientes",
    "tiempos": "Tiempos de tránsito y procesamiento",
}


def _tarjeta_reportes(titulo, descripcion, icono, *controles):
    cabecera = ft.Row([
        ft.Container(ft.Icon(icono, size=24, color=c.COLOR), padding=ft.Padding.all(10),
                     bgcolor=ft.Colors.TEAL_50, border_radius=10),
        ft.Column([ft.Text(titulo, size=18, weight=ft.FontWeight.W_600), c.nota(descripcion)],
                  spacing=3, expand=True),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
    tarjeta = c.tarjeta(cabecera, *controles)
    tarjeta.border_radius = 14
    tarjeta.content.spacing = 18
    tarjeta.content.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    return tarjeta


class SeccionReportes(Pantalla):
    nombre, icono = "Reportes", ft.Icons.BAR_CHART

    def construir(self):
        self.reporte = ft.Dropdown(label="Reporte", width=420, value="atenciones", dense=True, text_size=14, options=[
            ft.DropdownOption(key=k, text=t) for k, t in REPORTES.items()])
        self.fecha_ref = c.campo_fecha("Fecha de referencia (vacunas)", 220, date.today())
        self.fecha_ref.helper = "Se utiliza sólo en Vacunas pendientes."
        self.fecha_ref.helper_max_lines = 3
        self.fecha_ref.error_max_lines = 10
        for control in (self.reporte, self.fecha_ref):
            control.border = ft.OutlineInputBorder(border_radius=8)
            control.content_padding = ft.Padding.symmetric(horizontal=12, vertical=14)
            control.label_style = ft.TextStyle(size=14, weight=ft.FontWeight.W_500)
        self.reporte.expanded_insets = ft.Padding.all(0)
        for boton in self.fecha_ref.suffix.controls:
            boton.width = boton.height = 24
        self.titulo_rep = ft.Text("", size=18, weight=ft.FontWeight.W_600, no_wrap=False)
        self.resumen = ft.Text("", size=13, color=ft.Colors.GREY_700, no_wrap=False)
        # la tabla queda oculta hasta generar el primer reporte (evita un recuadro vacío)
        self.tabla = ft.DataTable(columns=[ft.DataColumn(ft.Text("—"))], rows=[], visible=False,
                                  heading_row_color=ft.Colors.TEAL_50, column_spacing=18,
                                  heading_row_height=44, data_row_min_height=46, data_row_max_height=float("inf"),
                                  horizontal_margin=16, border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=8)
        self.actual = None
        self._ancho_tabla = 520
        filtros = ft.Row([self.reporte, self.fecha_ref], wrap=True, spacing=14, run_spacing=16,
                         vertical_alignment=ft.CrossAxisAlignment.START)

        def ajustar_filtros(e):
            if e.width <= 0:
                return
            ancho = int(e.width * 100) / 100
            fecha = 240 if ancho >= 660 else ancho
            reporte = ancho - fecha - 14 if ancho >= 660 else ancho
            if self.reporte.width != reporte or self.fecha_ref.width != fecha:
                self.reporte.width, self.fecha_ref.width = reporte, fecha
                self.app.actualizar()

        filtros.on_size_change = ajustar_filtros
        botones = [c.boton("Generar reporte", self._generar, ft.Icons.TABLE_VIEW),
                   c.boton("Exportar PDF", lambda e: self._exportar("pdf"), ft.Icons.PICTURE_AS_PDF, False, grupo=self),
                   c.boton("Exportar CSV", lambda e: self._exportar("csv"), ft.Icons.DOWNLOAD, False, grupo=self)]
        for boton in botones:
            boton.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=22, vertical=14))
        marco = c.contenedor_tabla(self.tabla)
        marco.on_size_change = self._ajustar_tabla
        return c.pagina(
            c.titulo("Reportes", "Vista previa en pantalla y exportación a PDF o CSV"),
            _tarjeta_reportes("Parámetros del reporte", "Selecciona el reporte y la fecha de referencia para vacunas.",
                               ft.Icons.BAR_CHART, filtros,
                               ft.Row(botones, wrap=True, spacing=12, run_spacing=10, alignment=ft.MainAxisAlignment.END)),
            _tarjeta_reportes("Vista previa", "El contenido se actualiza al generar o exportar el reporte.",
                               ft.Icons.TABLE_VIEW,
                               ft.Column([self.titulo_rep, self.resumen], spacing=6, tight=True,
                                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH), marco))

    def _ajustar_tabla(self, e=None):
        """Dimensiona sólo la vista; generar y exportar conservan sus datos y parámetros."""
        if e is not None:
            if e.width <= 0:
                return
            self._ancho_tabla = round(e.width, 2)
        ancho = max(self._ancho_tabla, 520, 150 * len(self.tabla.columns))
        if self.tabla.width != ancho:
            self.tabla.width = ancho
            if e is not None:
                self.app.actualizar()

    def refrescar(self):
        pass

    def _generar(self, e=None):
        self.actual = None
        self.titulo_rep.value = self.resumen.value = ""
        self.tabla.columns = [ft.DataColumn(ft.Text("—"))]
        self.tabla.rows = []
        self.tabla.visible = False

        def accion():
            rep = self.srv.reportes
            clave = c.opcion_de(self.reporte)
            if clave == "vacunas":
                return rep.vacunas_pendientes(c.leer_fecha(self.fecha_ref.value, "Fecha de referencia"))
            return {"atenciones": rep.atenciones_derivaciones, "rechazadas": rep.muestras_rechazadas,
                    "tiempos": rep.tiempos}[clave]()
        datos = self.ejecutar(accion, campos={"Reporte": self.reporte, "Fecha de referencia": self.fecha_ref})
        if isinstance(datos, dict):
            self.actual = {**datos, "clave": self.reporte.value}
            self.titulo_rep.value = datos["titulo"]
            self.resumen.value = ("Sin datos para mostrar." if not datos["filas"]
                                  else f"{len(datos['filas'])} registro(s).")
            self.tabla.columns = [ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600, size=12))
                                  for _, t in datos["columnas"]]
            c.llenar_tabla(self.tabla, datos["columnas"], datos["filas"])
            self.tabla.visible = True
            self._ajustar_tabla()
            self.app.actualizar()
            return self.actual

    def _exportar(self, formato):
        datos = self._generar()             # siempre con los datos y parámetros actuales
        if datos is None:
            return

        def accion():
            exportador = exportar_pdf if formato == "pdf" else exportar_csv
            return exportar_con_nombre_unico(
                self.app.ruta_bd, f"reporte_{self.reporte.value}", formato,
                lambda ruta: exportador(ruta, datos))

        ruta = self.ejecutar(accion, mensaje_error=f"No se pudo generar el archivo {formato.upper()}. "
                              "Revise los permisos y la ubicación del archivo y vuelva a intentar.")
        if ruta is not None:
            self.app.ok(f"Reporte exportado: {ruta}")
            self.app.abrir_archivo(ruta)
            self.app.actualizar()
