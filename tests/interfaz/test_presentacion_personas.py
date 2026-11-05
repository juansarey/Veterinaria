"""Redimensionar Clientes y Mascotas conserva formularios, errores y acciones reales."""

from types import SimpleNamespace

import pytest

from test_pantallas import pestana, ui
from test_scroll_contenido import comprobar_flujo, recorrer
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_personas as sp


@pytest.mark.parametrize("clase", [sp.PestanaClientes, sp.PestanaMascotas])
def test_redimensionar_no_consulta_servicios_ni_pierde_edicion_y_errores(ui, monkeypatch, clase):
    app, _ = ui
    srv = app.servicios.clinica
    cliente = srv.crear_cliente("Ana", "Pérez", "0012345")
    srv.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    p = pestana(app, clase)
    p.refrescar()
    p._editar(p.datos[0])
    c.establecer_error(p.nombre_f, "Conservar este mensaje completo de validación.")
    campos = [control for control, _ in recorrer(p.vista)
              if isinstance(control, (c.ft.TextField, c.ft.Dropdown))]
    valores = [(control.value, control.disabled) for control in campos]
    filas = p.tabla.rows
    monkeypatch.setattr(p, "refrescar", lambda: pytest.fail("El layout no debe recargar datos"))
    monkeypatch.setattr(srv, "listar_clientes", lambda: pytest.fail("Consulta al redimensionar"))
    monkeypatch.setattr(srv, "listar_mascotas", lambda: pytest.fail("Consulta al redimensionar"))
    medidos = [control for control, _ in recorrer(p.vista)
               if getattr(control, "on_size_change", None)]
    for ancho in (1160, 820, 819.99, 560, 559.99, 380, 0, 1160):
        for control in medidos:
            control.on_size_change(SimpleNamespace(width=ancho))
        assert [(control.value, control.disabled) for control in campos] == valores
        assert p.nombre_f.error == "Conservar este mensaje completo de validación."
        assert p.tabla.rows is filas
        assert p.editando is not None and p.btn_cancelar.visible
        assert p.btn_guardar.content == "Guardar cambios"
        comprobar_flujo(p.vista)


@pytest.mark.parametrize("ancho, columnas", [(1160, 3), (820, 3), (819.99, 2),
                                           (560, 2), (559.99, 1), (380, 1)])
def test_filas_caben_en_el_ancho_util_y_expanden_los_selectores(ui, ancho, columnas):
    app, _ = ui
    for clase in (sp.PestanaClientes, sp.PestanaMascotas):
        p = pestana(app, clase)
        filas = [control for control, _ in recorrer(p.vista)
                 if isinstance(control, c.ft.Row) and control.on_size_change]
        for fila in filas:
            fila.on_size_change(SimpleNamespace(width=ancho))
            cantidad = min(len(fila.controls), columnas)
            # Responsable y búsqueda son filas de ancho completo; las restantes se reparten.
            ancho_total = sum(control.width for control in fila.controls[:cantidad]) + 14 * (cantidad - 1)
            assert 0 <= ancho - ancho_total < 0.04
            assert all(control.width <= ancho and control.height is None for control in fila.controls)
            for control in fila.controls:
                if isinstance(control, c.ft.Dropdown):
                    assert control.expanded_insets == c.ft.Padding.all(0)


@pytest.mark.parametrize("clase, minimo", [(sp.PestanaClientes, 860), (sp.PestanaMascotas, 1040)])
def test_listado_aprovecha_el_ancho_y_conserva_acciones_y_filas(ui, clase, minimo):
    app, _ = ui
    p = pestana(app, clase)
    cliente = p.srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    if clase is sp.PestanaMascotas:
        p.srv.clinica.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    p.refrescar()
    marco = p.tabla.data
    for ancho in (380, 680, 1200, 1500):
        marco.on_size_change(SimpleNamespace(width=ancho))
        assert p.tabla.width == max(minimo, ancho)
        assert marco.content.scroll == c.ft.ScrollMode.AUTO and marco.height is None
        assert len(p.tabla.rows) == 1
        acciones = p.tabla.rows[0].cells[-1].content.controls
        assert [boton.tooltip for boton in acciones] == (
            ["Editar", "Eliminar"] if clase is sp.PestanaClientes else ["Historia clínica", "Editar", "Eliminar"])
        acciones[-2].on_click(None)
        assert p.editando == p.datos[0]["id"] and p.btn_cancelar.visible
        p.btn_cancelar.on_click(None)
        assert p.editando is None and not p.btn_cancelar.visible
        comprobar_flujo(p.vista)
