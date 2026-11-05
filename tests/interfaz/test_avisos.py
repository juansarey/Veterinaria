"""Notificaciones arriba a la derecha: una a la vez, con cierre manual y automático."""

import flet as ft

from test_pantallas import ui  # noqa: F401  (fixture)


def _avisos(pag):
    return [x for x in pag.overlay if isinstance(getattr(x, "data", None), str)]


def test_aviso_arriba_a_la_derecha_y_reemplaza_al_anterior(ui):  # noqa: F811
    app, pag = ui
    app.ok("Primero")
    app.error("Segundo")
    avisos = _avisos(pag)
    assert len(avisos) == 1
    aviso = avisos[0]
    assert (aviso.top, aviso.right, aviso.bottom, aviso.left) == (20, 20, None, None)
    assert aviso.bgcolor == ft.Colors.RED_700
    assert pag.mensajes[-2:] == ["Primero", "Segundo"]


def test_aviso_se_cierra_con_su_boton_y_con_el_temporizador(ui, monkeypatch):  # noqa: F811
    app, pag = ui
    app.ok("Guardado")
    cerrar = _avisos(pag)[0].content.controls[-1]
    cerrar.on_click(None)
    assert _avisos(pag) == []

    temporizadores = []

    class TimerInmediato:
        def __init__(self, segundos, funcion):
            temporizadores.append(segundos)
            self.funcion = funcion
        def start(self):
            self.funcion()
    monkeypatch.setattr("veterinaria.interfaz.app.Timer", TimerInmediato)
    app.error("Falló")
    assert temporizadores == [10.0] and _avisos(pag) == []
    app.ok("Listo")
    assert temporizadores[-1] == 4.5
