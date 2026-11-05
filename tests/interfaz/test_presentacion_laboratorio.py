"""Layout de Laboratorio con estados reales y SQLite temporal, sin alterar sus flujos."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from test_fechas_interfaz import reloj
from test_pantallas import pestana, ui
from test_scroll_contenido import comprobar_flujo, recorrer
from test_usabilidad_flet import boton_en
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_laboratorio as sl

CLASES = [sl.PestanaEmpaquetado, sl.PestanaEnvio, sl.PestanaResultados, sl.PestanaSeguimiento]
INICIO = datetime(2026, 11, 4, 9)


@pytest.fixture
def laboratorio(ui, reloj):
    reloj["ahora"] = INICIO + timedelta(hours=5)
    app, pag = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "00123")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    atencion = srv.atencion.registrar_atencion(mascota, vet, INICIO, TipoAtencion.CONSULTA, "Control")
    lab = srv.laboratorio
    estados = {}
    for indice, estado in enumerate(("EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "RECHAZADA", "ANALIZADA")):
        muestra = lab.derivar(atencion, f"Estudio {estado}", "Sangre", INICIO)["id_muestra"]
        datos = {"muestra": muestra}
        if estado != "EXTRAIDA":
            cons = lab.crear_conservadora(f"C-{indice}")
            datos["remito"] = lab.empaquetar(clinica, cons, [muestra], f"P-{indice}",
                                             INICIO + timedelta(minutes=15))["id_remito"]
            if estado != "EMPAQUETADA":
                datos["envio"] = lab.despachar_remito(datos["remito"], INICIO + timedelta(minutes=30))
                if estado != "EN_TRANSITO":
                    lab.recibir_remito(datos["envio"], estado != "RECHAZADA", INICIO + timedelta(hours=1))
                    if estado == "ANALIZADA":
                        lab.registrar_resultado(muestra, "Resultado previo", fecha_resultado=INICIO + timedelta(hours=2))
        estados[estado] = datos
    libre = lab.crear_conservadora("Libre")
    for clase in CLASES:
        pestana(app, clase).refrescar()
    emp, env, res = (pestana(app, clase) for clase in CLASES[:3])
    emp.clinica.value, emp.conservadora.value = str(clinica), str(libre)
    emp._al_elegir_clinica()
    env.remito.value = str(estados["EMPAQUETADA"]["remito"])
    env.envio.value = str(estados["EN_TRANSITO"]["envio"])
    res.muestra.value = str(estados["RECIBIDA"]["muestra"])
    res._al_elegir_muestra()
    return app, pag, estados


def redimensionar(p, ancho):
    if isinstance(p, sl.PestanaEnvio):
        paneles = p.vista.controls[0]
        paneles.on_size_change(SimpleNamespace(width=ancho))
        esperado = (ancho - 14) / 2 if ancho >= 1120 else ancho
        for tarjeta in paneles.controls:
            assert 0 <= esperado - tarjeta.width < 0.02
            assert tarjeta.expand is None and tarjeta.height is None
        bloques = [(tarjeta, tarjeta.width - 34) for tarjeta in paneles.controls]
        bloques.append((p.vista.controls[1], ancho))
    else:
        bloques = [(p.vista, ancho)]
    for bloque, util in bloques:
        for control, _ in recorrer(bloque):
            evento = getattr(control, "on_size_change", None)
            if evento:
                evento(SimpleNamespace(width=util))
                if isinstance(control, c.ft.Row):
                    assert all(campo.width <= util and campo.height is None for campo in control.controls)
                    assert len({campo.width for campo in control.controls}) == 1
                    for campo in control.controls:
                        if isinstance(campo, c.ft.Dropdown):
                            assert campo.expanded_insets == c.ft.Padding.all(0)
                evento(SimpleNamespace(width=0))
    comprobar_flujo(p.vista)


@pytest.mark.parametrize("clase", CLASES)
@pytest.mark.parametrize("ancho", [1138, 1119.99, 380])
def test_redimensionar_conserva_entradas_errores_estados_y_muestras(laboratorio, monkeypatch, clase, ancho):
    app, _, _ = laboratorio
    p = pestana(app, clase)
    texto = "Primera línea <literal> &\nSegunda\nTercera\nCuarta\nQuinta"
    if clase is sl.PestanaEmpaquetado:
        p.codigo_cons.value, p.precinto.value = "Pendiente", "Precinto pendiente"
        p.fecha.value = "04/11/2026 13:00"
        for check in p.checks.values():
            check.value = False
        error = p.fecha
    elif clase is sl.PestanaEnvio:
        p.integro.value = "Precinto roto"
        p.obs_envio.value = p.obs_rec.value = texto
        p.salida.value, p.f_recepcion.value = "04/11/2026 13:00", "04/11/2026 13:15"
        error = p.f_recepcion
    elif clase is sl.PestanaResultados:
        p.resultado.value = p.obs.value = texto
        p.fecha.value = "04/11/2026 13:30"
        error = p.fecha
    else:
        p.filtro.value = "EN_TRANSITO"
        p._filtrar()
        error = p.filtro
    c.establecer_error(error, "Conservar este error completo de validación.")
    campos = [control for control, _ in recorrer(p.vista)
              if isinstance(control, (c.ft.TextField, c.ft.Dropdown, c.ft.Checkbox))]
    valores = [(control.value, control.disabled) for control in campos]
    eventos = [(getattr(control, "on_change", None), getattr(control, "on_select", None)) for control in campos]
    filas = p.tabla.rows
    if clase is sl.PestanaResultados:
        aviso, deshabilitado = p.aviso_muestra.value, p.btn_registrar.disabled
    monkeypatch.setattr(p, "refrescar", lambda: pytest.fail("No refrescar por layout"))
    for nombre in ("listar_muestras", "listar_remitos", "listar_envios", "listar_resultados", "listar_conservadoras"):
        monkeypatch.setattr(p.srv.laboratorio, nombre, lambda *a, **k: pytest.fail("Consulta al redimensionar"))
    redimensionar(p, ancho)
    redimensionar(p, 1138)
    assert [(control.value, control.disabled) for control in campos] == valores
    assert [(getattr(control, "on_change", None), getattr(control, "on_select", None)) for control in campos] == eventos
    assert p.tabla.rows is filas
    assert (error.error if isinstance(error, c.ft.TextField) else error.error_text) == "Conservar este error completo de validación."
    if clase is sl.PestanaEmpaquetado:
        assert p.checks and not any(check.value for check in p.checks.values())
    if clase is sl.PestanaResultados:
        assert (p.aviso_muestra.value, p.btn_registrar.disabled) == (aviso, deshabilitado)


@pytest.mark.parametrize("clase, minimo", [(sl.PestanaEmpaquetado, 1200), (sl.PestanaEnvio, 1100),
                                         (sl.PestanaResultados, 1300), (sl.PestanaSeguimiento, 1400)])
def test_tablas_adaptables_conservan_filas_columnas_y_acciones(laboratorio, clase, minimo):
    app, _, _ = laboratorio
    p = pestana(app, clase)
    filas, columnas = p.tabla.rows, p.tabla.columns
    assert filas
    for ancho in (380, 1200, 1700):
        p.tabla.data.on_size_change(SimpleNamespace(width=ancho))
        assert p.tabla.width == max(minimo, ancho)
        assert p.tabla.rows is filas and p.tabla.columns is columnas
        assert p.tabla.data.content.scroll == c.ft.ScrollMode.AUTO and p.tabla.data.height is None
        if clase is not sl.PestanaEnvio:
            esperado = {sl.PestanaEmpaquetado: "Liberar la conservadora (ya recibida)",
                        sl.PestanaResultados: "Comprobante de resultados (PDF)",
                        sl.PestanaSeguimiento: "Ver cadena de custodia"}[clase]
            assert all(fila.cells[-1].content.controls[0].tooltip == esperado for fila in filas)
        comprobar_flujo(p.vista)


@pytest.mark.parametrize("precinto, estado", [("Precinto intacto", "RECIBIDA"), ("Precinto roto", "RECHAZADA")])
def test_recepcion_mantiene_eleccion_obligatoria_y_transicion_al_apilar(laboratorio, monkeypatch, precinto, estado):
    app, _, estados = laboratorio
    p = pestana(app, sl.PestanaEnvio)
    p.f_recepcion.value = "04/11/2026 13:00"
    p.obs_rec.value = "Observación <literal>\n& segunda línea"
    original = p.srv.laboratorio.recibir_remito
    llamadas = []

    def recibir(*args):
        llamadas.append(args)
        return original(*args)

    monkeypatch.setattr(p.srv.laboratorio, "recibir_remito", recibir)
    redimensionar(p, 380)
    boton_en(p, "Registrar recepción").on_click(None)
    assert not llamadas and p.integro.error_text and p.integro.value is None
    p.integro.value = precinto
    redimensionar(p, 1138)
    boton_en(p, "Registrar recepción").on_click(None)
    assert len(llamadas) == 1 and llamadas[0][1] is (precinto == "Precinto intacto")
    assert p.srv.laboratorio.historial_muestra(estados["EN_TRANSITO"]["muestra"])[-1]["estado"] == estado
    assert p.integro.value is None and p.obs_rec.value == ""


@pytest.mark.parametrize("estado, deshabilitado", [("RECIBIDA", False), ("RECHAZADA", True)])
def test_resultados_conserva_disponibilidad_segun_estado_al_redimensionar(laboratorio, monkeypatch, estado, deshabilitado):
    app, _, estados = laboratorio
    p = pestana(app, sl.PestanaResultados)
    p.muestra.value = str(estados[estado]["muestra"])
    p.muestra.on_select(SimpleNamespace())
    p.resultado.value = "Texto del análisis\n< & >"
    aviso = p.aviso_muestra.value
    for ancho in (380, 1138, 680):
        redimensionar(p, ancho)
        assert p.btn_registrar.disabled is deshabilitado and p.aviso_muestra.value == aviso
        assert p.resultado.value == "Texto del análisis\n< & >"
    if deshabilitado:
        monkeypatch.setattr(p.srv.laboratorio, "registrar_resultado", lambda *a: pytest.fail("No analizar una rechazada"))
        p.btn_registrar.on_click(None)
        assert p.srv.laboratorio.obtener_resultado(estados[estado]["muestra"]) is None


def test_etiquetas_largas_de_muestras_se_ajustan_sin_perder_texto_ni_seleccion(laboratorio):
    app, _, _ = laboratorio
    p = pestana(app, sl.PestanaEmpaquetado)
    estudio = ("Estudio complementario " * 8).strip()
    atencion = p.srv.atencion.listar_atenciones()[0]["id"]
    muestra = p.srv.laboratorio.derivar(atencion, estudio, "Sangre", INICIO)["id_muestra"]
    p.refrescar()
    for check in p.checks.values():
        check.value = False
    for ancho in (380, 1138, 380):
        p.muestras_box.on_size_change(SimpleNamespace(width=ancho))
        etiqueta = p.checks[muestra].label
        assert isinstance(etiqueta, c.ft.Text)
        assert estudio in etiqueta.value and f"M-{muestra:04d}" in etiqueta.value
        assert not etiqueta.no_wrap and etiqueta.max_lines is None and etiqueta.height is None
        assert etiqueta.width <= ancho - 56
        assert not any(check.value for check in p.checks.values())
        p.refrescar()
    assert not any(check.value for check in p.checks.values())
