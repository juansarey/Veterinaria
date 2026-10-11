class ResultadoAnalisis:
    def __init__(
        self,
        id_resultado: int,
        muestra,
        fecha_resultado,
        resultado,
        observaciones: str = "",
    ):
        if muestra is None:
            raise ValueError("Un resultado debe tener una muestra.")

        if fecha_resultado is None:
            raise ValueError("Un resultado debe tener una fecha.")

        if resultado is None:
            raise ValueError("El contenido del resultado es obligatorio.")

        self.id_resultado = id_resultado
        self.muestra = muestra
        self.fecha_resultado = fecha_resultado
        self.resultado = resultado
        self.observaciones = observaciones

    def registrar_resultado(self):
        return self.muestra.analizar(
            self.fecha_resultado,
            self.observaciones,
        )
