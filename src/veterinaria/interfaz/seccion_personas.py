"""Clientes, mascotas e historias clínicas (procesos 1 y 2)."""

from datetime import date

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.base import validar_dni, validar_email, validar_nombre_persona, validar_telefono, validar_texto


def _fila_campos(pantalla, *controles, columnas=3):
    """Distribución local al ancho útil de la tarjeta, con altura natural para errores."""
    for control in controles:
        control.width = None
        control.border = ft.OutlineInputBorder(border_radius=8)
        control.content_padding = ft.Padding.symmetric(horizontal=12, vertical=14)
        control.label_style = ft.TextStyle(size=14, weight=ft.FontWeight.W_500)
        if isinstance(control, ft.Dropdown):
            control.expanded_insets = ft.Padding.all(0)
            control.helper_style = ft.TextStyle(size=12, color=ft.Colors.GREY_700)
        else:
            control.helper_max_lines = 3
            control.error_max_lines = 10
    fila = ft.Row(list(controles), wrap=True, spacing=14, run_spacing=16,
                  vertical_alignment=ft.CrossAxisAlignment.START)

    def ajustar_ancho(e):
        if e.width <= 0:
            return
        cantidad = min(columnas, 3 if e.width >= 820 else 2 if e.width >= 560 else 1)
        # Evita que el redondeo del cliente envíe la última celda a otra fila.
        ancho = int((e.width - 14 * (cantidad - 1)) / cantidad * 100) / 100
        if any(control.width != ancho for control in controles):
            for control in controles:
                control.width = ancho
            pantalla.app.actualizar()

    fila.on_size_change = ajustar_ancho
    return fila


def _cabecera(titulo, descripcion, icono):
    return ft.Row([
        ft.Container(ft.Icon(icono, color=c.COLOR, size=24), padding=ft.Padding.all(10),
                     bgcolor=ft.Colors.TEAL_50, border_radius=10),
        ft.Column([titulo, c.nota(descripcion)], spacing=3, expand=True),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)


def _tarjeta_personas(*controles):
    tarjeta = c.tarjeta(*controles)
    tarjeta.border_radius = 14
    tarjeta.content.spacing = 18
    tarjeta.content.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    return tarjeta


def _acciones_formulario(cancelar, guardar):
    guardar.style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.Padding.symmetric(horizontal=24, vertical=14))
    return ft.Row([cancelar, guardar], wrap=True, spacing=12, run_spacing=10,
                  alignment=ft.MainAxisAlignment.END)


def _listado_personas(pantalla, titulo, descripcion, icono, ancho_minimo, *controles):
    tabla = pantalla.tabla
    tabla.columns[-1].label.value = "Acciones"
    tabla.heading_row_color = ft.Colors.TEAL_50
    tabla.heading_row_height = 44
    tabla.data_row_min_height = 46
    tabla.data_row_max_height = float("inf")
    tabla.horizontal_margin = 16
    marco = c.contenedor_tabla(tabla)

    def ajustar_ancho(e):
        # Se mide el marco interior: no depende del ancho de ventana ni de la barra lateral.
        if e.width <= 0:
            return
        ancho = max(ancho_minimo, round(e.width, 2))
        if tabla.width != ancho:
            tabla.width = ancho
            pantalla.app.actualizar()

    marco.on_size_change = ajustar_ancho
    return _tarjeta_personas(
        _cabecera(ft.Text(titulo, size=18, weight=ft.FontWeight.W_600), descripcion, icono),
        *controles, marco)


class PestanaClientes(Pantalla):
    nombre, icono = "Clientes", ft.Icons.PEOPLE
    COLS = [("id", "ID"), ("apellido", "Apellido"), ("nombre", "Nombre"), ("dni", "DNI"),
            ("telefono", "Teléfono"), ("email", "Email")]

    def construir(self):
        self.editando = None
        self.encabezado = ft.Text("Nuevo cliente", size=18, weight=ft.FontWeight.W_600)
        self.nombre_f = c.campo("Nombre", validar=lambda t: validar_nombre_persona(t, "Nombre"), helper="Obligatorio")
        self.apellido_f = c.campo("Apellido", validar=lambda t: validar_nombre_persona(t, "Apellido"), helper="Obligatorio")
        self.dni_f = c.campo("DNI", 160, validar=validar_dni, helper="3 a 8 dígitos, sin puntos")
        self.tel_f = c.campo("Teléfono", 180, validar=validar_telefono, helper="Opcional")
        self.email_f = c.campo("Email", 260, validar=validar_email, helper="Opcional")
        self.btn_cancelar = c.boton("Cancelar edición", self._limpiar, ft.Icons.CLOSE, False)
        self.btn_cancelar.visible = False
        self.btn_guardar = c.boton("Guardar", self._guardar, ft.Icons.SAVE)
        self.buscar = c.campo("Buscar por nombre, apellido o DNI", 340, on_change=self._al_buscar)
        self.buscar.label = "Buscar clientes"
        self.buscar.hint_text = "Nombre, apellido o DNI"
        self.buscar.prefix_icon = ft.Icons.SEARCH
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        self.datos = []
        return c.pagina(
            _tarjeta_personas(
                _cabecera(self.encabezado, "Datos personales y de contacto del cliente.", ft.Icons.PERSON_ADD),
                _fila_campos(self, self.nombre_f, self.apellido_f, self.dni_f),
                _fila_campos(self, self.tel_f, self.email_f, columnas=2),
                _acciones_formulario(self.btn_cancelar, self.btn_guardar)),
            _listado_personas(self, "Clientes registrados", "Listado de clientes del sistema.",
                              ft.Icons.PEOPLE, 860, _fila_campos(self, self.buscar, columnas=1)))

    def refrescar(self):
        self.datos = self.srv.clinica.listar_clientes()
        self._filtrar()

    def _filtrar(self):
        texto = (self.buscar.value or "").strip().lower()
        filas = [d for d in self.datos if not texto or texto in
                 f"{d['nombre']} {d['apellido']} {d['dni']}".lower()]
        c.llenar_tabla(self.tabla, self.COLS, filas, lambda f: [
            c.boton_icono(ft.Icons.EDIT, "Editar", lambda e, f=f: self._editar(f), grupo=self),
            c.boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar", lambda e, f=f: self._pedir_baja(f),
                          ft.Colors.RED_400, grupo=self)])

    def _al_buscar(self, e=None):
        self._filtrar()
        self.app.actualizar()

    def _valores(self):
        return (self.nombre_f.value, self.apellido_f.value, self.dni_f.value,
                self.tel_f.value, self.email_f.value)

    def _guardar(self, e=None):
        campos = {"Nombre": self.nombre_f, "Apellido": self.apellido_f, "DNI": self.dni_f,
                  "Teléfono": self.tel_f, "Email": self.email_f}
        if self.editando is None:
            ok = self.ejecutar(lambda: self.srv.clinica.crear_cliente(*self._valores()),
                               "Cliente registrado.", campos)
        else:
            ok = self.ejecutar(lambda: self.srv.clinica.modificar_cliente(self.editando, *self._valores()),
                               "Cliente actualizado.", campos)
        if ok:
            self._limpiar()

    def _editar(self, fila):
        for control in (self.nombre_f, self.apellido_f, self.dni_f, self.tel_f, self.email_f):
            c.establecer_error(control, None)
        self.editando = fila["id"]
        self.encabezado.value = f"Editando a {fila['apellido']}, {fila['nombre']}"
        self.btn_guardar.content = "Guardar cambios"
        self.nombre_f.value, self.apellido_f.value, self.dni_f.value = fila["nombre"], fila["apellido"], fila["dni"]
        self.tel_f.value, self.email_f.value = fila["telefono"], fila["email"]
        self.btn_cancelar.visible = True
        self.app.actualizar()

    def _pedir_baja(self, fila):
        c.confirmar(self.app, f"¿Eliminar a {fila['apellido']}, {fila['nombre']}?",
                    lambda: self._baja(fila["id"]))

    def _baja(self, id_cliente):
        self.ejecutar(lambda: self.srv.clinica.eliminar_cliente(id_cliente), "Cliente eliminado.")

    def _limpiar(self, e=None):
        self.editando = None
        self.encabezado.value = "Nuevo cliente"
        self.btn_guardar.content = "Guardar"
        for f in (self.nombre_f, self.apellido_f, self.dni_f, self.tel_f, self.email_f):
            f.value = ""
            c.establecer_error(f, None)
        self.btn_cancelar.visible = False
        self.app.actualizar()


class PestanaMascotas(Pantalla):
    nombre, icono = "Mascotas", ft.Icons.PETS
    COLS = [("id", "ID"), ("nombre", "Nombre"), ("especie", "Especie"), ("raza", "Raza"),
            ("sexo", "Sexo"), ("fecha_nacimiento", "Nacimiento"), ("responsable", "Responsable")]
    COLS_AT = [("fecha_txt", "Fecha"), ("tipo", "Tipo"), ("veterinario", "Veterinario"),
               ("motivo", "Motivo"), ("diagnostico", "Diagnóstico")]
    COLS_VAC = [("vacuna", "Vacuna"), ("fecha_aplicacion", "Aplicada"),
                ("proxima_dosis", "Próxima dosis"), ("estado", "Estado")]

    def construir(self):
        self.editando = None
        self.encabezado = ft.Text("Nueva mascota", size=18, weight=ft.FontWeight.W_600)
        self.resp = c.selector("Responsable (obligatorio)", 340)
        self.nombre_f = c.campo("Nombre", 200, validar=lambda t: validar_texto(t, "Nombre", 80, True), helper="Obligatorio")
        self.especie = c.desplegable_fijo("Especie", c.ESPECIES, "Perro")
        self.raza_f = c.campo("Raza", 200, validar=lambda t: validar_texto(t, "Raza", 80), helper="Opcional")
        self.nac_f = c.campo_fecha("Nacimiento", fecha_minima=date.min, fecha_maxima=date.today, opcional=True)
        self.nac_f.helper = "Opcional; hasta hoy"
        for boton in self.nac_f.suffix.controls:
            boton.width = boton.height = 24
        self.sexo = c.desplegable_fijo("Sexo", ["", "Macho", "Hembra"], "", 130)
        self.btn_cancelar = c.boton("Cancelar edición", self._limpiar, ft.Icons.CLOSE, False)
        self.btn_cancelar.visible = False
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        self.btn_guardar = c.boton("Guardar", self._guardar, ft.Icons.SAVE)
        self.datos = []
        return c.pagina(
            _tarjeta_personas(
                _cabecera(self.encabezado, "Datos de la mascota y su responsable.", ft.Icons.PETS),
                _fila_campos(self, self.resp, columnas=1),
                _fila_campos(self, self.nombre_f, self.especie, self.raza_f),
                _fila_campos(self, self.nac_f, self.sexo, columnas=2),
                c.nota("Al registrar una mascota se abre automáticamente su historia clínica."),
                _acciones_formulario(self.btn_cancelar, self.btn_guardar)),
            _listado_personas(self, "Mascotas registradas", "Historia clínica, edición y baja de mascotas.",
                              ft.Icons.PETS, 1040))

    def refrescar(self):
        self.datos = self.srv.clinica.listar_mascotas()
        c.cargar_selector(self.resp, self.srv.clinica.listar_clientes())
        c.llenar_tabla(self.tabla, self.COLS, self.datos, lambda f: [
            c.boton_icono(ft.Icons.MEDICAL_INFORMATION, "Historia clínica", lambda e, f=f: self._historia(f), grupo=self),
            c.boton_icono(ft.Icons.EDIT, "Editar", lambda e, f=f: self._editar(f), grupo=self),
            c.boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar", lambda e, f=f: self._pedir_baja(f),
                          ft.Colors.RED_400, grupo=self)])

    def _guardar(self, e=None):
        nac = lambda: c.leer_fecha_opcional(self.nac_f.value, "Nacimiento")
        campos = {"Nombre": self.nombre_f, "Especie": self.especie, "Raza": self.raza_f,
                  "Sexo": self.sexo, "Nacimiento": self.nac_f, "Responsable": self.resp,
                  self.resp.label: self.resp}
        if self.editando is None:
            ok = self.ejecutar(lambda: self.srv.clinica.crear_mascota(
                c.requerir(self.resp, "un responsable"), self.nombre_f.value,
                c.opcion_de(self.especie), self.raza_f.value, nac(),
                c.opcion_de(self.sexo), abrir_historia=True), "Mascota registrada con su historia clínica.", campos)
        else:
            ok = self.ejecutar(lambda: self.srv.clinica.modificar_mascota(
                self.editando, self.nombre_f.value, c.opcion_de(self.especie), self.raza_f.value, nac(),
                c.opcion_de(self.sexo)), "Mascota actualizada (el responsable no cambia).", campos)
        if ok:
            self._limpiar()

    def _editar(self, fila):
        for control in (self.nombre_f, self.raza_f, self.nac_f, self.resp, self.especie, self.sexo):
            c.establecer_error(control, None)
        self.editando = fila["id"]
        self.encabezado.value = f"Editando a {fila['nombre']}"
        self.btn_guardar.content = "Guardar cambios"
        self.nombre_f.value, self.raza_f.value = fila["nombre"], fila["raza"]
        self.especie.value, self.sexo.value = fila["especie"], fila["sexo"] or ""
        self.nac_f.value = self.nac_f.data = fila["fecha_nacimiento"]
        self.resp.value = str(fila["id_responsable"])
        self.resp.disabled = True
        self.resp.helper_text = "El responsable no puede cambiarse desde este formulario."
        self.btn_cancelar.visible = True
        self.app.actualizar()

    def _pedir_baja(self, fila):
        c.confirmar(self.app, f"¿Eliminar a {fila['nombre']}?", lambda: self.ejecutar(
            lambda: self.srv.clinica.eliminar_mascota(fila["id"]), "Mascota eliminada."))

    def _limpiar(self, e=None):
        self.editando = None
        self.encabezado.value = "Nueva mascota"
        self.btn_guardar.content = "Guardar"
        for f in (self.nombre_f, self.raza_f, self.nac_f):
            f.value = ""
        for control in (self.nombre_f, self.raza_f, self.nac_f, self.resp, self.especie, self.sexo):
            c.establecer_error(control, None)
        self.nac_f.data = ""
        self.resp.value, self.especie.value, self.sexo.value = None, "Perro", ""
        self.resp.disabled = False
        self.resp.helper_text = None
        self.btn_cancelar.visible = False
        self.app.actualizar()

    def _historia(self, fila):
        """Ventana con la historia clínica: atenciones y vacunas de la mascota."""
        historia = self.srv.atencion.obtener_historia(fila["id"])
        atenciones = self.srv.atencion.listar_atenciones(fila["id"])
        aplicaciones = self.srv.atencion.listar_aplicaciones(fila["id"])
        pendientes = self.srv.atencion.vacunas_pendientes(fila["id"])
        t_at, t_vac = c.crear_tabla(self.COLS_AT), c.crear_tabla(self.COLS_VAC)
        c.llenar_tabla(t_at, self.COLS_AT, atenciones)
        c.llenar_tabla(t_vac, self.COLS_VAC, aplicaciones)
        cabecera = (f"Historia abierta el {historia['fecha_apertura']}" if historia
                    else "Sin historia clínica abierta")
        c.dialogo(self.app, f"Historia clínica de {fila['nombre']}", [
            ft.Text(f"{fila['especie']} · Responsable: {fila['responsable']} · {cabecera}", size=12),
            ft.Text("Atenciones", weight=ft.FontWeight.W_500),
            c.contenedor_tabla(t_at) if atenciones else c.nota("Todavía no tiene atenciones."),
            ft.Text("Vacunas aplicadas", weight=ft.FontWeight.W_500),
            c.contenedor_tabla(t_vac) if aplicaciones else c.nota("Sin vacunas registradas."),
            ft.Text("Vacunas obligatorias pendientes: " + (", ".join(pendientes) if pendientes else "ninguna"),
                    color=ft.Colors.RED_700 if pendientes else ft.Colors.GREEN_700,
                    weight=ft.FontWeight.W_500),
        ], ancho=760, alto=520)


class SeccionPersonas(Seccion):
    nombre, icono = "Clientes y mascotas", ft.Icons.PEOPLE
    subtitulo = "Toda mascota debe tener un responsable asociado"
    PESTANAS = [PestanaClientes, PestanaMascotas]
