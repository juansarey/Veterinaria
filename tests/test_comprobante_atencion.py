from datetime import datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.comprobante_atencion import ComprobanteAtencion
from veterinaria.dominio.clinica.veterinario import Veterinario


@pytest.fixture
def atencion():
    return Atencion(
        1,
        datetime(2026, 10, 12, 9),
        TipoAtencion.CONSULTA,
        "Control general",
        Veterinario(1, "Ana", "Pérez", "MP-100"),
        "Sin alteraciones",
        "Control realizado",
    )


@pytest.fixture
def fecha_emision():
    return datetime(2026, 10, 12, 10)


def test_construccion_valida_conserva_datos(atencion, fecha_emision):
    comprobante = ComprobanteAtencion(1, atencion, fecha_emision)

    assert comprobante.id_comprobante == 1
    assert comprobante.atencion is atencion
    assert comprobante.fecha_emision == fecha_emision


def test_atencion_obligatoria(fecha_emision):
    with pytest.raises(ValueError, match="atención"):
        ComprobanteAtencion(1, None, fecha_emision)


def test_fecha_emision_obligatoria(atencion):
    with pytest.raises(ValueError, match="fecha"):
        ComprobanteAtencion(1, atencion, None)


def test_construccion_no_modifica_atencion_ni_agrega_referencia_inversa(
    atencion, fecha_emision
):
    atributos_anteriores = vars(atencion).copy()
    ordenes_anteriores = atencion.obtener_ordenes_derivacion()

    comprobante = ComprobanteAtencion(1, atencion, fecha_emision)

    assert comprobante.atencion is atencion
    assert vars(atencion) == atributos_anteriores
    assert atencion.obtener_ordenes_derivacion() == ordenes_anteriores
    assert all(valor is not comprobante for valor in vars(atencion).values())
