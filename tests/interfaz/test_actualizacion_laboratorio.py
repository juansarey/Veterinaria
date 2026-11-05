"""Seguimiento sin filas fantasma, recarga entre pestañas y envíos rechazados por precinto roto."""

from datetime import datetime, timedelta

import pytest

from test_fechas_interfaz import reloj  # noqa: F401  (fixture)
from test_pantallas import pestana, ui  # noqa: F401  (fixture)
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import seccion_laboratorio as sl

INICIO = datetime(2026, 11, 4, 9)


@pytest.fixture
def circuito(ui, reloj):  # noqa: F811
    reloj["ahora"] = INICIO + timedelta(hours=5)
    app, _ = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, INICIO, TipoAtencion.CONSULTA, "Control")
    lab = srv.laboratorio
    muestra = lab.derivar(atencion, "Hemograma", "Sangre", INICIO)["id_muestra"]
    cons = lab.crear_conservadora("C-1")
    remito = lab.empaquetar(clinica, cons, [muestra], "P-1", INICIO + timedelta(minutes=15))["id_remito"]
    envio = lab.despachar_remito(remito, INICIO + timedelta(minutes=30))
    app.ir_a(3)
    return app, muestra, envio


def _celdas(tabla, clave, columnas):
    indice = [k for k, _ in columnas].index(clave)
    return [r.cells[indice].content for r in tabla.rows]


def _texto(control):
    return control.value if hasattr(control, "value") else control.content.value


def test_recepcion_con_precinto_roto_muestra_rechazado_y_actualiza_seguimiento(circuito):
    app, muestra, envio = circuito
    env, seg = pestana(app, sl.PestanaEnvio), pestana(app, sl.PestanaSeguimiento)
    emp = pestana(app, sl.PestanaEmpaquetado)
    assert [_texto(x) for x in _celdas(seg.tabla, "estado", seg.COLS)] == ["En tránsito"]

    env.envio.value = str(envio)
    env.integro.value = "Precinto roto"
    env.f_recepcion.value = (INICIO + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M")
    env._recibir()

    assert [_texto(x) for x in _celdas(env.tabla, "estado", env.COLS)] == ["Rechazado"]
    assert [_texto(x) for x in _celdas(emp.tabla, "estado", emp.COLS)] == ["Rechazado"]
    # Seguimiento se recarga sin cambiar de pestaña y la muestra figura una sola vez.
    assert [_texto(x) for x in _celdas(seg.tabla, "id_txt", seg.COLS)] == [f"M-{muestra:04d}"]
    assert [_texto(x) for x in _celdas(seg.tabla, "estado", seg.COLS)] == ["Rechazada"]


def test_recepcion_con_precinto_intacto_muestra_recibido(circuito):
    app, _, envio = circuito
    env = pestana(app, sl.PestanaEnvio)
    env.envio.value = str(envio)
    env.integro.value = "Precinto intacto"
    env.f_recepcion.value = (INICIO + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M")
    env._recibir()
    assert [_texto(x) for x in _celdas(env.tabla, "estado", env.COLS)] == ["Recibido"]


def _patch_tabla(tabla, inicial=False):
    """Operaciones que Flet enviaría a la ventana para esta tabla (mismo cálculo que page.update)."""
    import msgpack
    from flet.controls.base_control import BaseControl
    from flet.controls.object_patch import ObjectPatch
    from flet.messaging.protocol import configure_encode_object_for_msgpack
    patch = ObjectPatch.from_diff(None if inicial else tabla, tabla, control_cls=BaseControl)[0]
    datos = msgpack.packb(patch.to_message(), default=configure_encode_object_for_msgpack(BaseControl))
    return msgpack.unpackb(datos, strict_map_key=False, ext_hook=lambda codigo, d: d)


def test_cambio_de_estado_no_reemplaza_filas_enteras(circuito):
    """Reemplazar una fila completa dejaba en la ventana la fila vieja duplicada al final."""
    app, muestra, envio = circuito
    env, seg = pestana(app, sl.PestanaEnvio), pestana(app, sl.PestanaSeguimiento)
    claves = [r.key for r in seg.tabla.rows]
    assert len(set(claves)) == len(claves)
    _patch_tabla(seg.tabla, inicial=True)          # lo que la ventana ya muestra

    env.envio.value = str(envio)
    env.integro.value = "Precinto intacto"
    env.f_recepcion.value = (INICIO + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M")
    env._recibir()

    assert [r.key for r in seg.tabla.rows] == claves
    operaciones = _patch_tabla(seg.tabla)[1:]
    assert operaciones, "el cambio de estado debe llegar a la ventana"
    filas_enteras = [op for op in operaciones
                     if isinstance(op[-1], dict) and op[-1].get("_c") == "DataRow"]
    assert filas_enteras == []


def test_las_claves_de_fila_son_unicas_aunque_se_repita_el_id(ui):  # noqa: F811
    from veterinaria.interfaz import componentes as c
    app, _ = ui
    tabla = c.crear_tabla([("id", "Id")])
    c.llenar_tabla(tabla, [("id", "Id")], [{"id": 1}, {"id": 1}, {}])
    claves = [r.key for r in tabla.rows]
    assert len(set(claves)) == 3


class VentanaSimulada:
    """Página que aplica, como la ventana real, los patches que Flet calcula en cada update."""

    def __init__(self):
        from types import SimpleNamespace
        import flet as ft
        self.window = SimpleNamespace(width=0, height=0)
        self.raiz = ft.Column()
        self.overlay = []
        self.doc = None
        self.title = self.theme = self.padding = self.bgcolor = None

    def add(self, *controles): self.raiz.controls.extend(controles)
    def show_dialog(self, dialogo): pass
    def pop_dialog(self): pass

    @staticmethod
    def _ida_y_vuelta(valor):
        import msgpack
        from flet.controls.base_control import BaseControl
        from flet.messaging.protocol import configure_encode_object_for_msgpack
        datos = msgpack.packb(valor, default=configure_encode_object_for_msgpack(BaseControl))
        return msgpack.unpackb(datos, strict_map_key=False, ext_hook=lambda codigo, d: d)

    def update(self, *a):
        from flet.controls.base_control import BaseControl
        from flet.controls.object_patch import ObjectPatch
        if self.doc is None:
            self.doc = self._ida_y_vuelta(self.raiz)
            return
        mensaje = self._ida_y_vuelta(ObjectPatch.from_diff(self.raiz, self.raiz, control_cls=BaseControl)[0]
                                     .to_message())
        rutas = {}

        def recorrer(nodo, ruta):
            rutas[nodo[0]] = ruta
            for clave, sub in (nodo[1] if len(nodo) > 1 else {}).items():
                recorrer(sub, ruta + [clave])
        recorrer(mensaje[0], [])
        for op in mensaje[1:]:
            assert op[0] in (0, 1, 2), "operación move no simulada"
            *camino, clave = rutas[op[1]] + [op[2]]
            padre = self.doc
            for parte in camino:
                padre = padre[parte]
            if op[0] == 0:
                padre[clave] = op[3]
            elif op[0] == 1 and isinstance(padre, list):
                padre.insert(clave, op[3])
            elif op[0] == 1:
                padre[clave] = op[3]
            elif isinstance(padre, list):
                del padre[clave]
            else:
                padre.pop(clave, None)

    def filas_en_ventana(self, tabla):
        pendientes = [self.doc]
        while pendientes:
            nodo = pendientes.pop()
            if isinstance(nodo, dict):
                if nodo.get("_i") == tabla._i:
                    return [r["cells"][0]["content"]["value"] for r in nodo.get("rows", [])]
                pendientes.extend(nodo.values())
            elif isinstance(nodo, list):
                pendientes.extend(nodo)
        raise LookupError("tabla no montada")


def test_muestra_derivada_fuera_de_laboratorio_aparece_una_sola_vez_en_la_ventana(tmp_path, monkeypatch, reloj):  # noqa: F811
    """Derivar en Atención, volver a Laboratorio y empaquetar no deja filas duplicadas en la ventana."""
    from veterinaria.interfaz.app import AplicacionVeterinaria
    from veterinaria.servicios.fachada import Servicios
    reloj["ahora"] = INICIO + timedelta(hours=5)
    monkeypatch.setattr("veterinaria.interfaz.app.webbrowser.open", lambda *a, **k: True)
    ventana = VentanaSimulada()
    app = AplicacionVeterinaria(ventana, Servicios(tmp_path / "v.db"), tmp_path / "v.db")
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, INICIO, TipoAtencion.CONSULTA, "Control")
    srv.laboratorio.derivar(atencion, "Previo", "Sangre", INICIO)
    app.iniciar()
    seg, emp = pestana(app, sl.PestanaSeguimiento), pestana(app, sl.PestanaEmpaquetado)

    def comprobar():
        assert ventana.filas_en_ventana(seg.tabla) == [r.cells[0].content.value for r in seg.tabla.rows]

    app.ir_a(3)
    comprobar()
    app.ir_a(2)
    srv.laboratorio.derivar(atencion, "Nueva", "Orina", INICIO + timedelta(minutes=5))
    app.ir_a(3)
    comprobar()
    assert len(seg.tabla.rows) == 2
    emp.clinica.value = str(clinica)
    emp._al_elegir_clinica()
    emp.conservadora.value = str(srv.laboratorio.crear_conservadora("C-1"))
    emp.fecha.value = (INICIO + timedelta(minutes=30)).strftime("%d/%m/%Y %H:%M")
    emp._empaquetar()
    comprobar()
    assert len(ventana.filas_en_ventana(seg.tabla)) == 2
