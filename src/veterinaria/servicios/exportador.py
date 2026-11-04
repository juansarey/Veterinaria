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


def exportar_comprobante_pdf(ruta, comprobante: dict) -> str:
    estilos = getSampleStyleSheet()
    filas = [
        ("Comprobante N°", comprobante["numero"]), ("Fecha de emisión", comprobante["fecha_emision"]),
        ("Responsable", comprobante["responsable"]), ("Mascota", comprobante["mascota"]),
        ("Veterinario", comprobante["veterinario"]), ("Fecha de atención", comprobante["fecha_atencion"]),
        ("Tipo de atención", comprobante["tipo"]), ("Motivo", comprobante["motivo"]),
        ("Diagnóstico", comprobante["diagnostico"] or "—"),
        ("Observaciones", comprobante["observaciones"] or "—"),
    ]
    datos = [[Paragraph(f"<b>{k}</b>", estilos["BodyText"]),
              Paragraph(str(v), estilos["BodyText"])] for k, v in filas]
    tabla = Table(datos, colWidths=[4.5 * cm, 12 * cm])
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF5F2")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    SimpleDocTemplate(str(ruta), pagesize=A4).build([
        Paragraph("Comprobante de atención veterinaria", estilos["Title"]), Spacer(1, 12), tabla])
    return str(ruta)
