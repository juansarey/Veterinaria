"""Laboratorio: empaquetado, envío y recepción, resultados y seguimiento de muestras."""

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.pantalla import Pantalla, Seccion


class PestanaEmpaquetado(Pantalla):
    nombre, icono = "Empaquetado", ft.Icons.INVENTORY_2
    COLS = [("id", "Remito"), ("fecha", "Emitido"), ("clinica", "Clínica de origen"),
            ("conservadora", "Conservadora"), ("precinto", "Precinto"), ("muestras", "Muestras"),
            ("estado", "Estado")]

    def construir(self):
        self.clinica = c.selector("Clínica de origen", 260, self._al_elegir_clinica)
        self.conservadora = c.selector("Conservadora disponible", 260)
        self.codigo_cons = c.campo("Nueva conservadora (código)", 230)
        self.fecha = c.campo_fecha_hora("Fecha de empaquetado", 210)
        self.precinto = c.campo("Código del precinto (opcional)", 240)
        self.muestras_box = ft.Column(spacing=0)
        self.checks: dict[int, ft.Checkbox] = {}
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        return ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True, controls=[
            c.tarjeta(c.nota("Se genera el remito biológico y el precinto sanitario; las muestras pasan a "
                             "«Empaquetada» y la conservadora queda en uso."),
                      c.fila(self.clinica, self.conservadora, self.fecha),
                      c.fila(self.codigo_cons, c.boton("Agregar conservadora", self._crear_cons, ft.Icons.ADD, False)),
                      ft.Text("Muestras extraídas pendientes de envío:", weight=ft.FontWeight.W_500),
                      self.muestras_box, self.precinto,
                      c.boton("Empaquetar y precintar", self._empaquetar, ft.Icons.INVENTORY_2),
                      encabezado="Empaquetar muestras en una conservadora"),
            c.contenedor_tabla(self.tabla),
        ])

    def refrescar(self):
        lab = self.srv.laboratorio
        c.cargar_selector(self.clinica, self.srv.clinica.listar_clinicas())
        c.cargar_selector(self.conservadora, lab.listar_conservadoras(solo_disponibles=True))
        c.reponer_fecha(self.fecha)
        remitos = lab.listar_remitos()
        c.llenar_tabla(self.tabla, self.COLS, remitos, lambda r: [
            c.boton_icono(ft.Icons.LOCK_OPEN, "Liberar la conservadora (ya recibida)",
                          lambda e, r=r: self._liberar(r), visible=r["estado"] == "RECIBIDO")])
        self._cargar_muestras()

    def _cargar_muestras(self):
        idc = c.id_de(self.clinica)
        previas = {i for i, ch in self.checks.items() if ch.value}
        libres = [m for m in self.srv.laboratorio.listar_muestras()
                  if m["estado"] == "EXTRAIDA" and (idc is None or m["id_clinica"] == idc)]
        self.checks = {m["id"]: ft.Checkbox(label=f"{m['etiqueta']} · {m['estudio']} · extraída {m['extraccion']}",
                                            value=m["id"] in previas or not previas) for m in libres}
        self.muestras_box.controls = list(self.checks.values()) or [
            ft.Text("No hay muestras extraídas pendientes de envío.", italic=True, size=12)]

    def _al_elegir_clinica(self, e=None):
        self._cargar_muestras()
        self.app.actualizar()

    def _crear_cons(self, e=None):
        if self.ejecutar(lambda: self.srv.laboratorio.crear_conservadora(self.codigo_cons.value),
                         "Conservadora agregada."):
            self.codigo_cons.value = ""

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
        res = self.ejecutar(accion)
        if isinstance(res, dict):
            self.precinto.value = ""
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
        self.remito = c.selector("Remito listo para despachar", 380)
        self.salida = c.campo_fecha_hora("Salida", 200)
        self.obs_envio = c.campo("Observaciones", 260)
        self.envio = c.selector("Envío en tránsito", 380)
        self.f_recepcion = c.campo_fecha_hora("Recepción", 200)
        self.integro = ft.Checkbox(label="Precinto íntegro, sin signos de apertura", value=True)
        self.obs_rec = c.campo("Observaciones", 260)
        self.tabla = c.crear_tabla(self.COLS)
        return ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True, controls=[
            c.tarjeta(self.remito, c.fila(self.salida, self.obs_envio),
                      c.nota("Sólo se despachan remitos con conservadora, muestras y un precinto intacto."),
                      c.boton("Despachar", self._despachar, ft.Icons.LOCAL_SHIPPING),
                      encabezado="1. Despacho desde la clínica"),
            c.tarjeta(self.envio, c.fila(self.f_recepcion, self.obs_rec), self.integro,
                      c.nota("Si el precinto llega roto, las muestras quedan «Rechazadas» y no se procesan."),
                      c.boton("Registrar recepción", self._recibir, ft.Icons.FACT_CHECK),
                      encabezado="2. Recepción en el laboratorio central"),
            c.contenedor_tabla(self.tabla),
        ])

    def refrescar(self):
        lab = self.srv.laboratorio
        c.reponer_fecha(self.salida)
        c.reponer_fecha(self.f_recepcion)
        remitos = lab.listar_remitos()
        c.cargar_selector(self.remito, [r for r in remitos if r["estado"] == "GENERADO" and r["puede_despacharse"]])
        envios = lab.listar_envios()
        c.cargar_selector(self.envio, [e for e in envios if not e["recibido"]])
        c.llenar_tabla(self.tabla, self.COLS, envios)

    def _despachar(self, e=None):
        def accion():
            return self.srv.laboratorio.despachar_remito(
                c.requerir(self.remito, "un remito"), c.leer_fecha_hora(self.salida.value, "Salida"),
                self.obs_envio.value)
        if self.ejecutar(accion, "Remito despachado: las muestras pasan a «En tránsito»."):
            self.obs_envio.value = ""

    def _recibir(self, e=None):
        integro = self.integro.value

        def accion():
            return self.srv.laboratorio.recibir_remito(
                c.requerir(self.envio, "un envío"), integro,
                c.leer_fecha_hora(self.f_recepcion.value, "Recepción"), self.obs_rec.value)
        res = self.ejecutar(accion)
        if isinstance(res, dict):
            self.integro.value = True
            self.obs_rec.value = ""
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

    def construir(self):
        self.muestra = c.selector("Muestra", 480)
        self.resultado = ft.TextField(label="Resultado del análisis", multiline=True, min_lines=3,
                                      max_lines=6, width=520)
        self.obs = c.campo("Observaciones", 520)
        self.fecha = c.campo_fecha_hora("Fecha del resultado", 210)
        return ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True, controls=[
            c.tarjeta(self.muestra, self.resultado, self.obs, self.fecha,
                      c.nota("Sólo las muestras recibidas pueden analizarse; las rechazadas figuran "
                             "para que quede claro por qué no se procesan."),
                      c.boton("Registrar resultado", self._registrar, ft.Icons.ASSIGNMENT_TURNED_IN),
                      encabezado="Resultado de análisis"),
        ])

    def refrescar(self):
        c.reponer_fecha(self.fecha)
        opciones = []
        for m in self.srv.laboratorio.listar_muestras():
            if m["estado"] in ("RECIBIDA", "RECHAZADA"):
                sufijo = " · RECHAZADA" if m["estado"] == "RECHAZADA" else ""
                opciones.append({"id": m["id"], "etiqueta": m["etiqueta"] + sufijo})
        c.cargar_selector(self.muestra, opciones)

    def _registrar(self, e=None):
        def accion():
            return self.srv.laboratorio.registrar_resultado(
                c.requerir(self.muestra, "una muestra"), self.resultado.value, self.obs.value,
                c.leer_fecha_hora(self.fecha.value, "Fecha del resultado"))
        if self.ejecutar(accion, "Resultado registrado: la muestra pasó a «Analizada»."):
            self.resultado.value = self.obs.value = ""


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
        return ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True, controls=[
            c.tarjeta(c.nota("Cada cambio de estado queda registrado y no puede modificarse."),
                      self.filtro, c.contenedor_tabla(self.tabla), encabezado="Trazabilidad de muestras"),
        ])

    def refrescar(self):
        estado = self.filtro.value
        muestras = [m for m in self.srv.laboratorio.listar_muestras()
                    if estado in (None, "", "Todos") or m["estado"] == estado]
        for m in muestras:
            m["id_txt"] = f"M-{m['id']:04d}"
            m["remito_txt"] = f"R-{m['id_remito']:04d}" if m["id_remito"] else "—"
        c.llenar_tabla(self.tabla, self.COLS, muestras, lambda m: [
            c.boton_icono(ft.Icons.TIMELINE, "Ver cadena de custodia", lambda e, m=m: self._ver(m))])

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
