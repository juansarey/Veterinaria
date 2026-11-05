"""Nuevo turno según la referencia visual, con Flet simulado y SQLite temporal."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from test_fechas_interfaz import base, reloj
from test_pantallas import pestana, ui
from test_scroll_contenido import comprobar_flujo, recorrer
from test_usabilidad_flet import boton_en
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_turnos as st


@pytest.fixture
def agenda(ui, base):
    app, _ = ui
    p = pestana(app, st.PestanaAgenda)
    p.refrescar()
    p.vet.value, p.mascota.value = str(base["vet"]), str(base["mascota"])
    p.fecha.value, p.hora.value = "05/11/2026", "10:00"
    return p


def test_distribucion_de_referencia_etiquetas_y_ancho_completo(agenda):
    tarjeta = agenda.vista.controls[0]
    encabezado, primera, segunda, motivo, accion, nota = tarjeta.content.controls
    assert encabezado.controls[0].value == "Nuevo turno"
    assert encabezado.controls[1].value == "* Campos obligatorios"
    assert encabezado.alignment == c.ft.MainAxisAlignment.SPACE_BETWEEN
    assert [celda.controls[0].value for celda in primera.controls] == ["Veterinario *", "Mascota *"]
    assert [celda.controls[0].value for celda in segunda.controls] == ["Fecha *", "Hora *", "Duración *"]
    assert [celda.controls[1] for celda in primera.controls] == [agenda.vet, agenda.mascota]
    assert [celda.controls[1] for celda in segunda.controls] == [agenda.fecha, agenda.hora, agenda.duracion]
    assert motivo.controls[0].value == "Motivo de consulta (opcional)"
    assert motivo.controls[1] is agenda.motivo and agenda.motivo.width is None
    assert motivo.horizontal_alignment == tarjeta.content.horizontal_alignment == c.ft.CrossAxisAlignment.STRETCH
    assert accion.alignment == c.ft.MainAxisAlignment.END
    assert accion.controls == [boton_en(agenda, "Reservar turno")]
    assert "superponerse" in nota.value
    assert primera.wrap and segunda.wrap and primera.spacing == segunda.spacing == 14
    assert tarjeta.padding == c.ft.Padding.all(16)
    for control in (agenda.vet, agenda.mascota, agenda.fecha, agenda.hora, agenda.duracion, agenda.motivo):
        assert control.label is None and control.height is None
    assert agenda.vet.helper_text is agenda.mascota.helper_text is agenda.duracion.helper_text is None
    assert agenda.fecha.helper is agenda.hora.helper is agenda.motivo.helper is None
    assert agenda.vet.hint_text == agenda.mascota.hint_text == "Seleccionar"
    assert agenda.motivo.hint_text == "Ej.: Control general"
    comprobar_flujo(agenda.vista)


@pytest.mark.parametrize("ancho, columnas_primera, columnas_segunda", [
    (1500, 2, 3), (864, 2, 3), (674, 2, 3), (514, 2, 1), (430, 1, 1),
])
def test_ancho_medido_expande_tambien_el_control_interno_sin_desbordar(
        agenda, ancho, columnas_primera, columnas_segunda):
    agenda.vista.controls[0].on_size_change(SimpleNamespace(width=ancho))
    util = ancho - 34  # borde y padding de la tarjeta
    for fila, columnas in ((agenda._fila_selectores, columnas_primera),
                           (agenda._fila_horario, columnas_segunda)):
        anchos = [celda.width for celda in fila.controls]
        assert len(set(anchos)) == 1
        assert 0 <= util - (anchos[0] * columnas + 14 * (columnas - 1)) < 0.04
        for celda in fila.controls:
            assert celda.controls[1].width == celda.width
            assert celda.width <= util and celda.height is None
    comprobar_flujo(agenda.vista)


def test_redimensionar_no_recarga_datos_y_conserva_entradas_y_errores(ui, agenda, monkeypatch):
    app, _ = ui
    agenda.motivo.value = "No perder este motivo"
    c.establecer_error(agenda.hora, "Revisar la hora")
    campos = (agenda.vet, agenda.mascota, agenda.fecha, agenda.hora, agenda.duracion, agenda.motivo)
    valores = [campo.value for campo in campos]
    actualizaciones = []
    monkeypatch.setattr(app, "actualizar", lambda: actualizaciones.append(True))
    monkeypatch.setattr(agenda, "refrescar", lambda: pytest.fail("No consultar servicios al redimensionar"))
    for ancho in (864, 864, 0, 430, 430, 1500):
        agenda.vista.controls[0].on_size_change(SimpleNamespace(width=ancho))
    assert len(actualizaciones) == 3
    assert [campo.value for campo in campos] == valores
    assert agenda.hora.error == "Revisar la hora"


@pytest.mark.parametrize("duracion", ["15", "30", "45", "60"])
def test_reserva_con_minutos_visibles_conserva_ids_y_duracion_persistida(ui, agenda, base, duracion):
    app, pag = ui
    assert [(opcion.key, opcion.text) for opcion in agenda.duracion.options] == [
        (str(minutos), f"{minutos} min") for minutos in (15, 30, 45, 60)]
    agenda.duracion.value = duracion
    agenda.motivo.value = "Control"
    boton_en(agenda, "Reservar turno").on_click(None)
    turno, = app.servicios.clinica.listar_turnos()
    assert turno["id_veterinario"] == base["vet"] and turno["id_mascota"] == base["mascota"]
    assert turno["fin"] - turno["inicio"] == timedelta(minutes=int(duracion))
    assert turno["motivo"] == "Control" and agenda.motivo.value == ""
    assert agenda.fecha.value == agenda.dia.value == "05/11/2026"
    assert pag.mensajes[-1] == "Turno reservado."
    assert not agenda.vista.disabled and len(agenda.tabla.rows) == 1


@pytest.mark.parametrize("campo, valor", [
    ("vet", None), ("mascota", None), ("duracion", "inválida"),
    ("fecha", "03/11/2026"), ("hora", "10:29"), ("motivo", "x" * 201),
])
def test_validacion_conserva_error_localizado_foco_y_datos(ui, agenda, monkeypatch, campo, valor):
    app, pag = ui
    if campo == "hora":
        agenda.fecha.value = "04/11/2026"
    agenda.motivo.value = "No borrar"
    getattr(agenda, campo).value = valor
    campos = (agenda.vet, agenda.mascota, agenda.fecha, agenda.hora, agenda.duracion, agenda.motivo)
    valores = [control.value for control in campos]
    focos = []
    monkeypatch.setattr(pag, "run_task", lambda funcion: focos.append(funcion.__self__), raising=False)
    boton_en(agenda, "Reservar turno").on_click(None)
    control = getattr(agenda, campo)
    assert (control.error if isinstance(control, c.ft.TextField) else control.error_text)
    assert focos[-1] is control
    assert [control.value for control in campos] == valores
    assert not agenda.vista.disabled and app.servicios.clinica.listar_turnos() == []


@pytest.mark.parametrize("campo, etiqueta", [("vet", "Veterinario"), ("mascota", "Mascota"),
                                            ("duracion", "Duración")])
def test_etiqueta_externa_conserva_mensaje_y_revalidacion_del_selector(agenda, campo, etiqueta):
    control = getattr(agenda, campo)
    anterior = control.value
    control.value = "inexistente"
    boton_en(agenda, "Reservar turno").on_click(None)
    mensaje = f"Seleccione una opción válida en «{etiqueta}»."
    assert control.error_text == mensaje
    control.value = "otra entrada inválida"
    control.on_select(SimpleNamespace())
    assert control.error_text == mensaje
    control.value = anterior
    control.on_select(SimpleNamespace())
    assert control.error_text is None


def test_calendario_y_reloj_conservan_eventos_y_reflejan_seleccion(ui, agenda):
    _, pag = ui
    evento = SimpleNamespace(page=pag)
    agenda.fecha.suffix.controls[0].on_click(evento)
    calendario = pag.pickers[-1]
    calendario.value = st.datetime(2026, 11, 6)
    calendario.on_change(SimpleNamespace(control=calendario))
    assert agenda.fecha.value == "06/11/2026"
    agenda.hora.suffix.on_click(evento)
    reloj = pag.pickers[-1]
    reloj.value = st.datetime(2026, 11, 6, 11, 30).time()
    reloj.on_change(SimpleNamespace(control=reloj))
    assert agenda.hora.value == "11:30"


def test_boton_conserva_proteccion_contra_ejecucion_repetida(ui, agenda, monkeypatch):
    app, _ = ui
    boton = boton_en(agenda, "Reservar turno")
    original = app.servicios.clinica.agendar_turno
    llamadas = []

    def reservar(*args, **kwargs):
        llamadas.append(True)
        assert agenda.vista.disabled
        boton.on_click(None)
        return original(*args, **kwargs)

    monkeypatch.setattr(app.servicios.clinica, "agendar_turno", reservar)
    boton.on_click(None)
    assert llamadas == [True] and len(app.servicios.clinica.listar_turnos()) == 1
    assert not agenda.vista.disabled


def test_resto_de_turnos_conserva_tabla_filtros_y_profesionales(ui, agenda):
    app, _ = ui
    assert agenda.dia.label == "Ver día" and agenda.filtro_vet.label == "Filtrar veterinario"
    assert boton_en(agenda, "Ver agenda") and boton_en(agenda, "Ver todos")
    assert agenda.tabla.columns[-1].label.value == "Acciones"
    assert app.pantallas[1].hijas[1].nombre == "Veterinarios y agendas"


@pytest.mark.parametrize("ancho, columnas", [(1136, 3), (820, 3), (819.99, 2),
                                           (560, 2), (559.99, 1), (380, 1)])
def test_profesionales_redimensiona_sin_perder_agenda_entradas_ni_errores(ui, base, monkeypatch, ancho, columnas):
    app, _ = ui
    p = pestana(app, st.PestanaProfesionales)
    p.refrescar()
    p.vet_agenda.value = str(base["vet"])
    p._cargar_agenda()
    p.v_clinica.value = str(base["clinica"])
    p.cl_nombre.value, p.v_nombre.value = "Entrada pendiente", "Ana2"
    p.desde.value, p.hasta.value = "07:15", "17:45"
    p.dias[next(iter(p.dias))].value = False
    c.establecer_error(p.v_nombre, "Conservar el error completo del nombre.")
    campos = [control for control, _ in recorrer(p.vista)
              if isinstance(control, (c.ft.TextField, c.ft.Dropdown, c.ft.Checkbox))]
    valores = [control.value for control in campos]
    filas_tablas = p.t_cl.rows, p.t_vet.rows
    monkeypatch.setattr(p, "refrescar", lambda: pytest.fail("No recargar datos por layout"))
    for nombre in ("listar_clinicas", "listar_veterinarios", "obtener_agenda"):
        monkeypatch.setattr(p.srv.clinica, nombre, lambda *_: pytest.fail("Consulta al redimensionar"))
    for control, _ in recorrer(p.vista):
        evento = getattr(control, "on_size_change", None)
        if not evento:
            continue
        evento(SimpleNamespace(width=ancho))
        if isinstance(control, c.ft.Row):
            cantidad = min(len(control.controls), columnas)
            utilizado = sum(campo.width for campo in control.controls[:cantidad]) + 14 * (cantidad - 1)
            assert 0 <= ancho - utilizado < 0.04
            for campo in control.controls:
                assert campo.width <= ancho and campo.height is None
                if isinstance(campo, c.ft.Dropdown):
                    assert campo.expanded_insets == c.ft.Padding.all(0)
        evento(SimpleNamespace(width=0))
    assert [control.value for control in campos] == valores
    assert p.v_nombre.error == "Conservar el error completo del nombre."
    assert p.t_cl.rows is filas_tablas[0] and p.t_vet.rows is filas_tablas[1]
    assert len(p.dias) == 7
    assert all(0 < check.width <= ancho for check in p.dias.values())
    assert boton_en(p, "Registrar clínica") and boton_en(p, "Registrar veterinario") and boton_en(p, "Guardar agenda")
    comprobar_flujo(p.vista)


@pytest.mark.parametrize("tipo, minimo", [("turnos", 1100), ("clinicas", 760), ("veterinarios", 1000)])
def test_tablas_de_turnos_aprovechan_ancho_sin_perder_filas_ni_acciones(ui, agenda, base, tipo, minimo):
    app, _ = ui
    boton_en(agenda, "Reservar turno").on_click(None)
    p = pestana(app, st.PestanaProfesionales)
    p.refrescar()
    tabla = {"turnos": agenda.tabla, "clinicas": p.t_cl, "veterinarios": p.t_vet}[tipo]
    filas = tabla.rows
    for ancho in (380, 680, 1200, 1500):
        marco = tabla.data
        marco.on_size_change(SimpleNamespace(width=ancho))
        assert tabla.width == max(minimo, ancho)
        assert tabla.rows is filas and len(filas) == 1
        assert marco.height is None and marco.content.scroll == c.ft.ScrollMode.AUTO
        visibles = [boton.tooltip for boton in filas[0].cells[-1].content.controls if boton.visible]
        assert visibles == {"turnos": ["Confirmar", "Cancelar turno"],
                            "clinicas": ["Eliminar clínica"],
                            "veterinarios": ["Eliminar veterinario"]}[tipo]
    comprobar_flujo(agenda.vista)
    comprobar_flujo(p.vista)


def test_filtros_redimensionados_conservan_seleccion_y_transiciones(agenda, base, monkeypatch):
    boton_en(agenda, "Reservar turno").on_click(None)
    agenda.filtro_vet.value = str(base["vet"])
    agenda.dia.value = agenda.dia.data = "05/11/2026"
    filas = agenda.tabla.rows
    with monkeypatch.context() as parche:
        parche.setattr(agenda.srv.clinica, "listar_turnos", lambda: pytest.fail("Consulta al redimensionar"))
        for control, _ in recorrer(agenda.vista.controls[1]):
            if getattr(control, "on_size_change", None):
                for ancho in (1136, 680, 380, 1136):
                    control.on_size_change(SimpleNamespace(width=ancho))
        assert agenda.tabla.rows is filas
    assert agenda.dia.value == agenda.dia.data == "05/11/2026"
    assert agenda.filtro_vet.value == str(base["vet"])
    boton_en(agenda, "Ver agenda").on_click(None)
    acciones = agenda.tabla.rows[0].cells[-1].content.controls
    next(boton for boton in acciones if boton.tooltip == "Confirmar").on_click(None)
    acciones = agenda.tabla.rows[0].cells[-1].content.controls
    assert {b.tooltip for b in acciones if b.visible} == {"Marcar atendido", "Cancelar turno"}
    next(boton for boton in acciones if boton.tooltip == "Marcar atendido").on_click(None)
    assert not any(b.visible for b in agenda.tabla.rows[0].cells[-1].content.controls)
    boton_en(agenda, "Ver todos").on_click(None)
    assert agenda.dia.value == "" and agenda.filtro_vet.value is None
    assert len(agenda.tabla.rows) == 1
