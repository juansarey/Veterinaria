"""Límite del reloj en formularios y calendarios, conservando datos y estados al rechazar."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from test_pantallas import elegir, pestana, ui
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_laboratorio as sl
from veterinaria.persistencia.conexion import abrir_conexion

AHORA = datetime(2026, 11, 5, 12, 30)
INICIO = AHORA - timedelta(hours=6)


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    referencia = {"ahora": AHORA}
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return referencia["ahora"]
    class Fecha(date):
        @classmethod
        def today(cls):
            return referencia["ahora"].date()
    monkeypatch.setattr("veterinaria.servicios.laboratorio_servicio.ahora", lambda: referencia["ahora"])
    monkeypatch.setattr(c, "datetime", Reloj)
    monkeypatch.setattr(sl, "date", Fecha)
    return referencia


def datos(ruta):
    con = abrir_conexion(ruta)
    try:
        return tuple(con.iterdump())
    finally:
        con.close()


def preparar(app, operacion):
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "00123")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, INICIO, TipoAtencion.CONSULTA, "Control")
    muestra = srv.laboratorio.derivar(atencion, "Hemograma", "Sangre", INICIO)["id_muestra"]
    cons = srv.laboratorio.crear_conservadora("C-1")
    if operacion == "empaquetar":
        p = pestana(app, sl.PestanaEmpaquetado)
        p.refrescar(); p.clinica.value = str(clinica); p.conservadora.value = str(cons)
        return p, p.fecha, "Empaquetar y precintar"
    remito = srv.laboratorio.empaquetar(clinica, cons, [muestra], "P-1",
                                       INICIO + timedelta(minutes=10))["id_remito"]
    if operacion == "despachar":
        p = pestana(app, sl.PestanaEnvio)
        p.refrescar(); p.remito.value = str(remito)
        return p, p.salida, "Despachar"
    envio = srv.laboratorio.despachar_remito(remito, INICIO + timedelta(minutes=20))
    if operacion == "recibir":
        p = pestana(app, sl.PestanaEnvio)
        p.refrescar(); p.envio.value = str(envio); p.integro.value = "Precinto intacto"
        return p, p.f_recepcion, "Registrar recepción"
    srv.laboratorio.recibir_remito(envio, True, INICIO + timedelta(minutes=30))
    p = pestana(app, sl.PestanaResultados)
    p.refrescar(); elegir(p.muestra); p.muestra.on_select(SimpleNamespace())
    p.resultado.value = "Normal\nTexto <literal> & >"
    return p, p.fecha, "Registrar resultado y generar PDF"


@pytest.mark.parametrize("operacion", ["empaquetar", "despachar", "recibir", "resultado"])
@pytest.mark.parametrize("diferencia", [timedelta(hours=1), timedelta(days=1)], ids=["hora_futura", "dia_futuro"])
def test_fecha_futura_error_localizado_sin_escrituras_y_recuperacion(ui, operacion, diferencia):
    app, pag = ui
    p, campo, texto_boton = preparar(app, operacion)
    valor = (AHORA + diferencia).strftime(c.FMT_FECHA_HORA)
    campo.value = valor
    if hasattr(p, "obs_rec"):
        p.obs_rec.value = "Observación\nNo perder"
    if hasattr(p, "precinto"):
        p.precinto.value = "Conservar código"
    antes = datos(app.ruta_bd)
    boton = boton_en(p, texto_boton)
    boton.on_click(None)
    assert campo.error and "posterior al momento actual" in campo.error
    assert pag.mensajes[-1] == campo.error and campo.value == valor
    assert not p.vista.disabled and datos(app.ruta_bd) == antes
    if operacion == "recibir":
        assert p.integro.value == "Precinto intacto" and p.obs_rec.value == "Observación\nNo perder"
    if operacion == "resultado":
        assert p.resultado.value == "Normal\nTexto <literal> & >"
    if operacion == "empaquetar":
        assert p.precinto.value == "Conservar código" and all(ch.value for ch in p.checks.values())
    campo.value = AHORA.strftime(c.FMT_FECHA_HORA)
    boton.on_click(None)
    assert campo.error is None and datos(app.ruta_bd) != antes


@pytest.mark.parametrize("clase, atributo", [
    (sl.PestanaEmpaquetado, "fecha"), (sl.PestanaEnvio, "salida"),
    (sl.PestanaEnvio, "f_recepcion"), (sl.PestanaResultados, "fecha"),
])
def test_calendario_limite_dinamico_hoy_no_sobrescribe_fecha_historica_futura(ui, reloj, clase, atributo):
    app, pag = ui
    campo = getattr(pestana(app, clase), atributo)
    campo.value = "16/11/2026 08:15"
    campo.suffix.controls[0].on_click(SimpleNamespace(page=pag))
    selector = pag.pickers[-1]
    assert selector.last_date.date() == AHORA.date() and selector.value.date() == AHORA.date()
    assert campo.value == "16/11/2026 08:15"
    reloj["ahora"] += timedelta(days=1)
    campo.suffix.controls[0].on_click(SimpleNamespace(page=pag))
    selector = pag.pickers[-1]
    assert selector.last_date.date() == reloj["ahora"].date()
    selector.on_change(SimpleNamespace(control=SimpleNamespace(value=reloj["ahora"])))
    assert campo.value == "06/11/2026 08:15"  # conserva la hora elegida


def test_error_de_llegada_en_recepcion_combinada_se_asocia_al_campo_recepcion(ui):
    app, pag = ui
    p, campo, texto = preparar(app, "recibir")
    campo.value = (INICIO + timedelta(minutes=15)).strftime(c.FMT_FECHA_HORA)
    antes = datos(app.ruta_bd)
    boton_en(p, texto).on_click(None)
    assert campo.error and "anterior a la salida" in campo.error
    assert pag.mensajes[-1] == campo.error
    assert datos(app.ruta_bd) == antes and p.integro.value == "Precinto intacto"
