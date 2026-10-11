import pytest

from veterinaria.dominio.vacunacion.vacuna import Vacuna


@pytest.mark.parametrize("obligatoria", [True, False])
def test_informa_si_es_obligatoria(obligatoria):
    vacuna = Vacuna(1, "Antirrábica", "Perro", obligatoria)
    assert vacuna.es_obligatoria() is obligatoria


def test_conserva_la_especie():
    vacuna = Vacuna(1, "Triple felina", "Gato", True)
    assert vacuna.especie == "Gato"
