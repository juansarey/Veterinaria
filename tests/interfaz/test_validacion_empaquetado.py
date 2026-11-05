"""Validaciones independientes de alta de conservadoras y empaquetado en Flet."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_fechas_interfaz import reloj
from test_pantallas import pestana, ui
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz.seccion_laboratorio import PestanaEmpaquetado


@pytest.fixture
def empaquetado(ui, reloj, monkeypatch):
    reloj["ahora"] = datetime(2026, 11, 4, 12)
    app, pagina = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(
        mascota, vet, datetime(2026, 11, 4, 9), TipoAtencion.CONSULTA, "Control")
    srv.laboratorio.derivar(atencion, "Hemograma", "Sangre", datetime(2026, 11, 4, 9, 30))
    conservadora = srv.laboratorio.crear_conservadora("CONS-004")
    p = pestana(app, PestanaEmpaquetado)
    p.refrescar()
    p.clinica.value, p.conservadora.value = str(clinica), str(conservadora)
    p._al_elegir_clinica()
    p.fecha.value = "04/11/2026 10:00"
    p.precinto.value = "PRE-1"
    for nombre in ("crear_conservadora", "empaquetar"):
        monkeypatch.setattr(srv.laboratorio, nombre, Mock(wraps=getattr(srv.laboratorio, nombre)))
    return app, pagina, p


@pytest.mark.parametrize("codigo", ["", "   ", "C" * 51, "CONS-004"])
def test_empaquetar_con_existente_no_valida_ni_crea_una_conservadora(empaquetado, codigo):
    app, pagina, p = empaquetado
    lab = app.servicios.laboratorio
    p.codigo_cons.value = codigo

    boton_en(p, "Empaquetar y precintar").on_click(None)

    lab.crear_conservadora.assert_not_called()
    lab.empaquetar.assert_called_once()
    assert p.codigo_cons.value == codigo and p.codigo_cons.error is None
    assert pagina.dialogos[-1] == "Remito R-0001 emitido"
    assert lab.listar_muestras()[0]["estado"] == "EMPAQUETADA"
    assert lab.listar_conservadoras()[0]["estado"] == "EN_USO"
    assert lab.listar_remitos()[0]["precinto"] == "PRE-1 (INTACTO)"


def test_agregar_sin_codigo_muestra_su_error_y_reintentar_no_lo_oculta(empaquetado):
    app, pagina, p = empaquetado
    lab = app.servicios.laboratorio

    for _ in range(2):
        boton_en(p, "Agregar conservadora").on_click(None)
        assert p.codigo_cons.error == "El campo «Código» es obligatorio."
        assert pagina.mensajes[-1] == p.codigo_cons.error

    lab.empaquetar.assert_not_called()
    assert lab.crear_conservadora.call_count == 2
    assert len(lab.listar_conservadoras()) == 1 and lab.listar_remitos() == []
    assert lab.listar_muestras()[0]["estado"] == "EXTRAIDA"


@pytest.mark.parametrize("codigo", ["", "CONS-004"])
def test_error_previo_de_agregar_no_contamina_el_empaquetado(empaquetado, codigo):
    app, pagina, p = empaquetado
    lab = app.servicios.laboratorio
    p.codigo_cons.value = codigo
    boton_en(p, "Agregar conservadora").on_click(None)
    assert p.codigo_cons.error
    assert lab.listar_remitos() == []

    boton_en(p, "Empaquetar y precintar").on_click(None)

    assert p.codigo_cons.error is None and p.codigo_cons.value == codigo
    p.codigo_cons.on_blur(SimpleNamespace())
    assert p.codigo_cons.error is None
    lab.crear_conservadora.assert_called_once_with(codigo)
    lab.empaquetar.assert_called_once()
    assert pagina.dialogos[-1] == "Remito R-0001 emitido"
    assert lab.listar_muestras()[0]["estado"] == "EMPAQUETADA"


@pytest.mark.parametrize("evento", ["on_change", "on_blur"])
def test_corregir_codigo_limpia_error_y_agrega_sin_alterar_empaquetado(empaquetado, evento):
    app, _, p = empaquetado
    lab = app.servicios.laboratorio
    valores = (p.clinica.value, p.conservadora.value, p.fecha.value, p.precinto.value)
    boton_en(p, "Agregar conservadora").on_click(None)
    assert p.codigo_cons.error

    p.codigo_cons.value = "CONS-005"
    getattr(p.codigo_cons, evento)(SimpleNamespace())
    assert p.codigo_cons.error is None
    boton_en(p, "Agregar conservadora").on_click(None)

    assert p.codigo_cons.error is None and p.codigo_cons.value == ""
    assert (p.clinica.value, p.conservadora.value, p.fecha.value, p.precinto.value) == valores
    assert [c["codigo"] for c in lab.listar_conservadoras()] == ["CONS-004", "CONS-005"]
    assert all(c["estado"] == "DISPONIBLE" for c in lab.listar_conservadoras())
    lab.empaquetar.assert_not_called()
    assert lab.listar_remitos() == [] and lab.listar_muestras()[0]["estado"] == "EXTRAIDA"


def test_alta_conserva_duplicados_longitud_y_recuperacion_al_corregir(empaquetado):
    app, _, p = empaquetado
    lab = app.servicios.laboratorio
    for codigo, mensaje in [("CONS-004", "Ya existe"), ("C" * 51, "máximo 50")]:
        p.codigo_cons.value = codigo
        boton_en(p, "Agregar conservadora").on_click(None)
        assert mensaje in p.codigo_cons.error
        assert p.codigo_cons.value == codigo and len(lab.listar_conservadoras()) == 1

    p.codigo_cons.value = "  CONS-005  "
    boton_en(p, "Agregar conservadora").on_click(None)

    assert p.codigo_cons.error is None and p.codigo_cons.value == ""
    assert [c["codigo"] for c in lab.listar_conservadoras()] == ["CONS-004", "CONS-005"]
    lab.empaquetar.assert_not_called()


@pytest.mark.parametrize("campo, valor", [
    ("clinica", None),
    ("conservadora", None),
    ("fecha", "04/11/2026 09:00"),
    ("precinto", "P" * 51),
])
def test_error_de_empaquetar_no_contamina_alta_y_se_revalida_al_reintentar(empaquetado, campo, valor):
    app, _, p = empaquetado
    lab = app.servicios.laboratorio
    control = getattr(p, campo)
    original = control.value
    control.value = valor
    error = lambda: control.error if campo in ("fecha", "precinto") else control.error_text
    boton_en(p, "Empaquetar y precintar").on_click(None)
    assert error()
    assert p.codigo_cons.error is None
    assert lab.listar_remitos() == [] and lab.listar_muestras()[0]["estado"] == "EXTRAIDA"

    p.codigo_cons.value = "CONS-005"
    boton_en(p, "Agregar conservadora").on_click(None)

    assert error() is None and control.value == valor
    assert p.codigo_cons.error is None and p.codigo_cons.value == ""
    assert len(lab.listar_conservadoras()) == 2
    assert lab.listar_remitos() == [] and lab.listar_muestras()[0]["estado"] == "EXTRAIDA"
    boton_en(p, "Empaquetar y precintar").on_click(None)
    assert error() and p.codigo_cons.error is None

    control.value = original
    boton_en(p, "Empaquetar y precintar").on_click(None)
    assert error() is None and lab.listar_muestras()[0]["estado"] == "EMPAQUETADA"
