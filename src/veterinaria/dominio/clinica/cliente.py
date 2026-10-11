class Cliente:
    def __init__(
        self,
        id_cliente: int,
        nombre: str,
        apellido: str,
        dni: str,
        telefono: str = "",
        email: str = "",
    ):
        self.id_cliente = id_cliente
        self.nombre = nombre
        self.apellido = apellido
        self.dni = dni
        self.telefono = telefono
        self.email = email
