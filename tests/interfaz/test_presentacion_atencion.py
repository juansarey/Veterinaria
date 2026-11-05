"""Presentación adaptable de Atención sin alterar avisos, fechas ni flujos clínicos."""

from contextlib import closing
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from test_fechas_interfaz import base, reloj
from test_pantallas import pestana, ui
from test_scroll_contenido import comprobar_flujo, recorrer
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.conexion import abrir_conexion


def redimensionar(p, ancho):
    if isinstance(p, sa.PestanaVacunas):
        paneles = p.vista.controls[0]
        paneles.on_size_change(SimpleNamespace(width=ancho))
        esperado = (ancho - 14) / 2 if ancho >= 1120 else ancho
        for panel in paneles.controls:
            assert 0 <= esperado - panel.width < 0.02
            assert not panel.expand and panel.height is None
        bloques = [(panel, panel.width - 34) for panel in paneles.controls]
    else:
        bloques = [(p.vista, ancho)]
    for bloque, util in bloques:
        for control, _ in recorrer(bloque):
            evento = getattr(control, "on_size_change", None)
            if not evento:
                continue
            evento(SimpleNamespace(width=util))
            if isinstance(control, c.ft.Row):
                assert all(campo.width <= util and campo.height is None for campo in control.controls)
                assert len({campo.width for campo in control.controls}) == 1
                for campo in control.controls:
                    if isinstance(campo, c.ft.Dropdown):
                        assert campo.expanded_insets == c.ft.Padding.all(0)
            evento(SimpleNamespace(width=0))
    comprobar_flujo(p.vista)


@pytest.mark.parametrize("clase", [sa.PestanaAtenciones, sa.PestanaVacunas])
@pytest.mark.parametrize("ancho", [1138, 1119.99, 380])
def test_redimensionar_conserva_textos_fechas_selecciones_avisos_y_errores(ui, base, monkeypatch, clase, ancho):
    app, _ = ui
    srv = app.servicios
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    p = pestana(app, clase)
    p.refrescar()
    p.mascota.value = str(base["mascota"])
    if clase is sa.PestanaAtenciones:
        p.vet.value, p.fecha.value = str(base["vet"]), "04/11/2026 09:15"
        p._al_elegir_mascota()
        error = p.motivo
        for campo in (p.diagnostico, p.observaciones, p.obs_orden):
            campo.value = "Primera línea <literal> &\nSegunda\nTercera\nCuarta\nQuinta"
            assert campo.multiline and campo.min_lines == 2 and campo.max_lines == 4
        avisos = (p.estado_historia.value, p.estado_vacunas.value, p.estado_vacunas.color, p.btn_historia.visible)
    else:
        p._al_elegir()
        p.vacuna.value = str(vacuna)
        p.f_aplic.value, p.f_prox.value = "01/11/2026", "01/11/2027"
        p.v_nombre.value, p.v_oblig.value = "Entrada pendiente", False
        error = p.v_nombre
        avisos = (p.resumen.value, p.resumen.color)
    c.establecer_error(error, "Conservar este mensaje completo de validación.")
    campos = [control for control, _ in recorrer(p.vista)
              if isinstance(control, (c.ft.TextField, c.ft.Dropdown, c.ft.Checkbox))]
    valores = [campo.value for campo in campos]
    eventos = [(getattr(campo, "on_change", None), getattr(campo, "on_select", None)) for campo in campos]
    monkeypatch.setattr(p, "refrescar", lambda: pytest.fail("No refrescar por layout"))
    for servicio, nombre in ((srv.clinica, "listar_mascotas"), (srv.atencion, "obtener_historia"),
                             (srv.atencion, "vacunas_pendientes"), (srv.atencion, "listar_aplicaciones")):
        monkeypatch.setattr(servicio, nombre, lambda *_: pytest.fail("Consulta al redimensionar"))
    redimensionar(p, ancho)
    redimensionar(p, 1138)
    assert [campo.value for campo in campos] == valores
    assert [(getattr(campo, "on_change", None), getattr(campo, "on_select", None)) for campo in campos] == eventos
    assert error.error == "Conservar este mensaje completo de validación."
    assert avisos == ((p.estado_historia.value, p.estado_vacunas.value, p.estado_vacunas.color, p.btn_historia.visible)
                      if clase is sa.PestanaAtenciones else (p.resumen.value, p.resumen.color))


@pytest.mark.parametrize("tipo, minimo", [("atenciones", 1400), ("catalogo", 520), ("aplicaciones", 520)])
def test_tablas_conservan_filas_columnas_y_acciones_al_cambiar_ancho(ui, base, tipo, minimo):
    app, _ = ui
    srv = app.servicios
    srv.atencion.registrar_atencion(base["mascota"], base["vet"], datetime(2026, 11, 4, 9), TipoAtencion.CONSULTA, "Control")
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    srv.atencion.registrar_aplicacion(base["mascota"], vacuna, date(2026, 11, 1))
    p = pestana(app, sa.PestanaAtenciones if tipo == "atenciones" else sa.PestanaVacunas)
    p.refrescar()
    if tipo != "atenciones":
        p.mascota.value = str(base["mascota"])
        p._al_elegir()
    tabla = p.tabla if tipo == "atenciones" else p.t_vac if tipo == "catalogo" else p.t_apl
    filas, columnas = tabla.rows, tabla.columns
    for ancho in (380, 680, 1200, 1600):
        tabla.data.on_size_change(SimpleNamespace(width=ancho))
        assert tabla.width == max(minimo, ancho)
        assert tabla.rows is filas and tabla.columns is columnas and len(filas) == 1
        assert tabla.data.content.scroll == c.ft.ScrollMode.AUTO and tabla.data.height is None
        if tipo == "atenciones":
            assert [boton.tooltip for boton in filas[0].cells[-1].content.controls] == [
                "Derivar a laboratorio", "Comprobante (PDF)"]
        comprobar_flujo(p.vista)


def test_aviso_no_bloqueante_y_derivacion_siguen_funcionando_tras_redimensionar(ui, base):
    app, _ = ui
    srv = app.servicios
    srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    p = pestana(app, sa.PestanaAtenciones)
    p.refrescar()
    p.mascota.value, p.vet.value = str(base["mascota"]), str(base["vet"])
    p.fecha.value, p.tipo.value, p.motivo.value = "04/11/2026 09:00", "URGENCIA", "Control"
    p.observaciones.value = "Texto profesional <literal>\n& segunda línea"
    p._al_elegir_mascota()
    redimensionar(p, 380)
    assert "Puede registrar la atención" in p.estado_vacunas.value
    assert p.estado_vacunas.color == c.ft.Colors.AMBER_800
    boton_en(p, "Registrar atención").on_click(None)
    atencion, = srv.atencion.listar_atenciones(base["mascota"])
    with closing(abrir_conexion(app.ruta_bd)) as conexion:
        recuperada = AtencionDAO(conexion).obtener_por_id(atencion["id"])
        assert recuperada.observaciones == "Texto profesional <literal>\n& segunda línea"
    p.tabla.rows[0].cells[-1].content.controls[0].on_click(None)
    assert p.atencion.value == str(atencion["id"])
    p.estudio.value, p.obs_orden.value = "Hemograma", "Observación de derivación\n< & >"
    redimensionar(p, 1138)
    boton_en(p, "Derivar a laboratorio").on_click(None)
    assert len(srv.laboratorio.listar_muestras()) == 1
    assert p.estudio.value == p.obs_orden.value == ""


def test_catalogo_y_aplicacion_conservan_filtro_por_especie_y_fechas_al_apilar(ui, base):
    app, _ = ui
    srv = app.servicios
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    p = pestana(app, sa.PestanaVacunas)
    p.refrescar()
    p.mascota.value = str(base["mascota"])
    p._al_elegir()
    p.vacuna.value, p.f_aplic.value, p.f_prox.value = str(vacuna), "01/11/2026", ""
    p.v_nombre.value, p.v_especie.value, p.v_oblig.value = "Felina", "Gato", False
    redimensionar(p, 380)
    boton_en(p, "Registrar vacuna").on_click(None)
    assert len(p.t_vac.rows) == 2
    assert [opcion.key for opcion in p.vacuna.options] == [str(vacuna)]
    assert p.vacuna.value == str(vacuna) and p.f_aplic.value == "01/11/2026"
    redimensionar(p, 1138)
    boton_en(p, "Registrar aplicación").on_click(None)
    assert len(p.t_apl.rows) == 1 and len(srv.atencion.listar_aplicaciones(base["mascota"])) == 1
    assert p.f_aplic.value == "01/11/2026" and p.f_prox.value == ""
    assert p.resumen.value == "Vacunas obligatorias al día."
