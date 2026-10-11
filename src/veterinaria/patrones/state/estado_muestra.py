class EstadoMuestra:
    nombre = ""

    def empaquetar(self, muestra, fecha_hora, observaciones=""):
        return False

    def despachar(self, muestra, fecha_hora, observaciones=""):
        return False

    def recibir(self, muestra, fecha_hora, observaciones=""):
        return False

    def rechazar(self, muestra, fecha_hora, observaciones=""):
        return False

    def analizar(self, muestra, fecha_hora, observaciones=""):
        return False

    def obtener_nombre(self):
        return self.nombre


class EstadoExtraida(EstadoMuestra):
    nombre = "EXTRAIDA"

    def empaquetar(self, muestra, fecha_hora, observaciones=""):
        return muestra._cambiar_estado(
            EstadoEmpaquetada(), fecha_hora, observaciones
        )


class EstadoEmpaquetada(EstadoMuestra):
    nombre = "EMPAQUETADA"

    def despachar(self, muestra, fecha_hora, observaciones=""):
        return muestra._cambiar_estado(
            EstadoEnTransito(), fecha_hora, observaciones
        )


class EstadoEnTransito(EstadoMuestra):
    nombre = "EN_TRANSITO"

    def recibir(self, muestra, fecha_hora, observaciones=""):
        return muestra._cambiar_estado(EstadoRecibida(), fecha_hora, observaciones)

    def rechazar(self, muestra, fecha_hora, observaciones=""):
        return muestra._cambiar_estado(
            EstadoRechazada(), fecha_hora, observaciones
        )


class EstadoRecibida(EstadoMuestra):
    nombre = "RECIBIDA"

    def analizar(self, muestra, fecha_hora, observaciones=""):
        return muestra._cambiar_estado(EstadoAnalizada(), fecha_hora, observaciones)


class EstadoAnalizada(EstadoMuestra):
    nombre = "ANALIZADA"


class EstadoRechazada(EstadoMuestra):
    nombre = "RECHAZADA"
