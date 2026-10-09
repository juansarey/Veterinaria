from datetime import datetime, timedelta

import pytest

from veterinaria.dominio.clinica.turno import EstadoTurno, Turno


@pytest.fixture
def turno():
    return Turno(1, datetime(2026, 10, 12, 9), datetime(2026, 10, 12, 10))


def test_turno_valido_nace_pendiente(turno):
    assert turno.estado == EstadoTurno.PENDIENTE
    assert turno.fecha_hora_inicio == datetime(2026, 10, 12, 9)
    assert turno.fecha_hora_fin == datetime(2026, 10, 12, 10)


@pytest.mark.parametrize("duracion", [timedelta(0), timedelta(minutes=-1)])
def test_rechaza_fin_igual_o_anterior_al_inicio(duracion):
    inicio = datetime(2026, 10, 12, 9)
    with pytest.raises(ValueError, match="posterior"):
        Turno(1, inicio, inicio + duracion)


@pytest.mark.parametrize(
    "hora_inicio,minuto_inicio,hora_fin,minuto_fin,esperado",
    [
        (9, 0, 10, 0, True),
        (8, 30, 9, 30, True),
        (9, 30, 10, 30, True),
        (9, 15, 9, 45, True),
        (8, 0, 11, 0, True),
        (8, 0, 9, 0, False),
        (10, 0, 11, 0, False),
        (11, 0, 12, 0, False),
    ],
)
def test_compara_intervalos_en_ambos_sentidos(
    turno, hora_inicio, minuto_inicio, hora_fin, minuto_fin, esperado
):
    otro = Turno(
        2,
        datetime(2026, 10, 12, hora_inicio, minuto_inicio),
        datetime(2026, 10, 12, hora_fin, minuto_fin),
    )
    assert turno.se_superpone_con(otro) is esperado
    assert otro.se_superpone_con(turno) is esperado


def test_mismos_horarios_en_fechas_distintas_no_se_superponen(turno):
    otro = Turno(2, datetime(2026, 10, 19, 9), datetime(2026, 10, 19, 10))
    assert not turno.se_superpone_con(otro)


@pytest.mark.parametrize(
    "preparacion,operacion,resultado",
    [
        ((), "confirmar", EstadoTurno.CONFIRMADO),
        ((), "cancelar", EstadoTurno.CANCELADO),
        (("confirmar",), "marcar_atendido", EstadoTurno.ATENDIDO),
        (("confirmar",), "cancelar", EstadoTurno.CANCELADO),
    ],
)
def test_transiciones_permitidas(turno, preparacion, operacion, resultado):
    for paso in preparacion:
        getattr(turno, paso)()
    getattr(turno, operacion)()
    assert turno.estado == resultado


@pytest.mark.parametrize(
    "preparacion,operacion",
    [
        ((), "marcar_atendido"),
        (("confirmar",), "confirmar"),
        (("confirmar", "marcar_atendido"), "confirmar"),
        (("confirmar", "marcar_atendido"), "cancelar"),
        (("confirmar", "marcar_atendido"), "marcar_atendido"),
        (("cancelar",), "confirmar"),
        (("cancelar",), "cancelar"),
        (("cancelar",), "marcar_atendido"),
    ],
)
def test_transiciones_invalidas_conservan_estado(turno, preparacion, operacion):
    for paso in preparacion:
        getattr(turno, paso)()
    estado_anterior = turno.estado
    with pytest.raises(ValueError):
        getattr(turno, operacion)()
    assert turno.estado == estado_anterior


@pytest.mark.parametrize(
    "atributo,valor",
    [
        ("fecha_hora_inicio", datetime(2026, 10, 12, 8)),
        ("fecha_hora_fin", datetime(2026, 10, 12, 11)),
        ("estado", EstadoTurno.CANCELADO),
    ],
)
def test_horarios_y_estado_no_admiten_asignacion_directa(turno, atributo, valor):
    anterior = getattr(turno, atributo)
    with pytest.raises(AttributeError):
        setattr(turno, atributo, valor)
    assert getattr(turno, atributo) == anterior
