class GeneradorReportes:
    def __init__(self, estrategia):
        if estrategia is None:
            raise ValueError("El generador debe tener una estrategia.")

        self.estrategia = estrategia

    def establecer_estrategia(self, estrategia):
        if estrategia is None:
            return False

        self.estrategia = estrategia
        return True

    def generar_reporte(self) -> list:
        return self.estrategia.generar()
