"""Aviso de vacunación por fecha de atención, sin impedir ningún tipo de atención."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from test_pantallas import elegir, pestana, ui
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa
from veterinaria.servicios.fachada import Servicios


@pytest.fixture
def base(ui):
    app, pag = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    srv.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-1")
    vacuna = srv.atencion.crear_vacuna("Antirrábica", "Perro", True)
    srv.atencion.crear_vacuna("Opcional", "Perro", False)
    srv.atencion.crear_vacuna("Felina", "Gato", True)
    p = pestana(app, sa.PestanaAtenciones)
    p.refrescar(); p.mascota.value = str(mascota); elegir(p.vet)
    p.fecha.value, p.motivo.value = "04/11/2026 09:00", "Control"
    return app, pag, p, mascota, vacuna


@pytest.mark.parametrize("tipo", list(TipoAtencion))
@pytest.mark.parametrize("completo", [False, True])
def test_advertencia_no_invalida_formulario_y_permite_todos_los_tipos(base, tipo, completo):
    app, pag, p, mascota, vacuna = base
    if completo:
        app.servicios.atencion.registrar_aplicacion(mascota, vacuna, date(2026, 11, 1), date(2026, 11, 5))
    p.tipo.value = tipo.name
    p.fecha.on_change(SimpleNamespace())
    if completo:
        assert p.estado_vacunas.value == "Vacunas obligatorias al día."
        assert p.estado_vacunas.color == c.ft.Colors.GREEN_700
    else:
        assert "Advertencia" in p.estado_vacunas.value and "04/11/2026" in p.estado_vacunas.value
        assert "Antirrábica" in p.estado_vacunas.value and "Puede registrar la atención" in p.estado_vacunas.value
        assert "Opcional" not in p.estado_vacunas.value and "Felina" not in p.estado_vacunas.value
        assert p.estado_vacunas.color == c.ft.Colors.AMBER_800
    assert p.mascota.error_text is None and p.fecha.error is None
    boton = boton_en(p, "Registrar atención")
    assert not boton.disabled and not p.vista.disabled
    boton.on_click(None)
    assert "Atención registrada" in pag.mensajes[-1]
    nueva = Servicios(app.ruta_bd)
    atenciones = nueva.atencion.listar_atenciones(mascota)
    assert len(atenciones) == 1 and atenciones[0]["tipo"] == tipo.value
    assert atenciones[0]["fecha_hora"] == datetime(2026, 11, 4, 9)
    assert nueva.atencion.vacunas_pendientes(mascota, date(2026, 11, 4)) == ([] if completo else ["Antirrábica"])


def test_guardar_reconsulta_fecha_sin_evento_de_edicion_ni_fecha_actual(base, monkeypatch):
    app, _, p, mascota, vacuna = base
    srv = app.servicios
    srv.atencion.registrar_aplicacion(mascota, vacuna, date(2026, 11, 1), date(2026, 11, 5))
    p.fecha.on_change(SimpleNamespace())
    assert p.estado_vacunas.value == "Vacunas obligatorias al día."
    p.fecha.value = "05/11/2026 10:45"  # sin evento: el guardado debe revisar esta fecha
    original = srv.atencion.registrar_atencion
    def registrar(*args):
        assert "05/11/2026" in p.estado_vacunas.value and "Antirrábica" in p.estado_vacunas.value
        assert "Puede registrar" in p.estado_vacunas.value
        assert args[2] == datetime(2026, 11, 5, 10, 45)
        return original(*args)
    monkeypatch.setattr(srv.atencion, "registrar_atencion", registrar)
    boton_en(p, "Registrar atención").on_click(None)
    assert srv.atencion.listar_atenciones(mascota)[0]["fecha_hora"] == datetime(2026, 11, 5, 10, 45)


def test_advertencia_no_oculta_error_real_y_conserva_texto_profesional(base):
    app, pag, p, mascota, _ = base
    p.motivo.value = ""
    p.observaciones.value = "Observación <literal>\n& segunda línea"
    boton_en(p, "Registrar atención").on_click(None)
    assert p.motivo.error and "obligatorio" in pag.mensajes[-1]
    assert "Puede registrar" in p.estado_vacunas.value
    assert p.observaciones.value == "Observación <literal>\n& segunda línea"
    assert app.servicios.atencion.listar_atenciones(mascota) == []
    p.motivo.value = "Urgencia"; p.tipo.value = "URGENCIA"
    boton_en(p, "Registrar atención").on_click(None)
    assert len(Servicios(app.ruta_bd).atencion.listar_atenciones(mascota)) == 1
