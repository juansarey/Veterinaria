from datetime import datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    OrdenDerivacionLaboratorio,
)


@pytest.fixture
def atencion():
    veterinario = Veterinario(1, "Ana", "Pérez", "MP-100")
    return Atencion(
        1,
        datetime(2026, 10, 12, 9),
        TipoAtencion.CONSULTA,
        "Control general",
        veterinario,
    )


@pytest.fixture
def orden():
    return OrdenDerivacionLaboratorio(
        1,
        datetime(2026, 10, 12, 10),
        "Hemograma",
    )


@pytest.mark.parametrize(
    "tipo,valor",
    [
        (TipoAtencion.CONSULTA, "CONSULTA"),
        (TipoAtencion.CONTROL, "CONTROL"),
        (TipoAtencion.URGENCIA, "URGENCIA"),
    ],
)
def test_tipos_de_atencion(tipo, valor):
    assert tipo.value == valor


def test_conserva_referencia_al_veterinario():
    veterinario = Veterinario(1, "Ana", "Pérez", "MP-100")
    atencion = Atencion(
        1,
        datetime(2026, 10, 12, 9),
        TipoAtencion.CONSULTA,
        "Control general",
        veterinario,
    )

    assert atencion.veterinario is veterinario


def test_rechaza_veterinario_ausente():
    with pytest.raises(ValueError, match="veterinario"):
        Atencion(
            1,
            datetime(2026, 10, 12, 9),
            TipoAtencion.CONSULTA,
            "Control general",
            None,
        )


def test_registra_diagnostico():
    veterinario = Veterinario(1, "Ana", "Pérez", "MP-100")
    atencion = Atencion(
        1,
        datetime(2026, 10, 12, 9),
        TipoAtencion.CONSULTA,
        "Decaimiento",
        veterinario,
    )

    atencion.registrar_diagnostico("Gastritis leve")

    assert atencion.diagnostico == "Gastritis leve"


def test_atencion_comienza_sin_ordenes(atencion):
    assert atencion.obtener_ordenes_derivacion() == []


def test_agrega_orden_de_derivacion(atencion, orden):
    assert atencion.agregar_orden_derivacion(orden) is True
    assert atencion.obtener_ordenes_derivacion() == [orden]


def test_no_agrega_dos_veces_la_misma_orden(atencion, orden):
    atencion.agregar_orden_derivacion(orden)

    assert atencion.agregar_orden_derivacion(orden) is False
    assert atencion.obtener_ordenes_derivacion() == [orden]


def test_ordenes_devueltas_son_una_copia(atencion, orden):
    atencion.agregar_orden_derivacion(orden)
    atencion.obtener_ordenes_derivacion().clear()

    assert atencion.obtener_ordenes_derivacion() == [orden]
