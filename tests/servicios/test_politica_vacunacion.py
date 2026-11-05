"""Las vacunas pendientes se informan, pero no impiden la atención ni su circuito."""

from datetime import date, datetime, timedelta

import pytest

from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.historia_clinica_dao import HistoriaClinicaDAO
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.exportador import exportar_comprobante_pdf, exportar_comprobante_resultado_pdf
from veterinaria.servicios.fachada import Servicios

FECHA = datetime(2026, 11, 4, 9)


@pytest.fixture
def base(tmp_path):
    ruta = tmp_path / "vacunacion.db"
    srv = Servicios(ruta)
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "00123")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-1")
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    srv.atencion.crear_vacuna("Opcional", "Perro", False)
    srv.atencion.crear_vacuna("Triple felina", "Gato", True)
    return srv, ruta, cliente, mascota, cl, vet, vacuna


def aplicaciones(ruta):
    con = abrir_conexion(ruta)
    try:
        return [tuple(r) for r in con.execute("SELECT * FROM aplicacion_vacuna ORDER BY id_aplicacion")]
    finally:
        con.close()


@pytest.mark.parametrize("tipo", list(TipoAtencion))
@pytest.mark.parametrize("esquema", ["completo", "faltante", "vencida", "posterior"])
def test_atencion_permitida_sin_cambiar_vigencia_observaciones_ni_aplicaciones(base, tipo, esquema):
    srv, ruta, _, mascota, _, vet, vacuna = base
    if esquema == "completo":
        srv.atencion.registrar_aplicacion(mascota, vacuna, date(2026, 11, 1), date(2026, 11, 5))
    elif esquema == "vencida":
        srv.atencion.registrar_aplicacion(mascota, vacuna, date(2026, 11, 1), FECHA.date())
    elif esquema == "posterior":
        srv.atencion.registrar_aplicacion(mascota, vacuna, date(2026, 11, 5))
    esperadas = [] if esquema == "completo" else ["Antirrábica"]
    assert srv.atencion.vacunas_pendientes(mascota, FECHA.date()) == esperadas
    antes = aplicaciones(ruta)
    pendientes_reporte = srv.reportes.vacunas_pendientes(FECHA.date())["filas"]
    historia = srv.atencion.obtener_historia(mascota)
    diagnostico, observaciones = "  Diagnóstico <literal>\nSegunda línea & >  ", "  Texto profesional\nSin notas automáticas  "
    atencion = srv.atencion.registrar_atencion(
        mascota, vet, FECHA, tipo, "Control", diagnostico, observaciones)
    nuevo = Servicios(ruta)
    assert nuevo.atencion.vacunas_pendientes(mascota, FECHA.date()) == esperadas
    assert aplicaciones(ruta) == antes
    assert nuevo.reportes.vacunas_pendientes(FECHA.date())["filas"] == pendientes_reporte
    assert nuevo.atencion.obtener_historia(mascota) == historia
    con = abrir_conexion(ruta)
    try:
        h = HistoriaClinicaDAO(con).obtener_por_mascota(mascota)
        registros = AtencionDAO(con).listar_por_historia(h.id_historia)
        assert len(registros) == 1
        a = registros[0]
        assert (a.id_atencion, a.fecha_hora, a.tipo, a.veterinario.id_veterinario) == (atencion, FECHA, tipo, vet)
        assert a.diagnostico == diagnostico.strip() and a.observaciones == observaciones.strip()
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        con.close()


@pytest.mark.parametrize("invalido, mensaje", [
    ("mascota", "mascota no existe"), ("veterinario", "veterinario no existe"),
    ("historia", "no tiene historia"), ("motivo", "obligatorio"),
])
def test_pendientes_no_suprimen_las_demas_validaciones(base, invalido, mensaje):
    srv, ruta, cliente, mascota, _, vet, _ = base
    if invalido == "historia":
        mascota = srv.clinica.crear_mascota(cliente, "Sin historia", "Perro")
    with pytest.raises(ErrorNegocio, match=mensaje):
        srv.atencion.registrar_atencion(
            999 if invalido == "mascota" else mascota,
            999 if invalido == "veterinario" else vet,
            FECHA, TipoAtencion.URGENCIA, "" if invalido == "motivo" else "Urgencia")
    assert Servicios(ruta).atencion.listar_atenciones() == []
    assert aplicaciones(ruta) == []


def test_error_de_persistencia_revierte_atencion_sin_modificar_historia_ni_vacunas(base, monkeypatch):
    srv, ruta, _, mascota, _, vet, _ = base
    historia = srv.atencion.obtener_historia(mascota)
    original = AtencionDAO.crear

    def fallar(dao, atencion, id_historia):
        original(dao, atencion, id_historia)
        raise RuntimeError("Fallo posterior al INSERT")

    monkeypatch.setattr(AtencionDAO, "crear", fallar)
    with pytest.raises(RuntimeError, match="posterior al INSERT"):
        srv.atencion.registrar_atencion(mascota, vet, FECHA, TipoAtencion.CONTROL, "Control")
    nuevo = Servicios(ruta)
    assert nuevo.atencion.listar_atenciones(mascota) == []
    assert nuevo.atencion.obtener_historia(mascota) == historia
    assert nuevo.atencion.vacunas_pendientes(mascota, FECHA.date()) == ["Antirrábica"]
    assert aplicaciones(ruta) == []


@pytest.mark.parametrize("intacto", [True, False])
def test_pendientes_permiten_derivacion_laboratorio_comprobantes_y_reportes(base, tmp_path, intacto):
    srv, ruta, _, mascota, cl, vet, _ = base
    atencion = srv.atencion.registrar_atencion(mascota, vet, FECHA, TipoAtencion.URGENCIA,
                                               "Urgencia", observaciones="Observación profesional\n< & >")
    muestra = srv.laboratorio.derivar(atencion, "Hemograma", "Sangre", FECHA)["id_muestra"]
    cons = srv.laboratorio.crear_conservadora("C-1")
    remito = srv.laboratorio.empaquetar(cl, cons, [muestra], "P-1", FECHA)["id_remito"]
    envio = srv.laboratorio.despachar_remito(remito, FECHA + timedelta(hours=1))
    srv.laboratorio.recibir_remito(envio, intacto, FECHA + timedelta(hours=2))
    if intacto:
        srv.laboratorio.registrar_resultado(muestra, "Normal", fecha_resultado=FECHA + timedelta(hours=3))
    else:
        with pytest.raises(ErrorNegocio, match="RECHAZADA"):
            srv.laboratorio.registrar_resultado(muestra, "No permitido")
    srv.atencion.emitir_comprobante(atencion, FECHA + timedelta(hours=4))
    nuevo = Servicios(ruta)
    exportar_comprobante_pdf(tmp_path / "atencion.pdf", nuevo.atencion.obtener_comprobante(atencion))
    assert (tmp_path / "atencion.pdf").read_bytes().startswith(b"%PDF")
    if intacto:
        exportar_comprobante_resultado_pdf(tmp_path / "resultado.pdf",
                                           nuevo.laboratorio.obtener_comprobante_resultado(muestra))
        assert (tmp_path / "resultado.pdf").read_bytes().startswith(b"%PDF")
    estados = [h["estado"] for h in nuevo.laboratorio.historial_muestra(muestra)]
    assert estados == (["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA"] if intacto
                       else ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECHAZADA"])
    reportes = nuevo.reportes.todos(FECHA.date())
    assert set(reportes) == {"atenciones", "rechazadas", "vacunas", "tiempos"}
    assert reportes["atenciones"]["filas"][0]["derivaciones"] == 1
    assert len(reportes["rechazadas"]["filas"]) == (0 if intacto else 1)
    assert reportes["vacunas"]["filas"] and reportes["tiempos"]["filas"]
    assert nuevo.atencion.vacunas_pendientes(mascota, FECHA.date()) == ["Antirrábica"]
    assert aplicaciones(ruta) == []
