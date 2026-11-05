"""El reloj condiciona las altas, pero no la reconstrucción ni las consultas históricas."""

from datetime import date, datetime, time, timedelta

import pytest

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.servicios import clinica_servicio as cs
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios


@pytest.fixture
def reloj(monkeypatch):
    referencia = {"ahora": datetime(2026, 11, 4, 10, 30, 45)}
    monkeypatch.setattr(cs, "ahora", lambda: referencia["ahora"])
    return referencia


@pytest.fixture
def base(tmp_path, reloj):
    srv = Servicios(tmp_path / "vet.db")
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "12345678")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro")
    clinica = srv.clinica.crear_clinica("Centro", "Colón 100")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    srv.clinica.guardar_agenda(vet, set(DiaSemana), time(8), time(18))
    return srv, cliente, mascota, vet


@pytest.mark.parametrize("modificar", [False, True])
@pytest.mark.parametrize("nacimiento", [None, date(2026, 11, 4), date(2020, 1, 1), date(1950, 1, 1)])
def test_nacimiento_opcional_hoy_y_pasado_se_persisten(base, tmp_path, modificar, nacimiento):
    srv, cliente, mascota, _ = base
    if modificar:
        srv.clinica.modificar_mascota(mascota, "Luna", "Perro", fecha_nacimiento=nacimiento)
    else:
        mascota = srv.clinica.crear_mascota(cliente, "Mora", "Perro", fecha_nacimiento=nacimiento)
    con = abrir_conexion(tmp_path / "vet.db")
    try:
        assert MascotaDAO(con).obtener_por_id(mascota).fecha_nacimiento == nacimiento
    finally:
        con.close()


@pytest.mark.parametrize("modificar", [False, True])
@pytest.mark.parametrize("nacimiento", [date(2026, 11, 5), "05/11/2026", datetime(2026, 11, 4, 9)])
def test_nacimiento_futuro_o_tipo_incorrecto_no_altera_datos(base, modificar, nacimiento):
    srv, cliente, mascota, _ = base
    antes = srv.clinica.listar_mascotas()
    with pytest.raises(ErrorNegocio) as error:
        if modificar:
            srv.clinica.modificar_mascota(mascota, "Nombre nuevo", "Gato", fecha_nacimiento=nacimiento)
        else:
            srv.clinica.crear_mascota(cliente, "Otra", "Gato", fecha_nacimiento=nacimiento, abrir_historia=True)
    assert error.value.campo == "Nacimiento"
    assert srv.clinica.listar_mascotas() == antes


def test_nacimiento_consulta_el_reloj_en_cada_operacion(base, reloj):
    srv, cliente, _, _ = base
    with pytest.raises(ErrorNegocio, match="posterior a hoy"):
        srv.clinica.crear_mascota(cliente, "Mora", "Perro", fecha_nacimiento=date(2026, 11, 5))
    reloj["ahora"] = datetime(2026, 11, 5, 0, 0)
    assert srv.clinica.crear_mascota(cliente, "Mora", "Perro", fecha_nacimiento=date(2026, 11, 5))


def test_mascota_historica_con_nacimiento_futuro_se_sigue_consultando(base, tmp_path):
    srv, _, mascota, _ = base
    con = abrir_conexion(tmp_path / "vet.db")
    try:
        historica = MascotaDAO(con).obtener_por_id(mascota)
        historica.fecha_nacimiento = date(2030, 1, 1)
        MascotaDAO(con).actualizar(historica)
        con.commit()
    finally:
        con.close()
    esperado = srv.clinica.listar_mascotas()
    assert esperado[0]["fecha_nacimiento"] == "01/01/2030"
    assert Servicios(tmp_path / "vet.db").clinica.listar_mascotas() == esperado


@pytest.mark.parametrize("inicio, campo", [
    (datetime(2026, 11, 3, 11), "Fecha"),
    (datetime(2026, 11, 4, 10, 29), "Hora"),
    (datetime(2026, 11, 4, 0), "Hora"),
])
def test_turno_pasado_no_se_persiste(base, inicio, campo):
    srv, _, mascota, vet = base
    with pytest.raises(ErrorNegocio) as error:
        srv.clinica.agendar_turno(vet, mascota, inicio, inicio + timedelta(minutes=30))
    assert error.value.campo == campo and srv.clinica.listar_turnos() == []


@pytest.mark.parametrize("inicio", [
    datetime(2026, 11, 4, 10, 30), datetime(2026, 11, 4, 10, 31), datetime(2026, 11, 5, 9),
])
def test_turno_minuto_actual_o_futuro_se_persiste(base, tmp_path, inicio):
    srv, _, mascota, vet = base
    turno = srv.clinica.agendar_turno(vet, mascota, inicio, inicio + timedelta(minutes=30))
    filas = Servicios(tmp_path / "vet.db").clinica.listar_turnos()
    assert len(filas) == 1 and filas[0]["id"] == turno and filas[0]["inicio"] == inicio


@pytest.mark.parametrize("fin", [datetime(2026, 11, 4, 11), datetime(2026, 11, 4, 10, 59)])
def test_fin_de_turno_sigue_validado_por_dominio(base, fin):
    srv, _, mascota, vet = base
    with pytest.raises(ErrorNegocio, match="posterior al inicio") as error:
        srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 4, 11), fin)
    assert error.value.campo == "Hora" and srv.clinica.listar_turnos() == []


def test_agenda_superposicion_y_turnos_consecutivos_se_conservan(base):
    srv, _, mascota, vet = base
    srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 4, 11), datetime(2026, 11, 4, 11, 30))
    srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 4, 11, 30), datetime(2026, 11, 4, 12))
    with pytest.raises(ErrorNegocio, match="superpone"):
        srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 4, 11, 15), datetime(2026, 11, 4, 11, 45))
    with pytest.raises(ErrorNegocio, match="fuera de la agenda"):
        srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 4, 19), datetime(2026, 11, 4, 20))
    assert len(srv.clinica.listar_turnos()) == 2


def test_turno_historico_se_reconstruye_y_cambia_estado_segun_dominio(base, reloj, tmp_path):
    srv, _, mascota, vet = base
    turno = srv.clinica.agendar_turno(
        vet, mascota, datetime(2026, 11, 5, 9), datetime(2026, 11, 5, 9, 30))
    reloj["ahora"] = datetime(2027, 1, 1, 12)
    srv = Servicios(tmp_path / "vet.db")
    assert srv.clinica.listar_turnos()[0]["id"] == turno
    with pytest.raises(ErrorNegocio, match="CONFIRMADO"):
        srv.clinica.cambiar_estado_turno(turno, "atender")
    srv.clinica.cambiar_estado_turno(turno, "confirmar")
    srv.clinica.cambiar_estado_turno(turno, "atender")
    assert Servicios(tmp_path / "vet.db").clinica.listar_turnos()[0]["estado"] == "ATENDIDO"
    with pytest.raises(ErrorNegocio, match="fecha pasada"):
        srv.clinica.agendar_turno(vet, mascota, datetime(2026, 11, 5, 10), datetime(2026, 11, 5, 10, 30))
