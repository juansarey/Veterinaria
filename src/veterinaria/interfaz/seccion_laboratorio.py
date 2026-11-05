"""Laboratorio: empaquetado, envío y recepción, resultados y seguimiento de muestras."""

from datetime import date

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.exportaciones import exportar_con_nombre_unico
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.base import validar_texto
from veterinaria.servicios.exportador import exportar_comprobante_resultado_pdf


def _estado_visible(estado, recibido, precinto_roto):
    """Un envío/remito recibido con el precinto roto se muestra como «Rechazado»."""
    if recibido:
        return "RECHAZADO" if precinto_roto else "RECIBIDO"
    return estado


def _tarjeta_laboratorio(titulo, descripcion, icono, *controles):
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


def _fila_laboratorio(pantalla, *controles, columnas=3):
    """Ajusta sólo la presentación, conservando entradas, validadores y callbacks."""
    for control in controles:
        control.width = 240  # ancho inicial acotado, antes de recibir la medición de la fila
        control.border = ft.OutlineInputBorder(border_radius=8)
        control.content_padding = ft.Padding.symmetric(horizontal=12, vertical=14)
        control.label_style = ft.TextStyle(size=14, weight=ft.FontWeight.W_500)
        if isinstance(control, ft.Dropdown):
            control.expanded_insets = ft.Padding.all(0)
        else:
            control.error_max_lines = 10
            control.helper_max_lines = 4
            sufijo = control.suffix
            for boton in (sufijo.controls if isinstance(sufijo, ft.Row) else [sufijo] if sufijo else []):
                boton.width = boton.height = 24
    fila = ft.Row(list(controles), wrap=True, spacing=14, run_spacing=16,
                  vertical_alignment=ft.CrossAxisAlignment.START)

    def ajustar_ancho(e):
        if e.width <= 0:
            return
        if columnas == 4:
            cantidad = 4 if e.width >= 1120 else 2 if e.width >= 560 else 1
        else:
            cantidad = min(columnas, 3 if e.width >= 820 else 2 if e.width >= 560 else 1)
        ancho = int((e.width - 14 * (cantidad - 1)) / cantidad * 100) / 100
        if any(control.width != ancho for control in controles):
            for control in controles:
                control.width = ancho
            pantalla.app.actualizar()

    fila.on_size_change = ajustar_ancho
    return fila


def _acciones_laboratorio(*botones):
    for boton in botones:
        boton.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=22, vertical=14))
    return ft.Row(list(botones), wrap=True, spacing=12, run_spacing=10,
                  alignment=ft.MainAxisAlignment.END)


def _tabla_laboratorio(pantalla, tabla, ancho_minimo, con_acciones=False):
    if con_acciones:
        tabla.columns[-1].label.value = "Acciones"
    tabla.heading_row_color = ft.Colors.TEAL_50
    tabla.heading_row_height = 44
    tabla.data_row_min_height = 46
    tabla.data_row_max_height = float("inf")
    tabla.horizontal_margin = 16
    marco = c.contenedor_tabla(tabla)

    def ajustar_ancho(e):
        if e.width <= 0:
            return
        ancho = max(ancho_minimo, round(e.width, 2))
        if tabla.width != ancho:
            tabla.width = ancho
            pantalla.app.actualizar()

    marco.on_size_change = ajustar_ancho
    return marco


def _paneles_laboratorio(pantalla, *tarjetas):
    # Wrap no admite hijos Flex, ni siquiera el expand=False que trae la tarjeta.
    for tarjeta in tarjetas:
        tarjeta.expand = None
        tarjeta.width = 320
    paneles = ft.Row(list(tarjetas), wrap=True, spacing=14, run_spacing=14,
                     vertical_alignment=ft.CrossAxisAlignment.START)

    def ajustar_ancho(e):
        if e.width <= 0:
            return
        cantidad = 2 if e.width >= 1120 else 1
        ancho = int((e.width - 14 * (cantidad - 1)) / cantidad * 100) / 100
        if any(tarjeta.width != ancho for tarjeta in tarjetas):
            for tarjeta in tarjetas:
                tarjeta.width = ancho
            pantalla.app.actualizar()

    paneles.on_size_change = ajustar_ancho
    return paneles


class PestanaEmpaquetado(Pantalla):
    nombre, icono = "Empaquetado", ft.Icons.INVENTORY_2
    COLS = [("id", "Remito"), ("fecha", "Emitido"), ("clinica", "Clínica de origen"),
            ("conservadora", "Conservadora"), ("precinto", "Precinto"), ("muestras", "Muestras"),
            ("estado", "Estado")]

    def construir(self):
        self.clinica = c.selector("Clínica de origen", 240, self._al_elegir_clinica)
        self.conservadora = c.selector("Conservadora disponible", 240)
        self.codigo_cons = c.campo("Nueva conservadora (código)", 220,
                                   validar=lambda t: validar_texto(t, "Código", 50, True))
        self.fecha = c.campo_fecha_hora("Fecha de empaquetado", 260,
                                       fecha_maxima=date.today,
                                       helper="Hasta el momento actual. Vuelve al momento actual al guardar.")
        self.precinto = c.campo("Código del precinto (opcional)", 240,
                                validar=lambda t: validar_texto(t, "Código del precinto", 50))
        self.muestras_box = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.checks: dict[int, ft.Checkbox] = {}

        def ajustar_etiquetas(e):
            if e.width <= 0:
                return
            ancho = max(1, int((e.width - 56) * 100) / 100)
            if any(check.label.width != ancho for check in self.checks.values()):
                for check in self.checks.values():
                    check.label.width = ancho
                self.app.actualizar()

        self.muestras_box.on_size_change = ajustar_etiquetas
        marco_muestras = ft.Container(
            self.muestras_box,
            padding=ft.Padding.all(12), bgcolor=ft.Colors.GREY_50,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=8)
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        return c.pagina(
            _tarjeta_laboratorio("Empaquetar muestras en una conservadora",
                                 "Se genera el remito biológico y el precinto sanitario; las muestras pasan a "
                                 "«Empaquetada» y la conservadora queda en uso.", ft.Icons.INVENTORY_2,
                                 _fila_laboratorio(self, self.clinica, self.conservadora, self.fecha,
                                                   self.codigo_cons, columnas=4),
                                 _acciones_laboratorio(c.boton("Agregar conservadora", self._crear_cons,
                                                               ft.Icons.ADD, False)),
                                 ft.Text("Muestras extraídas pendientes de envío:", weight=ft.FontWeight.W_500),
                                 marco_muestras,
                                 _fila_laboratorio(self, self.precinto, columnas=1),
                                 _acciones_laboratorio(c.boton("Empaquetar y precintar", self._empaquetar,
                                                               ft.Icons.INVENTORY_2))),
            _tarjeta_laboratorio("Remitos emitidos", "Remitos biológicos generados desde la clínica.",
                                 ft.Icons.LOCAL_SHIPPING,
                                 _tabla_laboratorio(self, self.tabla, 1200, con_acciones=True)))

    def refrescar(self):
        lab = self.srv.laboratorio
        c.cargar_selector(self.clinica, self.srv.clinica.listar_clinicas())
        c.cargar_selector(self.conservadora, lab.listar_conservadoras(solo_disponibles=True))
        remitos = lab.listar_remitos()
        filas = [{**r, "estado": _estado_visible(r["estado"], r["estado"] == "RECIBIDO",
                                                 r["precinto"].endswith("(ROTO)"))} for r in remitos]
        c.llenar_tabla(self.tabla, self.COLS, filas, lambda r: [
            c.boton_icono(ft.Icons.LOCK_OPEN, "Liberar la conservadora (ya recibida)",
                          lambda e, r=r: self._liberar(r), visible=r["estado"] in ("RECIBIDO", "RECHAZADO"),
                          grupo=self)])
        self._cargar_muestras()

    def _cargar_muestras(self):
        idc = c.id_de(self.clinica)
        previas = {i: ch.value for i, ch in self.checks.items()}
        libres = [m for m in self.srv.laboratorio.listar_muestras()
                  if m["estado"] == "EXTRAIDA" and (idc is None or m["id_clinica"] == idc)]
        self.checks = {m["id"]: ft.Checkbox(
            label=ft.Text(f"{m['etiqueta']} · {m['estudio']} · extraída {m['extraccion']}",
                          size=12, no_wrap=False, width=220),
            value=previas.get(m["id"], not previas)) for m in libres}
        self.muestras_box.controls = list(self.checks.values()) or [
            ft.Text("No hay muestras extraídas pendientes de envío.", italic=True, size=12)]

    def _al_elegir_clinica(self, e=None):
        self._cargar_muestras()
        self.app.actualizar()

    def _crear_cons(self, e=None):
        if self.ejecutar(lambda: self.srv.laboratorio.crear_conservadora(self.codigo_cons.value),
                         "Conservadora agregada.", {"Código": self.codigo_cons}):
            self.codigo_cons.value = ""
            self.app.actualizar()

    def _liberar(self, remito):
        self.ejecutar(lambda: self.srv.laboratorio.liberar_conservadora(remito["id_conservadora"]),
                      "Conservadora liberada: ya puede usarse en otro remito.")

    def _empaquetar(self, e=None):
        def accion():
            ids = [i for i, ch in self.checks.items() if ch.value]
            return self.srv.laboratorio.empaquetar(
                c.requerir(self.clinica, "la clínica de origen"),
                c.requerir(self.conservadora, "una conservadora"), ids, self.precinto.value,
                c.leer_fecha_hora(self.fecha.value, "Fecha de empaquetado"))
        res = self.ejecutar(accion, campos={
            self.clinica.label: self.clinica, self.conservadora.label: self.conservadora,
            "Código del precinto": self.precinto, "Fecha de empaquetado": self.fecha})
        if isinstance(res, dict):
            self.precinto.value = ""
            c.reponer_fecha(self.fecha)
            self.app.actualizar()
            c.dialogo(self.app, f"Remito R-{res['id_remito']:04d} emitido", [
                ft.Text(f"Precinto sanitario: {res['precinto']}", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"Muestras empaquetadas: {res['muestras']}"),
                c.nota("En la recepción, el laboratorio verificará que el precinto llegue íntegro."),
            ], ancho=420, icono=ft.Icons.VERIFIED, color=ft.Colors.GREEN_600)


class PestanaEnvio(Pantalla):
    nombre, icono = "Envío y recepción", ft.Icons.LOCAL_SHIPPING
    COLS = [("id", "Envío"), ("id_remito", "Remito"), ("estado", "Estado"), ("salida", "Salida"),
            ("llegada", "Llegada"), ("precinto", "Precinto"), ("recepcion", "Recepción")]

    def construir(self):
        self.remito = c.selector("Remito listo para despachar", 360)
        self.salida = c.campo_fecha_hora("Salida", 200,
                                        fecha_maxima=date.today,
                                        helper="Hasta el momento actual. Vuelve al momento actual al guardar.")
        self.obs_envio = c.campo("Observaciones de despacho", 300,
                                 multiline=True, min_lines=2, max_lines=4)
        self.envio = c.selector("Envío pendiente de recepción", 360)
        self.f_recepcion = c.campo_fecha_hora("Recepción", 200,
                                             fecha_maxima=date.today,
                                             helper="Hasta el momento actual. Vuelve al momento actual al guardar.")
        self.integro = c.desplegable_fijo("Estado del precinto (obligatorio)",
                                         ["Precinto intacto", "Precinto roto"], ancho=300)
        self.integro.hint_text = "Seleccione el estado observado"
        self.obs_rec = c.campo("Observaciones de recepción", 300,
                               multiline=True, min_lines=2, max_lines=4)
        self.tabla = c.crear_tabla(self.COLS)
        despacho = _tarjeta_laboratorio(
            "1. Despacho desde la clínica", "Salida del remito hacia el laboratorio central.", ft.Icons.LOCAL_SHIPPING,
            _fila_laboratorio(self, self.remito, columnas=1),
            _fila_laboratorio(self, self.salida, columnas=1),
            _fila_laboratorio(self, self.obs_envio, columnas=1),
            c.nota("Sólo se despachan remitos con conservadora, muestras y un precinto intacto."),
            _acciones_laboratorio(c.boton("Despachar", self._despachar, ft.Icons.LOCAL_SHIPPING)))
        recepcion = _tarjeta_laboratorio(
            "2. Recepción en el laboratorio central", "Llegada del envío y verificación del precinto.", ft.Icons.FACT_CHECK,
            _fila_laboratorio(self, self.envio, columnas=1),
            _fila_laboratorio(self, self.f_recepcion, columnas=1),
            _fila_laboratorio(self, self.obs_rec, columnas=1),
            _fila_laboratorio(self, self.integro, columnas=1),
            c.nota("Si el precinto llega roto, las muestras quedan «Rechazadas» y no se procesan."),
            _acciones_laboratorio(c.boton("Registrar recepción", self._recibir, ft.Icons.FACT_CHECK)))
        return c.pagina(
            _paneles_laboratorio(self, despacho, recepcion),
            _tarjeta_laboratorio("Envíos y recepciones", "Estado del transporte, fechas y precintos.",
                                 ft.Icons.LOCAL_SHIPPING, _tabla_laboratorio(self, self.tabla, 1100)),
            scroll=True)

    def refrescar(self):
        lab = self.srv.laboratorio
        remitos = lab.listar_remitos()
        c.cargar_selector(self.remito, [r for r in remitos if r["estado"] == "GENERADO" and r["puede_despacharse"]])
        envios = lab.listar_envios()
        c.cargar_selector(self.envio, [e for e in envios
                                     if not e["recibido"] and e["estado"] in ("EN_TRANSITO", "ENTREGADO")])
        filas = [{**e, "estado": _estado_visible(e["estado"], e["recibido"], e["precinto"] == "ROTO")}
                 for e in envios]
        c.llenar_tabla(self.tabla, self.COLS, filas)

    def _despachar(self, e=None):
        def accion():
            return self.srv.laboratorio.despachar_remito(
                c.requerir(self.remito, "un remito"), c.leer_fecha_hora(self.salida.value, "Salida"),
                self.obs_envio.value)
        if self.ejecutar(accion, "Remito despachado: las muestras pasan a «En tránsito».",
                         {self.remito.label: self.remito, "Salida": self.salida}):
            self.obs_envio.value = ""
            c.reponer_fecha(self.salida)
            self.app.actualizar()

    def _recibir(self, e=None):
        def accion():
            if self.integro.value not in ("Precinto intacto", "Precinto roto"):
                raise ErrorNegocio("Seleccione si el precinto llegó intacto o roto.", self.integro.label)
            integro = self.integro.value == "Precinto intacto"
            return self.srv.laboratorio.recibir_remito(
                c.requerir(self.envio, "un envío"), integro,
                c.leer_fecha_hora(self.f_recepcion.value, "Recepción"), self.obs_rec.value)
        res = self.ejecutar(accion, campos={self.envio.label: self.envio, "Recepción": self.f_recepcion,
                                          "Llegada": self.f_recepcion,
                                          self.integro.label: self.integro})
        if isinstance(res, dict):
            self.integro.value = None
            self.obs_rec.value = ""
            c.reponer_fecha(self.f_recepcion)
            self.app.actualizar()
            ids = ", ".join(f"M-{i:04d}" for i, _ in res["muestras"])
            if res["precinto_intacto"]:
                c.dialogo(self.app, "Remito aceptado", [
                    ft.Text(f"Muestras recibidas y listas para analizar: {ids}")],
                    ancho=420, icono=ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600)
            else:
                c.dialogo(self.app, "Remito RECHAZADO", [
                    ft.Text("El precinto llegó roto."),
                    ft.Text(f"Las muestras {ids} pasan a «Rechazada» y no pueden procesarse.", size=12)],
                    ancho=420, icono=ft.Icons.CANCEL, color=ft.Colors.RED_600)


class PestanaResultados(Pantalla):
    nombre, icono = "Resultados", ft.Icons.ASSIGNMENT_TURNED_IN
    COLS = [("id_txt", "Muestra"), ("tipo", "Tipo"), ("estudio", "Estudio"), ("mascota", "Mascota"),
            ("clinica", "Clínica"), ("fecha_resultado", "Resultado del"), ("resumen", "Resumen")]

    def construir(self):
        self.muestra = c.selector("Muestra", 480, self._al_elegir_muestra)
        self.resultado = c.campo("Resultado del análisis", None, multiline=True, min_lines=3, max_lines=4,
                                 helper="Obligatorio. Se conserva el texto y sus saltos de línea.",
                                 validar=lambda t: validar_texto(t, "Resultado", obligatorio=True))
        self.obs = c.campo("Observaciones del resultado", 520, multiline=True, min_lines=2, max_lines=4)
        self.fecha = c.campo_fecha_hora("Fecha del resultado", 250,
                                       fecha_maxima=date.today,
                                       helper="Hasta el momento actual. Vuelve al momento actual al guardar.")
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        self.btn_registrar = c.boton("Registrar resultado y generar PDF", self._registrar,
                                     ft.Icons.ASSIGNMENT_TURNED_IN)
        self.btn_registrar.disabled = True
        self.aviso_muestra = c.nota("Seleccione una muestra recibida para registrar el resultado.")
        self.aviso_muestra.size = 13
        self.aviso_muestra.no_wrap = False
        return c.pagina(
            _tarjeta_laboratorio("Resultado de análisis", "Registro y comprobante del resultado de la muestra.",
                                 ft.Icons.ASSIGNMENT_TURNED_IN,
                                 _fila_laboratorio(self, self.muestra, self.fecha, columnas=2),
                                 ft.Container(self.aviso_muestra, padding=ft.Padding.all(12),
                                              bgcolor=ft.Colors.GREY_50, border_radius=8),
                                 _fila_laboratorio(self, self.resultado, columnas=1),
                                 _fila_laboratorio(self, self.obs, columnas=1),
                                 c.nota("Sólo las muestras recibidas pueden analizarse; las rechazadas figuran "
                                        "para que quede claro por qué no se procesan. Al registrar el resultado "
                                        "se emite el comprobante en PDF."),
                                 _acciones_laboratorio(self.btn_registrar)),
            _tarjeta_laboratorio("Resultados emitidos", "Resultados registrados y reemisión de comprobantes.",
                                 ft.Icons.ASSIGNMENT_TURNED_IN,
                                 _tabla_laboratorio(self, self.tabla, 1300, con_acciones=True)), scroll=True)

    def refrescar(self):
        opciones = []
        self._estados_muestra = {}
        for m in self.srv.laboratorio.listar_muestras():
            if m["estado"] in ("RECIBIDA", "RECHAZADA"):
                sufijo = " · RECHAZADA" if m["estado"] == "RECHAZADA" else ""
                opciones.append({"id": m["id"], "etiqueta": m["etiqueta"] + sufijo})
                self._estados_muestra[str(m["id"])] = m["estado"]
        c.cargar_selector(self.muestra, opciones)
        c.llenar_tabla(self.tabla, self.COLS, self.srv.laboratorio.listar_resultados(), lambda m: [
            c.boton_icono(ft.Icons.PICTURE_AS_PDF, "Comprobante de resultados (PDF)",
                          lambda e, m=m: self._comprobante(m["id"], "Comprobante emitido"), grupo=self)])
        self._al_elegir_muestra()

    def _al_elegir_muestra(self, e=None):
        estado = getattr(self, "_estados_muestra", {}).get(self.muestra.value)
        self.btn_registrar.disabled = estado != "RECIBIDA"
        self.aviso_muestra.value = ("La muestra fue rechazada y no puede analizarse." if estado == "RECHAZADA"
                                   else "Lista para registrar el resultado." if estado == "RECIBIDA"
                                   else "Seleccione una muestra recibida para registrar el resultado.")
        self.app.actualizar()

    def _registrar(self, e=None):
        id_muestra = None

        def accion():
            nonlocal id_muestra
            id_muestra = c.requerir(self.muestra, "una muestra")
            return self.srv.laboratorio.registrar_resultado(
                id_muestra, self.resultado.value, self.obs.value,
                c.leer_fecha_hora(self.fecha.value, "Fecha del resultado"))
        if self.ejecutar(accion, campos={
                "Muestra": self.muestra, "Resultado": self.resultado, "Fecha del resultado": self.fecha}):
            self.btn_registrar.disabled = True  # el commit ya ocurrió, incluso si falló el refresco
            self.resultado.value = self.obs.value = ""
            c.reponer_fecha(self.fecha)
            self.app.ok("Resultado registrado (muestra «Analizada»).")
            self._comprobante(id_muestra, "Comprobante emitido", resultado_recien_guardado=True)

    def _comprobante(self, id_muestra, mensaje, resultado_recien_guardado=False):
        """Genera el comprobante de resultados en PDF y lo abre."""
        def accion():
            datos = self.srv.laboratorio.obtener_comprobante_resultado(id_muestra)
            return exportar_con_nombre_unico(
                self.app.ruta_bd, f"comprobante_resultado_M{id_muestra:04d}", "pdf",
                lambda ruta: exportar_comprobante_resultado_pdf(ruta, datos))
        error_pdf = ("El resultado permanece guardado. No se pudo generar el PDF; "
                     "puede reemitirlo desde la tabla de resultados." if resultado_recien_guardado else
                     "No se pudo generar el comprobante PDF. El resultado permanece guardado; "
                     "puede reemitirlo desde la tabla de resultados.")
        ruta = self.ejecutar(accion, mensaje_error=error_pdf)
        if ruta:
            self.app.ok(f"{mensaje}: {ruta}")
            self.app.abrir_archivo(ruta)
            self.app.actualizar()
        return ruta


class PestanaSeguimiento(Pantalla):
    nombre, icono = "Seguimiento", ft.Icons.TIMELINE
    COLS = [("id_txt", "Muestra"), ("tipo", "Tipo"), ("estudio", "Estudio"), ("mascota", "Mascota"),
            ("clinica", "Clínica"), ("extraccion", "Extracción"), ("estado", "Estado"),
            ("remito_txt", "Remito")]

    def construir(self):
        self.filtro = c.desplegable_fijo("Estado", ["Todos", "EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO",
                                                    "RECIBIDA", "ANALIZADA", "RECHAZADA"], "Todos", 200)
        self.filtro.on_select = self._filtrar
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        return c.pagina(
            _tarjeta_laboratorio("Seguimiento de muestras", "Consulta de estado y cadena de custodia.", ft.Icons.TIMELINE,
                                 _fila_laboratorio(self, self.filtro),
                                 c.nota("Cada cambio de estado queda registrado y no puede modificarse.")),
            _tarjeta_laboratorio("Muestras registradas", "Muestras biológicas, remitos y estados actuales.",
                                 ft.Icons.BIOTECH, _tabla_laboratorio(self, self.tabla, 1400, con_acciones=True)))

    def refrescar(self):
        estado = self.filtro.value
        muestras = [m for m in self.srv.laboratorio.listar_muestras()
                    if estado in (None, "", "Todos") or m["estado"] == estado]
        for m in muestras:
            m["id_txt"] = f"M-{m['id']:04d}"
            m["remito_txt"] = f"R-{m['id_remito']:04d}" if m["id_remito"] else "—"
        c.llenar_tabla(self.tabla, self.COLS, muestras, lambda m: [
            c.boton_icono(ft.Icons.TIMELINE, "Ver cadena de custodia", lambda e, m=m: self._ver(m), grupo=self)])

    def _filtrar(self, e=None):
        self.refrescar()
        self.app.actualizar()

    def _ver(self, m):
        historial = self.srv.laboratorio.historial_muestra(m["id"])
        resultado = self.srv.laboratorio.obtener_resultado(m["id"])
        contenido = c.linea_tiempo(historial)
        if resultado:
            contenido += [ft.Divider(), ft.Text("Resultado", weight=ft.FontWeight.W_500),
                          ft.Text(resultado["resultado"], size=12),
                          ft.Text(resultado["observaciones"] or "", size=12, italic=True)]
        contenido.append(c.nota("Registro inmutable: el historial no puede modificarse ni eliminarse."))
        c.dialogo(self.app, f"Cadena de custodia de {m['id_txt']} · {m['tipo']}", contenido,
                  ancho=560, alto=460)


class SeccionLaboratorio(Seccion):
    nombre, icono = "Laboratorio", ft.Icons.BIOTECH
    subtitulo = "Del empaquetado en la clínica al resultado del análisis"
    PESTANAS = [PestanaEmpaquetado, PestanaEnvio, PestanaResultados, PestanaSeguimiento]
    refrescar_hermanas = True   # cada cambio de estado de una muestra actualiza el seguimiento
