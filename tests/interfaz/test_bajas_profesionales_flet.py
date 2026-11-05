"""Confirmaciones y bajas desde Flet, sin ventanas ni una base permanente."""

from datetime import datetime, time
from types import SimpleNamespace

import pytest

from test_pantallas import pestana, ui
from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa, seccion_laboratorio as sl
from veterinaria.interfaz import seccion_personas as sp, seccion_turnos as st
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO
from veterinaria.servicios.fachada import Servicios


@pytest.fixture
def vista(ui, monkeypatch):
    app, pagina = ui
    dialogos = []
    mostrar = pagina.show_dialog

    def capturar(dialogo):
        if isinstance(dialogo, c.ft.AlertDialog):
            dialogos.append(dialogo)
        mostrar(dialogo)

    monkeypatch.setattr(pagina, "show_dialog", capturar)
    srv = app.servicios
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(cl, "Ana", "Pérez", "MP-1")
    srv.clinica.guardar_agenda(vet, {DiaSemana.LUNES, DiaSemana.MIERCOLES}, time(8), time(18))
    for i in range(5):
        app.ir_a(i)
    return app, pagina, dialogos, pestana(app, st.PestanaProfesionales), cl, vet


def pulsar(dialogo, aceptar=True):
    boton = dialogo.actions[1 if aceptar else 0]
    boton.on_click(SimpleNamespace(control=boton))


@pytest.mark.parametrize("entidad", ["veterinario", "clinica"])
def test_botones_identifican_entidad_y_cancelar_no_invoca_servicio(vista, monkeypatch, entidad):
    app, pagina, dialogos, p, _, _ = vista
    tabla = p.t_vet if entidad == "veterinario" else p.t_cl
    accion = tabla.rows[0].cells[-1].content.controls[0]
    assert accion.tooltip == f"Eliminar {entidad if entidad == 'veterinario' else 'clínica'}"
    monkeypatch.setattr(app.servicios.clinica, f"eliminar_{entidad}",
                        lambda *args: pytest.fail("Cancelar no debe ejecutar la baja"))
    accion.on_click(None)
    accion.on_click(None)
    assert len(dialogos) == 1
    texto = dialogos[-1].content.value
    assert "ID #" in texto and ("MP-1" in texto if entidad == "veterinario" else "Centro" in texto)
    if entidad == "veterinario":
        assert "agenda semanal" in texto and "días y horarios" in texto
    pulsar(dialogos[-1], False)
    pulsar(dialogos[-1])  # un evento viejo del diálogo cancelado tampoco puede borrar
    assert not app._confirmacion_abierta
    assert not pagina.mensajes
    assert len(app.servicios.clinica.listar_veterinarios()) == 1
    assert len(app.servicios.clinica.listar_clinicas()) == 1
    accion.on_click(None)
    assert len(dialogos) == 2
    dialogos[-1].on_dismiss(None)
    assert not app._confirmacion_abierta


def test_confirmacion_elimina_exactamente_una_vez_y_actualiza_selectores(vista, monkeypatch):
    app, pagina, dialogos, p, cl, vet = vista
    otro = app.servicios.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-2")
    p.refrescar()
    agenda, atenciones = pestana(app, st.PestanaAgenda), pestana(app, sa.PestanaAtenciones)
    p.vet_agenda.value = agenda.vet.value = agenda.filtro_vet.value = atenciones.vet.value = str(vet)
    p._cargar_agenda()
    atenciones.motivo.value, atenciones.fecha.value = "Sin perder", "03/11/2026 12:30"
    agenda.fecha.value, agenda.hora.value, agenda.motivo.value = "05/11/2026", "11:00", "Reserva"
    campos = [atenciones.motivo, atenciones.fecha, agenda.fecha, agenda.hora, agenda.motivo,
              p.cl_nombre, p.v_nombre, p.v_mat]
    for control in (p.cl_nombre, p.v_nombre, p.v_mat):
        control.value = "Entrada pendiente"
    c.establecer_error(atenciones.fecha, "Error conservado")
    valores = [control.value for control in campos]
    original = app.servicios.clinica.eliminar_veterinario
    llamadas = []

    def eliminar(identificador):
        assert not any("eliminado" in m for m in pagina.mensajes)
        llamadas.append(identificador)
        # Tampoco puede abrirse otro diálogo mientras se procesa la confirmación.
        p._pedir_baja_veterinario(app.servicios.clinica.listar_veterinarios()[0])
        original(identificador)

    monkeypatch.setattr(app.servicios.clinica, "eliminar_veterinario", eliminar)
    fila = next(v for v in app.servicios.clinica.listar_veterinarios() if v["id"] == vet)
    p._pedir_baja_veterinario(fila)
    pulsar(dialogos[-1]); pulsar(dialogos[-1])
    dialogos[-1].on_dismiss(None)
    assert llamadas == [vet] and len(dialogos) == 1
    assert pagina.mensajes == ["Veterinario eliminado."]
    assert len(p.t_vet.rows) == 1
    for selector in (p.vet_agenda, agenda.vet, agenda.filtro_vet, atenciones.vet):
        assert selector.value is None
        assert {o.key for o in selector.options} == {str(otro)}
    assert not any(check.value for check in p.dias.values())
    assert (p.desde.value, p.hasta.value) == ("08:00", "16:00")
    assert [control.value for control in campos] == valores
    assert atenciones.fecha.error == "Error conservado"
    assert not app._confirmacion_abierta
    assert [v["id"] for v in Servicios(app.ruta_bd).clinica.listar_veterinarios()] == [otro]


def test_baja_clinica_refresca_opciones_sin_alterar_formularios(vista):
    app, pagina, dialogos, p, cl, vet = vista
    vacia = app.servicios.clinica.crear_clinica("Vacía", "Calle 2")
    for i in range(5):
        app.ir_a(i)
    emp = pestana(app, sl.PestanaEmpaquetado)
    at = pestana(app, sa.PestanaAtenciones)
    p.v_clinica.value = emp.clinica.value = str(vacia)
    p.vet_agenda.value = at.vet.value = str(vet)
    p._cargar_agenda()
    p.desde.value = "07:15"  # agenda en edición: no recargarla al borrar otra entidad
    controles = [emp.fecha, emp.precinto, emp.codigo_cons, at.fecha, at.motivo,
                 p.v_nombre, p.cl_nombre, p.desde]
    for control in controles[:-1]:
        control.value = "Valor pendiente"
    antes = [control.value for control in controles]
    fila = next(c for c in app.servicios.clinica.listar_clinicas() if c["id"] == vacia)
    p._pedir_baja_clinica(fila)
    pulsar(dialogos[-1])
    assert pagina.mensajes == ["Clínica eliminada."]
    assert len(p.t_cl.rows) == 1
    for selector in (p.v_clinica, emp.clinica):
        assert selector.value is None
        assert {o.key for o in selector.options} == {str(cl)}
    assert p.vet_agenda.value == at.vet.value == str(vet)
    assert [control.value for control in controles] == antes
    assert [c["id"] for c in Servicios(app.ruta_bd).clinica.listar_clinicas()] == [cl]


@pytest.mark.parametrize("dependencia", ["turno", "atencion", "veterinario", "remito"])
def test_rechazos_muestran_motivo_sin_exito_y_permiten_reintento(vista, monkeypatch, dependencia):
    app, pagina, dialogos, p, cl, vet = vista
    srv = app.servicios
    entidad, objetivo = "veterinario", vet
    if dependencia in {"turno", "atencion"}:
        cliente = srv.clinica.crear_cliente("Luis", "Gómez", "00123")
        mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
        fecha = datetime(2026, 11, 4, 9)
        if dependencia == "turno":
            monkeypatch.setattr("veterinaria.servicios.clinica_servicio.ahora", lambda: fecha)
            turno = srv.clinica.agendar_turno(vet, mascota, fecha, fecha.replace(minute=30))
            srv.clinica.cambiar_estado_turno(turno, "cancelar")
        else:
            srv.atencion.registrar_atencion(mascota, vet, fecha, TipoAtencion.CONSULTA, "Control")
    elif dependencia == "veterinario":
        entidad, objetivo = "clinica", cl
    else:
        entidad = "clinica"
        objetivo = srv.clinica.crear_clinica("Con remito", "Calle 9")
        cons = srv.laboratorio.crear_conservadora("C-1")
        srv.laboratorio.crear_remito(objetivo, cons)
    listar = srv.clinica.listar_veterinarios if entidad == "veterinario" else srv.clinica.listar_clinicas
    pedir = p._pedir_baja_veterinario if entidad == "veterinario" else p._pedir_baja_clinica
    fila = next(f for f in listar() if f["id"] == objetivo)
    pedir(fila); pulsar(dialogos[-1])
    assert dependencia in pagina.mensajes[-1]
    assert not any("eliminado." in m or "eliminada." in m for m in pagina.mensajes)
    assert any(f["id"] == objetivo for f in listar())
    assert srv.clinica.obtener_agenda(vet) is not None
    assert not app._confirmacion_abierta
    pedir(fila)
    assert len(dialogos) == 2
    pulsar(dialogos[-1], False)


def test_fallo_intermedio_desde_flet_no_muestra_exito_y_luego_permite_guardar(vista, monkeypatch):
    app, pagina, dialogos, p, _, vet = vista
    fila = app.servicios.clinica.listar_veterinarios()[0]
    original = VeterinarioDAO.eliminar

    def fallar(*args):
        raise OSError("Error simulado")

    monkeypatch.setattr(VeterinarioDAO, "eliminar", fallar)
    p._pedir_baja_veterinario(fila); pulsar(dialogos[-1])
    assert "No se pudo completar" in pagina.mensajes[-1]
    assert "Error simulado" not in pagina.mensajes[-1]
    reabierto = Servicios(app.ruta_bd)
    assert reabierto.clinica.obtener_agenda(vet) is not None
    assert reabierto.clinica.listar_veterinarios()
    assert not app._confirmacion_abierta
    monkeypatch.setattr(VeterinarioDAO, "eliminar", original)
    p._pedir_baja_veterinario(fila); pulsar(dialogos[-1])
    assert pagina.mensajes[-1] == "Veterinario eliminado."
    assert not app.servicios.clinica.listar_veterinarios()


@pytest.mark.parametrize("entidad", ["cliente", "mascota"])
def test_confirmar_conserva_compatibilidad_con_bajas_existentes(vista, monkeypatch, entidad):
    app, pagina, dialogos, _, _, _ = vista
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Luis", "Gómez", "00123")
    if entidad == "mascota":
        objetivo = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
        p = pestana(app, sp.PestanaMascotas)
        listar = srv.clinica.listar_mascotas
    else:
        objetivo = cliente
        p = pestana(app, sp.PestanaClientes)
        listar = srv.clinica.listar_clientes
    p.refrescar()
    fila = next(f for f in p.datos if f["id"] == objetivo)
    p._pedir_baja(fila); pulsar(dialogos[-1], False)
    assert any(f["id"] == objetivo for f in listar())
    metodo = f"eliminar_{entidad}"
    original = getattr(srv.clinica, metodo)
    llamadas = []

    def eliminar(identificador):
        llamadas.append(identificador)
        original(identificador)

    monkeypatch.setattr(srv.clinica, metodo, eliminar)
    p._pedir_baja(fila)
    pulsar(dialogos[-1]); pulsar(dialogos[-1]); pulsar(dialogos[-1], False)
    assert llamadas == [objetivo]
    assert not listar()
    assert not app._confirmacion_abierta


def test_error_al_mostrar_confirmacion_libera_bloqueo(vista, monkeypatch):
    app, _, _, p, _, _ = vista
    fila = app.servicios.clinica.listar_veterinarios()[0]
    with monkeypatch.context() as m:
        m.setattr(app.page, "show_dialog", lambda *args: (_ for _ in ()).throw(RuntimeError("Sin página")))
        with pytest.raises(RuntimeError, match="Sin página"):
            p._pedir_baja_veterinario(fila)
    assert not app._confirmacion_abierta
    p._pedir_baja_veterinario(fila)
    assert app._confirmacion_abierta
