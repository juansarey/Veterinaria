class ComprobanteAtencion:
    """Comprobante cuya construcción representa su emisión."""

    def __init__(self, id_comprobante: int, atencion, fecha_emision):
        if atencion is None:
            raise ValueError("Un comprobante debe tener una atención.")

        if fecha_emision is None:
            raise ValueError("Un comprobante debe tener una fecha de emisión.")

        self.id_comprobante = id_comprobante
        self.atencion = atencion
        self.fecha_emision = fecha_emision
