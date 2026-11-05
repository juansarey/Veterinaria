"""El límite del reloj se aplica al registrar, nunca al reconstruir la cadena de custodia."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.recepcion_dao import RecepcionDAO
from veterinaria.servicios import laboratorio_servicio as ls
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios

AHORA = datetime(2026, 11, 5, 12, 30)
INICIO = AHORA - timedelta(hours=6)
OPERACIONES = {
    "orden": "Fecha de emisión", "extraer": "Fecha de extracción", "derivar": "Fecha de extracción",
    "remito": "Fecha de emisión", "empaquetar": "Fecha de empaquetado", "agregar": "Fecha de empaquetado",
    "despachar": "Salida", "llegada": "Llegada", "recepcion": "Recepción", "recibir_intacto": "Recepción",
    "recibir_roto": "Recepción", "recibir_roto_llegada": "Recepción", "resultado": "Fecha del resultado",
}


@pytest.fixture
def base(tmp_path, monkeypatch):
    reloj = {"ahora": AHORA}
    monkeypatch.setattr(ls, "ahora", lambda: reloj["ahora"])
    ruta = tmp_path / "laboratorio.db"
    srv = Servicios(ruta)
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, INICIO - timedelta(days=1), TipoAtencion.CONSULTA, "Control")
    return dict(srv=srv, ruta=ruta, reloj=reloj, mascota=mascota, clinica=clinica, vet=vet, atencion=atencion)


def datos(ruta):
    con = abrir_conexion(ruta)
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        return tuple(con.iterdump())
    finally:
        con.close()


def preparar(b, operacion):
    lab = b["srv"].laboratorio
    if operacion == "orden":
        return lambda fecha: lab.crear_orden(b["atencion"], "Hemograma", fecha_emision=fecha)
    if operacion == "derivar":
        return lambda fecha: lab.derivar(b["atencion"], "Hemograma", "Sangre", fecha)
    orden = lab.crear_orden(b["atencion"], "Hemograma", fecha_emision=INICIO)
    if operacion == "extraer":
        return lambda fecha: lab.registrar_muestra(orden, "Sangre", fecha)
    muestra = lab.registrar_muestra(orden, "Sangre", INICIO)
    cons = lab.crear_conservadora("C-1")
    if operacion == "remito":
        return lambda fecha: lab.crear_remito(b["clinica"], cons, fecha_emision=fecha)
    if operacion == "empaquetar":
        return lambda fecha: lab.empaquetar(b["clinica"], cons, [muestra], "P-1", fecha)
    remito = lab.crear_remito(b["clinica"], cons, fecha_emision=INICIO)
    if operacion == "agregar":
        return lambda fecha: lab.agregar_muestras_a_remito(remito, [muestra], fecha)
    lab.agregar_muestras_a_remito(remito, [muestra], INICIO + timedelta(minutes=10))
    lab.asignar_precinto(remito, "P-1")
    if operacion == "despachar":
        return lambda fecha: lab.despachar_remito(remito, fecha)
    envio = lab.despachar_remito(remito, INICIO + timedelta(minutes=20))
    if operacion == "llegada":
        return lambda fecha: lab.registrar_llegada(envio, fecha)
    if operacion in ("recibir_intacto", "recibir_roto"):
        return lambda fecha: lab.recibir_remito(envio, operacion == "recibir_intacto", fecha)
    lab.registrar_llegada(envio, INICIO + timedelta(minutes=30))
    if operacion == "recibir_roto_llegada":
        return lambda fecha: lab.recibir_remito(envio, False, fecha)
    if operacion == "recepcion":
        return lambda fecha: lab.registrar_recepcion(envio, fecha)
    lab.registrar_recepcion(envio, INICIO + timedelta(minutes=40))
    return lambda fecha: lab.registrar_resultado(muestra, "Normal", fecha_resultado=fecha)


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_fecha_futura_se_rechaza_antes_de_transaccion_y_sin_escrituras(base, monkeypatch, operacion):
    ejecutar = preparar(base, operacion)
    antes = datos(base["ruta"])
    def transaccion_prohibida():
        pytest.fail("Una fecha futura debe rechazarse antes de abrir la transacción")
    monkeypatch.setattr(base["srv"].laboratorio, "_tx", transaccion_prohibida)
    with pytest.raises(ErrorNegocio, match="posterior al momento actual") as error:
        ejecutar(AHORA + timedelta(minutes=1))
    assert error.value.campo == OPERACIONES[operacion]
    assert datos(base["ruta"]) == antes


@pytest.mark.parametrize("operacion", OPERACIONES)
@pytest.mark.parametrize("fecha", [AHORA - timedelta(hours=1), AHORA])
def test_pasado_y_minuto_actual_permitidos_y_persistidos(base, operacion, fecha):
    ejecutar = preparar(base, operacion)
    antes = datos(base["ruta"])
    ejecutar(fecha)
    despues = datos(base["ruta"])
    assert despues != antes
    assert any(fecha.isoformat() in linea for linea in despues)
    # Reabrir los servicios y consultar no ejecuta las validaciones de alta.
    nuevo = Servicios(base["ruta"])
    nuevo.laboratorio.listar_ordenes()
    nuevo.laboratorio.listar_muestras()
    nuevo.laboratorio.listar_envios()


@pytest.mark.parametrize("operacion, minutos", [
    ("empaquetar", -1), ("agregar", -1), ("despachar", 5), ("llegada", 15),
    ("recepcion", 25), ("recibir_roto_llegada", 25), ("resultado", 35),
])
def test_orden_cronologico_se_conserva_y_revierte_todos_los_cambios(base, operacion, minutos):
    ejecutar = preparar(base, operacion)
    antes = datos(base["ruta"])
    with pytest.raises(ErrorNegocio) as error:
        ejecutar(INICIO + timedelta(minutes=minutos))
    assert error.value.campo == OPERACIONES[operacion]
    assert datos(base["ruta"]) == antes


@pytest.mark.parametrize("fecha", ["05/11/2026", date(2026, 11, 5), AHORA.replace(tzinfo=timezone.utc)])
def test_fecha_local_invalida_se_informa_sin_mutaciones(base, fecha):
    ejecutar = preparar(base, "extraer")
    antes = datos(base["ruta"])
    with pytest.raises(ErrorNegocio) as error:
        ejecutar(fecha)
    assert error.value.campo == "Fecha de extracción"
    assert datos(base["ruta"]) == antes


@pytest.mark.parametrize("operacion", ["derivar", "empaquetar", "recibir_roto"])
def test_operacion_combinada_toma_un_solo_momento_del_reloj(base, monkeypatch, operacion):
    ejecutar = preparar(base, operacion)
    llamadas = []
    def reloj():
        llamadas.append(1)
        return AHORA
    monkeypatch.setattr(ls, "ahora", reloj)
    ejecutar(None)
    assert llamadas == [1]


def test_rollback_se_mantiene_ante_fallo_despues_de_actualizar_recepcion(base, monkeypatch):
    ejecutar = preparar(base, "recibir_roto")
    antes = datos(base["ruta"])
    original = RecepcionDAO.guardar_recepcion
    def fallar(dao, recepcion):
        original(dao, recepcion)
        raise RuntimeError("Fallo después de persistir")
    monkeypatch.setattr(RecepcionDAO, "guardar_recepcion", fallar)
    with pytest.raises(RuntimeError, match="después de persistir"):
        ejecutar(AHORA)
    assert datos(base["ruta"]) == antes


def test_m0008_historica_con_cadena_futura_se_reconstruye_sin_modificar(base):
    srv, reloj = base["srv"], base["reloj"]
    reloj["ahora"] = datetime(2026, 11, 16, 12)
    orden = srv.laboratorio.crear_orden(base["atencion"], "Histórico", fecha_emision=datetime(2026, 11, 5, 0, 30))
    for _ in range(7):
        srv.laboratorio.registrar_muestra(orden, "Sangre", INICIO)
    muestra = srv.laboratorio.registrar_muestra(orden, "Sangre", datetime(2026, 11, 5, 0, 38))
    assert muestra == 8
    cons = srv.laboratorio.crear_conservadora("HISTORICA")
    remito = srv.laboratorio.empaquetar(base["clinica"], cons, [muestra], "HISTORICO",
                                       datetime(2026, 11, 6, 0, 36))["id_remito"]
    envio = srv.laboratorio.despachar_remito(remito, datetime(2026, 11, 14, 1, 1))
    srv.laboratorio.recibir_remito(envio, True, datetime(2026, 11, 15, 0, 56))
    srv.laboratorio.registrar_resultado(muestra, "Normal", fecha_resultado=datetime(2026, 11, 16, 0, 56))
    antes = datos(base["ruta"])
    reloj["ahora"] = AHORA
    nuevo = Servicios(base["ruta"])
    historial = nuevo.laboratorio.historial_muestra(muestra)
    assert [h["fecha"] for h in historial] == ["05/11/2026 00:38", "06/11/2026 00:36", "14/11/2026 01:01",
                                              "15/11/2026 00:56", "16/11/2026 00:56"]
    assert nuevo.laboratorio.obtener_resultado(muestra)["resultado"] == "Normal"
    assert nuevo.laboratorio.obtener_comprobante_resultado(muestra)
    nuevo.laboratorio.listar_muestras(); nuevo.laboratorio.listar_remitos(); nuevo.laboratorio.listar_envios()
    nuevo.reportes.todos(date(2026, 11, 20))
    assert datos(base["ruta"]) == antes


def test_excepciones_turnos_proximas_dosis_y_referencia_de_reportes(base, monkeypatch):
    srv = base["srv"]
    monkeypatch.setattr("veterinaria.servicios.clinica_servicio.ahora", lambda: AHORA)
    srv.clinica.guardar_agenda(base["vet"], set(DiaSemana), time(8), time(18))
    futuro = AHORA.replace(hour=10) + timedelta(days=1)
    assert srv.clinica.agendar_turno(base["vet"], base["mascota"], futuro, futuro + timedelta(minutes=30))
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    proxima = date(2027, 11, 5)
    srv.atencion.registrar_aplicacion(base["mascota"], vacuna, AHORA.date(), proxima)
    assert srv.atencion.listar_aplicaciones(base["mascota"])[0]["proxima_dosis"] == "05/11/2027"
    assert srv.reportes.vacunas_pendientes(date(2030, 1, 1))["filas"]
