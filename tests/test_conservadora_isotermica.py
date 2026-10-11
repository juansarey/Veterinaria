from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)


def test_estado_inicial_disponible():
    conservadora = ConservadoraIsotermica(1, "CONS-001")

    assert conservadora.estado == EstadoConservadora.DISPONIBLE
    assert conservadora.esta_disponible() is True


def test_marca_conservadora_en_uso():
    conservadora = ConservadoraIsotermica(1, "CONS-001")

    assert conservadora.marcar_en_uso() is True
    assert conservadora.estado == EstadoConservadora.EN_USO
    assert conservadora.esta_disponible() is False


def test_no_marca_dos_veces_en_uso():
    conservadora = ConservadoraIsotermica(1, "CONS-001")
    conservadora.marcar_en_uso()

    assert conservadora.marcar_en_uso() is False
    assert conservadora.estado == EstadoConservadora.EN_USO


def test_libera_conservadora_en_uso():
    conservadora = ConservadoraIsotermica(1, "CONS-001")
    conservadora.marcar_en_uso()

    assert conservadora.liberar() is True
    assert conservadora.estado == EstadoConservadora.DISPONIBLE
    assert conservadora.esta_disponible() is True


def test_no_libera_conservadora_disponible():
    conservadora = ConservadoraIsotermica(1, "CONS-001")

    assert conservadora.liberar() is False
    assert conservadora.estado == EstadoConservadora.DISPONIBLE
