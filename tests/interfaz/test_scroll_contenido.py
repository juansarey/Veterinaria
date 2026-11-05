"""Un scroll vertical por página, con tablas completas y navegación sin reconstruir formularios."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from test_pantallas import _hijos, pestana, ui
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa, seccion_laboratorio as sl
from veterinaria.interfaz import seccion_personas as sp, seccion_reportes as sr, seccion_turnos as st

PAGINAS = [sp.PestanaClientes, sp.PestanaMascotas, st.PestanaAgenda, st.PestanaProfesionales,
           sa.PestanaAtenciones, sa.PestanaVacunas, sl.PestanaEmpaquetado, sl.PestanaEnvio,
           sl.PestanaResultados, sl.PestanaSeguimiento, sr.SeccionReportes]
FECHA = datetime(2026, 11, 4, 9)


def recorrer(control, ancestros=()):
    yield control, ancestros
    for hijo in _hijos(control):
        yield from recorrer(hijo, (*ancestros, control))


def comprobar_flujo(vista):
    nodos = list(recorrer(vista))
    verticales = [control for control, _ in nodos
                  if isinstance(control, c.ft.Column) and control.scroll is not None]
    assert verticales == [vista]
    assert not any(isinstance(control, c.ft.ListView) and not control.horizontal for control, _ in nodos)
    assert vista.expand is True and vista.scroll == c.ft.ScrollMode.AUTO
    for control, ancestros in nodos:
        if control is vista:
            continue
        # Column reparte su eje vertical: ningún hijo debe pedir expand dentro del scroll.
        if isinstance(ancestros[-1], c.ft.Column):
            assert not control.expand, type(control).__name__
        if isinstance(control, c.ft.Container):
            assert control.height is None, type(control.content).__name__
        if isinstance(control, c.ft.DataTable):
            padre = ancestros[-1]
            assert isinstance(padre, c.ft.Row) and padre.scroll == c.ft.ScrollMode.AUTO
            assert padre.height is None
            assert not any(isinstance(a, c.ft.Column) and a.scroll is not None for a in ancestros[1:])


@pytest.mark.parametrize("clase", PAGINAS, ids=lambda clase: clase.__name__)
def test_jerarquia_tiene_un_scroll_vertical_sin_alturas_que_oculten_contenido(ui, clase):
    app, _ = ui
    p = app.pantallas[4] if clase is sr.SeccionReportes else pestana(app, clase)
    comprobar_flujo(p.vista)
    assert any(isinstance(control, c.ft.DataTable) for control, _ in recorrer(p.vista))
    # La navegación y el contenedor que limita la altura siguen fuera del scroll de la pestaña.
    assert app.contenido.expand is True
    assert all(control is not app.riel for control, _ in recorrer(p.vista))


@pytest.mark.parametrize("cantidad", [0, 1, 35])
def test_laboratorio_muestra_todas_las_filas_y_preserva_formularios_al_navegar(ui, cantidad):
    app, _ = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, FECHA, TipoAtencion.CONSULTA, "Control")
    libre = srv.laboratorio.crear_conservadora("Libre")
    for i in range(cantidad):
        srv.laboratorio.derivar(atencion, f"Estudio pendiente {i}", "Sangre", FECHA)
        muestra = srv.laboratorio.derivar(atencion, f"Estudio completo {i}", "Sangre", FECHA)["id_muestra"]
        cons = srv.laboratorio.crear_conservadora(f"C-{i}")
        remito = srv.laboratorio.empaquetar(clinica, cons, [muestra], f"P-{i}", FECHA)["id_remito"]
        envio = srv.laboratorio.despachar_remito(remito, FECHA + timedelta(hours=1))
        srv.laboratorio.recibir_remito(envio, True, FECHA + timedelta(hours=2))
        srv.laboratorio.registrar_resultado(muestra, f"Resultado {i}", fecha_resultado=FECHA + timedelta(hours=3))
    app.ir_a(3)
    emp, env = pestana(app, sl.PestanaEmpaquetado), pestana(app, sl.PestanaEnvio)
    res, seg = pestana(app, sl.PestanaResultados), pestana(app, sl.PestanaSeguimiento)
    emp.clinica.value, emp.conservadora.value = str(clinica), str(libre)
    campos = [emp.fecha, emp.precinto, env.salida, env.f_recepcion, env.obs_envio, env.obs_rec,
              res.fecha, res.resultado, res.obs]
    for campo in (emp.fecha, env.salida, env.f_recepcion, res.fecha):
        campo.value = "04/11/2026 12:30"
    for campo in (emp.precinto, env.obs_envio, env.obs_rec, res.resultado, res.obs):
        campo.value = "Texto\n< & >"
    c.establecer_error(emp.precinto, "Conservar este error")
    if cantidad:
        emp.checks[next(iter(emp.checks))].value = False
    selecciones = {i: check.value for i, check in emp.checks.items()}
    valores = [campo.value for campo in campos]
    vistas = [p.vista for p in (emp, env, res, seg)]
    seccion = app.pantallas[3]
    tabs = seccion.vista.controls[1]
    for indice, (p, esperadas) in enumerate(zip((emp, env, res, seg), (cantidad, cantidad, cantidad, cantidad * 2))):
        tabs.selected_index = indice
        seccion._cambio(SimpleNamespace(control=tabs))
        assert len(p.tabla.rows) == esperadas
        comprobar_flujo(p.vista)
        if p is not seg:
            texto = ("Empaquetar y precintar" if p is emp else "Registrar recepción" if p is env
                     else "Registrar resultado y generar PDF")
            boton = boton_en(p, texto)
            assert any(control is boton for control, _ in recorrer(p.vista))
    assert sum(isinstance(control, c.ft.Checkbox) for control, _ in recorrer(emp.muestras_box)) == cantidad
    for indice in (0, 1, 2, 4, 3):
        app.ir_a(indice)
    assert [campo.value for campo in campos] == valores
    assert emp.precinto.error == "Conservar este error"
    assert emp.clinica.value == str(clinica) and emp.conservadora.value == str(libre)
    assert {i: check.value for i, check in emp.checks.items()} == selecciones
    assert all(p.vista is vista for p, vista in zip((emp, env, res, seg), vistas))
    assert len(app.servicios.laboratorio.listar_resultados()) == cantidad
