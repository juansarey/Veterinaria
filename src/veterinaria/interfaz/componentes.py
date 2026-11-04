"""Controles reutilizables y utilidades de entrada para las pantallas Flet.

Este módulo sólo conoce Flet y ``ErrorNegocio``; no contiene reglas de negocio ni SQL.
"""

import re
from datetime import date, datetime, time

import flet as ft

from veterinaria.servicios.errores import ErrorNegocio

COLOR = ft.Colors.TEAL_700
FMT_FECHA = "%d/%m/%Y"
FMT_FECHA_HORA = "%d/%m/%Y %H:%M"
FMT_HORA = "%H:%M"
ESPECIES = ["Perro", "Gato", "Conejo", "Ave", "Otro"]

# estado -> (texto visible, color de la etiqueta)
ESTADOS = {
    "PENDIENTE": ("Pendiente", ft.Colors.BLUE_GREY_400), "CONFIRMADO": ("Confirmado", ft.Colors.BLUE_400),
    "ATENDIDO": ("Atendido", ft.Colors.GREEN_600), "CANCELADO": ("Cancelado", ft.Colors.GREY_500),
    "EXTRAIDA": ("Extraída", ft.Colors.BLUE_GREY_400), "EMPAQUETADA": ("Empaquetada", ft.Colors.INDIGO_400),
    "EN_TRANSITO": ("En tránsito", ft.Colors.AMBER_700), "RECIBIDA": ("Recibida", ft.Colors.TEAL_500),
    "ANALIZADA": ("Analizada", ft.Colors.GREEN_600), "RECHAZADA": ("Rechazada", ft.Colors.RED_600),
    "GENERADO": ("Generado", ft.Colors.INDIGO_400), "DESPACHADO": ("Despachado", ft.Colors.AMBER_700),
    "RECIBIDO": ("Recibido", ft.Colors.GREEN_600), "ENTREGADO": ("Entregado", ft.Colors.TEAL_500),
    "EN_PROCESO": ("En proceso", ft.Colors.AMBER_700), "COMPLETADA": ("Completada", ft.Colors.GREEN_600),
    "CANCELADA": ("Cancelada", ft.Colors.GREY_500), "DISPONIBLE": ("Disponible", ft.Colors.GREEN_600),
    "EN_USO": ("En uso", ft.Colors.AMBER_700), "INTACTO": ("Intacto", ft.Colors.GREEN_600),
    "ROTO": ("Roto", ft.Colors.RED_600), "VIGENTE": ("Vigente", ft.Colors.GREEN_600),
    "VENCIDA": ("Vencida", ft.Colors.RED_600), "FUTURA": ("Futura", ft.Colors.GREY_500),
}


# ------------------------------------------------------------------ entrada
def _parsear(texto, formato, campo, ejemplo):
    try:
        return datetime.strptime((texto or "").strip(), formato)
    except ValueError:
        raise ErrorNegocio(f"«{campo}» no tiene un formato válido (ejemplo: {ejemplo}).") from None


def leer_fecha(texto, campo="Fecha") -> date:
    return _parsear(texto, FMT_FECHA, campo, "25/11/2026").date()


def leer_fecha_opcional(texto, campo="Fecha") -> date | None:
    return leer_fecha(texto, campo) if (texto or "").strip() else None


def leer_fecha_hora(texto, campo="Fecha y hora") -> datetime:
    return _parsear(texto, FMT_FECHA_HORA, campo, "25/11/2026 09:30")


def leer_hora(texto, campo="Hora") -> time:
    return _parsear(texto, FMT_HORA, campo, "09:30").time()


def leer_entero(texto, campo="Valor") -> int:
    try:
        valor = int((texto or "").strip())
    except ValueError:
        raise ErrorNegocio(f"«{campo}» debe ser un número entero.") from None
    if valor <= 0:
        raise ErrorNegocio(f"«{campo}» debe ser mayor que cero.")
    return valor


def hoy() -> str:
    return date.today().strftime(FMT_FECHA)


def ahora() -> str:
    return datetime.now().strftime(FMT_FECHA_HORA)


# ----------------------------------------------------------------- controles
def campo(etiqueta, ancho=220, valor="", **opciones) -> ft.TextField:
    return ft.TextField(label=etiqueta, value=valor, width=ancho, dense=True, **opciones)


_SEPARADORES = {2: "/", 4: "/", 8: " ", 10: ":"}


def formatear_fecha(texto: str, anterior: str = "", con_hora: bool = False) -> str:
    """Máscara DD/MM/AAAA [HH:MM]: se escriben sólo números y los separadores se agregan solos."""
    maximo = 12 if con_hora else 8
    digitos = re.sub(r"\D", "", texto or "")[:maximo]
    resultado = ""
    for i, d in enumerate(digitos):
        if i in _SEPARADORES:
            resultado += _SEPARADORES[i]
        resultado += d
    borrando = len(texto or "") < len(anterior or "")
    if not borrando and len(digitos) in _SEPARADORES and len(digitos) < maximo:
        resultado += _SEPARADORES[len(digitos)]
    return resultado


def campo_fecha(etiqueta="Fecha", ancho=170, valor: date | datetime | None = None,
                con_hora=False, **opciones) -> ft.TextField:
    """Campo de fecha (o fecha y hora) con máscara. ``valor``: date/datetime o None."""
    formato = FMT_FECHA_HORA if con_hora else FMT_FECHA
    texto = valor.strftime(formato) if valor else ""
    control = campo(etiqueta, ancho, texto, input_filter=ft.InputFilter(regex_string=r"[0-9/: ]"),
                    hint_text="DD/MM/AAAA HH:MM" if con_hora else "DD/MM/AAAA", **opciones)
    control.data = texto

    def al_escribir(e):
        nuevo = formatear_fecha(control.value, control.data, con_hora)
        if nuevo != control.value:
            control.value = nuevo
            control.selection = ft.TextSelection(base_offset=len(nuevo), extent_offset=len(nuevo))
        control.data = nuevo
        control.update()

    control.on_change = al_escribir
    return control


def campo_fecha_hora(etiqueta="Fecha y hora", ancho=200) -> ft.TextField:
    return campo_fecha(etiqueta, ancho, datetime.now(), con_hora=True)


def reponer_fecha(control: ft.TextField):
    """Vuelve a poner la fecha y hora actuales (los valores por defecto no deben quedar viejos)."""
    control.value = control.data = ahora()


def selector(etiqueta, ancho=300, on_select=None) -> ft.Dropdown:
    """Lista desplegable con búsqueda por escritura."""
    return ft.Dropdown(label=etiqueta, width=ancho, options=[], on_select=on_select,
                       enable_filter=True, editable=True, menu_height=320, dense=True)


def desplegable_fijo(etiqueta, opciones: list[str], valor=None, ancho=160) -> ft.Dropdown:
    return ft.Dropdown(label=etiqueta, width=ancho, value=valor, dense=True,
                       options=[ft.DropdownOption(key=o, text=o) for o in opciones])


def cargar_selector(dropdown: ft.Dropdown, items: list[dict], clave="id", texto="etiqueta"):
    """Rellena las opciones conservando la selección si sigue existiendo."""
    dropdown.options = [ft.DropdownOption(key=str(i[clave]), text=str(i[texto])) for i in items]
    if dropdown.value not in {str(i[clave]) for i in items}:
        dropdown.value = None


def id_de(dropdown: ft.Dropdown) -> int | None:
    return int(dropdown.value) if dropdown.value not in (None, "") else None


def requerir(dropdown: ft.Dropdown, nombre: str) -> int:
    valor = id_de(dropdown)
    if valor is None:
        raise ErrorNegocio(f"Seleccione {nombre}.")
    return valor


def boton(texto, on_click, icono=None, primario=True) -> ft.Control:
    clase = ft.FilledButton if primario else ft.OutlinedButton
    return clase(texto, icon=icono, on_click=on_click)


def boton_icono(icono, tooltip, on_click, color=COLOR, visible=True) -> ft.IconButton:
    return ft.IconButton(icono, tooltip=tooltip, icon_color=color, on_click=on_click, visible=visible)


def chip_estado(estado) -> ft.Control:
    texto, color = ESTADOS.get(str(estado), (str(estado), ft.Colors.GREY_600))
    return ft.Container(ft.Text(texto, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                        bgcolor=color, border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2))


# ------------------------------------------------------------------- tablas
COLUMNAS_CHIP = {"estado", "estado_precinto", "precinto_estado"}


def crear_tabla(columnas: list[tuple[str, str]], con_acciones=False) -> ft.DataTable:
    cols = [ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600, size=12)) for _, t in columnas]
    if con_acciones:
        cols.append(ft.DataColumn(ft.Text("")))
    return ft.DataTable(columns=cols, rows=[], heading_row_color=ft.Colors.BLUE_GREY_50,
                        column_spacing=18, data_row_min_height=36, data_row_max_height=52,
                        border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=8)


def _celda(clave, valor) -> ft.DataCell:
    if isinstance(valor, ft.Control):
        return ft.DataCell(valor)
    if clave in COLUMNAS_CHIP and valor:
        return ft.DataCell(chip_estado(valor))
    return ft.DataCell(ft.Text("" if valor is None else str(valor), size=12))


def llenar_tabla(tabla: ft.DataTable, columnas: list[tuple[str, str]], filas: list[dict],
                 acciones=None):
    """``acciones(fila)`` devuelve la lista de botones de icono de esa fila (última columna)."""
    rows = []
    for fila in filas:
        celdas = [_celda(clave, fila.get(clave)) for clave, _ in columnas]
        if acciones is not None:
            celdas.append(ft.DataCell(ft.Row(acciones(fila), spacing=0, tight=True)))
        rows.append(ft.DataRow(cells=celdas))
    tabla.rows = rows


def contenedor_tabla(tabla: ft.DataTable) -> ft.Control:
    """Permite desplazar horizontalmente las tablas anchas."""
    return ft.Row(controls=[tabla], scroll=ft.ScrollMode.AUTO)


# ---------------------------------------------------------------- estructura
def titulo(texto, subtitulo="") -> ft.Column:
    controles = [ft.Text(texto, size=24, weight=ft.FontWeight.BOLD, color=COLOR)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=13, color=ft.Colors.GREY_700))
    return ft.Column(controles, spacing=2)


def nota(texto) -> ft.Text:
    return ft.Text(texto, size=12, color=ft.Colors.GREY_700)


def tarjeta(*controles, encabezado: str | None = None) -> ft.Container:
    contenido = ([ft.Text(encabezado, size=16, weight=ft.FontWeight.W_600)] if encabezado else [])
    contenido += list(controles)
    return ft.Container(
        content=ft.Column(controls=contenido, spacing=10, tight=True), padding=ft.Padding.all(16),
        bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=10)


def fila(*controles) -> ft.Row:
    return ft.Row(controls=list(controles), wrap=True, spacing=12,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


# ----------------------------------------------------------------- diálogos
def dialogo(app, titulo_texto, controles, ancho=620, alto=None, icono=None, color=None):
    """Muestra una ventana modal informativa con un botón «Cerrar»."""
    contenido = ft.Container(ft.Column(controles, tight=True, scroll=ft.ScrollMode.AUTO),
                             width=ancho, height=alto)
    app.page.show_dialog(ft.AlertDialog(
        icon=ft.Icon(icono, color=color, size=40) if icono else None,
        title=ft.Text(titulo_texto), content=contenido,
        actions=[ft.TextButton("Cerrar", on_click=lambda e: app.page.pop_dialog())]))


def confirmar(app, mensaje, al_aceptar):
    """Pide confirmación antes de una acción destructiva."""
    def aceptar(e):
        app.page.pop_dialog()
        al_aceptar()

    app.page.show_dialog(ft.AlertDialog(
        title=ft.Text("Confirmar"), content=ft.Text(mensaje),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: app.page.pop_dialog()),
                 ft.FilledButton("Eliminar", on_click=aceptar)]))


def linea_tiempo(historial: list[dict]) -> list[ft.Control]:
    """Pasos de la cadena de custodia: una etiqueta de estado y la fecha de cada cambio."""
    pasos = []
    for i, h in enumerate(historial):
        pasos.append(ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, controls=[
            ft.Column([chip_estado(h["estado"]),
                       ft.Container(width=2, height=18, bgcolor=ft.Colors.BLUE_GREY_100,
                                    visible=i < len(historial) - 1)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, width=130),
            ft.Column([ft.Text(h["fecha"], weight=ft.FontWeight.W_500, size=12),
                       ft.Text(h.get("observaciones") or "", size=12, color=ft.Colors.GREY_700)],
                      spacing=0, expand=True),
        ]))
    return pasos
