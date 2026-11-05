"""Presentación adaptable de los cuatro reportes sin alterar datos ni exportaciones."""

import csv
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from test_id_reporte_vacunas import capturar_tabla_pdf
from test_pantallas import ui
from test_scroll_contenido import comprobar_flujo, recorrer
from test_usabilidad_flet import boton_en
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_reportes as sr
from veterinaria.servicios.datos_demo import cargar_demo

REFERENCIA = date(2026, 11, 3)


@pytest.fixture
def reportes(ui):
    app, pag = ui
    cargar_demo(app.servicios)
    p = app.pantallas[4]
    p.fecha_ref.value = "03/11/2026"
    return app, pag, p


def referencia(p, clave):
    srv = p.srv.reportes
    return (srv.vacunas_pendientes(REFERENCIA) if clave == "vacunas" else
            {"atenciones": srv.atenciones_derivaciones, "rechazadas": srv.muestras_rechazadas,
             "tiempos": srv.tiempos}[clave]())


def redimensionar(p, ancho):
    filtros = next(control for control, _ in recorrer(p.vista)
                   if isinstance(control, c.ft.Row) and control.on_size_change)
    filtros.on_size_change(SimpleNamespace(width=ancho))
    if ancho >= 660:
        assert p.reporte.width + p.fecha_ref.width + filtros.spacing == ancho
    else:
        assert p.reporte.width == p.fecha_ref.width == ancho
    assert p.reporte.expanded_insets == c.ft.Padding.all(0)
    p.tabla.data.on_size_change(SimpleNamespace(width=ancho))
    assert p.tabla.width == max(ancho, 520, 150 * len(p.tabla.columns))
    assert p.tabla.data.content.scroll == c.ft.ScrollMode.AUTO
    assert p.tabla.height is None and p.tabla.data.height is None
    comprobar_flujo(p.vista)


@pytest.mark.parametrize("clave", sr.REPORTES)
def test_redimensionar_conserva_reporte_datos_fechas_errores_y_callbacks(reportes, monkeypatch, clave):
    _, _, p = reportes
    esperado = referencia(p, clave)
    p.reporte.value = clave
    boton_en(p, "Generar reporte").on_click(None)
    assert p.actual == {**esperado, "clave": clave}
    assert [col.label.value for col in p.tabla.columns] == [titulo for _, titulo in esperado["columnas"]]
    datos, filas, columnas = p.actual, p.tabla.rows, p.tabla.columns
    textos = p.titulo_rep.value, p.resumen.value
    evento_fecha = p.fecha_ref.on_change
    botones = [boton_en(p, texto) for texto in ("Generar reporte", "Exportar PDF", "Exportar CSV")]
    eventos = [boton.on_click for boton in botones]
    c.establecer_error(p.fecha_ref, "Conservar este mensaje de validación completo.")
    for nombre in ("atenciones_derivaciones", "muestras_rechazadas", "vacunas_pendientes", "tiempos"):
        monkeypatch.setattr(p.srv.reportes, nombre, lambda *a: pytest.fail("No generar datos al redimensionar"))
    for ancho in (1138, 680, 380, 1138):
        redimensionar(p, ancho)
        assert p.actual is datos and p.tabla.rows is filas and p.tabla.columns is columnas
        assert p.reporte.value == clave and p.fecha_ref.value == "03/11/2026"
        assert p.fecha_ref.error == "Conservar este mensaje de validación completo."
        assert (p.titulo_rep.value, p.resumen.value) == textos and p.tabla.visible
        assert p.fecha_ref.on_change is evento_fecha
        assert [boton.on_click for boton in botones] == eventos


def test_cambiar_de_reporte_actualiza_ancho_con_la_misma_medicion(reportes):
    _, _, p = reportes
    redimensionar(p, 380)
    for clave in sr.REPORTES:
        p.reporte.value = clave
        boton_en(p, "Generar reporte").on_click(None)
        assert p.tabla.width == max(520, 150 * len(p.actual["columnas"]))
        assert p.tabla.visible and p.actual["clave"] == clave
    assert [col.label.value for col in p.tabla.columns] == ["Indicador", "Casos", "Tiempo promedio"]


@pytest.mark.parametrize("clave", sr.REPORTES)
@pytest.mark.parametrize("formato", ["pdf", "csv"])
def test_exportacion_tras_redimensionar_usa_parametros_actuales_y_columnas_originales(reportes, monkeypatch, clave, formato):
    app, pag, p = reportes
    boton_en(p, "Generar reporte").on_click(None)
    p.reporte.value = clave
    redimensionar(p, 380)
    esperado = referencia(p, clave)
    tablas = capturar_tabla_pdf(monkeypatch) if formato == "pdf" else None
    boton_en(p, f"Exportar {formato.upper()}").on_click(None)
    assert p.actual == {**esperado, "clave": clave}
    assert p.fecha_ref.value == "03/11/2026" and not p.vista.disabled
    ruta, = (app.ruta_bd.parent / "exportaciones").glob(f"reporte_{clave}_*.{formato}")
    encabezados = [titulo for _, titulo in esperado["columnas"]]
    if formato == "pdf":
        assert ruta.read_bytes().startswith(b"%PDF") and tablas[0][0] == encabezados
        assert len(tablas[0]) == len(esperado["filas"]) + 1
    else:
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.reader(archivo, delimiter=";"))
        assert filas[0] == encabezados and len(filas) == len(esperado["filas"]) + 1
    assert "Reporte exportado" in pag.mensajes[-1]
    comprobar_flujo(p.vista)


def test_error_de_fecha_descarta_vista_previa_sin_exportar_datos_anteriores(reportes, monkeypatch):
    app, _, p = reportes
    p.reporte.value = "vacunas"
    boton_en(p, "Generar reporte").on_click(None)
    p.fecha_ref.value = "fecha inválida"
    redimensionar(p, 380)
    monkeypatch.setattr(sr, "exportar_csv", lambda *a: pytest.fail("No exportar una vista previa anterior"))
    boton_en(p, "Exportar CSV").on_click(None)
    redimensionar(p, 1138)
    assert p.actual is None and not p.tabla.visible and p.tabla.rows == []
    assert p.titulo_rep.value == p.resumen.value == ""
    assert p.fecha_ref.error and p.fecha_ref.value == "fecha inválida"
    assert not list((app.ruta_bd.parent / "exportaciones").glob("*.csv"))


def test_sin_datos_conserva_estado_original_y_no_crea_indicadores(ui):
    app, _ = ui
    p = app.pantallas[4]
    redimensionar(p, 380)
    assert p.actual is None and not p.tabla.visible
    p.reporte.value = "vacunas"
    boton_en(p, "Generar reporte").on_click(None)
    assert p.actual["filas"] == [] and p.tabla.rows == [] and p.tabla.visible
    assert p.resumen.value == "Sin datos para mostrar."
    assert len(p.tabla.columns) == 5
    redimensionar(p, 1138)
    assert p.actual["filas"] == [] and p.resumen.value == "Sin datos para mostrar."


def test_calendario_y_fecha_futura_siguen_disponibles_al_apilar(ui):
    app, pag = ui
    p = app.pantallas[4]
    redimensionar(p, 380)
    p.fecha_ref.suffix.controls[0].on_click(SimpleNamespace(page=pag))
    calendario = pag.pickers[-1]
    calendario.value = datetime(2030, 2, 1)
    calendario.on_change(SimpleNamespace(control=calendario))
    assert p.fecha_ref.value == p.fecha_ref.data == "01/02/2030"
    redimensionar(p, 1138)
    p.reporte.value = "vacunas"
    boton_en(p, "Generar reporte").on_click(None)
    assert p.fecha_ref.value == "01/02/2030" and p.fecha_ref.error is None
    assert "01/02/2030" in p.actual["titulo"]
