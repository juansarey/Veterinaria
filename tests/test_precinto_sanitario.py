from veterinaria.dominio.transporte.precinto_sanitario import (
    EstadoPrecinto,
    PrecintoSanitario,
)


def test_estado_inicial_intacto():
    precinto = PrecintoSanitario(1, "PREC-001")

    assert precinto.estado == EstadoPrecinto.INTACTO
    assert precinto.esta_intacto() is True


def test_marca_precinto_roto():
    precinto = PrecintoSanitario(1, "PREC-001")

    assert precinto.marcar_roto() is True
    assert precinto.estado == EstadoPrecinto.ROTO
    assert precinto.esta_intacto() is False


def test_no_marca_dos_veces_roto():
    precinto = PrecintoSanitario(1, "PREC-001")
    precinto.marcar_roto()

    assert precinto.marcar_roto() is False
    assert precinto.estado == EstadoPrecinto.ROTO
