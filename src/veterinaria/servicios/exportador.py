"""Exportación de reportes y comprobantes a CSV y PDF (ReportLab)."""

import csv

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def exportar_csv(ruta, reporte: dict) -> str:
    claves = [c for c, _ in reporte["columnas"]]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow([titulo for _, titulo in reporte["columnas"]])
        for fila in reporte["filas"]:
            escritor.writerow(["" if fila.get(c) is None else fila.get(c) for c in claves])
    return str(ruta)


def exportar_pdf(ruta, reporte: dict) -> str:
    estilos = getSampleStyleSheet()
    celda = estilos["BodyText"]
    celda.fontSize = 8
    claves = [c for c, _ in reporte["columnas"]]
    datos = [[Paragraph(f"<b>{t}</b>", celda) for _, t in reporte["columnas"]]]
    for fila in reporte["filas"]:
        datos.append([Paragraph(str(fila.get(c, "") if fila.get(c) is not None else ""), celda)
                      for c in claves])
    if len(datos) == 1:
        datos.append([Paragraph("Sin datos para mostrar", celda)] + [""] * (len(claves) - 1))

    doc = SimpleDocTemplate(str(ruta), pagesize=landscape(A4), leftMargin=1.5 * cm,
                            rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D6B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF5F2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    doc.build([
        Paragraph(reporte["titulo"], estilos["Title"]),
        Paragraph(f"Total de registros: {len(reporte['filas'])}", estilos["Normal"]),
        Spacer(1, 12), tabla,
    ])
    return str(ruta)


def _ficha_pdf(ruta, titulo, filas, bloques=()):
    """PDF de una página: título, tabla de datos (etiqueta/valor) y bloques de texto."""
    estilos = getSampleStyleSheet()
    datos = [[Paragraph(f"<b>{k}</b>", estilos["BodyText"]),
              Paragraph(str(v), estilos["BodyText"])] for k, v in filas]
    tabla = Table(datos, colWidths=[4.8 * cm, 12 * cm])
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF5F2")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elementos = [Paragraph(titulo, estilos["Title"]), Spacer(1, 12), tabla]
    for encabezado, texto in bloques:
        elementos += [Spacer(1, 14), Paragraph(f"<b>{encabezado}</b>", estilos["Heading3"]),
                      Paragraph((texto or "—").replace("\n", "<br/>"), estilos["BodyText"])]
    SimpleDocTemplate(str(ruta), pagesize=A4).build(elementos)
    return str(ruta)


def exportar_comprobante_pdf(ruta, comprobante: dict) -> str:
    filas = [
        ("Comprobante N°", comprobante["numero"]), ("Fecha de emisión", comprobante["fecha_emision"]),
        ("Responsable", comprobante["responsable"]), ("Mascota", comprobante["mascota"]),
        ("Veterinario", comprobante["veterinario"]), ("Fecha de atención", comprobante["fecha_atencion"]),
        ("Tipo de atención", comprobante["tipo"]), ("Motivo", comprobante["motivo"]),
        ("Diagnóstico", comprobante["diagnostico"] or "—"),
        ("Observaciones", comprobante["observaciones"] or "—"),
    ]
    return _ficha_pdf(ruta, "Comprobante de atención veterinaria", filas)


def exportar_comprobante_resultado_pdf(ruta, c: dict) -> str:
    filas = [
        ("Comprobante N°", c["numero"]), ("Fecha de emisión", c["fecha_emision"]),
        ("Mascota", c["mascota"]), ("Responsable", c["responsable"]),
        ("Clínica de origen", c["clinica"]), ("Veterinario solicitante", c["veterinario"]),
        ("Muestra", f"{c['muestra']} · {c['tipo_muestra']}"), ("Estudio solicitado", c["estudio"]),
        ("Remito / Precinto", f"{c['remito']} · {c['precinto']}"),
        ("Extracción", c["extraccion"]), ("Recepción en laboratorio", c["recepcion"] or "—"),
        ("Fecha del resultado", c["fecha_resultado"]),
    ]
    return _ficha_pdf(ruta, "Comprobante de resultados de laboratorio", filas,
                      [("Resultado", c["resultado"]), ("Observaciones", c["observaciones"])])
