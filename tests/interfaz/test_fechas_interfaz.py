"""Fechas y transiciones desde los eventos Flet, sin abrir una ventana real."""

from datetime import date, datetime, time
from types import SimpleNamespace

import pytest

from test_pantallas import elegir, pestana, ui
from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa, seccion_laboratorio as sl
from veterinaria.interfaz import seccion_personas as sp, seccion_turnos as st
from veterinaria.servicios import clinica_servicio as cs


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    referencia = {"ahora": datetime(2026, 11, 4, 10, 30, 45)}

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return referencia["ahora"]

    class Fecha(date):
        @classmethod
        def today(cls):
            return referencia["ahora"].date()

    monkeypatch.setattr(cs, "ahora", lambda: referencia["ahora"])
    monkeypatch.setattr("veterinaria.servicios.laboratorio_servicio.ahora", lambda: referencia["ahora"])
    monkeypatch.setattr(c, "datetime", Reloj)
    monkeypatch.setattr(c, "date", Fecha)
    monkeypatch.setattr(sp, "date", Fecha)
    monkeypatch.setattr(st, "date", Fecha)
    monkeypatch.setattr(sa, "date", Fecha)
    monkeypatch.setattr(sl, "date", Fecha)
    return referencia


@pytest.fixture
def base(ui):
    app, _ = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "12345678")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Colón 100")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    srv.clinica.guardar_agenda(vet, set(DiaSemana), time(8), time(18))
    return dict(cliente=cliente, mascota=mascota, clinica=clinica, vet=vet)


@pytest.mark.parametrize("editar", [False, True])
@pytest.mark.parametrize("nacimiento", ["05/11/2026", "31/02/2026"])
def test_nacimiento_invalido_conserva_formulario_y_se_corrige(ui, base, editar, nacimiento):
    app, _ = ui
    p = pestana(app, sp.PestanaMascotas)
    p.refrescar()
    if editar:
        p._editar(p.datos[0])
    else:
        p.resp.value = str(base["cliente"])
    p.nombre_f.value, p.raza_f.value, p.nac_f.value = "Otra Luna", "Mestiza", nacimiento
    p._guardar()
    assert p.nac_f.error and p.nac_f.value == nacimiento
    assert p.nombre_f.value == "Otra Luna" and p.raza_f.value == "Mestiza"
    assert len(app.servicios.clinica.listar_mascotas()) == 1
    assert app.servicios.clinica.listar_mascotas()[0]["nombre"] == "Luna"
    p.nac_f.value = "04/11/2026"
    p._guardar()
    assert p.nac_f.error is None and p.nac_f.value == ""
    assert len(app.servicios.clinica.listar_mascotas()) == (1 if editar else 2)


def test_calendarios_limites_dinamicos_y_apertura_fuera_de_rango(ui, reloj):
    app, pag = ui
    p = pestana(app, sp.PestanaMascotas)
    p.nac_f.value = p.nac_f.data = "01/01/2030"
    evento = SimpleNamespace(page=pag)
    p.nac_f.suffix.controls[0].on_click(evento)
    calendario = pag.pickers[-1]
    assert calendario.last_date.date() == date(2026, 11, 4)
    assert calendario.first_date.date() < date(1950, 1, 1)
    assert calendario.value.date() == date(2026, 11, 4)
    assert p.nac_f.value == "01/01/2030"  # abrir o cancelar no corrige el dato escrito
    reloj["ahora"] = datetime(2026, 11, 5, 9)
    p.nac_f.suffix.controls[0].on_click(evento)
    assert pag.pickers[-1].last_date.date() == date(2026, 11, 5)
    ag = pestana(app, st.PestanaAgenda)
    ag.fecha.value = ag.fecha.data = "02/11/2026"
    ag.fecha.suffix.controls[0].on_click(evento)
    assert pag.pickers[-1].first_date.date() == date(2026, 11, 5)
    assert pag.pickers[-1].value.date() == date(2026, 11, 5)
    assert ag.fecha.value == "02/11/2026"
    ag.dia.suffix.controls[0].on_click(evento)
    assert pag.pickers[-1].first_date.date() < date(2026, 11, 5)


@pytest.mark.parametrize("clase, atributo, valor", [
    (st.PestanaAgenda, "fecha", "01/02/2020"),
    (st.PestanaAgenda, "hora", "09:15"),
    (st.PestanaAgenda, "dia", "01/02/2020"),
    (sa.PestanaAtenciones, "fecha", "01/02/2020 09:15"),
    (sa.PestanaVacunas, "f_aplic", "01/02/2020"),
    (sa.PestanaVacunas, "f_prox", "01/02/2021"),
    (sl.PestanaEmpaquetado, "fecha", "01/02/2020 09:15"),
    (sl.PestanaEnvio, "salida", "01/02/2020 09:15"),
    (sl.PestanaEnvio, "f_recepcion", "01/02/2020 09:15"),
    (sl.PestanaResultados, "fecha", "01/02/2020 09:15"),
])
def test_refrescar_y_navegar_preserva_fechas(ui, clase, atributo, valor):
    app, _ = ui
    pantalla = pestana(app, clase)
    control = getattr(pantalla, atributo)
    control.value = control.data = valor
    pantalla.refrescar()
    for indice in range(5):
        app.ir_a(indice)
    assert control.value == control.data == valor


def test_reporte_historico_y_error_preservan_filtro(ui):
    app, _ = ui
    p = app.pantallas[4]
    p.reporte.value = "vacunas"
    p.fecha_ref.value = "01/02/2020"
    p._generar()
    assert p.actual is not None and p.fecha_ref.value == "01/02/2020"
    p.fecha_ref.value = "fecha inválida"
    p._generar()
    assert p.actual is None and p.fecha_ref.error and p.fecha_ref.value == "fecha inválida"


@pytest.mark.parametrize("fecha, hora, campo", [
    ("03/11/2026", "11:00", "fecha"), ("04/11/2026", "10:29", "hora"),
])
def test_reserva_pasada_error_localizado_y_valores_conservados(ui, base, fecha, hora, campo):
    app, _ = ui
    p = pestana(app, st.PestanaAgenda)
    p.refrescar(); elegir(p.vet); elegir(p.mascota)
    p.fecha.value, p.hora.value, p.motivo.value = fecha, hora, "Control"
    p._reservar()
    assert getattr(p, campo).error
    assert (p.fecha.value, p.hora.value, p.motivo.value) == (fecha, hora, "Control")
    assert app.servicios.clinica.listar_turnos() == []


def test_reserva_futura_conserva_dia_y_luego_se_consulta_como_historica(ui, base, reloj):
    app, pag = ui
    p = pestana(app, st.PestanaAgenda)
    p.refrescar(); elegir(p.vet); elegir(p.mascota)
    p.fecha.value, p.hora.value, p.motivo.value = "05/11/2026", "11:00", "Control"
    p._reservar()
    assert "Turno reservado" in pag.mensajes[-1]
    assert p.fecha.value == p.dia.value == "05/11/2026" and p.hora.value == "11:00"
    assert p.motivo.value == ""
    reloj["ahora"] = datetime(2027, 1, 1, 12)
    p.refrescar(); p._ver()
    assert len(p.tabla.rows) == 1 and p.dia.value == "05/11/2026"


@pytest.mark.parametrize("accion_final", ["atender", "cancelar"])
def test_botones_reflejan_transiciones_de_turno(ui, base, accion_final):
    app, _ = ui
    srv = app.servicios
    turno = srv.clinica.agendar_turno(
        base["vet"], base["mascota"], datetime(2026, 11, 5, 11), datetime(2026, 11, 5, 11, 30))
    p = pestana(app, st.PestanaAgenda)
    p.dia.value = "05/11/2026"

    def visibles():
        p.refrescar()
        return {b.tooltip for b in p.tabla.rows[0].cells[-1].content.controls if b.visible}

    assert visibles() == {"Confirmar", "Cancelar turno"}
    srv.clinica.cambiar_estado_turno(turno, "confirmar")
    assert visibles() == {"Marcar atendido", "Cancelar turno"}
    p._cambiar(srv.clinica.listar_turnos()[0], accion_final)
    assert visibles() == set()


def test_responsable_bloqueado_al_editar_y_seleccionable_en_alta(ui, base):
    app, _ = ui
    otro = app.servicios.clinica.crear_cliente("Eva", "Ruiz", "87654321")
    p = pestana(app, sp.PestanaMascotas)
    p.refrescar(); p._editar(p.datos[0])
    assert p.resp.disabled and "no puede cambiarse" in p.resp.helper_text
    assert p.resp.value == str(base["cliente"])
    p.resp.value = str(otro)  # ni una asignación externa al control cambia la asociación
    p._guardar()
    assert app.servicios.clinica.listar_mascotas()[0]["id_responsable"] == base["cliente"]
    assert not p.resp.disabled and p.resp.helper_text is None
    p.nombre_f.value, p.resp.value = "Mora", str(otro)
    p._guardar()
    assert app.servicios.clinica.listar_mascotas()[-1]["id_responsable"] == otro


@pytest.mark.parametrize("via", ["escritura", "calendario"])
def test_aviso_vacunas_usa_fecha_y_mascota_y_coincide_con_guardado(ui, base, monkeypatch, via):
    app, pag = ui
    srv = app.servicios
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    srv.atencion.registrar_aplicacion(base["mascota"], vacuna, date(2026, 11, 1), date(2026, 11, 5))
    otra = srv.clinica.crear_mascota(base["cliente"], "Mora", "Perro", abrir_historia=True)
    p = pestana(app, sa.PestanaAtenciones)
    p.refrescar(); p.mascota.value = str(base["mascota"]); elegir(p.vet)
    p.fecha.value = "03/11/2026 09:15"
    p.fecha.on_change(SimpleNamespace())
    assert p.estado_vacunas.value == "Vacunas obligatorias al día."
    if via == "escritura":
        p.fecha.value = "05/11/2026 09:15"
        p.fecha.on_change(SimpleNamespace())
    else:
        p.fecha.suffix.controls[0].on_click(SimpleNamespace(page=pag))
        pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=datetime(2026, 11, 5))))
    assert "Antirrábica" in p.estado_vacunas.value

    consultas = []
    original = srv.atencion.vacunas_pendientes

    def consultar(id_mascota, fecha_referencia=None):
        consultas.append(fecha_referencia)
        return original(id_mascota, fecha_referencia)

    monkeypatch.setattr(srv.atencion, "vacunas_pendientes", consultar)
    p.fecha.suffix.controls[1].on_click(SimpleNamespace(page=pag))
    pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=time(10, 45))))
    assert consultas[-1] == date(2026, 11, 5)
    p.motivo.value = "Control"
    p._registrar()
    assert "Atención registrada" in pag.mensajes[-1]
    assert srv.atencion.listar_atenciones()[0]["fecha_hora"] == datetime(2026, 11, 5, 10, 45)
    assert p.fecha.value == "04/11/2026 10:30" and p.motivo.value == ""
    p.fecha.value = "03/11/2026 09:15"; p.fecha.on_change(SimpleNamespace())
    p.mascota.value = str(otra); p.mascota.on_select(SimpleNamespace())
    assert "Antirrábica" in p.estado_vacunas.value
    p.mascota.value = str(base["mascota"]); p.mascota.on_select(SimpleNamespace())
    assert p.estado_vacunas.value == "Vacunas obligatorias al día."
    p.motivo.value = "Control"; p._registrar()
    assert len(srv.atencion.listar_atenciones()) == 2
    assert srv.atencion.listar_atenciones()[0]["fecha_hora"] == datetime(2026, 11, 3, 9, 15)
    assert p.fecha.value == "04/11/2026 10:30" and p.motivo.value == ""


def test_fecha_incompleta_no_consulta_vacunas_para_otro_dia(ui, base, monkeypatch):
    app, _ = ui
    p = pestana(app, sa.PestanaAtenciones)
    p.refrescar(); p.mascota.value = str(base["mascota"]); elegir(p.vet)
    monkeypatch.setattr(app.servicios.atencion, "vacunas_pendientes",
                        lambda *_: pytest.fail("No debe usar hoy para una fecha inválida"))
    p.fecha.value = "04/11/2"
    p.fecha.on_change(SimpleNamespace())
    assert "Complete una fecha válida" in p.estado_vacunas.value and p.fecha.error is None
    p._registrar()
    assert p.fecha.error and p.fecha.value == "04/11/2"


def test_laboratorio_conserva_fechas_al_refrescar_y_reinicia_solo_tras_guardar(ui, base):
    app, pag = ui
    srv = app.servicios
    atencion = srv.atencion.registrar_atencion(
        base["mascota"], base["vet"], datetime(2026, 11, 3, 9), TipoAtencion.CONSULTA, "Control")
    muestra = srv.laboratorio.derivar(atencion, "Hemograma", "Sangre", datetime(2026, 11, 3, 9, 10))["id_muestra"]
    srv.laboratorio.crear_conservadora("CONS-1")
    emp = pestana(app, sl.PestanaEmpaquetado)
    emp.refrescar(); elegir(emp.clinica); elegir(emp.conservadora)
    emp.fecha.value = "03/11/2026 09:30"; emp._empaquetar()
    assert "Remito R-0001 emitido" in pag.dialogos[-1] and emp.fecha.value == "04/11/2026 10:30"
    assert srv.laboratorio.historial_muestra(muestra)[-1]["fecha"] == "03/11/2026 09:30"
    env = pestana(app, sl.PestanaEnvio)
    env.refrescar(); elegir(env.remito)
    env.salida.value, env.f_recepcion.value = "03/11/2026 10:00", "03/11/2026 11:00"
    env._despachar()
    assert env.salida.value == "04/11/2026 10:30" and env.f_recepcion.value == "03/11/2026 11:00"
    elegir(env.envio); env.integro.value = "Precinto intacto"; env._recibir()
    assert env.f_recepcion.value == "04/11/2026 10:30"
    res = pestana(app, sl.PestanaResultados)
    res.refrescar(); elegir(res.muestra)
    res.fecha.value, res.resultado.value = "03/11/2026 12:00", "Normal"
    res._registrar()
    assert "Comprobante emitido" in pag.mensajes[-1]
    assert srv.laboratorio.obtener_resultado(muestra)["fecha"] == "03/11/2026 12:00"
    assert res.fecha.value == "04/11/2026 10:30" and res.resultado.value == ""


@pytest.mark.parametrize("clase, atributo, accion", [
    (sa.PestanaAtenciones, "fecha", "_registrar"),
    (sl.PestanaEmpaquetado, "fecha", "_empaquetar"),
    (sl.PestanaEnvio, "salida", "_despachar"),
    (sl.PestanaEnvio, "f_recepcion", "_recibir"),
    (sl.PestanaResultados, "fecha", "_registrar"),
])
def test_rechazo_no_reinicia_fecha_ingresada(ui, clase, atributo, accion):
    app, _ = ui
    p = pestana(app, clase)
    control = getattr(p, atributo)
    control.value = control.data = "03/11/2026 09:15"
    getattr(p, accion)()  # faltan selecciones obligatorias
    assert control.value == control.data == "03/11/2026 09:15"
