"""La creación exclusiva protege los archivos exportados y limpia los fallos."""

from datetime import datetime

import pytest

from veterinaria.interfaz import exportaciones
from veterinaria.servicios import exportador


REPORTE = {"titulo": "Atenciones", "columnas": [("dato", "Dato")],
           "filas": [{"dato": "primero"}]}


@pytest.fixture
def reloj_fijo(monkeypatch):
    class Reloj:
        @staticmethod
        def now():
            return datetime(2026, 11, 4, 12, 30, 0)

    monkeypatch.setattr(exportaciones, "datetime", Reloj)


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_dos_exportaciones_consecutivas_conservan_la_primera(tmp_path, reloj_fijo, extension):
    escribir = exportador.exportar_csv if extension == "csv" else exportador.exportar_pdf
    base = tmp_path / "vet.db"
    primera = exportaciones.exportar_con_nombre_unico(
        base, "reporte", extension, lambda ruta: escribir(ruta, REPORTE))
    contenido_primero = primera.read_bytes()

    segunda = exportaciones.exportar_con_nombre_unico(
        base, "reporte", extension, lambda ruta: escribir(ruta, REPORTE))

    assert primera.name == f"reporte_20261104_123000.{extension}"
    assert segunda.name == f"reporte_20261104_123000_1.{extension}"
    assert primera.read_bytes() == contenido_primero
    assert segunda.is_file() and segunda != primera


def test_nombre_ya_existente_no_se_sobrescribe(tmp_path, reloj_fijo):
    base = tmp_path / "vet.db"
    carpeta = exportaciones.carpeta_exportacion(base)
    existente = carpeta / exportaciones.nombre_archivo("reporte", "csv")
    existente.write_bytes(b"archivo anterior")

    nueva = exportaciones.exportar_con_nombre_unico(
        base, "reporte", "csv", lambda ruta: exportador.exportar_csv(ruta, REPORTE))

    assert nueva.name == "reporte_20261104_123000_1.csv"
    assert existente.read_bytes() == b"archivo anterior"
    assert nueva.read_bytes() != existente.read_bytes()


def test_colision_al_abrir_reintenta_otro_nombre(tmp_path, reloj_fijo):
    llamadas = []

    def escribir(ruta):
        llamadas.append(ruta)
        if len(llamadas) == 1:
            ruta.write_bytes(b"otro proceso")  # ocupa el candidato justo antes de abrirlo
        return exportador.exportar_csv(ruta, REPORTE)

    nueva = exportaciones.exportar_con_nombre_unico(
        tmp_path / "vet.db", "reporte", "csv", escribir)

    assert len(llamadas) == 2 and nueva == llamadas[1]
    assert llamadas[0].read_bytes() == b"otro proceso"
    assert nueva.name == "reporte_20261104_123000_1.csv"


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_exportador_directo_rechaza_archivo_existente(tmp_path, extension):
    ruta = tmp_path / f"existente.{extension}"
    ruta.write_bytes(b"no sobrescribir")
    escribir = exportador.exportar_csv if extension == "csv" else exportador.exportar_pdf

    with pytest.raises(FileExistsError):
        escribir(ruta, REPORTE)

    assert ruta.read_bytes() == b"no sobrescribir"


def test_csv_incompleto_se_elimina_tras_error(tmp_path):
    class DatoRoto:
        def __str__(self):
            raise RuntimeError("fallo al escribir")

    ruta = tmp_path / "parcial.csv"
    reporte = {**REPORTE, "filas": [{"dato": DatoRoto()}]}
    with pytest.raises(RuntimeError, match="fallo al escribir"):
        exportador.exportar_csv(ruta, reporte)
    assert not ruta.exists()


def test_pdf_incompleto_se_elimina_tras_error(tmp_path, monkeypatch):
    ruta = tmp_path / "parcial.pdf"
    anterior = tmp_path / "anterior.pdf"
    anterior.write_bytes(b"PDF anterior completo")

    def fallar(self, elementos):
        self.filename.write(b"PDF incompleto")
        raise RuntimeError("fallo al construir")

    monkeypatch.setattr(exportador.SimpleDocTemplate, "build", fallar)
    with pytest.raises(RuntimeError, match="fallo al construir"):
        exportador.exportar_pdf(ruta, REPORTE)
    assert not ruta.exists()
    assert anterior.read_bytes() == b"PDF anterior completo"
