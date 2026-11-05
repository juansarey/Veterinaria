"""Turnos, veterinarios, clínicas y agenda médica."""

from datetime import date, datetime, timedelta

import flet as ft

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.base import validar_nombre_persona, validar_telefono, validar_texto


def _cabecera_turnos(titulo, descripcion, icono):
    return ft.Row([
        ft.Container(ft.Icon(icono, size=24, color=c.COLOR), padding=ft.Padding.all(10),
                     bgcolor=ft.Colors.TEAL_50, border_radius=10),
        ft.Column([ft.Text(titulo, size=18, weight=ft.FontWeight.W_600), c.nota(descripcion)],
                  spacing=3, expand=True),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)


def _tarjeta_turnos(titulo, descripcion, icono, *controles):
    tarjeta = c.tarjeta(_cabecera_turnos(titulo, descripcion, icono), *controles)
    tarjeta.border_radius = 14
    tarjeta.content.spacing = 18
    tarjeta.content.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    return tarjeta


def _fila_turnos(pantalla, *controles, columnas=3):
    """Reparte campos por el ancho interior real, sin reconstruir controles ni sus eventos."""
    for control in controles:
        control.width = None
        control.border = ft.OutlineInputBorder(border_radius=8)
        control.content_padding = ft.Padding.symmetric(horizontal=12, vertical=14)
        control.label_style = ft.TextStyle(size=14, weight=ft.FontWeight.W_500)
        if isinstance(control, ft.Dropdown):
            control.expanded_insets = ft.Padding.all(0)
        else:
            control.error_max_lines = 10
            control.helper_max_lines = 3
            sufijo = control.suffix
            for boton in (sufijo.controls if isinstance(sufijo, ft.Row) else [sufijo] if sufijo else []):
                boton.width = boton.height = 24
    fila = ft.Row(list(controles), wrap=True, spacing=14, run_spacing=16,
                  vertical_alignment=ft.CrossAxisAlignment.START)

    def ajustar_ancho(e):
        if e.width <= 0:
            return
        cantidad = min(columnas, 3 if e.width >= 820 else 2 if e.width >= 560 else 1)
        ancho = int((e.width - 14 * (cantidad - 1)) / cantidad * 100) / 100
        if any(control.width != ancho for control in controles):
            for control in controles:
                control.width = ancho
            pantalla.app.actualizar()

    fila.on_size_change = ajustar_ancho
    return fila


def _acciones_turnos(*botones):
    for boton in botones:
        boton.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=22, vertical=14))
    return ft.Row(list(botones), wrap=True, spacing=12, run_spacing=10,
                  alignment=ft.MainAxisAlignment.END)


def _tabla_turnos(pantalla, tabla, ancho_minimo):
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


class PestanaAgenda(Pantalla):
    nombre, icono = "Agenda de turnos", ft.Icons.EVENT
    COLS = [("inicio_txt", "Inicio"), ("fin_txt", "Fin"), ("veterinario", "Veterinario"),
            ("mascota", "Mascota"), ("motivo", "Motivo"), ("estado", "Estado")]

    def construir(self):
        self.vet = c.selector("Veterinario", 300)
        self.mascota = c.selector("Mascota", 300)
        self.fecha = c.campo_fecha("Fecha", 180, date.today(), fecha_minima=date.today)
        self.hora = c.campo_hora("Hora (HH:MM)", 150, "10:00")
        self.duracion = c.desplegable_fijo("Duración", ["15", "30", "45", "60"], "30", 110)
        self.motivo = c.campo("Motivo", 260, validar=lambda t: validar_texto(t, "Motivo", 200))
        self.dia = c.campo_fecha("Ver día", 180, date.today(), on_submit=self._ver, opcional=True)
        self.filtro_vet = c.selector("Filtrar veterinario", 280, self._ver)
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)

        # Las etiquetas externas permanecen visibles, sin etiquetas flotantes duplicadas.
        for control in (self.vet, self.mascota, self.fecha, self.hora, self.duracion, self.motivo):
            control.width = None
            control.label = None
            control.content_padding = ft.Padding.symmetric(horizontal=14, vertical=16)
            control.border = ft.OutlineInputBorder(border_radius=8)
            if isinstance(control, ft.TextField):
                control.error_max_lines = 10
        for control, etiqueta, nombre in ((self.vet, "Veterinario", "un veterinario"),
                                          (self.mascota, "Mascota", "una mascota"),
                                          (self.duracion, "Duración", None)):
            # También se expande el campo interno del Dropdown, no sólo su celda.
            control.expanded_insets = ft.Padding.all(0)
            control.dense = False
            control.content_padding = ft.Padding.symmetric(horizontal=14, vertical=21)
            control._validar_entrada = lambda valor, control=control, etiqueta=etiqueta, nombre=nombre: (
                self._seleccion_turno(control, etiqueta, nombre))
        self.vet.hint_text = self.mascota.hint_text = "Seleccionar"
        self.motivo.hint_text = "Ej.: Control general"
        self.motivo.content_padding = ft.Padding.symmetric(horizontal=14, vertical=17)
        for control in (self.fecha, self.hora):
            control.content_padding = ft.Padding.symmetric(horizontal=14, vertical=18.5)
        for boton in (*self.fecha.suffix.controls, self.hora.suffix):
            boton.width = boton.height = 24
        for opcion in self.duracion.options:
            opcion.text = f"{opcion.key} min"

        self._fila_selectores = ft.Row([
            ft.Column([ft.Text(etiqueta, size=14, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
                       control], spacing=6, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
            for etiqueta, control in (("Veterinario *", self.vet), ("Mascota *", self.mascota))],
            wrap=True, spacing=14, run_spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)
        self._fila_horario = ft.Row([
            ft.Column([ft.Text(etiqueta, size=14, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
                       control], spacing=6, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
            for etiqueta, control in (("Fecha *", self.fecha), ("Hora *", self.hora), ("Duración *", self.duracion))],
            wrap=True, spacing=14, run_spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)
        motivo = ft.Column([
            ft.Text("Motivo de consulta (opcional)", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
            self.motivo], spacing=6, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        reservar = c.boton("Reservar turno", self._reservar, ft.Icons.EVENT_AVAILABLE)
        reservar.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14),
                                        padding=ft.Padding.symmetric(horizontal=22, vertical=16),
                                        text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600))
        reservar.height = 56
        nuevo_turno = c.tarjeta(
            ft.Row([ft.Text("Nuevo turno", size=20, weight=ft.FontWeight.W_600), c.nota("* Campos obligatorios")],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, spacing=14, run_spacing=4),
            self._fila_selectores, self._fila_horario, motivo,
            ft.Row([reservar], alignment=ft.MainAxisAlignment.END),
            c.nota("El turno debe estar dentro de la agenda del veterinario y no superponerse "
                   "con otro turno activo."))
        nuevo_turno.padding = ft.Padding.all(16)
        nuevo_turno.border_radius = 18
        nuevo_turno.content.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        nuevo_turno.content.spacing = 16
        nuevo_turno.on_size_change = self._ajustar_formulario_turno
        return c.pagina(
            nuevo_turno,
            _tarjeta_turnos("Turnos agendados", "Consulta por día y veterinario o muestra todos los turnos.",
                            ft.Icons.EVENT_NOTE,
                            _fila_turnos(self, self.dia, self.filtro_vet, columnas=2),
                            _acciones_turnos(c.boton("Ver agenda", self._ver, ft.Icons.SEARCH, False),
                                             c.boton("Ver todos", self._ver_todos, ft.Icons.LIST, False)),
                            _tabla_turnos(self, self.tabla, 1100)))

    def _ajustar_formulario_turno(self, e):
        """Ajusta las celdas y sus campos al ancho medido de la tarjeta, incluida la barra lateral."""
        ancho = round(e.width - 34, 2)  # padding de 16 y borde de 1 a cada lado
        if ancho <= 0 or ancho == getattr(self, "_ancho_formulario", None):
            return
        self._ancho_formulario = ancho
        for fila, minimo in ((self._fila_selectores, 480), (self._fila_horario, 640)):
            cantidad = len(fila.controls) if ancho >= minimo else 1
            # Redondear hacia abajo evita que una fracción desplace la última celda a otra fila.
            celda = int((ancho - 14 * (cantidad - 1)) / cantidad * 100) / 100
            for columna in fila.controls:
                columna.width = columna.controls[1].width = celda
        self.app.actualizar()

    def refrescar(self):
        vets = self.srv.clinica.listar_veterinarios()
        c.cargar_selector(self.vet, vets)
        c.cargar_selector(self.filtro_vet, vets)
        c.cargar_selector(self.mascota, self.srv.clinica.listar_mascotas())
        self._tabla()

    def _tabla(self, estricto=False):
        turnos = self.srv.clinica.listar_turnos()
        try:
            dia = c.leer_fecha_opcional(self.dia.value, "Ver día")
        except ErrorNegocio:
            if estricto:
                raise
            dia = None
        idv = c.id_de(self.filtro_vet)
        filas = [t for t in turnos if (dia is None or t["fecha"] == dia) and (idv is None or t["id_veterinario"] == idv)]
        c.llenar_tabla(self.tabla, self.COLS, filas, lambda t: [
            c.boton_icono(ft.Icons.CHECK, "Confirmar", lambda e, t=t: self._cambiar(t, "confirmar"),
                          visible=t["estado"] == "PENDIENTE", grupo=self),
            c.boton_icono(ft.Icons.DONE_ALL, "Marcar atendido", lambda e, t=t: self._cambiar(t, "atender"),
                          ft.Colors.GREEN_600, visible=t["estado"] == "CONFIRMADO", grupo=self),
            c.boton_icono(ft.Icons.EVENT_BUSY, "Cancelar turno", lambda e, t=t: self._cambiar(t, "cancelar"),
                          ft.Colors.RED_400, visible=t["estado"] in ("PENDIENTE", "CONFIRMADO"), grupo=self)])

    def _ver(self, e=None):
        self.ejecutar(lambda: self._tabla(estricto=True))

    def _ver_todos(self, e=None):
        self.dia.value = self.dia.data = ""
        self.filtro_vet.value = None
        self.ejecutar(self._tabla)

    def _seleccion_turno(self, control, etiqueta, nombre=None):
        """Mantiene mensajes y campos de error al separar la etiqueta visual del selector."""
        try:
            return c.requerir(control, nombre) if nombre else c.opcion_de(control)
        except ErrorNegocio as error:
            raise ErrorNegocio(str(error).replace("«None»", f"«{etiqueta}»"), etiqueta) from error

    def _reservar(self, e=None):
        def accion():
            inicio = datetime.combine(c.leer_fecha(self.fecha.value, "Fecha"),
                                      c.leer_hora(self.hora.value, "Hora"))
            fin = inicio + timedelta(minutes=int(self._seleccion_turno(self.duracion, "Duración")))
            self.srv.clinica.agendar_turno(self._seleccion_turno(self.vet, "Veterinario", "un veterinario"),
                                           self._seleccion_turno(self.mascota, "Mascota", "una mascota"), inicio, fin,
                                           self.motivo.value)
            self.dia.value = self.dia.data = self.fecha.value      # muestra el día reservado
            self.motivo.value = ""
        self.ejecutar(accion, "Turno reservado.", {
            "Veterinario": self.vet, "Mascota": self.mascota, "Fecha": self.fecha, "Hora": self.hora,
            "Duración": self.duracion, "Motivo": self.motivo})

    def _cambiar(self, turno, accion):
        textos = {"confirmar": "confirmado", "cancelar": "cancelado (el horario queda libre)",
                  "atender": "marcado como atendido"}
        self.ejecutar(lambda: self.srv.clinica.cambiar_estado_turno(turno["id"], accion),
                      f"Turno {textos[accion]}.")


class PestanaProfesionales(Pantalla):
    nombre, icono = "Veterinarios y agendas", ft.Icons.BADGE
    COLS_V = [("id", "ID"), ("apellido", "Apellido"), ("nombre", "Nombre"), ("matricula", "Matrícula"),
              ("especialidad", "Especialidad"), ("clinica", "Clínica")]
    COLS_C = [("id", "ID"), ("nombre", "Clínica"), ("direccion", "Dirección"), ("telefono", "Teléfono")]
    ETIQUETAS_DIAS = {DiaSemana.LUNES: "Lun", DiaSemana.MARTES: "Mar", DiaSemana.MIERCOLES: "Mié",
                      DiaSemana.JUEVES: "Jue", DiaSemana.VIERNES: "Vie", DiaSemana.SABADO: "Sáb",
                      DiaSemana.DOMINGO: "Dom"}

    def construir(self):
        self.cl_nombre = c.campo("Nombre", 220, validar=lambda t: validar_texto(t, "Nombre", 100, True))
        self.cl_dir = c.campo("Dirección", 280, validar=lambda t: validar_texto(t, "Dirección", 200, True))
        self.cl_tel = c.campo("Teléfono", 160, validar=validar_telefono, helper="Opcional")
        self.v_clinica = c.selector("Clínica", 260)
        self.v_nombre = c.campo("Nombre", 180, validar=lambda t: validar_nombre_persona(t, "Nombre"))
        self.v_apellido = c.campo("Apellido", 180, validar=lambda t: validar_nombre_persona(t, "Apellido"))
        self.v_mat = c.campo("Matrícula", 140, validar=lambda t: validar_texto(t, "Matrícula", 30, True))
        self.v_esp = c.campo("Especialidad", 200, validar=lambda t: validar_texto(t, "Especialidad", 100))
        self.vet_agenda = c.selector("Veterinario", 320, self._cargar_agenda)
        self.dias = {d: ft.Checkbox(label=t, value=False, width=82) for d, t in self.ETIQUETAS_DIAS.items()}
        self.desde, self.hasta = c.campo_hora("Desde (HH:MM)", 160, "08:00"), c.campo_hora("Hasta (HH:MM)", 160, "16:00")
        self.t_cl = c.crear_tabla(self.COLS_C, con_acciones=True)
        self.t_vet = c.crear_tabla(self.COLS_V, con_acciones=True)
        return c.pagina(
            _tarjeta_turnos("Registrar clínica", "Datos de contacto de la clínica.", ft.Icons.LOCAL_HOSPITAL,
                            _fila_turnos(self, self.cl_nombre, self.cl_dir, self.cl_tel),
                            _acciones_turnos(c.boton("Registrar clínica", self._crear_clinica, ft.Icons.ADD))),
            _tarjeta_turnos("Clínicas registradas", "Clínicas de la red y sus datos de contacto.",
                            ft.Icons.LOCAL_HOSPITAL, _tabla_turnos(self, self.t_cl, 760)),
            _tarjeta_turnos("Registrar veterinario", "Profesional y clínica a la que pertenece.", ft.Icons.BADGE,
                            _fila_turnos(self, self.v_clinica, columnas=1),
                            _fila_turnos(self, self.v_nombre, self.v_apellido, columnas=2),
                            _fila_turnos(self, self.v_mat, self.v_esp, columnas=2),
                            _acciones_turnos(c.boton("Registrar veterinario", self._crear_vet, ft.Icons.ADD))),
            _tarjeta_turnos("Veterinarios registrados", "Profesionales, matrículas y clínicas.",
                            ft.Icons.BADGE, _tabla_turnos(self, self.t_vet, 1000)),
            _tarjeta_turnos("Agenda semanal del veterinario", "Selecciona un profesional y sus días de trabajo.",
                            ft.Icons.CALENDAR_MONTH,
                            _fila_turnos(self, self.vet_agenda, columnas=1),
                            ft.Row(controls=list(self.dias.values()), wrap=True, spacing=12, run_spacing=8),
                            _fila_turnos(self, self.desde, self.hasta, columnas=2),
                            c.nota("Un mismo horario se aplica a todos los días marcados."),
                            _acciones_turnos(c.boton("Guardar agenda", self._guardar_agenda, ft.Icons.SAVE))),
            scroll=True)

    def refrescar(self):
        clinicas = self.srv.clinica.listar_clinicas()
        vets = self.srv.clinica.listar_veterinarios()
        c.cargar_selector(self.v_clinica, clinicas)
        anterior = self.vet_agenda.value
        c.cargar_selector(self.vet_agenda, vets)
        if anterior is not None and self.vet_agenda.value is None:
            for check in self.dias.values():
                check.value = False
            self.desde.value, self.hasta.value = "08:00", "16:00"
        c.llenar_tabla(self.t_cl, self.COLS_C, clinicas, lambda f: [
            c.boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar clínica",
                          lambda e, f=f: self._pedir_baja_clinica(f), ft.Colors.RED_400, grupo=self)])
        c.llenar_tabla(self.t_vet, self.COLS_V, vets, lambda f: [
            c.boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar veterinario",
                          lambda e, f=f: self._pedir_baja_veterinario(f), ft.Colors.RED_400, grupo=self)])

    def _pedir_baja_veterinario(self, fila):
        c.confirmar(self.app,
                    f"¿Eliminar a {fila['apellido']}, {fila['nombre']} "
                    f"(matrícula {fila['matricula']}, ID #{fila['id']})? "
                    "Si tiene agenda semanal, también se eliminarán sus días y horarios.",
                    lambda: self._eliminar_profesional(
                        lambda: self.srv.clinica.eliminar_veterinario(fila["id"]),
                        "Veterinario eliminado."))

    def _pedir_baja_clinica(self, fila):
        c.confirmar(self.app, f"¿Eliminar la clínica {fila['nombre']} (ID #{fila['id']})?",
                    lambda: self._eliminar_profesional(
                        lambda: self.srv.clinica.eliminar_clinica(fila["id"]), "Clínica eliminada."))

    def _eliminar_profesional(self, accion, mensaje):
        if self.ejecutar(accion, mensaje):
            self.app.refrescar_selectores_profesionales()

    def _crear_clinica(self, e=None):
        if self.ejecutar(lambda: self.srv.clinica.crear_clinica(
                self.cl_nombre.value, self.cl_dir.value, self.cl_tel.value), "Clínica registrada.",
                {"Nombre": self.cl_nombre, "Dirección": self.cl_dir, "Teléfono": self.cl_tel}):
            self.cl_nombre.value = self.cl_dir.value = self.cl_tel.value = ""
            self.app.actualizar()

    def _crear_vet(self, e=None):
        if self.ejecutar(lambda: self.srv.clinica.crear_veterinario(
                c.requerir(self.v_clinica, "la clínica del veterinario"), self.v_nombre.value,
                self.v_apellido.value, self.v_mat.value, self.v_esp.value),
                "Veterinario registrado. Falta definir su agenda semanal.",
                {"Clínica": self.v_clinica, "Nombre": self.v_nombre, "Apellido": self.v_apellido,
                 "Matrícula": self.v_mat, "Especialidad": self.v_esp}):
            self.v_nombre.value = self.v_apellido.value = self.v_mat.value = self.v_esp.value = ""
            self.app.actualizar()

    def _cargar_agenda(self, e=None):
        idv = c.id_de(self.vet_agenda)
        agenda = self.srv.clinica.obtener_agenda(idv) if idv else None
        for dia, check in self.dias.items():
            check.value = bool(agenda and dia in agenda["dias"])
        if agenda:
            self.desde.value = agenda["desde"].strftime(c.FMT_HORA)
            self.hasta.value = agenda["hasta"].strftime(c.FMT_HORA)
        self.app.actualizar()

    def _guardar_agenda(self, e=None):
        def accion():
            dias = {d for d, check in self.dias.items() if check.value}
            self.srv.clinica.guardar_agenda(c.requerir(self.vet_agenda, "un veterinario"), dias,
                                            c.leer_hora(self.desde.value, "Desde"),
                                            c.leer_hora(self.hasta.value, "Hasta"))
        self.ejecutar(accion, "Agenda guardada.")


class SeccionTurnos(Seccion):
    nombre, icono = "Turnos", ft.Icons.EVENT
    subtitulo = "La agenda impide turnos fuera de horario o superpuestos"
    PESTANAS = [PestanaAgenda, PestanaProfesionales]
