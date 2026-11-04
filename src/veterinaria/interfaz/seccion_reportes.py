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


class SeccionReportes(Pantalla):
    nombre, icono = "Reportes", ft.Icons.BAR_CHART

    def construir(self):
        self.reporte = ft.Dropdown(label="Reporte", width=420, value="atenciones", dense=True, options=[
            ft.DropdownOption(key=k, text=t) for k, t in REPORTES.items()])
        self.fecha_ref = c.campo_fecha("Fecha de referencia (vacunas)", 220, date.today())
        self.titulo_rep = ft.Text("", size=18, weight=ft.FontWeight.W_600)
        self.resumen = ft.Text("", size=12, color=ft.Colors.GREY_700)
        # la tabla queda oculta hasta generar el primer reporte (evita un recuadro vacío)
        self.tabla = ft.DataTable(columns=[ft.DataColumn(ft.Text("—"))], rows=[], visible=False,
                                  heading_row_color=ft.Colors.BLUE_GREY_50, column_spacing=18)
        self.actual = None
        return c.pagina(
            c.titulo("Reportes", "Vista previa en pantalla y exportación a PDF o CSV"),
            c.tarjeta(c.fila(self.reporte, self.fecha_ref,
                             c.boton("Ver en pantalla", self._generar, ft.Icons.TABLE_VIEW),
                             c.boton("Exportar PDF", lambda e: self._exportar("pdf"), ft.Icons.PICTURE_AS_PDF, False),
                             c.boton("Exportar CSV", lambda e: self._exportar("csv"), ft.Icons.DOWNLOAD, False))),
            c.fila(self.titulo_rep, self.resumen),
            c.contenedor_tabla(self.tabla, expandir=True))

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
            clave = self.reporte.value
            if clave == "vacunas":
                return rep.vacunas_pendientes(c.leer_fecha(self.fecha_ref.value, "Fecha de referencia"))
            return {"atenciones": rep.atenciones_derivaciones, "rechazadas": rep.muestras_rechazadas,
                    "tiempos": rep.tiempos}[clave]()
        datos = self.ejecutar(accion)
        if isinstance(datos, dict):
            self.actual = {**datos, "clave": self.reporte.value}
            self.titulo_rep.value = datos["titulo"]
            self.resumen.value = ("Sin datos para mostrar." if not datos["filas"]
                                  else f"{len(datos['filas'])} registro(s).")
            self.tabla.columns = [ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600, size=12))
                                  for _, t in datos["columnas"]]
            c.llenar_tabla(self.tabla, datos["columnas"], datos["filas"])
            self.tabla.visible = True
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

        ruta = self.ejecutar(accion)
        if ruta is not None:
            self.app.ok(f"Reporte exportado: {ruta}")
            self.app.abrir_archivo(ruta)
            self.app.actualizar()
