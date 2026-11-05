"""Bajas restringidas, transacciones y conservación real de SQLite al reabrir."""

from datetime import datetime, time, timedelta

import pytest

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.dominio.transporte.envio import Envio
from veterinaria.persistencia.agenda_medica_dao import AgendaMedicaDAO
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO
from veterinaria.persistencia.turno_dao import TurnoDAO
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios

FECHA = datetime(2026, 11, 4, 9)


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr("veterinaria.servicios.clinica_servicio.ahora", lambda: FECHA)
    ruta = tmp_path / "v.db"
    srv = Servicios(ruta)
    cl = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(cl, "Ana", "Pérez", "MP-1")
    cliente = srv.clinica.crear_cliente("Luis", "Gómez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    return srv, ruta, cl, vet, mascota


def instantanea(ruta):
    con = abrir_conexion(ruta)
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return {t: [tuple(r) for r in con.execute(f'SELECT * FROM "{t}" ORDER BY rowid')]
                for t in tablas}
    finally:
        con.close()


def agendar(srv, vet):
    srv.clinica.guardar_agenda(vet, {DiaSemana.LUNES, DiaSemana.MIERCOLES}, time(8), time(18))


def atencion(srv, vet, mascota):
    return srv.atencion.registrar_atencion(mascota, vet, FECHA, TipoAtencion.CONSULTA, "Control")


def circuito(base, fase):
    srv, ruta, cl, vet, mascota = base
    if fase == "GENERADO":
        cons = srv.laboratorio.crear_conservadora("C-1")
        srv.laboratorio.crear_remito(cl, cons, fecha_emision=FECHA)
    else:
        muestra = srv.laboratorio.derivar(atencion(srv, vet, mascota), "Hemograma", "Sangre", FECHA)["id_muestra"]
        cons = srv.laboratorio.crear_conservadora("C-1")
        remito = srv.laboratorio.empaquetar(cl, cons, [muestra], "P-1", FECHA)["id_remito"]
        if fase == "PENDIENTE":
            con = abrir_conexion(ruta)
            try:
                EnvioDAO(con).crear(Envio(1, RemitoBiologicoDAO(con).obtener_por_id(remito)))
                con.commit()
            finally:
                con.close()
        elif fase != "EMPAQUETADO":
            envio = srv.laboratorio.despachar_remito(remito, FECHA + timedelta(hours=1))
            if fase == "ENTREGADO":
                srv.laboratorio.registrar_llegada(envio, FECHA + timedelta(hours=2))
            elif fase in {"RECIBIDO", "RECHAZADO", "ANALIZADO"}:
                srv.laboratorio.recibir_remito(envio, fase != "RECHAZADO", FECHA + timedelta(hours=2))
                if fase == "ANALIZADO":
                    srv.laboratorio.registrar_resultado(muestra, "Normal", fecha_resultado=FECHA + timedelta(hours=3))
    # La clínica conserva sus remitos aunque el profesional trabaje ahora en otra.
    otra = srv.clinica.crear_clinica("Sur", "Calle 2")
    con = abrir_conexion(ruta)
    try:
        dao = VeterinarioDAO(con)
        dao.actualizar(dao.obtener_por_id(vet), otra)
        con.commit()
    finally:
        con.close()


@pytest.mark.parametrize("con_agenda", [False, True])
def test_eliminar_veterinario_y_solo_su_agenda_y_dias(base, con_agenda):
    srv, ruta, cl, vet, _ = base
    otro = srv.clinica.crear_veterinario(cl, "Luis", "Gómez", "MP-2")
    agendar(srv, otro)
    if con_agenda:
        agendar(srv, vet)
    antes = instantanea(ruta)
    srv.clinica.eliminar_veterinario(vet)
    reabierto = Servicios(ruta)
    assert [v["id"] for v in reabierto.clinica.listar_veterinarios()] == [otro]
    assert reabierto.clinica.obtener_agenda(vet) is None
    assert reabierto.clinica.obtener_agenda(otro)["dias"] == [DiaSemana.LUNES, DiaSemana.MIERCOLES]
    despues = instantanea(ruta)
    assert len(despues["agenda_medica_dia"]) == 2
    for tabla in antes.keys() - {"veterinario", "agenda_medica", "agenda_medica_dia"}:
        assert despues[tabla] == antes[tabla]


@pytest.mark.parametrize("entidad", ["veterinario", "clinica"])
def test_baja_inexistente_no_modifica_datos(base, entidad):
    srv, ruta, *_ = base
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="no existe"):
        getattr(srv.clinica, f"eliminar_{entidad}")(999)
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("estado", ["PENDIENTE", "CONFIRMADO", "ATENDIDO", "CANCELADO"])
def test_turnos_de_cualquier_estado_impiden_baja_y_preservan_agenda(base, estado):
    srv, ruta, _, vet, mascota = base
    agendar(srv, vet)
    turno = srv.clinica.agendar_turno(vet, mascota, FECHA, FECHA + timedelta(minutes=30))
    if estado in {"CONFIRMADO", "ATENDIDO"}:
        srv.clinica.cambiar_estado_turno(turno, "confirmar")
    if estado == "ATENDIDO":
        srv.clinica.cambiar_estado_turno(turno, "atender")
    elif estado == "CANCELADO":
        srv.clinica.cambiar_estado_turno(turno, "cancelar")
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="turnos registrados"):
        srv.clinica.eliminar_veterinario(vet)
    assert instantanea(ruta) == antes
    assert Servicios(ruta).clinica.listar_turnos()[0]["estado"] == estado


def test_atencion_historica_sin_turnos_impide_baja(base):
    srv, ruta, _, vet, mascota = base
    agendar(srv, vet)
    id_at = atencion(srv, vet, mascota)
    srv.atencion.emitir_comprobante(id_at, FECHA)
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="atenciones clínicas"):
        srv.clinica.eliminar_veterinario(vet)
    assert instantanea(ruta) == antes
    assert Servicios(ruta).atencion.obtener_comprobante(id_at)


def test_eliminar_clinica_vacia_preserva_otras_entidades(base):
    srv, ruta, *_ = base
    vacia = srv.clinica.crear_clinica("Vacía", "Calle 9")
    antes = instantanea(ruta)
    srv.clinica.eliminar_clinica(vacia)
    despues = instantanea(ruta)
    assert all(c["id"] != vacia for c in Servicios(ruta).clinica.listar_clinicas())
    for tabla in antes.keys() - {"clinica"}:
        assert despues[tabla] == antes[tabla]
    with pytest.raises(ErrorNegocio, match="no existe"):
        srv.clinica.eliminar_clinica(vacia)


def test_clinica_con_veterinario_no_se_elimina(base):
    srv, ruta, cl, *_ = base
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="veterinarios asociados"):
        srv.clinica.eliminar_clinica(cl)
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("fase", ["GENERADO", "EMPAQUETADO", "PENDIENTE", "EN_TRANSITO", "ENTREGADO",
                                  "RECIBIDO", "RECHAZADO", "ANALIZADO"])
def test_remitos_y_transporte_historico_impiden_baja_clinica(base, fase):
    srv, ruta, cl, *_ = base
    circuito(base, fase)
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="remitos biológicos"):
        srv.clinica.eliminar_clinica(cl)
    assert instantanea(ruta) == antes
    assert any(c["id"] == cl for c in Servicios(ruta).clinica.listar_clinicas())


@pytest.mark.parametrize("consulta", ["atencion", "remito"])
def test_consultas_dao_son_puntuales_y_solo_lectura(base, consulta):
    srv, ruta, cl, vet, mascota = base
    atencion(srv, vet, mascota)
    cons = srv.laboratorio.crear_conservadora("C-1")
    srv.laboratorio.crear_remito(cl, cons, fecha_emision=FECHA)
    antes = instantanea(ruta)
    con = abrir_conexion(ruta)
    try:
        buscar = (AtencionDAO(con).existe_por_veterinario if consulta == "atencion"
                  else RemitoBiologicoDAO(con).existe_por_clinica)
        assert buscar(vet if consulta == "atencion" else cl) is True
        assert buscar(999) is False
        assert buscar("1 OR 1=1") is False
        assert not con.in_transaction
    finally:
        con.close()
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("entidad", ["veterinario", "clinica"])
def test_dependencias_ajenas_no_impiden_eliminacion(base, entidad):
    srv, ruta, cl, vet, mascota = base
    agendar(srv, vet)
    srv.clinica.agendar_turno(vet, mascota, FECHA, FECHA + timedelta(minutes=30))
    atencion(srv, vet, mascota)
    cons = srv.laboratorio.crear_conservadora("C-1")
    srv.laboratorio.crear_remito(cl, cons, fecha_emision=FECHA)
    otro_cl = srv.clinica.crear_clinica("Sur", "Calle 9")
    objetivo = otro_cl
    if entidad == "veterinario":
        objetivo = srv.clinica.crear_veterinario(otro_cl, "Juan", "Pérez", "MP-9")
    getattr(srv.clinica, f"eliminar_{entidad}")(objetivo)
    assert Servicios(ruta).clinica.listar_turnos()
    assert instantanea(ruta)["remito_biologico"]


@pytest.mark.parametrize("momento", ["dias", "agenda", "veterinario", "agenda_false", "veterinario_false"])
def test_fallo_intermedio_revierte_toda_la_baja_veterinario(base, monkeypatch, momento):
    srv, ruta, _, vet, _ = base
    agendar(srv, vet)
    antes = instantanea(ruta)
    clase = AgendaMedicaDAO if momento in {"dias", "agenda_false"} else VeterinarioDAO
    nombre = "eliminar_por_veterinario" if clase is AgendaMedicaDAO else "eliminar"
    original = getattr(clase, nombre)

    def fallar(dao, identificador):
        if momento == "dias":
            dao._conexion.execute("DELETE FROM agenda_medica_dia WHERE id_agenda IN "
                                  "(SELECT id_agenda FROM agenda_medica WHERE id_veterinario = ?)",
                                  (identificador,)).close()
        elif momento != "agenda":
            original(dao, identificador)
        if momento.endswith("false"):
            return False
        raise RuntimeError("Fallo intermedio")

    monkeypatch.setattr(clase, nombre, fallar)
    with pytest.raises(ErrorNegocio if momento.endswith("false") else RuntimeError):
        srv.clinica.eliminar_veterinario(vet)
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("devuelve_false", [False, True])
def test_fallo_baja_clinica_revierte_delete(base, monkeypatch, devuelve_false):
    srv, ruta, *_ = base
    cl = srv.clinica.crear_clinica("Vacía", "Calle 2")
    antes = instantanea(ruta)
    original = ClinicaDAO.eliminar

    def fallar(dao, identificador):
        original(dao, identificador)
        if devuelve_false:
            return False
        raise RuntimeError("Fallo después del DELETE")

    monkeypatch.setattr(ClinicaDAO, "eliminar", fallar)
    with pytest.raises(ErrorNegocio if devuelve_false else RuntimeError):
        srv.clinica.eliminar_clinica(cl)
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("entidad", ["veterinario", "clinica"])
def test_fk_como_ultima_defensa_y_rollback(base, monkeypatch, entidad):
    srv, ruta, cl, vet, mascota = base
    if entidad == "veterinario":
        agendar(srv, vet)
        srv.clinica.agendar_turno(vet, mascota, FECHA, FECHA + timedelta(minutes=30))
        monkeypatch.setattr(TurnoDAO, "listar_por_veterinario", lambda *args: [])
        objetivo = vet
    else:
        circuito(base, "GENERADO")
        monkeypatch.setattr(RemitoBiologicoDAO, "existe_por_clinica", lambda *args: False)
        objetivo = cl
    antes = instantanea(ruta)
    with pytest.raises(ErrorNegocio, match="relacionado con otros datos"):
        getattr(srv.clinica, f"eliminar_{entidad}")(objetivo)
    assert instantanea(ruta) == antes


@pytest.mark.parametrize("entidad", ["veterinario", "clinica"])
def test_lecturas_y_delete_comparten_transaccion_con_fk(base, monkeypatch, entidad):
    srv, _, _, vet, _ = base
    clase = VeterinarioDAO if entidad == "veterinario" else ClinicaDAO
    objetivo = vet if entidad == "veterinario" else srv.clinica.crear_clinica("Vacía", "Calle 2")
    original = clase.obtener_por_id
    sentencias = []

    def comprobar(dao, identificador):
        assert dao._conexion.in_transaction
        assert dao._conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        dao._conexion.set_trace_callback(sentencias.append)
        return original(dao, identificador)

    monkeypatch.setattr(clase, "obtener_por_id", comprobar)
    getattr(srv.clinica, f"eliminar_{entidad}")(objetivo)
    assert sum(s == "COMMIT" for s in sentencias) == 1
    assert not any(s.startswith("BEGIN") for s in sentencias)  # ya estaba abierta al comprobar existencia
