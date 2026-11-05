"""Atención clínica, derivación a laboratorio, comprobantes y vacunación."""

from datetime import date

import flet as ft

from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.exportaciones import exportar_con_nombre_unico
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.exportador import exportar_comprobante_pdf
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.base import validar_texto

TIPOS_MUESTRA = ["Sangre", "Orina", "Materia fecal", "Piel / raspado", "Biopsia", "Otra"]


class PestanaAtenciones(Pantalla):
    nombre, icono = "Atenciones", ft.Icons.MEDICAL_SERVICES
    COLS = [("fecha_txt", "Fecha"), ("mascota", "Mascota"), ("tipo", "Tipo"), ("veterinario", "Veterinario"),
            ("motivo", "Motivo"), ("diagnostico", "Diagnóstico"), ("derivaciones", "Derivaciones"),
            ("comprobante", "Comprobante")]

    def construir(self):
        self.mascota = c.selector("Mascota", 300, self._al_elegir_mascota)
        self.estado_historia = ft.Text("Seleccione una mascota.", size=12)
        self.estado_vacunas = ft.Text("", size=12, weight=ft.FontWeight.W_500)
        self.btn_historia = c.boton("Abrir historia clínica", self._abrir_historia, ft.Icons.FOLDER_OPEN, False)
        self.btn_historia.visible = False
        self.vet = c.selector("Veterinario", 280)
        self.fecha = c.campo_fecha_hora(
            "Fecha y hora", 250, on_change=self._al_cambiar_fecha,
            helper="Vuelve al momento actual al guardar.")
        self.tipo = c.desplegable_fijo("Tipo", [t.name for t in TipoAtencion], TipoAtencion.CONSULTA.name, 150)
        self.motivo = c.campo("Motivo", 300, validar=lambda t: validar_texto(t, "Motivo", 200))
        self.diagnostico = c.campo("Diagnóstico", 300, multiline=True, min_lines=2, max_lines=4)
        self.observaciones = c.campo("Observaciones de atención", 300,
                                    multiline=True, min_lines=2, max_lines=4)
        # derivación
        self.atencion = c.selector("Atención a derivar", 380)
        self.estudio = c.campo("Estudio solicitado", 230, hint_text="Hemograma, urianálisis…",
                               validar=lambda t: validar_texto(t, "Estudio solicitado", 200, True))
        self.tipo_muestra = c.desplegable_fijo("Tipo de muestra", TIPOS_MUESTRA, "Sangre", 190)
        self.obs_orden = c.campo("Observaciones de derivación", 300,
                                 multiline=True, min_lines=2, max_lines=4)
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        return c.pagina(
            c.tarjeta(c.fila(self.mascota, self.vet, self.fecha, self.tipo),
                      c.fila(self.estado_historia, self.estado_vacunas, self.btn_historia),
                      c.fila(self.motivo, self.diagnostico, self.observaciones,
                             c.boton("Registrar atención", self._registrar, ft.Icons.SAVE)),
                      encabezado="Nueva atención"),
            c.tarjeta(c.fila(self.atencion, self.estudio, self.tipo_muestra, self.obs_orden,
                             c.boton("Derivar a laboratorio", self._derivar, ft.Icons.BIOTECH)),
                      encabezado="Derivar a laboratorio (emite la orden y registra la muestra extraída)"),
            c.contenedor_tabla(self.tabla), scroll=True)

    def refrescar(self):
        c.cargar_selector(self.mascota, self.srv.clinica.listar_mascotas())
        c.cargar_selector(self.vet, self.srv.clinica.listar_veterinarios())
        self.atenciones = self.srv.atencion.listar_atenciones()
        c.cargar_selector(self.atencion, self.atenciones)
        c.llenar_tabla(self.tabla, self.COLS, self.atenciones, lambda a: [
            c.boton_icono(ft.Icons.BIOTECH, "Derivar a laboratorio", lambda e, a=a: self._elegir_derivar(a), grupo=self),
            c.boton_icono(ft.Icons.RECEIPT_LONG, "Comprobante (PDF)", lambda e, a=a: self._comprobante(a), grupo=self)])
        self._estado_mascota()

    # ---------------------------------------------------------- estado de la mascota
    def _al_elegir_mascota(self, e=None):
        self._estado_mascota()
        self.app.actualizar()

    def _al_cambiar_fecha(self, e=None):
        self._estado_mascota()
        self.app.actualizar()

    def _estado_mascota(self):
        idm = c.id_de(self.mascota)
        if idm is None:
            self.estado_historia.value, self.estado_vacunas.value = "Seleccione una mascota.", ""
            self.btn_historia.visible = False
            return
        historia = self.srv.atencion.obtener_historia(idm)
        self.estado_historia.value = (
            f"Historia clínica abierta el {historia['fecha_apertura']}." if historia
            else "La mascota no tiene historia clínica: ábrala antes de registrar la atención.")
        self.btn_historia.visible = historia is None
        try:
            referencia = c.leer_fecha_hora(self.fecha.value, "Fecha y hora").date()
        except ErrorNegocio:
            self.estado_vacunas.value = "Complete una fecha válida para consultar las vacunas."
            self.estado_vacunas.color = ft.Colors.GREY_700
            return
        pendientes = self.srv.atencion.vacunas_pendientes(idm, referencia)
        self.estado_vacunas.value = (f"Advertencia: vacunas obligatorias pendientes al {referencia:%d/%m/%Y}: "
                                     + ", ".join(pendientes) + ". Puede registrar la atención. "
                                     "Regularice la vacunación en la pestaña Vacunas." if pendientes
                                     else "Vacunas obligatorias al día.")
        self.estado_vacunas.color = ft.Colors.AMBER_800 if pendientes else ft.Colors.GREEN_700

    def _abrir_historia(self, e=None):
        self.ejecutar(lambda: self.srv.atencion.abrir_historia(c.requerir(self.mascota, "una mascota")),
                      "Historia clínica abierta.")

    # ------------------------------------------------------------------ acciones
    def _registrar(self, e=None):
        def accion():
            id_mascota = c.requerir(self.mascota, "una mascota")
            id_veterinario = c.requerir(self.vet, "un veterinario")
            fecha = c.leer_fecha_hora(self.fecha.value, "Fecha y hora")
            # Reconsultar con la fecha a guardar, aunque no haya ocurrido un evento de edición.
            self._estado_mascota()
            return self.srv.atencion.registrar_atencion(
                id_mascota, id_veterinario, fecha, TipoAtencion[c.opcion_de(self.tipo)],
                self.motivo.value, self.diagnostico.value, self.observaciones.value)
        if self.ejecutar(accion, "Atención registrada.", {
                "Mascota": self.mascota, "Veterinario": self.vet, "Fecha y hora": self.fecha,
                "Tipo": self.tipo, "Motivo": self.motivo}):
            self.motivo.value = self.diagnostico.value = self.observaciones.value = ""
            c.reponer_fecha(self.fecha)
            self._estado_mascota()
            self.app.actualizar()

    def _elegir_derivar(self, atencion):
        self.atencion.value = str(atencion["id"])
        self.app.actualizar()

    def _derivar(self, e=None):
        def accion():
            return self.srv.laboratorio.derivar(
                c.requerir(self.atencion, "una atención"), self.estudio.value, c.opcion_de(self.tipo_muestra),
                observaciones=self.obs_orden.value)
        res = self.ejecutar(accion, campos={
            "Atención": self.atencion, self.atencion.label: self.atencion,
            "Estudio solicitado": self.estudio, "Tipo de muestra": self.tipo_muestra})
        if isinstance(res, dict):
            self.estudio.value = self.obs_orden.value = ""
            self.app.ok(f"Orden #{res['id_orden']} emitida y muestra M-{res['id_muestra']:04d} extraída. "
                        "Siga en Laboratorio › Empaquetado.")
            self.app.actualizar()

    def _comprobante(self, atencion):
        """Emite el comprobante (si falta), lo exporta a PDF y lo abre."""
        def accion():
            id_at = atencion["id"]
            if self.srv.atencion.obtener_comprobante(id_at) is None:
                self.srv.atencion.emitir_comprobante(id_at)
            comp = self.srv.atencion.obtener_comprobante(id_at)
            return exportar_con_nombre_unico(
                self.app.ruta_bd, f"comprobante_{id_at}", "pdf",
                lambda ruta: exportar_comprobante_pdf(ruta, comp))
        ruta = self.ejecutar(accion, mensaje_error="La atención permanece guardada. No se pudo generar "
                              "el comprobante PDF; puede volver a emitirlo desde la tabla de atenciones.")
        if ruta:
            self.app.ok(f"Comprobante emitido: {ruta}")
            self.app.abrir_archivo(ruta)


class PestanaVacunas(Pantalla):
    nombre, icono = "Vacunas", ft.Icons.VACCINES
    COLS_V = [("id", "ID"), ("nombre", "Vacuna"), ("especie", "Especie"), ("obligatoria", "Obligatoria")]
    COLS_A = [("vacuna", "Vacuna"), ("fecha_aplicacion", "Aplicada"),
              ("proxima_dosis", "Próxima dosis"), ("estado", "Estado")]

    def construir(self):
        self.v_nombre = c.campo("Nombre de la vacuna", 260, validar=lambda t: validar_texto(t, "Nombre", 100, True))
        self.v_especie = c.desplegable_fijo("Especie", c.ESPECIES, "Perro")
        self.v_oblig = ft.Checkbox(label="Obligatoria", value=True)
        self.mascota = c.selector("Mascota", 320, self._al_elegir)
        self.vacuna = c.selector("Vacuna", 300)
        self.f_aplic = c.campo_fecha("Aplicación", 150, date.today())
        self.f_prox = c.campo_fecha("Próxima dosis", 150, opcional=True)
        self.resumen = ft.Text("", size=12, weight=ft.FontWeight.W_500)
        self.t_vac, self.t_apl = c.crear_tabla(self.COLS_V), c.crear_tabla(self.COLS_A)
        izquierda = ft.Column(expand=True, tight=True, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                              controls=[
            c.tarjeta(self.mascota, self.resumen, c.fila(self.vacuna, self.f_aplic, self.f_prox),
                      c.nota("La próxima dosis es opcional; sin ella la aplicación no vence."),
                      c.boton("Registrar aplicación", self._aplicar, ft.Icons.VACCINES),
                      encabezado="Vacunas de la mascota"),
            c.contenedor_tabla(self.t_apl)])
        derecha = ft.Column(expand=True, tight=True, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            controls=[
            c.tarjeta(c.fila(self.v_nombre, self.v_especie, self.v_oblig),
                      c.boton("Registrar vacuna", self._crear_vacuna, ft.Icons.ADD),
                      encabezado="Catálogo de vacunas"),
            c.contenedor_tabla(self.t_vac)])
        return c.pagina(ft.Row([izquierda, derecha], spacing=14,
                               vertical_alignment=ft.CrossAxisAlignment.START))

    def refrescar(self):
        self.vacunas = self.srv.atencion.listar_vacunas()
        c.llenar_tabla(self.t_vac, self.COLS_V, self.vacunas)
        self.mascotas = self.srv.clinica.listar_mascotas()
        c.cargar_selector(self.mascota, self.mascotas)
        self._aplicaciones()

    def _cargar_vacunas_de_la_especie(self):
        """Sólo se ofrecen las vacunas de la especie de la mascota elegida."""
        idm = c.id_de(self.mascota)
        especie = next((m["especie"] for m in self.mascotas if m["id"] == idm), None)
        c.cargar_selector(self.vacuna, [v for v in self.vacunas if especie is None or v["especie"] == especie])

    def _aplicaciones(self):
        self._cargar_vacunas_de_la_especie()
        idm = c.id_de(self.mascota)
        c.llenar_tabla(self.t_apl, self.COLS_A, self.srv.atencion.listar_aplicaciones(idm) if idm else [])
        pendientes = self.srv.atencion.vacunas_pendientes(idm) if idm else []
        self.resumen.value = ("Pendientes: " + ", ".join(pendientes) if pendientes
                              else ("Vacunas obligatorias al día." if idm else ""))
        self.resumen.color = ft.Colors.RED_700 if pendientes else ft.Colors.GREEN_700

    def _al_elegir(self, e=None):
        self._aplicaciones()
        self.app.actualizar()

    def _crear_vacuna(self, e=None):
        if self.ejecutar(lambda: self.srv.atencion.crear_vacuna(
                self.v_nombre.value, c.opcion_de(self.v_especie), self.v_oblig.value), "Vacuna registrada.",
                {"Nombre": self.v_nombre, "Especie": self.v_especie}):
            self.v_nombre.value = ""
            self.app.actualizar()

    def _aplicar(self, e=None):
        def accion():
            return self.srv.atencion.registrar_aplicacion(
                c.requerir(self.mascota, "una mascota"), c.requerir(self.vacuna, "una vacuna"),
                c.leer_fecha(self.f_aplic.value, "Aplicación"),
                c.leer_fecha_opcional(self.f_prox.value, "Próxima dosis"))
        self.ejecutar(accion, "Aplicación registrada.", {
            "Mascota": self.mascota, "Vacuna": self.vacuna,
            "Aplicación": self.f_aplic, "Próxima dosis": self.f_prox})


class SeccionAtencion(Seccion):
    nombre, icono = "Atención", ft.Icons.MEDICAL_SERVICES
    subtitulo = "Consultas, control de vacunas obligatorias, derivación al laboratorio y comprobantes"
    PESTANAS = [PestanaAtenciones, PestanaVacunas]
