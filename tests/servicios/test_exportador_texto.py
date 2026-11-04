"""Regresiones del tratamiento de texto literal en los PDF."""

from datetime import date

from veterinaria.servicios import exportador
from veterinaria.servicios.datos_demo import cargar_demo
from veterinaria.servicios.fachada import Servicios


def _capturar_parrafos(monkeypatch):
    textos = []
    original = exportador.Paragraph

    def registrar(texto, estilo):
        textos.append(texto)
        return original(texto, estilo)

    monkeypatch.setattr(exportador, "Paragraph", registrar)
    return textos


def test_reporte_pdf_escapa_titulo_encabezado_y_celdas(tmp_path, monkeypatch):
    textos = _capturar_parrafos(monkeypatch)
    valor = "<b>sin cerrar & >\r\nsegunda línea"
    reporte = {
        "titulo": valor,
        "columnas": [("dato", valor)],
        "filas": [{"dato": valor}],
    }
    ruta = tmp_path / "reporte.pdf"

    exportador.exportar_pdf(ruta, reporte)

    escapado = "&lt;b&gt;sin cerrar &amp; &gt;<br/>segunda línea"
    assert escapado in textos
    assert f"<b>{escapado}</b>" in textos  # sólo el formato agregado por el código
    assert reporte["titulo"] == reporte["filas"][0]["dato"] == valor
    assert ruta.read_bytes().startswith(b"%PDF")


def test_comprobante_atencion_escapa_diagnostico_y_observaciones(tmp_path, monkeypatch):
    textos = _capturar_parrafos(monkeypatch)
    valor = "Control <b>sin cerrar & >\nsegunda línea"
    comprobante = {
        "numero": 1, "fecha_emision": "04/11/2026", "responsable": "Ana & Juan",
        "mascota": "Luna <Perra>", "veterinario": "Dra. Pérez",
        "fecha_atencion": "04/11/2026", "tipo": "CONSULTA", "motivo": "Control",
        "diagnostico": valor, "observaciones": valor,
    }
    ruta = tmp_path / "atencion.pdf"

    exportador.exportar_comprobante_pdf(ruta, comprobante)

    assert textos.count("Control &lt;b&gt;sin cerrar &amp; &gt;<br/>segunda línea") == 2
    assert "Ana &amp; Juan" in textos and "Luna &lt;Perra&gt;" in textos
    assert comprobante["diagnostico"] == valor
    assert ruta.read_bytes().startswith(b"%PDF")


def test_comprobante_resultado_escapa_bloques_multilinea(tmp_path, monkeypatch):
    textos = _capturar_parrafos(monkeypatch)
    valor = "<b>sin cerrar & >\r\nresultado final"
    comprobante = {
        "numero": 1, "fecha_emision": "04/11/2026", "mascota": "Luna <Perra>",
        "responsable": "Ana & Juan", "clinica": "Centro", "veterinario": "Dra. Pérez",
        "muestra": "M-0001", "tipo_muestra": "Sangre", "estudio": "Hemograma",
        "remito": "R-0001", "precinto": "PRE-1", "extraccion": "04/11/2026",
        "recepcion": "04/11/2026", "fecha_resultado": "04/11/2026",
        "resultado": valor, "observaciones": valor,
    }
    ruta = tmp_path / "resultado.pdf"

    exportador.exportar_comprobante_resultado_pdf(ruta, comprobante)

    assert textos.count("&lt;b&gt;sin cerrar &amp; &gt;<br/>resultado final") == 2
    assert "Luna &lt;Perra&gt;" in textos and "Ana &amp; Juan" in textos
    assert comprobante["resultado"] == valor
    assert ruta.read_bytes().startswith(b"%PDF")


def test_cuatro_reportes_persistidos_siguen_exportando_pdf(tmp_path):
    servicios = Servicios(tmp_path / "vet.db")
    cargar_demo(servicios)

    reportes = servicios.reportes.todos(date(2026, 11, 4))
    assert set(reportes) == {"atenciones", "rechazadas", "vacunas", "tiempos"}
    for nombre, reporte in reportes.items():
        ruta = tmp_path / f"{nombre}.pdf"
        exportador.exportar_pdf(ruta, reporte)
        assert ruta.read_bytes().startswith(b"%PDF")
