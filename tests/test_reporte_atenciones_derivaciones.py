from datetime import datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    OrdenDerivacionLaboratorio,
)
from veterinaria.patrones.strategy.reporte_atenciones_derivaciones import (
    ReporteAtencionesDerivaciones,
)


@pytest.fixture
def atencion():
    return Atencion(
        1, datetime(2026, 10, 12, 10), TipoAtencion.CONSULTA, "Control",
        Veterinario(1, "Ana", "Pérez", "MAT-001"),
    )


def test_lista_vacia():
    assert ReporteAtencionesDerivaciones([]).generar() == []


def test_atencion_sin_derivaciones(atencion):
    assert ReporteAtencionesDerivaciones([atencion]).generar() == [{
        "id_atencion": 1,
        "fecha_hora": datetime(2026, 10, 12, 10),
        "tipo": "CONSULTA",
        "id_veterinario": 1,
        "veterinario": "Ana Pérez",
        "cantidad_derivaciones": 0,
        "derivaciones": [],
    }]


@pytest.mark.parametrize("cantidad", [1, 3])
def test_agrupa_derivaciones_incluyendo_canceladas(atencion, cantidad):
    ordenes = [
        OrdenDerivacionLaboratorio(i, atencion.fecha_hora, f"Estudio {i}")
        for i in range(1, cantidad + 1)
    ]
    for orden in ordenes:
        assert atencion.agregar_orden_derivacion(orden)
    assert ordenes[-1].cancelar()

    fila = ReporteAtencionesDerivaciones([atencion]).generar()[0]

    assert fila["cantidad_derivaciones"] == cantidad
    assert fila["derivaciones"] == [
        {
            "id_orden": i,
            "estudio_solicitado": f"Estudio {i}",
            "estado": "CANCELADA" if i == cantidad else "PENDIENTE",
        }
        for i in range(1, cantidad + 1)
    ]


def test_multiples_atenciones_conservan_sus_derivaciones(atencion):
    otra = Atencion(
        2, atencion.fecha_hora, TipoAtencion.URGENCIA, "Dolor",
        Veterinario(2, "Luis", "Gómez", "MAT-002"),
    )
    orden = OrdenDerivacionLaboratorio(1, atencion.fecha_hora, "Hemograma")
    assert otra.agregar_orden_derivacion(orden)

    filas = ReporteAtencionesDerivaciones([atencion, otra]).generar()

    assert [fila["id_atencion"] for fila in filas] == [1, 2]
    assert [fila["cantidad_derivaciones"] for fila in filas] == [0, 1]
    assert filas[1]["veterinario"] == "Luis Gómez"
    assert filas[1]["tipo"] == "URGENCIA"


def test_no_modifica_atencion_orden_ni_colecciones(atencion):
    orden = OrdenDerivacionLaboratorio(1, atencion.fecha_hora, "Hemograma")
    assert atencion.agregar_orden_derivacion(orden)
    datos_atencion = vars(atencion).copy()
    datos_orden = vars(orden).copy()
    atenciones = [atencion]
    reporte = ReporteAtencionesDerivaciones(atenciones)

    filas = reporte.generar()
    filas[0]["derivaciones"][0]["estado"] = "MODIFICADO"
    filas[0]["derivaciones"].clear()
    filas.clear()

    assert vars(atencion) == datos_atencion
    assert vars(orden) == datos_orden
    assert atenciones == [atencion]
    assert atencion.obtener_ordenes_derivacion() == [orden]
    assert orden.obtener_muestras() == []
    assert reporte.generar()[0]["derivaciones"][0]["estado"] == "PENDIENTE"
