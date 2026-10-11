from datetime import datetime

import pytest

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.veterinario import Veterinario


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
