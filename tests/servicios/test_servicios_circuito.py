"""Circuito completo a través de la capa de servicios (sin interfaz)."""

from datetime import date, datetime, time, timedelta

import pytest

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.exportador import exportar_csv, exportar_pdf, exportar_comprobante_pdf
from veterinaria.servicios.fachada import Servicios

LUNES = datetime(2026, 11, 2, 9, 0)  # lunes


@pytest.fixture
def s(tmp_path):
    return Servicios(tmp_path / "vet.db")


@pytest.fixture
def base(s):
    id_cli = s.clinica.crear_cliente("Ana", "Pérez", "30111222", "351", "a@x.com")
    id_mas = s.clinica.crear_mascota(id_cli, "Firulais", "Perro")
    id_cl = s.clinica.crear_clinica("Clínica Centro", "Colón 100")
    id_vet = s.clinica.crear_veterinario(id_cl, "Luis", "Gómez", "MP-1")
    s.clinica.guardar_agenda(id_vet, {DiaSemana.LUNES}, time(8), time(13))
    s.atencion.abrir_historia(id_mas, "Primera visita", date(2026, 11, 2))
    return {"cli": id_cli, "mas": id_mas, "cl": id_cl, "vet": id_vet}


def _atencion_con_orden(s, b):
    id_at = s.atencion.registrar_atencion(b["mas"], b["vet"], LUNES, TipoAtencion.CONSULTA, "Control")
    id_or = s.laboratorio.crear_orden(id_at, "Hemograma", fecha_emision=LUNES)
    id_mu = s.laboratorio.registrar_muestra(id_or, "Sangre", LUNES)
    return id_at, id_or, id_mu


def _despachado(s, b, id_mu, romper=False):
    id_c = s.laboratorio.crear_conservadora("CONS-1")
    id_r = s.laboratorio.crear_remito(b["cl"], id_c, fecha_emision=LUNES)
    s.laboratorio.agregar_muestras_a_remito(id_r, [id_mu], LUNES + timedelta(minutes=10))
    s.laboratorio.asignar_precinto(id_r, "PRE-1")
    id_e = s.laboratorio.despachar_remito(id_r, LUNES + timedelta(minutes=30))
    if romper:
        s.laboratorio.romper_precinto(id_r)
    s.laboratorio.registrar_llegada(id_e, LUNES + timedelta(hours=2))
    return id_r, id_e


def test_mascota_sin_responsable(s):
    with pytest.raises(ErrorNegocio):
        s.clinica.crear_mascota(None, "X", "Perro")
    with pytest.raises(ErrorNegocio):
        s.clinica.crear_mascota(999, "X", "Perro")


def test_turnos_agenda_superposicion_y_cancelado(s, base):
    t = lambda h, m, h2, m2: (LUNES.replace(hour=h, minute=m), LUNES.replace(hour=h2, minute=m2))
    s.clinica.agendar_turno(base["vet"], base["mas"], *t(9, 0, 9, 30))
    s.clinica.agendar_turno(base["vet"], base["mas"], *t(9, 30, 10, 0))      # consecutivo
    with pytest.raises(ErrorNegocio, match="superpone"):
        s.clinica.agendar_turno(base["vet"], base["mas"], *t(9, 15, 9, 45))
    with pytest.raises(ErrorNegocio, match="fuera de la agenda"):
        s.clinica.agendar_turno(base["vet"], base["mas"], *t(13, 0, 13, 30))
    with pytest.raises(ErrorNegocio, match="fuera de la agenda"):            # martes
        s.clinica.agendar_turno(base["vet"], base["mas"], LUNES + timedelta(days=1), LUNES + timedelta(days=1, minutes=30))
    primero = s.clinica.listar_turnos()[0]["id"]
    s.clinica.cambiar_estado_turno(primero, "cancelar")
    s.clinica.agendar_turno(base["vet"], base["mas"], *t(9, 15, 9, 30))      # libera el horario


def test_atencion_exige_historia_y_vacunas(s, base):
    id_cli = s.clinica.crear_cliente("Bea", "Ruiz", "30999888")
    sin_historia = s.clinica.crear_mascota(id_cli, "Michi", "Gato")
    with pytest.raises(ErrorNegocio, match="historia"):
        s.atencion.registrar_atencion(sin_historia, base["vet"], LUNES, TipoAtencion.CONSULTA, "x")

    id_vac = s.atencion.crear_vacuna("Antirrábica", "Perro", True)
    with pytest.raises(ErrorNegocio, match="Antirrábica"):
        s.atencion.registrar_atencion(base["mas"], base["vet"], LUNES, TipoAtencion.CONSULTA, "x")
    s.atencion.registrar_aplicacion(base["mas"], id_vac, date(2026, 10, 1), date(2027, 10, 1))
    assert s.atencion.vacunas_pendientes(base["mas"], date(2026, 11, 2)) == []
    s.atencion.registrar_atencion(base["mas"], base["vet"], LUNES, TipoAtencion.CONSULTA, "ok")


def test_circuito_precinto_intacto(s, base, tmp_path):
    id_at, id_or, id_mu = _atencion_con_orden(s, base)
    id_r, id_e = _despachado(s, base, id_mu)
    res = s.laboratorio.registrar_recepcion(id_e, LUNES + timedelta(hours=2, minutes=15))
    assert res["resultado"] == "ACEPTADO" and res["muestras"] == [(id_mu, "RECIBIDA")]
    s.laboratorio.registrar_resultado(id_mu, "Normal", fecha_resultado=LUNES + timedelta(hours=4))
    assert [h["estado"] for h in s.laboratorio.historial_muestra(id_mu)] == [
        "EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA"]
    assert s.laboratorio.listar_ordenes()[0]["estado"] == "COMPLETADA"
    assert s.laboratorio.obtener_resultado(id_mu)["resultado"] == "Normal"

    s.atencion.emitir_comprobante(id_at, LUNES + timedelta(hours=5))
    comp = s.atencion.obtener_comprobante(id_at)
    assert comp["mascota"].startswith("Firulais")
    with pytest.raises(ErrorNegocio):
        s.atencion.emitir_comprobante(id_at)

    t = s.reportes.tiempos()["filas"]
    assert t[0]["cantidad"] == 1 and t[1]["cantidad"] == 1
    assert s.reportes.muestras_rechazadas()["filas"] == []
    rep = s.reportes.atenciones_derivaciones()["filas"]
    assert rep[0]["mascota"] == "Firulais" and rep[0]["clinica"] == "Clínica Centro"
    assert rep[0]["derivaciones"] == 1

    exportar_csv(tmp_path / "r.csv", s.reportes.atenciones_derivaciones())
    exportar_pdf(tmp_path / "r.pdf", s.reportes.tiempos())
    exportar_comprobante_pdf(tmp_path / "c.pdf", comp)
    assert (tmp_path / "r.pdf").stat().st_size > 500 and (tmp_path / "c.pdf").stat().st_size > 500


def test_circuito_precinto_roto_rechaza(s, base):
    _, _, id_mu = _atencion_con_orden(s, base)
    id_r, id_e = _despachado(s, base, id_mu, romper=True)
    res = s.laboratorio.registrar_recepcion(id_e, LUNES + timedelta(hours=3))
    assert res["resultado"] == "RECHAZADO" and res["muestras"] == [(id_mu, "RECHAZADA")]
    with pytest.raises(ErrorNegocio, match="RECHAZADA"):
        s.laboratorio.registrar_resultado(id_mu, "x")
    assert [h["estado"] for h in s.laboratorio.historial_muestra(id_mu)][-1] == "RECHAZADA"
    fila = s.reportes.muestras_rechazadas()["filas"][0]
    assert fila["estado_precinto"] == "ROTO" and fila["id_remito"] == id_r
    assert s.reportes.tiempos()["filas"][1]["cantidad"] == 0


def test_no_despacha_sin_condiciones(s, base):
    _, _, id_mu = _atencion_con_orden(s, base)
    id_c = s.laboratorio.crear_conservadora("CONS-2")
    id_r = s.laboratorio.crear_remito(base["cl"], id_c)
    with pytest.raises(ErrorNegocio, match="muestras"):
        s.laboratorio.despachar_remito(id_r)
    s.laboratorio.agregar_muestras_a_remito(id_r, [id_mu], LUNES + timedelta(minutes=1))
    with pytest.raises(ErrorNegocio, match="precinto"):
        s.laboratorio.despachar_remito(id_r)
    with pytest.raises(ErrorNegocio, match="no está disponible"):
        s.laboratorio.crear_remito(base["cl"], id_c)


def test_vacunas_pendientes_reporte(s, base):
    s.atencion.crear_vacuna("Antirrábica", "Perro", True)
    filas = s.reportes.vacunas_pendientes(date(2026, 11, 2))["filas"]
    assert filas[0]["mascota"] == "Firulais" and filas[0]["vacuna"] == "Antirrábica"


# ---------------------------------------------------------- acciones en un solo paso
def test_mascota_con_historia_automatica(s, base):
    id_mas = s.clinica.crear_mascota(base["cli"], "Nina", "Gato", abrir_historia=True)
    assert s.atencion.obtener_historia(id_mas) is not None
    s.atencion.registrar_atencion(id_mas, base["vet"], LUNES, TipoAtencion.CONSULTA, "Control")


def test_derivar_empaquetar_y_recibir_en_un_paso(s, base):
    id_at = s.atencion.registrar_atencion(base["mas"], base["vet"], LUNES, TipoAtencion.CONSULTA, "x")
    r = s.laboratorio.derivar(id_at, "Hemograma", "Sangre", LUNES)
    id_c = s.laboratorio.crear_conservadora("CONS-9")
    emp = s.laboratorio.empaquetar(base["cl"], id_c, [r["id_muestra"]], "", LUNES + timedelta(hours=1))
    assert emp["precinto"].startswith("PRE-")
    id_e = s.laboratorio.despachar_remito(emp["id_remito"], LUNES + timedelta(hours=2))
    res = s.laboratorio.recibir_remito(id_e, True, LUNES + timedelta(hours=4))
    assert res["resultado"] == "ACEPTADO"
    # sin muestras no se crea nada: la operación es atómica
    id_c2 = s.laboratorio.crear_conservadora("CONS-10")
    with pytest.raises(ErrorNegocio):
        s.laboratorio.empaquetar(base["cl"], id_c2, [], "", LUNES)
    assert [c["estado"] for c in s.laboratorio.listar_conservadoras() if c["id"] == id_c2] == ["DISPONIBLE"]


def test_recibir_remito_con_precinto_roto(s, base):
    id_at = s.atencion.registrar_atencion(base["mas"], base["vet"], LUNES, TipoAtencion.CONSULTA, "x")
    id_mu = s.laboratorio.derivar(id_at, "Urianálisis", "Orina", LUNES)["id_muestra"]
    id_c = s.laboratorio.crear_conservadora("CONS-1")
    emp = s.laboratorio.empaquetar(base["cl"], id_c, [id_mu], "PRE-X", LUNES + timedelta(hours=1))
    id_e = s.laboratorio.despachar_remito(emp["id_remito"], LUNES + timedelta(hours=2))
    res = s.laboratorio.recibir_remito(id_e, False, LUNES + timedelta(hours=3))
    assert res["resultado"] == "RECHAZADO" and res["muestras"] == [(id_mu, "RECHAZADA")]
    with pytest.raises(ErrorNegocio, match="RECHAZADA"):
        s.laboratorio.registrar_resultado(id_mu, "x")
    # liberar manualmente la conservadora tras la recepción
    s.laboratorio.liberar_conservadora(id_c)


def test_empaquetar_con_fecha_anterior_a_la_extraccion(s, base):
    id_at = s.atencion.registrar_atencion(base["mas"], base["vet"], LUNES, TipoAtencion.CONSULTA, "x")
    id_mu = s.laboratorio.derivar(id_at, "Hemograma", "Sangre", LUNES)["id_muestra"]
    id_c = s.laboratorio.crear_conservadora("CONS-1")
    with pytest.raises(ErrorNegocio, match="anterior a la extracción"):
        s.laboratorio.empaquetar(base["cl"], id_c, [id_mu], "", LUNES - timedelta(hours=1))


def test_datos_demo(tmp_path):
    from veterinaria.servicios.datos_demo import cargar_demo, hay_datos
    s = Servicios(tmp_path / "demo.db")
    assert not hay_datos(s)
    cargar_demo(s)
    assert hay_datos(s)
    estados = {m["estado"] for m in s.laboratorio.listar_muestras()}
    assert {"ANALIZADA", "RECHAZADA", "EN_TRANSITO", "EXTRAIDA"} <= estados
    reportes = s.reportes.todos()
    assert len(reportes["rechazadas"]["filas"]) == 2 and reportes["vacunas"]["filas"]
    assert reportes["tiempos"]["filas"][0]["cantidad"] >= 1
    with pytest.raises(ErrorNegocio, match="pendientes"):        # Toby tiene vacunas pendientes
        toby = next(m for m in s.clinica.listar_mascotas() if m["nombre"] == "Toby")["id"]
        vet = s.clinica.listar_veterinarios()[0]["id"]
        s.atencion.registrar_atencion(toby, vet, datetime.now(), TipoAtencion.CONSULTA, "x")
