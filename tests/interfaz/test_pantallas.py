"""Humo de la interfaz Flet con una página simulada (sin abrir ventanas)."""

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
        self.mensajes, self.dialogos, self.controles = [], [], []
        self.title = self.theme = self.padding = self.bgcolor = None

    def add(self, *controles): self.controles.extend(controles)
    def update(self, *a): pass
    def pop_dialog(self): pass

    def show_dialog(self, dialogo):
        if isinstance(dialogo, ft.SnackBar):
            self.mensajes.append(dialogo.content.value)
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
    mas._historia(mas.datos[0]); assert any("Historia clínica" in d for d in pag.dialogos)
    mas._pedir_baja(mas.datos[0]); assert "Confirmar" in pag.dialogos


def test_turnos_y_profesionales(ui):
    app, pag = ui
    ultimo = lambda: pag.mensajes[-1]
    app.servicios.clinica.crear_cliente("Ana", "Pérez", "1")
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
    cli = srv.clinica.crear_cliente("Ana", "Pérez", "1")
    mas = srv.clinica.crear_mascota(cli, "Firulais", "Perro", abrir_historia=True)
    at, va = pestana(app, sa.PestanaAtenciones), pestana(app, sa.PestanaVacunas)

    va.refrescar(); va.v_nombre.value = "Antirrábica"; va._crear_vacuna()
    at.refrescar(); elegir(at.mascota); at._al_elegir_mascota(); elegir(at.vet)
    assert "pendientes" in at.estado_vacunas.value
    at.motivo.value = "Control"; at._registrar(); assert "Antirrábica" in ultimo()
    va.refrescar(); elegir(va.mascota); elegir(va.vacuna)
    va.f_prox.value = ""; va._aplicar(); assert "Aplicación registrada" in ultimo()
    at.refrescar(); at.motivo.value = "Control"; at._registrar(); assert "Atención registrada" in ultimo()

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
    cli = srv.clinica.crear_cliente("Ana", "Pérez", "1")
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
    env.refrescar(); elegir(env.envio); env.integro.value = False; env._recibir()
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


def test_parsers_y_mascara():
    assert c.leer_fecha("25/11/2026").day == 25
    assert c.leer_fecha_hora("25/11/2026 09:30").hour == 9
    assert c.leer_hora("08:15").minute == 15
    with pytest.raises(ErrorNegocio): c.leer_fecha("2026-11-25")
    with pytest.raises(ErrorNegocio): c.leer_entero("0")
    assert c.leer_fecha_opcional("") is None
    assert c.formatear_fecha("2511") == "25/11/"
    assert c.formatear_fecha("251120261030", "", True) == "25/11/2026 10:30"
