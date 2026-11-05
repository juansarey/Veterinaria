"""Turnos, veterinarios, clínicas y agenda médica."""

from datetime import date, datetime, timedelta

import flet as ft

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.pantalla import Pantalla, Seccion
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.base import validar_nombre_persona, validar_telefono, validar_texto


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
        return c.pagina(
            c.tarjeta(c.fila(self.vet, self.mascota, self.fecha, self.hora, self.duracion),
                      c.fila(self.motivo, c.boton("Reservar turno", self._reservar, ft.Icons.EVENT_AVAILABLE)),
                      c.nota("El turno debe estar dentro de la agenda del veterinario y no superponerse "
                             "con otro turno activo."),
                      encabezado="Nuevo turno"),
            c.tarjeta(c.fila(self.dia, self.filtro_vet, c.boton("Ver agenda", self._ver, ft.Icons.SEARCH, False),
                             c.boton("Ver todos", self._ver_todos, ft.Icons.LIST, False)),
                      c.contenedor_tabla(self.tabla), encabezado="Agenda"))

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

    def _reservar(self, e=None):
        def accion():
            inicio = datetime.combine(c.leer_fecha(self.fecha.value, "Fecha"),
                                      c.leer_hora(self.hora.value, "Hora"))
            fin = inicio + timedelta(minutes=int(c.opcion_de(self.duracion)))
            self.srv.clinica.agendar_turno(c.requerir(self.vet, "un veterinario"),
                                           c.requerir(self.mascota, "una mascota"), inicio, fin,
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
        self.dias = {d: ft.Checkbox(label=t, value=False) for d, t in self.ETIQUETAS_DIAS.items()}
        self.desde, self.hasta = c.campo_hora("Desde (HH:MM)", 160, "08:00"), c.campo_hora("Hasta (HH:MM)", 160, "16:00")
        self.t_cl = c.crear_tabla(self.COLS_C, con_acciones=True)
        self.t_vet = c.crear_tabla(self.COLS_V, con_acciones=True)
        return c.pagina(
            c.tarjeta(c.fila(self.cl_nombre, self.cl_dir, self.cl_tel),
                      c.boton("Registrar clínica", self._crear_clinica, ft.Icons.ADD),
                      c.contenedor_tabla(self.t_cl), encabezado="Clínicas"),
            c.tarjeta(self.v_clinica, c.fila(self.v_nombre, self.v_apellido, self.v_mat, self.v_esp),
                      c.boton("Registrar veterinario", self._crear_vet, ft.Icons.ADD),
                      c.contenedor_tabla(self.t_vet), encabezado="Veterinarios"),
            c.tarjeta(self.vet_agenda, ft.Row(controls=list(self.dias.values()), wrap=True),
                      c.fila(self.desde, self.hasta),
                      c.nota("Un mismo horario se aplica a todos los días marcados."),
                      c.boton("Guardar agenda", self._guardar_agenda, ft.Icons.SAVE),
                      encabezado="Agenda semanal del veterinario"),
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
