"""Identidad de mascotas coincidentes desde SQLite hasta la vista y los archivos exportados."""

import csv
from datetime import date

import pytest

from test_pantallas import ui
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.servicios import exportador
from veterinaria.servicios.fachada import Servicios

ENCABEZADOS = ["ID mascota", "Mascota", "Especie", "Responsable", "Vacuna pendiente"]
REFERENCIA = date(2026, 11, 3)


@pytest.fixture
def base(ui):
    app, pag = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Juan", "Pérez", "00123")
    srv.clinica.crear_mascota(cliente, "Otra", "Gato")  # los IDs visibles no son números de fila
    mascotas = [srv.clinica.crear_mascota(cliente, "Rocky", "Perro") for _ in range(2)]
    vacunas = [srv.atencion.crear_vacuna(nombre, "Perro", True) for nombre in ("Antirrábica", "Quíntuple")]
    return app, pag, mascotas, vacunas


def leer_csv(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        return lector.fieldnames, list(lector)


def capturar_tabla_pdf(monkeypatch):
    tablas = []
    original = exportador.Table
    def crear(datos, *args, **kwargs):
        tablas.append([[celda.getPlainText() for celda in fila] for fila in datos])
        return original(datos, *args, **kwargs)  # construir y escribir realmente el PDF
    monkeypatch.setattr(exportador, "Table", crear)
    return tablas


def test_ids_reales_distinguen_rockys_y_se_repiten_por_vacuna_sin_escrituras(base):
    app, _, mascotas, _ = base
    con = abrir_conexion(app.ruta_bd)
    try:
        originales = tuple(con.iterdump())
        ids_sqlite = [r[0] for r in con.execute("SELECT id_mascota FROM mascota WHERE nombre = ? ORDER BY id_mascota", ("Rocky",))]
    finally:
        con.close()
    assert ids_sqlite == mascotas and len(set(mascotas)) == 2
    reporte = Servicios(app.ruta_bd).reportes.vacunas_pendientes(REFERENCIA)
    assert [titulo for _, titulo in reporte["columnas"]] == ENCABEZADOS
    assert reporte["columnas"][0] == ("id_mascota", "ID mascota")
    assert [(f["id_mascota"], f["vacuna"]) for f in reporte["filas"]] == [
        (mascotas[0], "Antirrábica"), (mascotas[0], "Quíntuple"),
        (mascotas[1], "Antirrábica"), (mascotas[1], "Quíntuple"),
    ]
    assert {(f["mascota"], f["especie"], f["responsable"]) for f in reporte["filas"]} == {("Rocky", "Perro", "Juan Pérez")}
    assert all(f["fecha_referencia"] == REFERENCIA for f in reporte["filas"])
    con = abrir_conexion(app.ruta_bd)
    try:
        assert tuple(con.iterdump()) == originales
    finally:
        con.close()


@pytest.mark.parametrize("referencia, primera", [(date(2026, 11, 3), 2), (date(2026, 11, 4), 1), (date(2026, 11, 6), 2)])
def test_id_conserva_filtro_por_fecha_aplicacion_y_vencimiento(base, referencia, primera):
    app, _, mascotas, vacunas = base
    app.servicios.atencion.registrar_aplicacion(mascotas[0], vacunas[0], date(2026, 11, 4), date(2026, 11, 6))
    reporte = app.servicios.reportes.vacunas_pendientes(referencia)
    assert sum(f["id_mascota"] == mascotas[0] for f in reporte["filas"]) == primera
    assert sum(f["id_mascota"] == mascotas[1] for f in reporte["filas"]) == 2
    assert all(f["fecha_referencia"] == referencia for f in reporte["filas"])


def test_csv_incluye_columna_id_y_las_cuatro_columnas_previas(base, tmp_path):
    app, _, mascotas, _ = base
    reporte = app.servicios.reportes.vacunas_pendientes(REFERENCIA)
    ruta = tmp_path / "vacunas.csv"
    exportador.exportar_csv(ruta, reporte)
    encabezados, filas = leer_csv(ruta)
    assert encabezados == ENCABEZADOS
    assert [int(f["ID mascota"]) for f in filas] == [mascotas[0], mascotas[0], mascotas[1], mascotas[1]]
    assert all(f["Mascota"] == "Rocky" and f["Especie"] == "Perro" and f["Responsable"] == "Juan Pérez" for f in filas)
    assert [f["Vacuna pendiente"] for f in filas] == ["Antirrábica", "Quíntuple"] * 2


def test_pdf_construye_tabla_con_id_real_en_cada_fila(base, tmp_path, monkeypatch):
    app, _, mascotas, _ = base
    tablas = capturar_tabla_pdf(monkeypatch)
    ruta = tmp_path / "vacunas.pdf"
    exportador.exportar_pdf(ruta, app.servicios.reportes.vacunas_pendientes(REFERENCIA))
    assert ruta.read_bytes().startswith(b"%PDF")
    assert len(tablas) == 1 and tablas[0][0] == ENCABEZADOS
    assert [int(fila[0]) for fila in tablas[0][1:]] == [mascotas[0], mascotas[0], mascotas[1], mascotas[1]]
    assert all(fila[1:4] == ["Rocky", "Perro", "Juan Pérez"] for fila in tablas[0][1:])


def test_vista_previa_muestra_id_real_sin_modificar_nombre(base):
    app, _, mascotas, _ = base
    p = app.pantallas[4]
    p.reporte.value, p.fecha_ref.value = "vacunas", "03/11/2026"
    p._generar()
    assert p.tabla.visible and [col.label.value for col in p.tabla.columns] == ENCABEZADOS
    assert [int(fila.cells[0].content.value) for fila in p.tabla.rows] == [mascotas[0], mascotas[0], mascotas[1], mascotas[1]]
    assert all(fila.cells[1].content.value == "Rocky" for fila in p.tabla.rows)


@pytest.mark.parametrize("formato", ["pdf", "csv"])
def test_exportar_desde_flet_incluye_id_y_fecha_seleccionada(base, tmp_path, monkeypatch, formato):
    app, pag, mascotas, vacunas = base
    app.servicios.atencion.registrar_aplicacion(mascotas[0], vacunas[0], date(2026, 11, 4), date(2026, 11, 6))
    p = app.pantallas[4]
    p.reporte.value, p.fecha_ref.value = "vacunas", "04/11/2026"
    tablas = capturar_tabla_pdf(monkeypatch) if formato == "pdf" else None
    p._exportar(formato)
    assert "Reporte exportado" in pag.mensajes[-1]
    assert [f["id_mascota"] for f in p.actual["filas"]] == [mascotas[0], mascotas[1], mascotas[1]]
    assert all(f["fecha_referencia"] == date(2026, 11, 4) for f in p.actual["filas"])
    archivos = list((tmp_path / "exportaciones").glob(f"reporte_vacunas_*.{formato}"))
    assert len(archivos) == 1
    if formato == "csv":
        encabezados, filas = leer_csv(archivos[0])
        assert encabezados == ENCABEZADOS
        assert [int(f["ID mascota"]) for f in filas] == [mascotas[0], mascotas[1], mascotas[1]]
    else:
        assert archivos[0].read_bytes().startswith(b"%PDF")
        assert tablas[0][0] == ENCABEZADOS
        assert [int(fila[0]) for fila in tablas[0][1:]] == [mascotas[0], mascotas[1], mascotas[1]]


@pytest.mark.parametrize("metodo, encabezados", [
    ("atenciones_derivaciones", ["Fecha", "Tipo", "Mascota", "Veterinario", "Clínica", "Derivaciones", "Estudios solicitados"]),
    ("muestras_rechazadas", ["Muestra", "Tipo", "Fecha de rechazo", "Remito", "Clínica de origen", "Precinto"]),
    ("tiempos", ["Indicador", "Casos", "Tiempo promedio"]),
])
def test_los_otros_tres_reportes_conservan_sus_columnas(base, metodo, encabezados):
    app, _, _, _ = base
    reporte = getattr(app.servicios.reportes, metodo)()
    assert [titulo for _, titulo in reporte["columnas"]] == encabezados
    assert "id_mascota" not in [clave for clave, _ in reporte["columnas"]]
