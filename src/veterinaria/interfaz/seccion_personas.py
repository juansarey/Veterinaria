"""Clientes, mascotas e historias clínicas (procesos 1 y 2)."""

from datetime import date

import flet as ft

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.base import validar_dni, validar_email, validar_nombre_persona, validar_telefono, validar_texto


class PestanaClientes(Pantalla):
    nombre, icono = "Clientes", ft.Icons.PEOPLE
    COLS = [("id", "ID"), ("apellido", "Apellido"), ("nombre", "Nombre"), ("dni", "DNI"),
            ("telefono", "Teléfono"), ("email", "Email")]

    def construir(self):
        self.editando = None
        self.encabezado = ft.Text("Nuevo cliente", size=16, weight=ft.FontWeight.W_600)
        self.nombre_f = c.campo("Nombre", validar=lambda t: validar_nombre_persona(t, "Nombre"), helper="Obligatorio")
        self.apellido_f = c.campo("Apellido", validar=lambda t: validar_nombre_persona(t, "Apellido"), helper="Obligatorio")
        self.dni_f = c.campo("DNI", 160, validar=validar_dni, helper="3 a 8 dígitos, sin puntos")
        self.tel_f = c.campo("Teléfono", 180, validar=validar_telefono, helper="Opcional")
        self.email_f = c.campo("Email", 260, validar=validar_email, helper="Opcional")
        self.btn_cancelar = c.boton("Cancelar edición", self._limpiar, ft.Icons.CLOSE, False)
        self.btn_cancelar.visible = False
        self.btn_guardar = c.boton("Guardar", self._guardar, ft.Icons.SAVE)
        self.buscar = c.campo("Buscar por nombre, apellido o DNI", 340, on_change=self._al_buscar)
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        self.datos = []
        return c.pagina(
            c.tarjeta(self.encabezado, c.fila(self.nombre_f, self.apellido_f, self.dni_f),
                      c.fila(self.tel_f, self.email_f),
                      c.fila(self.btn_guardar, self.btn_cancelar)),
            ft.Row([self.buscar]), c.contenedor_tabla(self.tabla))

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
        self.encabezado = ft.Text("Nueva mascota", size=16, weight=ft.FontWeight.W_600)
        self.resp = c.selector("Responsable (obligatorio)", 340)
        self.nombre_f = c.campo("Nombre", 200, validar=lambda t: validar_texto(t, "Nombre", 80, True), helper="Obligatorio")
        self.especie = c.desplegable_fijo("Especie", c.ESPECIES, "Perro")
        self.raza_f = c.campo("Raza", 200, validar=lambda t: validar_texto(t, "Raza", 80), helper="Opcional")
        self.nac_f = c.campo_fecha("Nacimiento", fecha_minima=date.min, fecha_maxima=date.today, opcional=True)
        self.nac_f.helper = "Opcional; hasta hoy"
        self.sexo = c.desplegable_fijo("Sexo", ["", "Macho", "Hembra"], "", 130)
        self.btn_cancelar = c.boton("Cancelar edición", self._limpiar, ft.Icons.CLOSE, False)
        self.btn_cancelar.visible = False
        self.tabla = c.crear_tabla(self.COLS, con_acciones=True)
        self.btn_guardar = c.boton("Guardar", self._guardar, ft.Icons.SAVE)
        self.datos = []
        return c.pagina(
            c.tarjeta(self.encabezado, self.resp,
                      c.fila(self.nombre_f, self.especie, self.raza_f, self.nac_f, self.sexo),
                      c.nota("Al registrar una mascota se abre automáticamente su historia clínica."),
                      c.fila(self.btn_guardar, self.btn_cancelar)),
            c.contenedor_tabla(self.tabla))

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
