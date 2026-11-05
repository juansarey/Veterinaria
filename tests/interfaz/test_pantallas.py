"""Humo de la interfaz Flet con una página simulada (sin abrir ventanas)."""

from datetime import datetime, time
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")

from veterinaria.interfaz import componentes as c
from veterinaria.interfaz.app import SECCIONES, AplicacionVeterinaria
from veterinaria.interfaz import seccion_atencion as sa, seccion_laboratorio as sl
from veterinaria.interfaz import seccion_personas as sp, seccion_reportes as sr, seccion_turnos as st
from veterinaria.servicios.datos_demo import cargar_demo
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios


class PaginaFalsa:
    def __init__(self):
        self.window = SimpleNamespace(width=0, height=0)
        self.mensajes, self.dialogos, self.pickers, self.controles = [], [], [], []
        self.title = self.theme = self.padding = self.bgcolor = None

    def add(self, *controles): self.controles.extend(controles)
    def update(self, *a): pass
    def pop_dialog(self): pass

    def show_dialog(self, dialogo):
        if isinstance(dialogo, ft.SnackBar):
            self.mensajes.append(dialogo.content.value)
        elif isinstance(dialogo, (ft.DatePicker, ft.TimePicker)):
            self.pickers.append(dialogo)
        else:
            self.dialogos.append(dialogo.title.value)


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setattr("veterinaria.interfaz.app.webbrowser.open", lambda *a, **k: True)
    pagina = PaginaFalsa()
    servicios = Servicios(tmp_path / "v.db")
    app = AplicacionVeterinaria(pagina, servicios, tmp_path / "v.db")
    app.iniciar()
    return app, pagina


def pestana(app, clase):
    for seccion in app.pantallas:
        for hija in getattr(seccion, "hijas", []):
            if isinstance(hija, clase):
                return hija
    raise LookupError(clase)


def elegir(dd, indice=0):
    dd.value = dd.options[indice].key


def test_cinco_secciones_y_todas_se_construyen(ui):
    app, pag = ui
    assert pag.theme_mode == ft.ThemeMode.LIGHT        # textos legibles aunque el sistema sea oscuro
    assert len(app.pantallas) == len(SECCIONES) == 5
    for i in range(5):
        app.ir_a(i)
        assert app.contenido.content is app.pantallas[i].vista
    for seccion in app.pantallas:
        for hija in getattr(seccion, "hijas", []):
            hija.refrescar()


def test_clientes_y_mascotas(ui):
    app, pag = ui
    cli, mas = pestana(app, sp.PestanaClientes), pestana(app, sp.PestanaMascotas)
    ultimo = lambda: pag.mensajes[-1]
    cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value = "Ana", "Pérez", "30111222"
    cli._guardar()
    assert "registrado" in ultimo() and len(cli.tabla.rows) == 1
    cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value = "Beto", "Ruiz", "30111222"
    cli._guardar(); assert "Ya existe" in ultimo()
    cli.dni_f.value = "30999999"; cli._guardar()
    fila = cli.datos[0]
    cli._editar(fila); assert cli.editando == fila["id"] and cli.btn_cancelar.visible
    cli.tel_f.value = "351-1"; cli._guardar(); assert "actualizado" in ultimo()
    assert not cli.btn_cancelar.visible
    cli.buscar.value = "zzz"; cli._filtrar(); assert len(cli.tabla.rows) == 0

    mas.refrescar()
    mas.nombre_f.value = "Firulais"; mas._guardar()
    assert "responsable" in ultimo().lower()                      # RN01
    elegir(mas.resp); mas._guardar()
    assert "historia" in ultimo()
    assert app.servicios.atencion.obtener_historia(mas.datos[0]["id"]) is not None
    mas.nombre_f.value = "Firulais"; elegir(mas.resp); mas._guardar()      # mismo responsable y especie
    assert "registrada" in ultimo() and len(mas.datos) == 2
    assert len({m["id"] for m in mas.datos}) == 2
    assert len({m["etiqueta"] for m in mas.datos}) == 2
    mas._historia(mas.datos[0]); assert any("Historia clínica" in d for d in pag.dialogos)
    mas._pedir_baja(mas.datos[0]); assert "Confirmar" in pag.dialogos


def test_error_de_campo_enfoca_conserva_valores_y_permite_corregir(ui, monkeypatch):
    app, pag = ui
    cli = pestana(app, sp.PestanaClientes)
    focos = []
    monkeypatch.setattr(pag, "run_task", lambda funcion: focos.append(funcion.__self__), raising=False)
    cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value = "Ana2", "Pérez", "12a"
    cli._guardar()
    assert cli.nombre_f.error and "letras" in cli.nombre_f.error
    assert focos[-1] is cli.nombre_f
    assert (cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value) == ("Ana2", "Pérez", "12a")
    assert app.servicios.clinica.listar_clientes() == []

    cli.nombre_f.value = "María José"
    cli.nombre_f.on_change(SimpleNamespace())
    assert cli.nombre_f.error is None
    cli._guardar()
    assert cli.dni_f.error and focos[-1] is cli.dni_f
    assert cli.nombre_f.value == "María José"
    cli.dni_f.value = "00123456"
    cli._guardar()
    assert "registrado" in pag.mensajes[-1]
    assert cli.nombre_f.error is cli.dni_f.error is None
    assert cli.nombre_f.value == cli.dni_f.value == ""
    assert app.servicios.clinica.listar_clientes()[0]["dni"] == "00123456"


def test_correo_se_valida_al_guardar_sin_interferir_con_la_escritura(ui):
    app, pag = ui
    cli = pestana(app, sp.PestanaClientes)
    cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value = "Ana", "Pérez", "12345678"
    cli.email_f.value = "ana@"
    cli.email_f.on_change(SimpleNamespace())
    assert cli.email_f.value == "ana@" and cli.email_f.error is None
    assert pag.mensajes == []
    cli._guardar()
    assert cli.email_f.error and cli.email_f.value == "ana@"
    cli.email_f.value = "ana@correo.com"
    cli.email_f.on_change(SimpleNamespace())
    assert cli.email_f.error is None
    cli._guardar()
    assert app.servicios.clinica.listar_clientes()[0]["email"] == "ana@correo.com"


def test_edicion_rechazada_preserva_formulario_y_datos_originales(ui):
    app, _ = ui
    cliente = app.servicios.clinica.crear_cliente("Ana", "Pérez", "12345678")
    cli = pestana(app, sp.PestanaClientes)
    cli.refrescar(); cli._editar(cli.datos[0])
    cli.nombre_f.value, cli.tel_f.value = "Eva", "teléfono?"
    cli._guardar()
    assert cli.editando == cliente and cli.btn_cancelar.visible
    assert cli.tel_f.error and cli.nombre_f.value == "Eva"
    assert app.servicios.clinica.listar_clientes()[0]["nombre"] == "Ana"
    cli.tel_f.value = "+54 (351) 555-0101"
    cli._guardar()
    assert cli.editando is None and cli.tel_f.error is None
    assert app.servicios.clinica.listar_clientes()[0]["nombre"] == "Eva"


def test_dni_duplicado_se_marca_en_el_campo(ui):
    app, _ = ui
    app.servicios.clinica.crear_cliente("Ana", "Pérez", "12345678")
    cli = pestana(app, sp.PestanaClientes)
    cli.nombre_f.value, cli.apellido_f.value, cli.dni_f.value = "Eva", "Ruiz", "12345678"
    cli._guardar()
    assert "Ya existe" in cli.dni_f.error
    assert cli.nombre_f.value == "Eva" and len(app.servicios.clinica.listar_clientes()) == 1


def test_selector_invalido_se_informa_y_se_recupera(ui):
    app, pag = ui
    app.servicios.clinica.crear_clinica("Vet & Cía. Nº 2", "Av. 9 de Julio 100")
    prof = pestana(app, st.PestanaProfesionales)
    prof.refrescar()
    prof.v_clinica.value = "texto"
    prof.v_nombre.value, prof.v_apellido.value, prof.v_mat.value = "Ana", "Pérez", "MP-2/26"
    prof._crear_vet()
    assert prof.v_clinica.error_text and prof.v_nombre.value == "Ana"
    assert app.servicios.clinica.listar_veterinarios() == []
    elegir(prof.v_clinica)
    prof.v_clinica.on_select(SimpleNamespace())
    assert prof.v_clinica.error_text is None
    prof._crear_vet()
    assert "Veterinario registrado" in pag.mensajes[-1]
    assert prof.v_mat.value == ""


def test_longitudes_se_muestran_en_los_formularios_correspondientes(ui):
    app, _ = ui
    prof = pestana(app, st.PestanaProfesionales)
    prof.cl_nombre.value, prof.cl_dir.value = "Clínica 2", "D" * 201
    prof._crear_clinica()
    assert prof.cl_dir.error and prof.cl_nombre.value == "Clínica 2"
    vacunas = pestana(app, sa.PestanaVacunas)
    vacunas.v_nombre.value = "V" * 101
    vacunas._crear_vacuna()
    assert vacunas.v_nombre.error and vacunas.v_nombre.value == "V" * 101
    emp = pestana(app, sl.PestanaEmpaquetado)
    emp.codigo_cons.value = "C" * 51
    emp._crear_cons()
    assert emp.codigo_cons.error and emp.codigo_cons.value == "C" * 51


def test_error_general_sigue_informandose_sin_marcar_campos(ui):
    app, pag = ui
    cli = pestana(app, sp.PestanaClientes)
    cli.nombre_f.value = "Ana"

    def rechazar():
        raise ErrorNegocio("La operación no está disponible.")

    assert cli.ejecutar(rechazar, campos={"Nombre": cli.nombre_f}) is None
    assert pag.mensajes[-1] == "La operación no está disponible."
    assert cli.nombre_f.error is None and cli.nombre_f.value == "Ana"


def test_foco_no_disponible_no_oculta_el_error_de_validacion(ui, monkeypatch):
    app, pag = ui
    cli = pestana(app, sp.PestanaClientes)

    def sin_sesion(*_):
        raise RuntimeError("sin sesión de Flet")

    monkeypatch.setattr(pag, "run_task", sin_sesion, raising=False)
    cli._guardar()
    assert cli.nombre_f.error and cli.nombre_f.value == ""
    assert "obligatorio" in pag.mensajes[-1]


def test_seleccion_de_mascotas_coincidentes_utiliza_el_id(ui):
    app, _ = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "00123456")
    una = srv.clinica.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    otra = srv.clinica.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Colón 100")
    srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    at = pestana(app, sa.PestanaAtenciones)
    at.refrescar()
    assert len({opcion.text for opcion in at.mascota.options}) == 2
    at.mascota.value = str(otra)
    elegir(at.vet)
    at.motivo.value = "Control"
    at._registrar()
    assert srv.atencion.listar_atenciones(una) == []
    assert len(srv.atencion.listar_atenciones(otra)) == 1


def test_turnos_y_profesionales(ui, monkeypatch):
    monkeypatch.setattr("veterinaria.servicios.clinica_servicio.ahora", lambda: datetime(2026, 11, 2, 6))
    app, pag = ui
    ultimo = lambda: pag.mensajes[-1]
    app.servicios.clinica.crear_cliente("Ana", "Pérez", "30111222")
    app.servicios.clinica.crear_mascota(1, "Firulais", "Perro")
    prof, ag = pestana(app, st.PestanaProfesionales), pestana(app, st.PestanaAgenda)
    prof.cl_nombre.value, prof.cl_dir.value = "Centro", "Colón 100"; prof._crear_clinica()
    prof.refrescar(); elegir(prof.v_clinica)
    prof.v_nombre.value, prof.v_apellido.value, prof.v_mat.value = "Luis", "Gómez", "MP-1"
    prof._crear_vet(); assert "Veterinario registrado" in ultimo()
    prof.refrescar(); elegir(prof.vet_agenda)
    from veterinaria.dominio.clinica.agenda_medica import DiaSemana
    for d in DiaSemana: prof.dias[d].value = True
    prof._guardar_agenda(); assert "Agenda guardada" in ultimo()

    ag.refrescar(); elegir(ag.vet); elegir(ag.mascota)
    ag.fecha.value, ag.hora.value, ag.duracion.value = "02/11/2026", "09:00", "30"
    ag._reservar(); assert "Turno reservado" in ultimo()
    assert len(ag.tabla.rows) == 1                                # se muestra el día reservado
    ag.hora.value = "09:15"; ag._reservar(); assert "superpone" in ultimo()
    ag.hora.value = "07:00"; ag._reservar(); assert "fuera de la agenda" in ultimo()
    ag.fecha.value = "texto"; ag._reservar(); assert "formato" in ultimo()
    turno = ag.srv.clinica.listar_turnos()[0]
    ag._cambiar(turno, "confirmar"); assert "confirmado" in ultimo()
    ag._cambiar(turno, "cancelar"); assert "cancelado" in ultimo()
    ag._ver_todos(); assert len(ag.tabla.rows) == 1


def test_atencion_derivacion_y_comprobante(ui, tmp_path):
    app, pag = ui
    ultimo = lambda: pag.mensajes[-1]
    srv = app.servicios
    cl = srv.clinica.crear_clinica("Centro", "Colón"); vet = srv.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-1")
    cli = srv.clinica.crear_cliente("Ana", "Pérez", "30111222")
    mas = srv.clinica.crear_mascota(cli, "Firulais", "Perro", abrir_historia=True)
    at, va = pestana(app, sa.PestanaAtenciones), pestana(app, sa.PestanaVacunas)

    va.refrescar(); va.v_nombre.value = "Antirrábica"; va._crear_vacuna()
    at.refrescar(); elegir(at.mascota); at._al_elegir_mascota(); elegir(at.vet)
    assert "pendientes" in at.estado_vacunas.value
    at.motivo.value = "Control"; at._registrar(); assert "Atención registrada" in ultimo()
    assert "Puede registrar la atención" in at.estado_vacunas.value
    assert len(srv.atencion.listar_atenciones(mas)) == 1
    va.refrescar(); elegir(va.mascota); elegir(va.vacuna)
    va.f_prox.value = ""; va._aplicar(); assert "Aplicación registrada" in ultimo()
    at.refrescar(); at.motivo.value = "Control"; at._registrar(); assert "Atención registrada" in ultimo()
    assert len(srv.atencion.listar_atenciones(mas)) == 2

    at.refrescar(); elegir(at.atencion)
    at.estudio.value = "Hemograma"; at._derivar(); assert "Orden #1" in ultimo()
    at.refrescar(); assert at.tabla.rows[0].cells[6].content.value == "1"      # derivaciones
    at._comprobante(at.atenciones[0]); assert "Comprobante emitido" in ultimo()
    assert list((tmp_path / "exportaciones").glob("comprobante_*.pdf"))


def test_laboratorio_completo_con_rechazo(ui, tmp_path):
    app, pag = ui
    ultimo = lambda: pag.mensajes[-1]
    srv = app.servicios
    cl = srv.clinica.crear_clinica("Centro", "Colón"); vet = srv.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-1")
    cli = srv.clinica.crear_cliente("Ana", "Pérez", "30111222")
    mas = srv.clinica.crear_mascota(cli, "Firulais", "Perro", abrir_historia=True)
    from datetime import datetime, timedelta
    at = srv.atencion.registrar_atencion(mas, vet, datetime.now() - timedelta(days=1),
                                         __import__("veterinaria.dominio.clinica.atencion", fromlist=["x"]).TipoAtencion.CONSULTA, "x")
    srv.laboratorio.derivar(at, "Hemograma", "Sangre")

    emp, env = pestana(app, sl.PestanaEmpaquetado), pestana(app, sl.PestanaEnvio)
    res, seg = pestana(app, sl.PestanaResultados), pestana(app, sl.PestanaSeguimiento)
    emp.refrescar(); emp._empaquetar(); assert "una conservadora" in ultimo() or "clínica" in ultimo()
    emp.codigo_cons.value = "CONS-1"; emp._crear_cons(); emp.refrescar()
    elegir(emp.clinica); emp._al_elegir_clinica(); elegir(emp.conservadora)
    assert len(emp.checks) == 1
    emp._empaquetar(); assert "Remito R-0001 emitido" in pag.dialogos[-1]

    env.refrescar(); elegir(env.remito); env._despachar(); assert "En tránsito" in ultimo()
    env.refrescar(); elegir(env.envio); env.integro.value = "Precinto roto"; env._recibir()
    assert pag.dialogos[-1] == "Remito RECHAZADO"

    res.refrescar(); elegir(res.muestra); res.resultado.value = "x"; res._registrar()
    assert "RECHAZADA" in ultimo()                                # no puede analizarse
    seg.refrescar(); seg._ver(seg.srv.laboratorio.listar_muestras()[0] | {"id_txt": "M-0001"})
    assert any("Cadena de custodia" in d for d in pag.dialogos)
    emp.refrescar(); emp._liberar(emp.srv.laboratorio.listar_remitos()[0]); assert "liberada" in ultimo()


def test_reportes_con_datos_demo(ui, tmp_path):
    app, pag = ui
    cargar_demo(app.servicios)
    rp = app.pantallas[4]
    for clave in sr.REPORTES:
        rp.reporte.value = clave; rp._generar()
        assert rp.actual["titulo"] and len(rp.tabla.columns) == len(rp.actual["columnas"])
    rp.reporte.value = "rechazadas"; rp._generar(); assert len(rp.actual["filas"]) == 2
    rp._exportar("pdf"); rp._exportar("csv")
    assert list((tmp_path / "exportaciones").glob("reporte_rechazadas_*.csv"))
    # secciones con datos reales: todas refrescan sin errores
    for i in range(5):
        app.ir_a(i)


def test_reporte_fallido_descarta_vista_previa_y_no_exporta_datos_previos(ui, tmp_path, monkeypatch):
    app, pag = ui
    cargar_demo(app.servicios)
    rp = app.pantallas[4]
    rp.reporte.value = "vacunas"
    rp.fecha_ref.value = "04/11/2026"
    rp._generar()
    assert rp.actual is not None and rp.tabla.visible

    rp.fecha_ref.value = "fecha inválida"
    with monkeypatch.context() as parche:
        parche.setattr(sr, "exportar_csv", lambda *_: pytest.fail("Se exportaron datos anteriores"))
        rp._exportar("csv")
    assert rp.actual is None
    assert not rp.tabla.visible and rp.tabla.rows == []
    assert rp.titulo_rep.value == rp.resumen.value == ""
    assert not list((tmp_path / "exportaciones").glob("*.csv"))
    assert "Reporte exportado" not in pag.mensajes[-1]

    rp.fecha_ref.value = "04/11/2026"
    rp._exportar("csv")
    assert rp.actual is not None and rp.tabla.visible
    assert "Reporte exportado" in pag.mensajes[-1]
    assert list((tmp_path / "exportaciones").glob("reporte_vacunas_*.csv"))


@pytest.mark.parametrize("formato, nombre", [("pdf", "exportar_pdf"), ("csv", "exportar_csv")])
def test_error_de_escritura_no_anuncia_exito_y_permite_reintento(
        ui, tmp_path, monkeypatch, formato, nombre):
    app, pag = ui
    rp = app.pantallas[4]
    archivos_abiertos = []
    monkeypatch.setattr(app, "abrir_archivo", archivos_abiertos.append)

    def sin_permisos(*_):
        raise PermissionError("sin permisos")

    inicio_avisos = len(pag.mensajes)
    with monkeypatch.context() as parche:
        parche.setattr(sr, nombre, sin_permisos)
        rp._exportar(formato)
    avisos_fallo = pag.mensajes[inicio_avisos:]
    assert any("permisos" in aviso for aviso in avisos_fallo)
    assert not any("sin permisos" in aviso for aviso in avisos_fallo)  # no exponer la excepción técnica
    assert not any("Reporte exportado" in aviso for aviso in avisos_fallo)
    assert archivos_abiertos == []
    assert rp.actual is not None and rp.tabla.visible

    rp._exportar(formato)
    assert "Reporte exportado" in pag.mensajes[-1]
    assert len(archivos_abiertos) == 1
    assert list((tmp_path / "exportaciones").glob(f"reporte_atenciones_*.{formato}"))


def test_parsers_y_mascara():
    assert c.leer_fecha("25/11/2026").day == 25
    assert c.leer_fecha_hora("25/11/2026 09:30").hour == 9
    assert c.leer_hora("08:15").minute == 15
    with pytest.raises(ErrorNegocio): c.leer_fecha("2026-11-25")
    with pytest.raises(ErrorNegocio): c.leer_entero("0")
    assert c.leer_fecha_opcional("") is None
    assert c.formatear_fecha("2511") == "25/11/"
    assert c.formatear_fecha("251120261030", "", True) == "25/11/2026 10:30"


def test_calendario_y_reloj_en_los_campos_de_fecha(ui):
    app, pag = ui
    campo_fh = c.campo_fecha_hora("Fecha y hora")
    campo_f = c.campo_fecha("Fecha")
    hora = c.campo_hora("Hora", valor="10:00")
    assert len(campo_fh.suffix.controls) == 2 and len(campo_f.suffix.controls) == 1 and hora.suffix
    evento = SimpleNamespace(page=pag)

    campo_fh.value = campo_fh.data = "02/11/2026 09:30"
    c.abrir_calendario(evento, campo_fh, True)
    pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=datetime(2026, 12, 25))))
    assert campo_fh.value == "25/12/2026 09:30"                         # conserva la hora
    c.abrir_reloj(evento, campo_fh, True)
    pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=time(14, 5))))
    assert campo_fh.value == "25/12/2026 14:05"

    c.abrir_calendario(evento, campo_f, False)                          # campo vacío: parte de hoy
    pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=datetime(2027, 1, 3))))
    assert campo_f.value == "03/01/2027"
    c.abrir_reloj(evento, hora, False)
    pag.pickers[-1].on_change(SimpleNamespace(control=SimpleNamespace(value=time(8, 45))))
    assert hora.value == "08:45"
    assert c.leer_fecha_hora(campo_fh.value).minute == 5 and c.leer_hora(hora.value).hour == 8


def test_todas_las_fechas_de_las_pantallas_tienen_calendario(ui):
    app, _ = ui
    def recorrer(control, hallados):
        if isinstance(control, ft.TextField) and control.hint_text and "DD/MM" in control.hint_text:
            hallados.append(control)
        for hijo in ([control.content] if getattr(control, "content", None) is not None and
                     not isinstance(control.content, str) else []) + list(getattr(control, "controls", []) or []):
            recorrer(hijo, hallados)
    hallados = []
    for seccion in app.pantallas:
        recorrer(seccion.vista, hallados)
    assert len(hallados) == 11 and all(f.suffix is not None for f in hallados)


def test_las_tablas_crecen_con_filas_y_solo_tienen_scroll_horizontal():
    cols = [("a", "A")]
    tabla = c.crear_tabla(cols)
    marco = c.contenedor_tabla(tabla)
    assert isinstance(marco.content, ft.Row) and marco.content.scroll == ft.ScrollMode.AUTO
    c.llenar_tabla(tabla, cols, [{"a": i} for i in range(40)])
    assert marco.height is None and marco.expand in (None, False)
    assert len(tabla.rows) == 40 and tabla.rows[-1].cells[0].content.value == "39"
    c.llenar_tabla(tabla, cols, [{"a": 1}, {"a": 2}])
    assert marco.height is None and len(tabla.rows) == 2


def test_comprobante_de_resultados_desde_la_interfaz(ui, tmp_path):
    app, pag = ui
    cargar_demo(app.servicios)
    env, res = pestana(app, sl.PestanaEnvio), pestana(app, sl.PestanaResultados)
    env.refrescar(); env.envio.value = "3"; env.integro.value = "Precinto intacto"; env._recibir()
    assert pag.dialogos[-1] == "Remito aceptado"
    res.refrescar(); res.muestra.value = "4"
    res.resultado.value, res.obs.value = "Sin hallazgos de importancia", "Control en 6 meses"
    res._registrar()
    assert "Comprobante emitido" in pag.mensajes[-1]
    pdfs = list((tmp_path / "exportaciones").glob("comprobante_resultado_M0004_*.pdf"))
    assert pdfs and pdfs[0].stat().st_size > 800
    assert len(res.tabla.rows) == 3                                       # 2 de la demo + la nueva
    res._comprobante(1, "Comprobante emitido")                             # reimpresión desde la tabla
    assert list((tmp_path / "exportaciones").glob("comprobante_resultado_M0001_*.pdf"))
    res.muestra.value = "3"; res.resultado.value = "x"; res._registrar()   # rechazada: sin comprobante
    assert "RECHAZADA" in pag.mensajes[-1]


def test_resultado_permanece_guardado_si_falla_pdf_y_se_reemite(ui, tmp_path, monkeypatch):
    app, pag = ui
    cargar_demo(app.servicios)
    env, res = pestana(app, sl.PestanaEnvio), pestana(app, sl.PestanaResultados)
    env.refrescar(); env.envio.value = "3"; env.integro.value = "Precinto intacto"; env._recibir()
    res.refrescar(); res.muestra.value = "4"
    res.resultado.value, res.obs.value = "Sin hallazgos", "Revisar en 6 meses"

    def fallo_pdf(*_):
        raise PermissionError("sin permisos para PDF")

    inicio_avisos = len(pag.mensajes)
    with monkeypatch.context() as parche:
        parche.setattr(sl, "exportar_comprobante_resultado_pdf", fallo_pdf)
        res._registrar()

    avisos = pag.mensajes[inicio_avisos:]
    assert any("Resultado registrado" in aviso for aviso in avisos)
    assert any("permanece guardado" in aviso and "reemitirlo" in aviso for aviso in avisos)
    assert not any("Comprobante emitido" in aviso for aviso in avisos)
    assert not list((tmp_path / "exportaciones").glob("comprobante_resultado_M0004_*.pdf"))
    assert len(res.tabla.rows) == 3  # el resultado aparece con opción de reemisión
    assert all(opcion.key != "4" for opcion in res.muestra.options)

    servicios_reabiertos = Servicios(tmp_path / "v.db")
    assert servicios_reabiertos.laboratorio.obtener_resultado(4)["resultado"] == "Sin hallazgos"
    assert next(m for m in servicios_reabiertos.laboratorio.listar_muestras()
                if m["id"] == 4)["estado"] == "ANALIZADA"

    res._comprobante(4, "Comprobante emitido")
    assert "Comprobante emitido" in pag.mensajes[-1]
    assert list((tmp_path / "exportaciones").glob("comprobante_resultado_M0004_*.pdf"))


def _hijos(control):
    contenido = getattr(control, "content", None)
    return ([contenido] if contenido is not None and not isinstance(contenido, str) else []) + \
        list(getattr(control, "controls", []) or [])


def _listados_expandidos(control):
    """Detecta los antiguos marcos con expansión y scroll vertical interno."""
    hallados = []
    if (isinstance(control, ft.Container) and control.expand is True
            and isinstance(control.content, ft.Column) and control.content.scroll == ft.ScrollMode.ALWAYS):
        hallados.append(control)
    for hijo in _hijos(control):
        hallados += _listados_expandidos(hijo)
    return hallados


def test_formularios_y_listados_comparten_un_scroll_vertical(ui):
    app, _ = ui
    vistas = [(h.nombre, h.vista) for seccion in app.pantallas
              for h in getattr(seccion, "hijas", [seccion])]
    for nombre, vista in vistas:
        assert vista.scroll == ft.ScrollMode.AUTO, nombre
        assert vista.horizontal_alignment == ft.CrossAxisAlignment.STRETCH, nombre
        assert not _listados_expandidos(vista), nombre


def test_listado_vacio_no_reserva_altura_ni_espacio_expandido():
    cols = [("a", "A")]
    tabla = c.crear_tabla(cols)
    marco = c.contenedor_tabla(tabla)
    c.llenar_tabla(tabla, cols, [])
    assert marco.expand in (None, False) and marco.height is None
    assert marco.content.controls == [tabla] and tabla.rows == []


def test_vacunas_se_filtran_por_la_especie_de_la_mascota(ui):
    app, _ = ui
    p = pestana(app, sa.PestanaVacunas)
    cargar_demo(p.srv)
    p.refrescar()
    for m in p.mascotas:
        p.mascota.value = str(m["id"])
        p._al_elegir()
        especies = {v["especie"] for v in p.vacunas if str(v["id"]) in {o.key for o in p.vacuna.options}}
        assert especies == {m["especie"]}


def test_tabla_de_reportes_oculta_hasta_generar(ui):
    app, _ = ui
    p = next(x for x in app.pantallas if isinstance(x, sr.SeccionReportes))
    assert p.tabla.visible is False
    p._generar()
    assert p.tabla.visible is True
