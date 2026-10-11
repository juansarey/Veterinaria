from datetime import date
from unittest.mock import patch

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna
from veterinaria.patrones.strategy.reporte_vacunas_pendientes import (
    ReporteVacunasPendientes,
)


FECHA = date(2026, 10, 12)


@pytest.fixture
def mascota():
    return Mascota(1, "Luna", "Perro", Cliente(1, "Juan", "Pérez", "12345678"))


@pytest.fixture
def vacuna():
    return Vacuna(1, "Antirrábica", "Perro", True)


@pytest.mark.parametrize("con_mascota,con_vacuna", [(False, False), (True, False), (False, True)])
def test_colecciones_vacias(mascota, vacuna, con_mascota, con_vacuna):
    reporte = ReporteVacunasPendientes(
        [mascota] if con_mascota else [], [vacuna] if con_vacuna else [], FECHA
    )

    assert reporte.generar() == []


def test_mascota_al_dia_no_genera_filas(mascota, vacuna):
    assert mascota.agregar_aplicacion_vacuna(AplicacionVacuna(1, vacuna, FECHA))

    assert ReporteVacunasPendientes([mascota], [vacuna], FECHA).generar() == []


def test_vacuna_pendiente_incluye_fecha_y_responsable(mascota, vacuna):
    assert ReporteVacunasPendientes([mascota], [vacuna], FECHA).generar() == [{
        "id_mascota": 1,
        "mascota": "Luna",
        "especie": "Perro",
        "id_responsable": 1,
        "responsable": "Juan Pérez",
        "id_vacuna": 1,
        "vacuna": "Antirrábica",
        "fecha_referencia": FECHA,
    }]


def test_varias_mascotas_y_vacunas_reutilizan_reglas_del_dominio(mascota, vacuna):
    otra = Mascota(2, "Sol", "Perro", Cliente(2, "Ana", "Gómez", "87654321"))
    segunda = Vacuna(2, "Séxtuple", "Perro", True)
    opcional = Vacuna(3, "Opcional", "Perro", False)
    felina = Vacuna(4, "Triple felina", "Gato", True)
    assert otra.agregar_aplicacion_vacuna(AplicacionVacuna(1, vacuna, FECHA))
    vacunas = [vacuna, segunda, opcional, felina]

    filas = ReporteVacunasPendientes([mascota, otra], vacunas, FECHA).generar()

    assert [(fila["id_mascota"], fila["id_vacuna"]) for fila in filas] == [
        (1, 1), (1, 2), (2, 2),
    ]
    assert filas[-1]["id_responsable"] == 2
    assert filas[-1]["responsable"] == "Ana Gómez"


def test_delega_consulta_con_catalogo_y_fecha_exactos(mascota, vacuna):
    # Una respuesta controlada demuestra que el reporte no vuelve a filtrar.
    vacuna.obligatoria = False
    vacunas = [vacuna]
    with patch.object(mascota, "obtener_vacunas_pendientes", return_value=[vacuna]) as consulta:
        filas = ReporteVacunasPendientes([mascota], vacunas, FECHA).generar()

    consulta.assert_called_once_with(vacunas, FECHA)
    assert filas[0]["id_vacuna"] == vacuna.id_vacuna


def test_no_modifica_mascotas_aplicaciones_ni_catalogo(mascota, vacuna):
    aplicacion = AplicacionVacuna(1, vacuna, date(2025, 1, 1), date(2026, 1, 1))
    assert mascota.agregar_aplicacion_vacuna(aplicacion)
    datos_mascota = vars(mascota).copy()
    datos_aplicacion = vars(aplicacion).copy()
    datos_vacuna = vars(vacuna).copy()
    mascotas, vacunas = [mascota], [vacuna]
    reporte = ReporteVacunasPendientes(mascotas, vacunas, FECHA)

    filas = reporte.generar()
    assert len(filas) == 1
    filas[0]["vacuna"] = "MODIFICADA"
    filas.clear()

    assert vars(mascota) == datos_mascota
    assert vars(aplicacion) == datos_aplicacion
    assert vars(vacuna) == datos_vacuna
    assert mascota.obtener_aplicaciones_vacuna() == [aplicacion]
    assert mascotas == [mascota]
    assert vacunas == [vacuna]
    assert reporte.generar()[0]["vacuna"] == "Antirrábica"
