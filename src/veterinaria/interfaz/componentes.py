"""Controles reutilizables y utilidades de entrada para las pantallas Flet.

Este módulo sólo conoce Flet y ``ErrorNegocio``; no contiene reglas de negocio ni SQL.
"""

import re
from datetime import date, datetime, time
from threading import Lock

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
        raise ErrorNegocio(f"«{campo}» no tiene un formato válido (ejemplo: {ejemplo}).", campo) from None


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
def campo(etiqueta, ancho=220, valor="", validar=None, **opciones) -> ft.TextField:
    al_cambiar = opciones.pop("on_change", None)
    al_salir = opciones.pop("on_blur", None)
    control = ft.TextField(label=etiqueta, value=valor, width=ancho, dense=True, **opciones)
    control._validar_entrada = validar

    def cambiar(e):
        revisar_error(control)
        if al_cambiar:
            al_cambiar(e)

    control.on_change = cambiar
    def salir(e):
        revisar_error(control)
        if al_salir:
            al_salir(e)
    control.on_blur = salir
    return control


def establecer_error(control, mensaje):
    # Flet 1.x llama «error» a la propiedad de TextField y «error_text» a la de Dropdown.
    if isinstance(control, ft.TextField):
        control.error = mensaje
    else:
        control.error_text = mensaje
    control._valor_error = control.value if mensaje else None


def revisar_error(control):
    """Revalida sólo un error previo y una entrada modificada; nunca bloquea la escritura."""
    error = control.error if isinstance(control, ft.TextField) else control.error_text
    validar = getattr(control, "_validar_entrada", None)
    if not error or validar is None or control.value == getattr(control, "_valor_error", None):
        return
    try:
        validar(control.value)
    except ErrorNegocio as exc:
        establecer_error(control, str(exc))
        _actualizar_control(control)
    else:
        limpiar_error(control)


def limpiar_error(control):
    error = control.error if isinstance(control, ft.TextField) else control.error_text
    if error:
        establecer_error(control, None)
        _actualizar_control(control)


def enfocar_control(page, control):
    """Flet 1.x solicita foco mediante una corrutina; una página simulada puede omitirlo."""
    ejecutar = getattr(page, "run_task", None)
    foco = getattr(control, "focus", None)
    if ejecutar and foco:
        try:
            ejecutar(foco)
        except (RuntimeError, AssertionError):
            pass  # una página aún sin sesión no puede recibir foco


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


LOCALE = ft.Locale("es", "AR")


def _actualizar_control(control):
    """Refleja el cambio en pantalla (si el control todavía no está en una página, no hace nada)."""
    try:
        control.update()
    except Exception:
        pass


def _valor_o_ahora(texto: str, formato: str) -> datetime:
    try:
        return datetime.strptime((texto or "").strip(), formato)
    except ValueError:
        return datetime.now().replace(second=0, microsecond=0)


def abrir_calendario(e, control: ft.TextField, con_hora: bool,
                     fecha_minima=None, fecha_maxima=None, on_change=None):
    """Abre el calendario desplegable y escribe la fecha elegida en el campo
    (conserva la hora si el campo es de fecha y hora)."""
    formato = FMT_FECHA_HORA if con_hora else FMT_FECHA
    actual = _valor_o_ahora(control.value, formato)
    desde = fecha_minima() if callable(fecha_minima) else fecha_minima
    hasta = fecha_maxima() if callable(fecha_maxima) else fecha_maxima
    desde = desde or date(1990, 1, 1)
    hasta = hasta or date(2100, 12, 31)
    desde = datetime(desde.year, desde.month, desde.day)
    hasta = datetime(hasta.year, hasta.month, hasta.day)
    inicial = max(desde, min(hasta, datetime(actual.year, actual.month, actual.day)))

    def al_elegir(ev):
        elegida = ev.control.value
        nuevo = actual.replace(year=elegida.year, month=elegida.month, day=elegida.day)
        control.value = control.data = nuevo.strftime(formato)
        revisar_error(control)
        _actualizar_control(control)
        if on_change:
            on_change(ev)

    e.page.show_dialog(ft.DatePicker(
        value=inicial, first_date=desde, last_date=hasta,
        locale=LOCALE, help_text="Seleccionar fecha", cancel_text="Cancelar",
        confirm_text="Aceptar", on_change=al_elegir))


def abrir_reloj(e, control: ft.TextField, con_fecha: bool, on_change=None):
    """Abre el selector de hora y escribe la hora elegida (HH:MM) en el campo."""
    formato = FMT_FECHA_HORA if con_fecha else FMT_HORA
    actual = _valor_o_ahora(control.value, formato)

    def al_elegir(ev):
        hora = ev.control.value
        nuevo = actual.replace(hour=hora.hour, minute=hora.minute)
        control.value = control.data = nuevo.strftime(formato)
        revisar_error(control)
        _actualizar_control(control)
        if on_change:
            on_change(ev)

    e.page.show_dialog(ft.TimePicker(
        value=actual.time(), locale=LOCALE, help_text="Seleccionar hora", cancel_text="Cancelar",
        confirm_text="Aceptar", hour_label_text="Hora", minute_label_text="Minuto",
        on_change=al_elegir))


def _boton_pequeno(icono, tooltip, on_click) -> ft.IconButton:
    return ft.IconButton(icono, tooltip=tooltip, icon_size=20, icon_color=COLOR,
                         padding=ft.Padding.all(4), on_click=on_click)


def campo_fecha(etiqueta="Fecha", ancho=170, valor: date | datetime | None = None,
                con_hora=False, fecha_minima=None, fecha_maxima=None, on_change=None,
                opcional=False, **opciones) -> ft.TextField:
    """Campo de fecha (o fecha y hora) con máscara y calendario desplegable.

    ``valor``: date/datetime o None. En los campos con hora hay además un reloj para elegir la hora."""
    formato = FMT_FECHA_HORA if con_hora else FMT_FECHA
    texto = valor.strftime(formato) if valor else ""
    ancho = max(ancho, 250 if con_hora else 175)
    control = campo(etiqueta, ancho, texto, input_filter=ft.InputFilter(regex_string=r"[0-9/: ]"),
                    hint_text="DD/MM/AAAA HH:MM" if con_hora else "DD/MM/AAAA", **opciones)

    def validar_fecha(texto):
        if opcional and not (texto or "").strip():
            return
        elegida = (leer_fecha_hora(texto, etiqueta).date() if con_hora else leer_fecha(texto, etiqueta))
        desde = fecha_minima() if callable(fecha_minima) else fecha_minima
        hasta = fecha_maxima() if callable(fecha_maxima) else fecha_maxima
        if (desde and elegida < desde) or (hasta and elegida > hasta):
            raise ErrorNegocio("La fecha está fuera del rango permitido para este campo.", etiqueta)

    control._validar_entrada = validar_fecha
    control.data = texto
    botones = [_boton_pequeno(ft.Icons.CALENDAR_MONTH, "Elegir fecha en el calendario",
                              lambda e: abrir_calendario(
                                  e, control, con_hora, fecha_minima, fecha_maxima, on_change))]
    if con_hora:
        botones.append(_boton_pequeno(ft.Icons.ACCESS_TIME, "Elegir hora",
                                      lambda e: abrir_reloj(e, control, True, on_change)))
    control.suffix = ft.Row(botones, tight=True, spacing=0)

    def al_escribir(e):
        nuevo = formatear_fecha(control.value, control.data, con_hora)
        if nuevo != control.value:
            control.value = nuevo
            control.selection = ft.TextSelection(base_offset=len(nuevo), extent_offset=len(nuevo))
        control.data = nuevo
        revisar_error(control)
        _actualizar_control(control)
        if on_change:
            on_change(e)

    control.on_change = al_escribir
    return control


def campo_fecha_hora(etiqueta="Fecha y hora", ancho=250, **opciones) -> ft.TextField:
    return campo_fecha(etiqueta, ancho, datetime.now(), con_hora=True, **opciones)


def campo_hora(etiqueta="Hora (HH:MM)", ancho=150, valor="") -> ft.TextField:
    """Campo de hora con selector de reloj."""
    control = campo(etiqueta, ancho, valor, input_filter=ft.InputFilter(regex_string=r"[0-9:]"),
                    hint_text="HH:MM", validar=lambda texto: leer_hora(texto, etiqueta))
    control.suffix = _boton_pequeno(ft.Icons.ACCESS_TIME, "Elegir hora",
                                    lambda e: abrir_reloj(e, control, False))
    return control


def reponer_fecha(control: ft.TextField):
    """Restablece explícitamente la fecha tras guardar; no se usa al refrescar listados."""
    control.value = control.data = ahora()
    limpiar_error(control)


def selector(etiqueta, ancho=300, on_select=None) -> ft.Dropdown:
    """Lista desplegable con búsqueda por escritura."""
    control = ft.Dropdown(label=etiqueta, width=ancho, options=[],
                          enable_filter=True, editable=True, menu_height=320, dense=True)
    control._validar_entrada = lambda valor: requerir(control, "una opción válida")

    def seleccionar(e):
        revisar_error(control)
        if on_select:
            on_select(e)

    control.on_select = seleccionar
    control.on_text_change = lambda e: revisar_error(control)
    return control


def desplegable_fijo(etiqueta, opciones: list[str], valor=None, ancho=160) -> ft.Dropdown:
    control = ft.Dropdown(label=etiqueta, width=ancho, value=valor, dense=True,
                          options=[ft.DropdownOption(key=o, text=o) for o in opciones])
    control._validar_entrada = lambda valor: opcion_de(control)
    control.on_select = lambda e: revisar_error(control)
    return control


def cargar_selector(dropdown: ft.Dropdown, items: list[dict], clave="id", texto="etiqueta"):
    """Rellena las opciones conservando la selección si sigue existiendo."""
    dropdown.options = [ft.DropdownOption(key=str(i[clave]), text=str(i[texto])) for i in items]
    if dropdown.value not in {str(i[clave]) for i in items}:
        dropdown.value = None


def id_de(dropdown: ft.Dropdown) -> int | None:
    if dropdown.value in (None, ""):
        return None
    try:
        valor = int(dropdown.value)
    except (ValueError, TypeError):
        valor = 0
    if valor <= 0 or str(dropdown.value) not in {opcion.key for opcion in dropdown.options}:
        raise ErrorNegocio(f"Seleccione una opción válida en «{dropdown.label}».", dropdown.label)
    return valor


def requerir(dropdown: ft.Dropdown, nombre: str) -> int:
    valor = id_de(dropdown)
    if valor is None:
        raise ErrorNegocio(f"Seleccione {nombre}.", dropdown.label)
    return valor


def opcion_de(dropdown: ft.Dropdown) -> str:
    if dropdown.value not in {opcion.key for opcion in dropdown.options}:
        raise ErrorNegocio(f"Seleccione una opción válida en «{dropdown.label}».", dropdown.label)
    return dropdown.value


def _proteger_boton(control, accion, grupo=None):
    grupo = grupo or getattr(accion, "__self__", None)
    bloqueo = getattr(grupo, "_bloqueo_accion", None)
    if bloqueo is None:
        grupo = None
        bloqueo = Lock()

    def ejecutar(e):
        vista = grupo.vista if grupo is not None else control
        if control.disabled or vista.disabled or not bloqueo.acquire(blocking=False):
            return
        anterior = vista.disabled
        try:
            # Deshabilitar el formulario no pisa el estado propio de cada botón.
            vista.disabled = True
            _actualizar_control(vista)
            return accion(e)
        finally:
            vista.disabled = anterior
            _actualizar_control(vista)
            bloqueo.release()

    control.on_click = ejecutar
    return control


def boton(texto, on_click, icono=None, primario=True, grupo=None, destructivo=False) -> ft.Control:
    clase = ft.FilledButton if primario else ft.OutlinedButton
    control = clase(texto, icon=icono)
    if destructivo:
        control.style = ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE)
    return _proteger_boton(control, on_click, grupo)


def boton_icono(icono, tooltip, on_click, color=COLOR, visible=True, grupo=None) -> ft.IconButton:
    return _proteger_boton(ft.IconButton(icono, tooltip=tooltip, icon_color=color, visible=visible),
                           on_click, grupo)


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
    """Todas las filas participan del scroll de la página; sólo la anchura tiene scroll propio."""
    marco = ft.Container(content=ft.Row([tabla], scroll=ft.ScrollMode.AUTO,
                                       vertical_alignment=ft.CrossAxisAlignment.START))
    tabla.data = marco
    return marco


# ---------------------------------------------------------------- estructura
def titulo(texto, subtitulo="") -> ft.Column:
    controles = [ft.Text(texto, size=24, weight=ft.FontWeight.BOLD, color=COLOR)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=13, color=ft.Colors.GREY_700))
    return ft.Column(controles, spacing=2)


def subtitulo_texto(texto) -> ft.Text:
    return ft.Text(texto, size=16, weight=ft.FontWeight.W_600)


def nota(texto) -> ft.Text:
    return ft.Text(texto, size=12, color=ft.Colors.GREY_700)


def tarjeta(*controles, encabezado: str | None = None, expandir=False) -> ft.Container:
    """Cuadro blanco con sus controles. ``expandir=True`` lo hace ocupar el alto que sobra."""
    contenido = ([ft.Text(encabezado, size=16, weight=ft.FontWeight.W_600)] if encabezado else [])
    contenido += list(controles)
    return ft.Container(
        content=ft.Column(controls=contenido, spacing=10, tight=not expandir, expand=expandir),
        padding=ft.Padding.all(16), bgcolor=ft.Colors.WHITE, expand=expandir,
        border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=10)


def mitad(control: ft.Control) -> ft.Control:
    """Hace que un cuadro ocupe una parte igual del ancho dentro de una fila."""
    control.expand = 1
    return control


def pagina(*controles, scroll=True) -> ft.Column:
    """Una única columna desplazable para formularios, listados y acciones de la pestaña.

    Sus hijos tienen altura natural, sin expansión vertical ni scroll vertical propio."""
    return ft.Column(list(controles), spacing=14, expand=True,
                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                     scroll=ft.ScrollMode.AUTO if scroll else None)


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
    if getattr(app, "_confirmacion_abierta", False):
        return
    app._confirmacion_abierta = True
    resuelto = False

    def resolver(aceptar=False, cerrar=True):
        nonlocal resuelto
        if resuelto:
            return
        resuelto = True
        try:
            if cerrar:
                app.page.pop_dialog()
            if aceptar:
                al_aceptar()
        finally:
            app._confirmacion_abierta = False

    try:
        app.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Confirmar"), content=ft.Text(mensaje),
            on_dismiss=lambda e: resolver(cerrar=False),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: resolver()),
                     boton("Eliminar", lambda e: resolver(aceptar=True), destructivo=True)]))
    except Exception:
        app._confirmacion_abierta = False
        raise


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
