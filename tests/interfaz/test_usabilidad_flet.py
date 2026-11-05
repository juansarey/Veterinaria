"""Regresiones de la Etapa 4 con página simulada, archivos y SQLite temporales."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html import escape
from threading import Event
from types import SimpleNamespace

import pytest

from test_pantallas import _hijos, elegir, pestana, ui
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import componentes as c
from veterinaria.interfaz import seccion_atencion as sa, seccion_laboratorio as sl
from veterinaria.interfaz import seccion_personas as sp, seccion_reportes as sr, seccion_turnos as st
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.servicios import exportador
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios

FECHA = datetime(2026, 11, 4, 9)


@pytest.fixture
def envio(ui):
    app, pag = ui
    srv = app.servicios
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(cl, "Ana", "Pérez", "MP-1")
    cliente = srv.clinica.crear_cliente("Luis", "Gómez", "00123")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    at = srv.atencion.registrar_atencion(mascota, vet, FECHA, TipoAtencion.CONSULTA, "Control")
    muestra = srv.laboratorio.derivar(at, "Hemograma", "Sangre", FECHA)["id_muestra"]
    cons = srv.laboratorio.crear_conservadora("C-1")
    remito = srv.laboratorio.empaquetar(cl, cons, [muestra], "P-1", FECHA)["id_remito"]
    id_envio = srv.laboratorio.despachar_remito(remito, FECHA + timedelta(hours=1))
    p = pestana(app, sl.PestanaEnvio)
    p.refrescar()
    p.envio.value = str(id_envio)
    p.f_recepcion.value = "04/11/2026 11:00"
    return app, pag, p, muestra, id_envio


def boton_en(p, texto):
    def buscar(control):
        if isinstance(control, (c.ft.FilledButton, c.ft.OutlinedButton)) and control.content == texto:
            return control
        for hijo in _hijos(control):
            encontrado = buscar(hijo)
            if encontrado is not None:
                return encontrado
    encontrado = buscar(p.vista)
    assert encontrado is not None, texto
    return encontrado


@pytest.mark.parametrize("valor", [None, "", True, False, "INTACTO", "otro"])
def test_precinto_requiere_opcion_explicita_antes_de_invocar_servicio(envio, monkeypatch, valor):
    app, pag, p, muestra, _ = envio
    assert isinstance(p.integro, c.ft.Dropdown) and p.integro.value is None
    assert not p.integro.editable and not p.integro.enable_filter
    assert [o.key for o in p.integro.options] == ["Precinto intacto", "Precinto roto"]
    p.integro.value = valor
    p.obs_rec.value = "No perder\nobservación < & >"
    monkeypatch.setattr(app.servicios.laboratorio, "recibir_remito",
                        lambda *a: pytest.fail("No debe invocarse recepción sin una opción válida"))
    boton_en(p, "Registrar recepción").on_click(None)
    assert "intacto o roto" in p.integro.error_text
    assert pag.mensajes[-1] == p.integro.error_text
    assert p.integro.value == valor and p.obs_rec.value.startswith("No perder\n")
    assert p.f_recepcion.value == "04/11/2026 11:00"
    assert not p.vista.disabled
    con = abrir_conexion(app.ruta_bd)
    try:
        assert con.execute("SELECT COUNT(*) FROM recepcion").fetchone()[0] == 0
    finally:
        con.close()
    assert Servicios(app.ruta_bd).laboratorio.historial_muestra(muestra)[-1]["estado"] == "EN_TRANSITO"


@pytest.mark.parametrize("opcion, booleano, estado", [
    ("Precinto intacto", True, "RECIBIDA"), ("Precinto roto", False, "RECHAZADA"),
])
def test_recepcion_persiste_estado_y_reinicia_solo_tras_exito(envio, monkeypatch, opcion, booleano, estado):
    app, pag, p, muestra, _ = envio
    original = app.servicios.laboratorio.recibir_remito
    llamadas = []

    def recibir(identificador, intacto, *args):
        assert intacto is booleano  # no bool() aplicado a cadenas
        llamadas.append(identificador)
        return original(identificador, intacto, *args)

    monkeypatch.setattr(app.servicios.laboratorio, "recibir_remito", recibir)
    p._recibir()
    assert p.integro.error_text
    p.integro.value = opcion
    p.integro.on_select(SimpleNamespace())
    assert p.integro.error_text is None
    boton_en(p, "Registrar recepción").on_click(None)
    assert len(llamadas) == 1 and p.integro.value is None and p.integro.error_text is None
    assert not p.vista.disabled
    nuevo = Servicios(app.ruta_bd)
    assert nuevo.laboratorio.historial_muestra(muestra)[-1]["estado"] == estado
    assert nuevo.laboratorio.listar_envios()[0]["recibido"]
    assert pag.dialogos[-1] == ("Remito aceptado" if booleano else "Remito RECHAZADO")


@pytest.mark.parametrize("opcion", ["Precinto intacto", "Precinto roto"])
def test_error_recepcion_conserva_seleccion_y_permite_corregir(envio, opcion):
    app, _, p, muestra, _ = envio
    p.integro.value = opcion
    p.obs_rec.value = "Observación\n<literal> & más"
    p.f_recepcion.value = "04/11/2026 08:00"  # anterior a la salida
    boton = boton_en(p, "Registrar recepción")
    boton.on_click(None)
    assert p.integro.value == opcion and p.obs_rec.value == "Observación\n<literal> & más"
    p.refrescar()
    assert p.integro.value == opcion and p.f_recepcion.value == "04/11/2026 08:00"
    assert not p.vista.disabled
    assert Servicios(app.ruta_bd).laboratorio.historial_muestra(muestra)[-1]["estado"] == "EN_TRANSITO"
    p.f_recepcion.value = "04/11/2026 11:00"
    boton.on_click(None)
    assert p.integro.value is None


@pytest.mark.parametrize("clase, campo", [
    (sa.PestanaAtenciones, "diagnostico"), (sa.PestanaAtenciones, "observaciones"),
    (sa.PestanaAtenciones, "obs_orden"), (sl.PestanaEnvio, "obs_envio"),
    (sl.PestanaEnvio, "obs_rec"), (sl.PestanaResultados, "obs"),
])
def test_campos_clinicos_multilinea_sin_limite_de_contenido(ui, clase, campo):
    app, _ = ui
    control = getattr(pestana(app, clase), campo)
    assert control.multiline and control.min_lines >= 2 and control.max_lines == 4
    assert control.max_length is None and control.input_filter is None
    texto = "\n".join(f"Línea {n}: <b>sin cerrar & >" for n in range(50))
    control.value = texto
    control.on_change(SimpleNamespace())
    assert control.value == texto


def test_seis_textos_clinicos_se_persisten_y_pdf_preserva_saltos_y_escape(ui, monkeypatch, tmp_path):
    referencia = {"ahora": FECHA}
    monkeypatch.setattr("veterinaria.servicios.laboratorio_servicio.ahora", lambda: referencia["ahora"])
    class Reloj(datetime):
        @classmethod
        def now(cls):
            return FECHA
    monkeypatch.setattr("veterinaria.servicios.atencion_servicio.datetime", Reloj)
    app, _ = ui
    srv = app.servicios
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(cl, "Ana", "Pérez", "MP-1")
    cliente = srv.clinica.crear_cliente("Luis", "Gómez", "00123")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    texto = "\n".join(f"Línea {i}: <b>sin cerrar & >" for i in range(12))
    parrafos = []
    original = exportador.Paragraph

    def capturar(contenido, estilo):
        parrafos.append(contenido)
        return original(contenido, estilo)

    monkeypatch.setattr(exportador, "Paragraph", capturar)
    at = pestana(app, sa.PestanaAtenciones)
    at.refrescar(); at.mascota.value = str(mascota); at.vet.value = str(vet)
    at.fecha.value, at.motivo.value = "04/11/2026 09:00", "Control"
    at.diagnostico.value = at.observaciones.value = texto
    boton_en(at, "Registrar atención").on_click(None)
    at._comprobante(at.atenciones[0])
    elegir(at.atencion)
    at.estudio.value, at.obs_orden.value = "Hemograma", texto
    boton_en(at, "Derivar a laboratorio").on_click(None)
    referencia["ahora"] = FECHA + timedelta(hours=1)  # las operaciones posteriores ya ocurrieron
    cons = srv.laboratorio.crear_conservadora("C-1")
    emp = pestana(app, sl.PestanaEmpaquetado)
    emp.refrescar(); emp.clinica.value = str(cl); emp.conservadora.value = str(cons)
    emp.fecha.value = "04/11/2026 10:00"
    # Reloj controlado: el transporte debe ser posterior a la extracción.
    extraccion = datetime.strptime(srv.laboratorio.listar_muestras()[0]["extraccion"], c.FMT_FECHA_HORA)
    emp.fecha.value = (extraccion + timedelta(minutes=10)).strftime(c.FMT_FECHA_HORA)
    boton_en(emp, "Empaquetar y precintar").on_click(None)
    env = pestana(app, sl.PestanaEnvio)
    env.refrescar(); elegir(env.remito)
    env.salida.value = (extraccion + timedelta(minutes=20)).strftime(c.FMT_FECHA_HORA)
    env.obs_envio.value = texto
    boton_en(env, "Despachar").on_click(None)
    elegir(env.envio); env.integro.value = "Precinto intacto"
    env.f_recepcion.value = (extraccion + timedelta(minutes=30)).strftime(c.FMT_FECHA_HORA)
    env.obs_rec.value = texto
    boton_en(env, "Registrar recepción").on_click(None)
    res = pestana(app, sl.PestanaResultados)
    res.refrescar(); elegir(res.muestra); res.muestra.on_select(SimpleNamespace())
    res.resultado.value = res.obs.value = texto
    res.fecha.value = (extraccion + timedelta(minutes=40)).strftime(c.FMT_FECHA_HORA)
    res.btn_registrar.on_click(None)
    con = abrir_conexion(app.ruta_bd)
    try:
        consultas = ["SELECT diagnostico, observaciones FROM atencion",
                     "SELECT observaciones FROM orden_derivacion_laboratorio",
                     "SELECT observaciones FROM envio", "SELECT observaciones FROM recepcion",
                     "SELECT observaciones, resultado FROM resultado_analisis"]
        assert all(valor == texto for sql in consultas for valor in con.execute(sql).fetchone())
    finally:
        con.close()
    assert Servicios(app.ruta_bd).laboratorio.obtener_resultado(1)["resultado"] == texto
    assert escape(texto).replace("\n", "<br/>") in parrafos
    pdfs = list((tmp_path / "exportaciones").glob("*.pdf"))
    assert len(pdfs) == 2 and all(p.read_bytes().startswith(b"%PDF") for p in pdfs)
    assert res.btn_registrar.disabled  # no volver a registrar la muestra ya analizada


@pytest.mark.parametrize("campo, invalido, incompleto, correcto", [
    ("nombre_f", "Ana2", "Ana3", "María José"),
    ("dni_f", "12x", "12", "00123"),
    ("email_f", "ana@", "ana@.", "ana@correo.com"),
    ("tel_f", "tel?", "+", "+54 (351) 123-456"),
])
def test_error_persiste_hasta_corregir_sin_bloquear_escritura(ui, campo, invalido, incompleto, correcto):
    app, _ = ui
    p = pestana(app, sp.PestanaClientes)
    p.nombre_f.value, p.apellido_f.value, p.dni_f.value = "Ana", "Pérez", "00123"
    control = getattr(p, campo)
    control.value = invalido
    p.btn_guardar.on_click(None)
    assert control.error
    p.btn_guardar.on_click(None)
    assert control.error  # reintentar sin corregir no oculta el error
    control.value = incompleto
    control.on_change(SimpleNamespace())
    assert control.value == incompleto and control.error
    control.value = correcto
    control.on_blur(SimpleNamespace())
    assert control.error is None and control.value == correcto
    p.btn_guardar.on_click(None)
    assert len(app.servicios.clinica.listar_clientes()) == 1
    assert not p.vista.disabled


def test_corregir_otro_campo_no_borra_error_ni_unicidad(ui):
    app, _ = ui
    srv = app.servicios
    srv.clinica.crear_cliente("Luis", "Gómez", "00123")
    p = pestana(app, sp.PestanaClientes)
    p.nombre_f.value, p.apellido_f.value, p.dni_f.value = "Ana", "Pérez", "00123"
    p._guardar()
    assert "Ya existe" in p.dni_f.error
    p.email_f.value = "ana@correo.com"; p.email_f.on_change(SimpleNamespace())
    p.dni_f.on_change(SimpleNamespace())
    assert "Ya existe" in p.dni_f.error
    p._guardar()
    assert "Ya existe" in p.dni_f.error and len(srv.clinica.listar_clientes()) == 1


def test_botones_bloquean_operaciones_simultaneas_y_recuperan_el_formulario(ui, monkeypatch):
    app, _ = ui
    p = pestana(app, sp.PestanaClientes)
    p.nombre_f.value, p.apellido_f.value, p.dni_f.value = "Ana", "Pérez", "00123"
    original = app.servicios.clinica.crear_cliente
    iniciado, continuar = Event(), Event()
    llamadas = []

    def guardar(*args):
        llamadas.append(args)
        iniciado.set()
        assert continuar.wait(5)
        return original(*args)

    monkeypatch.setattr(app.servicios.clinica, "crear_cliente", guardar)
    with ThreadPoolExecutor(max_workers=1) as pool:
        futuro = pool.submit(p.btn_guardar.on_click, None)
        try:
            assert iniciado.wait(5) and p.vista.disabled
            p.btn_guardar.on_click(None)
            p.btn_cancelar.on_click(None)
            otro = c.boton("Otra entrada", p._guardar)
            otro.on_click(None)
            assert len(llamadas) == 1 and p.nombre_f.value == "Ana"
        finally:
            continuar.set()
        futuro.result(timeout=5)
    assert not p.vista.disabled and not p.btn_guardar.disabled
    assert len(app.servicios.clinica.listar_clientes()) == 1


@pytest.mark.parametrize("clase", [sp.PestanaClientes, st.PestanaAgenda, sa.PestanaAtenciones,
                                   sl.PestanaEnvio, sr.SeccionReportes])
def test_guardia_y_finally_funcionan_en_cinco_secciones(ui, clase):
    app, _ = ui
    p = app.pantallas[4] if clase is sr.SeccionReportes else pestana(app, clase)
    llamadas = []
    def fallar(e):
        assert p.vista.disabled
        llamadas.append(1)
        boton.on_click(None)
        raise RuntimeError("Fallo controlado")
    boton = c.boton("Prueba", fallar, grupo=p)
    with pytest.raises(RuntimeError, match="Fallo controlado"):
        boton.on_click(None)
    assert llamadas == [1] and not p.vista.disabled
    # Un botón deshabilitado por su estado no puede disparar su acción.
    boton.disabled = True
    boton.on_click(None)
    assert llamadas == [1] and boton.disabled


def test_n02_bloqueo_cubre_pdf_fallido_sin_repetir_registro_y_permite_reemitir(envio, monkeypatch):
    app, pag, env, muestra, _ = envio
    env.integro.value = "Precinto intacto"; env._recibir()
    p = pestana(app, sl.PestanaResultados)
    p.refrescar(); elegir(p.muestra); p.muestra.on_select(SimpleNamespace())
    p.resultado.value, p.obs.value = "Normal\n<literal> & más", "Control\nen 6 meses"
    p.fecha.value = "04/11/2026 12:00"
    original = app.servicios.laboratorio.registrar_resultado
    registros = []
    def registrar(*args):
        registros.append(args)
        return original(*args)
    monkeypatch.setattr(app.servicios.laboratorio, "registrar_resultado", registrar)
    def fallar_pdf(*args):
        assert p.vista.disabled and p.btn_registrar.disabled
        assert Servicios(app.ruta_bd).laboratorio.obtener_resultado(muestra)
        p.btn_registrar.on_click(None)
        reemitir = p.tabla.rows[0].cells[-1].content.controls[0]
        reemitir.on_click(None)  # otra entrada durante el PDF también queda bloqueada
        raise PermissionError("detalle técnico privado")
    with monkeypatch.context() as m:
        m.setattr(sl, "exportar_comprobante_resultado_pdf", fallar_pdf)
        p.btn_registrar.on_click(None)
    assert len(registros) == 1 and p.btn_registrar.disabled and not p.vista.disabled
    assert any("Resultado registrado" in mensaje for mensaje in pag.mensajes)
    assert "permanece guardado" in pag.mensajes[-1]
    assert not any("No se pudo completar" in mensaje for mensaje in pag.mensajes)
    assert not any("detalle técnico privado" in mensaje or "Comprobante emitido" in mensaje for mensaje in pag.mensajes)
    p.tabla.rows[0].cells[-1].content.controls[0].on_click(None)
    assert "Comprobante emitido" in pag.mensajes[-1] and len(registros) == 1
    assert Servicios(app.ruta_bd).laboratorio.historial_muestra(muestra)[-1]["estado"] == "ANALIZADA"


def test_resultado_rechazado_no_habilita_boton_y_tiene_explicacion(envio):
    app, _, env, _, _ = envio
    env.integro.value = "Precinto roto"; env._recibir()
    p = pestana(app, sl.PestanaResultados)
    p.refrescar(); elegir(p.muestra); p.muestra.on_select(SimpleNamespace())
    assert p.btn_registrar.disabled and "rechazada" in p.aviso_muestra.value
    p.btn_registrar.on_click(None)
    assert app.servicios.laboratorio.listar_resultados() == []


@pytest.mark.parametrize("tipo", [PermissionError, RuntimeError])
def test_errores_tecnicos_no_se_exponen_y_boton_permite_reintentar(ui, tipo):
    app, pag = ui
    p = pestana(app, sp.PestanaClientes)
    p.nombre_f.value = "Conservar"
    def accion():
        raise tipo("información técnica privada")
    boton = c.boton("Intentar", lambda e: p.ejecutar(accion), grupo=p)
    boton.on_click(None)
    assert "información técnica privada" not in pag.mensajes[-1]
    assert "No se pudo completar" in pag.mensajes[-1]
    assert not p.vista.disabled and p.nombre_f.value == "Conservar"
    p.nombre_f.value, p.apellido_f.value, p.dni_f.value = "Ana", "Pérez", "00123"
    p.btn_guardar.on_click(None)
    assert len(app.servicios.clinica.listar_clientes()) == 1


def test_fallo_de_refresco_despues_de_commit_no_sugiere_repetir_alta(ui, monkeypatch):
    app, pag = ui
    p = pestana(app, sp.PestanaClientes)
    p.nombre_f.value, p.apellido_f.value, p.dni_f.value = "Ana", "Pérez", "00123"
    monkeypatch.setattr(p, "refrescar", lambda: (_ for _ in ()).throw(RuntimeError("sin vista")))
    p.btn_guardar.on_click(None)
    assert len(Servicios(app.ruta_bd).clinica.listar_clientes()) == 1
    assert any("Cliente registrado" in m for m in pag.mensajes)
    assert "se completó" in pag.mensajes[-1] and "no repita el registro" in pag.mensajes[-1]
    assert not p.vista.disabled and not p.nombre_f.value


@pytest.mark.parametrize("clase", [sp.PestanaClientes, sp.PestanaMascotas])
def test_guardar_cambios_y_cancelar_edicion_tienen_etiquetas_claras(ui, clase):
    app, _ = ui
    cliente = app.servicios.clinica.crear_cliente("Ana", "Pérez", "00123")
    if clase is sp.PestanaMascotas:
        app.servicios.clinica.crear_mascota(cliente, "Luna", "Perro")
    p = pestana(app, clase)
    p.refrescar()
    assert p.btn_guardar.content == "Guardar"
    p._editar(p.datos[0])
    assert p.btn_guardar.content == "Guardar cambios" and p.btn_cancelar.visible
    p.btn_cancelar.on_click(None)
    assert p.btn_guardar.content == "Guardar" and not p.btn_cancelar.visible


def test_avisos_tienen_cierre_y_errores_mas_tiempo_y_reporte_etiqueta_clara(ui, monkeypatch):
    app, pag = ui
    avisos = []
    monkeypatch.setattr(pag, "show_dialog", avisos.append)
    app.ok("Guardado"); app.error("Error para leer")
    assert avisos[0].duration == 4500 and avisos[1].duration == 10000
    assert all(a.show_close_icon for a in avisos)
    assert boton_en(app.pantallas[4], "Generar reporte")


@pytest.mark.parametrize("clase, campos, accion", [
    (sa.PestanaAtenciones, ["diagnostico", "observaciones"], "_registrar"),
    (sa.PestanaAtenciones, ["obs_orden"], "_derivar"),
    (sl.PestanaEnvio, ["obs_envio"], "_despachar"),
    (sl.PestanaResultados, ["obs"], "_registrar"),
])
def test_rechazo_conserva_textos_clinicos(ui, clase, campos, accion):
    app, _ = ui
    p = pestana(app, clase)
    texto = "Primera línea <b>sin cerrar\nSegunda & >\nTercera"
    for nombre in campos:
        getattr(p, nombre).value = texto
    getattr(p, accion)()  # faltan selecciones obligatorias
    assert all(getattr(p, nombre).value == texto for nombre in campos)
    assert app.servicios.atencion.listar_atenciones() == []
    assert app.servicios.laboratorio.listar_resultados() == []


def test_corregir_fecha_fuera_de_rango_no_oculta_error_hasta_ser_valida():
    control = c.campo_fecha("Nacimiento", fecha_maxima=lambda: FECHA.date(), opcional=True)
    control.value = "05/11/2026"
    c.establecer_error(control, "El nacimiento no puede ser futuro.")
    control.value = "06/11/2026"; control.on_change(SimpleNamespace())
    assert control.error
    control.value = "04/11/2026"; control.on_change(SimpleNamespace())
    assert control.error is None


def test_corregir_longitud_reutiliza_validador_sin_recortar_valor(ui):
    app, _ = ui
    p = pestana(app, st.PestanaProfesionales)
    p.cl_nombre.value, p.cl_dir.value = "Centro", "X" * 201
    p._crear_clinica()
    assert p.cl_dir.error
    p.cl_dir.value = "X" * 202; p.cl_dir.on_change(SimpleNamespace())
    assert p.cl_dir.error and len(p.cl_dir.value) == 202
    p.cl_dir.value = "Calle 1"; p.cl_dir.on_change(SimpleNamespace())
    assert p.cl_dir.error is None
    p._crear_clinica()
    assert app.servicios.clinica.listar_clinicas()[0]["direccion"] == "Calle 1"


def test_resultado_confirmado_no_se_repite_si_falla_refresco(envio, monkeypatch):
    app, pag, env, muestra, _ = envio
    env.integro.value = "Precinto intacto"; env._recibir()
    p = pestana(app, sl.PestanaResultados)
    p.refrescar(); elegir(p.muestra); p.muestra.on_select(SimpleNamespace())
    p.resultado.value, p.fecha.value = "Normal", "04/11/2026 12:00"
    original = app.servicios.laboratorio.registrar_resultado
    llamadas = []
    def registrar(*args):
        llamadas.append(args)
        return original(*args)
    monkeypatch.setattr(app.servicios.laboratorio, "registrar_resultado", registrar)
    monkeypatch.setattr(p, "refrescar", lambda: (_ for _ in ()).throw(RuntimeError("Sin vista")))
    p.btn_registrar.on_click(None)
    assert p.btn_registrar.disabled and not p.vista.disabled
    p.btn_registrar.on_click(None)
    assert len(llamadas) == 1
    assert Servicios(app.ruta_bd).laboratorio.obtener_resultado(muestra)["resultado"] == "Normal"
    assert any("no repita el registro" in m for m in pag.mensajes)
