import pytest

from veterinaria.patrones.strategy.estrategia_reporte import EstrategiaReporte
from veterinaria.patrones.strategy.generador_reportes import GeneradorReportes
from veterinaria.patrones.strategy.reporte_atenciones_derivaciones import (
    ReporteAtencionesDerivaciones,
)
from veterinaria.patrones.strategy.reporte_tiempos_transito_procesamiento import (
    ReporteTiemposTransitoProcesamiento,
)


def test_base_exige_implementar_generar():
    with pytest.raises(NotImplementedError):
        EstrategiaReporte().generar()


def test_constructor_rechaza_estrategia_ausente():
    with pytest.raises(ValueError, match="estrategia"):
        GeneradorReportes(None)


def test_delega_y_devuelve_el_resultado_sin_transformarlo():
    class EstrategiaPrueba(EstrategiaReporte):
        def __init__(self):
            self.llamadas = 0
            self.resultado = [{"cantidad": 2}]

        def generar(self):
            self.llamadas += 1
            return self.resultado

    estrategia = EstrategiaPrueba()
    generador = GeneradorReportes(estrategia)

    assert generador.estrategia is estrategia
    assert generador.generar_reporte() is estrategia.resultado
    assert estrategia.llamadas == 1


def test_cambia_entre_estrategias_concretas():
    generador = GeneradorReportes(ReporteAtencionesDerivaciones([]))
    assert generador.generar_reporte() == []

    nueva = ReporteTiemposTransitoProcesamiento([])
    assert generador.establecer_estrategia(nueva) is True
    assert generador.estrategia is nueva
    assert generador.generar_reporte() == [{
        "cantidad_envios_con_transito": 0,
        "tiempo_promedio_transito": None,
        "cantidad_muestras_procesadas": 0,
        "tiempo_promedio_procesamiento": None,
    }]


def test_rechaza_none_y_conserva_estrategia_anterior():
    estrategia = ReporteAtencionesDerivaciones([])
    generador = GeneradorReportes(estrategia)

    assert generador.establecer_estrategia(None) is False
    assert generador.estrategia is estrategia
    assert generador.generar_reporte() == []
