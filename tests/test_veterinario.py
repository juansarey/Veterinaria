from datetime import datetime, time

import pytest

from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana
from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.turno import EstadoTurno, Turno
from veterinaria.dominio.clinica.veterinario import Veterinario


@pytest.fixture
def veterinario():
    profesional = Veterinario(1, "Ana", "Pérez", "MP-100")
    profesional.asignar_agenda(
        AgendaMedica(
            {
                DiaSemana.LUNES,
                DiaSemana.MARTES,
                DiaSemana.JUEVES,
                DiaSemana.VIERNES,
            },
            time(9),
            time(12),
        )
    )
    return profesional


@pytest.fixture
def mascota():
    responsable = Cliente(1, "Laura", "García", "30111222")
    return Mascota(1, "Luna", "Perro", responsable)


def crear_turno(mascota, id_turno=1, inicio=(10, 0), fin=(11, 0), dia=12):
    return Turno(
        id_turno,
        datetime(2026, 10, dia, *inicio),
        datetime(2026, 10, dia, *fin),
        mascota,
    )


@pytest.mark.parametrize(
    "inicio,fin", [((10, 0), (11, 0)), ((9, 0), (12, 0))]
)
def test_registra_turno_dentro_de_agenda(veterinario, mascota, inicio, fin):
    turno = crear_turno(mascota, inicio=inicio, fin=fin)
    veterinario.agregar_turno(turno)
    assert veterinario.obtener_turnos() == [turno]


@pytest.mark.parametrize(
    "inicio,fin",
    [
        ((8, 59), (10, 0)),
        ((11, 0), (12, 1)),
    ],
)
def test_rechaza_turno_fuera_de_agenda_sin_registrarlo(veterinario, mascota, inicio, fin):
    turno = crear_turno(mascota, inicio=inicio, fin=fin)
    assert not veterinario.puede_agendar(turno)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(turno)
    assert veterinario.obtener_turnos() == []


def test_rechaza_turno_sin_agenda(mascota):
    profesional = Veterinario(1, "Ana", "Pérez", "MP-100")
    turno = crear_turno(mascota)
    assert not profesional.puede_agendar(turno)
    with pytest.raises(ValueError):
        profesional.agregar_turno(turno)
    assert profesional.obtener_turnos() == []


def test_rechaza_turno_en_dia_no_laboral(veterinario, mascota):
    turno = crear_turno(mascota, dia=14)
    assert not veterinario.puede_agendar(turno)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(turno)
    assert veterinario.obtener_turnos() == []


@pytest.mark.parametrize(
    "inicio,fin",
    [
        ((10, 0), (11, 0)),
        ((9, 30), (10, 30)),
        ((10, 30), (11, 30)),
        ((10, 15), (10, 45)),
        ((9, 0), (12, 0)),
    ],
)
def test_rechaza_superposiciones_sin_modificar_registro(veterinario, mascota, inicio, fin):
    existente = crear_turno(mascota)
    veterinario.agregar_turno(existente)
    nuevo = crear_turno(mascota, 2, inicio, fin)
    assert not veterinario.puede_agendar(nuevo)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(nuevo)
    assert veterinario.obtener_turnos() == [existente]


@pytest.mark.parametrize(
    "inicio,fin", [((9, 0), (10, 0)), ((11, 0), (12, 0))]
)
def test_acepta_turnos_consecutivos(veterinario, mascota, inicio, fin):
    existente = crear_turno(mascota)
    consecutivo = crear_turno(mascota, 2, inicio, fin)
    veterinario.agregar_turno(existente)
    veterinario.agregar_turno(consecutivo)
    assert veterinario.obtener_turnos() == [existente, consecutivo]


@pytest.mark.parametrize(
    "pasos,estado",
    [
        ((), EstadoTurno.PENDIENTE),
        (("confirmar",), EstadoTurno.CONFIRMADO),
        (("confirmar", "marcar_atendido"), EstadoTurno.ATENDIDO),
    ],
)
def test_todos_los_estados_no_cancelados_bloquean(veterinario, mascota, pasos, estado):
    existente = crear_turno(mascota)
    veterinario.agregar_turno(existente)
    for paso in pasos:
        getattr(existente, paso)()
    assert existente.estado == estado
    nuevo = crear_turno(mascota, 2)
    assert not veterinario.puede_agendar(nuevo)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(nuevo)
    assert veterinario.obtener_turnos() == [existente]


@pytest.mark.parametrize("confirmado", [False, True])
def test_cancelar_libera_horario_y_conserva_registro(veterinario, mascota, confirmado):
    existente = crear_turno(mascota)
    veterinario.agregar_turno(existente)
    if confirmado:
        existente.confirmar()
    existente.cancelar()
    nuevo = crear_turno(mascota, 2)
    assert veterinario.puede_agendar(nuevo)
    veterinario.agregar_turno(nuevo)
    assert veterinario.obtener_turnos() == [existente, nuevo]
    assert existente.estado == EstadoTurno.CANCELADO


def test_mismos_horarios_para_distintos_veterinarios(veterinario, mascota):
    otro = Veterinario(2, "Luis", "Gómez", "MP-101")
    otro.asignar_agenda(AgendaMedica({DiaSemana.LUNES}, time(9), time(12)))
    primero, segundo = crear_turno(mascota), crear_turno(mascota, 2)
    veterinario.agregar_turno(primero)
    otro.agregar_turno(segundo)
    assert veterinario.obtener_turnos() == [primero]
    assert otro.obtener_turnos() == [segundo]


def test_turnos_de_fechas_distintas_no_se_bloquean(veterinario, mascota):
    primero, segundo = crear_turno(mascota), crear_turno(mascota, 2, dia=19)
    veterinario.agregar_turno(primero)
    veterinario.agregar_turno(segundo)
    assert veterinario.obtener_turnos() == [primero, segundo]


def test_rechaza_turno_que_cruza_de_fecha(veterinario, mascota):
    turno = Turno(
        1,
        datetime(2026, 10, 12, 10),
        datetime(2026, 10, 13, 11),
        mascota,
    )
    assert not veterinario.puede_agendar(turno)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(turno)
    assert veterinario.obtener_turnos() == []


@pytest.mark.parametrize("ocupado", [False, True])
def test_puede_agendar_solo_consulta(veterinario, mascota, ocupado):
    if ocupado:
        veterinario.agregar_turno(crear_turno(mascota))
    turnos_antes = veterinario.obtener_turnos()
    agenda_antes = veterinario.obtener_agenda()
    nuevo = crear_turno(mascota, 2)

    assert veterinario.puede_agendar(nuevo) is (not ocupado)
    assert veterinario.puede_agendar(nuevo) is (not ocupado)

    assert veterinario.obtener_turnos() == turnos_antes
    assert veterinario.obtener_agenda() == agenda_antes
    assert nuevo.estado == EstadoTurno.PENDIENTE


def test_turnos_devueltos_son_una_copia(veterinario, mascota):
    turno = crear_turno(mascota)
    veterinario.agregar_turno(turno)
    veterinario.obtener_turnos().clear()
    assert veterinario.obtener_turnos() == [turno]


def test_rechaza_agregar_dos_veces_el_mismo_turno_cancelado(veterinario, mascota):
    turno = crear_turno(mascota)
    veterinario.agregar_turno(turno)
    turno.cancelar()
    assert not veterinario.puede_agendar(turno)
    with pytest.raises(ValueError):
        veterinario.agregar_turno(turno)
    assert veterinario.obtener_turnos() == [turno]


def test_asigna_una_agenda():
    profesional = Veterinario(1, "Ana", "Pérez", "MP-100")
    agenda = AgendaMedica({DiaSemana.LUNES}, time(8), time(13))
    profesional.asignar_agenda(agenda)
    assert profesional.obtener_agenda() is agenda
