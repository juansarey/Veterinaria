from veterinaria.dominio.clinica.cliente import Cliente


def test_crea_cliente_con_sus_datos_basicos():
    cliente = Cliente(
        1,
        "Laura",
        "García",
        "30111222",
        "11-5555-1234",
        "laura@example.com",
    )

    assert cliente.id_cliente == 1
    assert cliente.nombre == "Laura"
    assert cliente.apellido == "García"
    assert cliente.dni == "30111222"
    assert cliente.telefono == "11-5555-1234"
    assert cliente.email == "laura@example.com"
