"""Derivación, empaquetado, envío, recepción y resultados (procesos 3 a 7)."""

from datetime import datetime

from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    EstadoOrden,
    OrdenDerivacionLaboratorio,
)
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.dominio.transporte.conservadora_isotermica import ConservadoraIsotermica
from veterinaria.dominio.transporte.envio import Envio, EstadoEnvio
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito, RemitoBiologico
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.conservadora_isotermica_dao import ConservadoraIsotermicaDAO
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO
from veterinaria.persistencia.orden_derivacion_laboratorio_dao import (
    OrdenDerivacionLaboratorioDAO,
)
from veterinaria.persistencia.precinto_sanitario_dao import PrecintoSanitarioDAO
from veterinaria.persistencia.recepcion_dao import RecepcionDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO
from veterinaria.persistencia.resultado_analisis_dao import ResultadoAnalisisDAO
from veterinaria.servicios.base import ServicioBase, ahora, fmt_fecha_hora, requerir_texto
from veterinaria.servicios.errores import ErrorNegocio


class LaboratorioServicio(ServicioBase):
    # ---------------------------------------------------------------- órdenes
    def crear_orden(self, id_atencion, estudio_solicitado, observaciones="",
                    fecha_emision: datetime | None = None) -> int:
        with self._tx() as con:
            return self._crear_orden(con, id_atencion, estudio_solicitado, observaciones, fecha_emision)

    def _crear_orden(self, con, id_atencion, estudio_solicitado, observaciones, fecha_emision) -> int:
        estudio = requerir_texto(estudio_solicitado, "Estudio solicitado")
        atencion = AtencionDAO(con).obtener_por_id(id_atencion)
        if atencion is None:
            raise ErrorNegocio("La atención no existe.")
        orden = OrdenDerivacionLaboratorio(
            self._siguiente_id(con, "orden_derivacion_laboratorio"),
            fecha_emision or ahora(), estudio, (observaciones or "").strip(),
        )
        atencion.agregar_orden_derivacion(orden)
        OrdenDerivacionLaboratorioDAO(con).crear(orden, id_atencion)
        return orden.id_orden

    def derivar(self, id_atencion, estudio_solicitado, tipo_muestra,
                fecha_extraccion: datetime | None = None, observaciones="") -> dict:
        """Emite la orden de derivación y registra su muestra (EXTRAIDA) en un solo paso."""
        fecha = fecha_extraccion or ahora()
        with self._tx() as con:
            id_orden = self._crear_orden(con, id_atencion, estudio_solicitado, observaciones, fecha)
            id_muestra = self._registrar_muestra(con, id_orden, tipo_muestra, fecha, "")
            return {"id_orden": id_orden, "id_muestra": id_muestra}

    def listar_ordenes(self) -> list[dict]:
        with self._lectura() as con:
            orden_dao, muestra_dao = OrdenDerivacionLaboratorioDAO(con), MuestraBiologicaDAO(con)
            filas = []
            for a in AtencionDAO(con).listar():
                for o in orden_dao.listar_por_atencion(a.id_atencion):
                    filas.append({
                        "id": o.id_orden, "id_atencion": a.id_atencion,
                        "fecha": fmt_fecha_hora(o.fecha_emision),
                        "estudio": o.estudio_solicitado, "estado": o.estado.name,
                        "muestras": len(muestra_dao.listar_por_orden(o.id_orden)),
                        "etiqueta": f"Orden #{o.id_orden} - {o.estudio_solicitado}",
                    })
            return sorted(filas, key=lambda f: f["id"])

    def cancelar_orden(self, id_orden):
        with self._tx() as con:
            dao = OrdenDerivacionLaboratorioDAO(con)
            orden = dao.obtener_por_id(id_orden)
            if orden is None:
                raise ErrorNegocio("La orden no existe.")
            if not orden.cancelar():
                raise ErrorNegocio("Sólo se pueden cancelar órdenes pendientes o en proceso.")
            dao.actualizar(orden)

    # ---------------------------------------------------------------- muestras
    def registrar_muestra(self, id_orden, tipo_muestra, fecha_extraccion: datetime,
                          observaciones="") -> int:
        """RN06: toda muestra nace en estado EXTRAIDA."""
        with self._tx() as con:
            return self._registrar_muestra(con, id_orden, tipo_muestra, fecha_extraccion, observaciones)

    def _registrar_muestra(self, con, id_orden, tipo_muestra, fecha_extraccion, observaciones) -> int:
        tipo = requerir_texto(tipo_muestra, "Tipo de muestra")
        orden = OrdenDerivacionLaboratorioDAO(con).obtener_por_id(id_orden)
        if orden is None:
            raise ErrorNegocio("La orden no existe.")
        muestra = MuestraBiologica(self._siguiente_id(con, "muestra_biologica"), tipo,
                                   fecha_extraccion, (observaciones or "").strip())
        if not orden.agregar_muestra(muestra):
            raise ErrorNegocio("La orden no admite más muestras (finalizada o cancelada).")
        MuestraBiologicaDAO(con).crear(muestra, id_orden)
        return muestra.id_muestra

    def listar_muestras(self) -> list[dict]:
        from veterinaria.servicios.atencion_servicio import AtencionServicio
        from veterinaria.servicios.clinica_servicio import ClinicaServicio

        atencion_de = {a["id"]: a for a in AtencionServicio(self._ruta).listar_atenciones()}
        clinica_de = {v["id"]: v for v in ClinicaServicio(self._ruta).listar_veterinarios()}
        with self._lectura() as con:
            remito_de = {}
            for r in RemitoBiologicoDAO(con).listar():
                for m in r.obtener_muestras():
                    remito_de[m.id_muestra] = r.id_remito
            orden_dao, muestra_dao = OrdenDerivacionLaboratorioDAO(con), MuestraBiologicaDAO(con)
            resultado_dao = ResultadoAnalisisDAO(con)
            filas = []
            for a in AtencionDAO(con).listar():
                datos_at = atencion_de.get(a.id_atencion, {})
                vet = clinica_de.get(a.veterinario.id_veterinario, {})
                for o in orden_dao.listar_por_atencion(a.id_atencion):
                    for m in muestra_dao.listar_por_orden(o.id_orden):
                        estado = m.estado.obtener_nombre()
                        mascota, clinica = datos_at.get("mascota", ""), vet.get("clinica", "")
                        filas.append({
                            "id": m.id_muestra, "tipo": m.tipo_muestra, "estado": estado,
                            "estudio": o.estudio_solicitado, "id_orden": o.id_orden,
                            "id_atencion": a.id_atencion,
                            "id_remito": remito_de.get(m.id_muestra),
                            "mascota": mascota, "clinica": clinica,
                            "id_clinica": vet.get("id_clinica"),
                            "extraccion": fmt_fecha_hora(m.fecha_extraccion),
                            "resultado": "Sí" if resultado_dao.obtener_por_muestra(m.id_muestra) else "—",
                            "etiqueta": f"M-{m.id_muestra:04d} · {m.tipo_muestra} · {mascota} ({clinica})",
                        })
            return sorted(filas, key=lambda f: f["id"])

    def historial_muestra(self, id_muestra) -> list[dict]:
        """RN14/RN15: historial inmutable de estados."""
        with self._lectura() as con:
            muestra = MuestraBiologicaDAO(con).obtener_por_id(id_muestra)
            if muestra is None:
                raise ErrorNegocio("La muestra no existe.")
            return [{"estado": h.nombre_estado, "fecha": fmt_fecha_hora(h.fecha_hora),
                     "observaciones": h.observaciones}
                    for h in muestra.obtener_historial()]

    # ----------------------------------------------------------- conservadoras
    def crear_conservadora(self, codigo) -> int:
        codigo = requerir_texto(codigo, "Código")
        with self._tx() as con:
            id_c = self._siguiente_id(con, "conservadora_isotermica")
            ConservadoraIsotermicaDAO(con).crear(ConservadoraIsotermica(id_c, codigo))
        return id_c

    def listar_conservadoras(self, solo_disponibles=False) -> list[dict]:
        with self._lectura() as con:
            return [
                {"id": c.id_conservadora, "codigo": c.codigo, "estado": c.estado.name,
                 "etiqueta": f"{c.codigo} ({c.estado.name})"}
                for c in ConservadoraIsotermicaDAO(con).listar()
                if not solo_disponibles or c.esta_disponible()
            ]

    def liberar_conservadora(self, id_conservadora):
        """La liberación no es automática: la decide el usuario tras la recepción."""
        with self._tx() as con:
            dao = ConservadoraIsotermicaDAO(con)
            c = dao.obtener_por_id(id_conservadora)
            if c is None:
                raise ErrorNegocio("La conservadora no existe.")
            envio_dao, recepcion_dao = EnvioDAO(con), RecepcionDAO(con)
            for remito in RemitoBiologicoDAO(con).listar():
                if remito.conservadora.id_conservadora != id_conservadora:
                    continue
                if remito.estado != EstadoRemito.RECIBIDO:
                    raise ErrorNegocio("La conservadora tiene un remito pendiente de recepción.")
                envio = envio_dao.obtener_por_remito(remito.id_remito)
                if (envio is None or envio.estado != EstadoEnvio.ENTREGADO
                        or recepcion_dao.obtener_por_envio(envio.id_envio) is None):
                    raise ErrorNegocio("La conservadora tiene un remito sin recepción registrada.")
            if not c.liberar():
                raise ErrorNegocio("La conservadora ya está disponible.")
            dao.actualizar(c)

    # ------------------------------------------------------------------ remitos
    def crear_remito(self, id_clinica, id_conservadora, observaciones="",
                     fecha_emision: datetime | None = None) -> int:
        with self._tx() as con:
            return self._crear_remito(con, id_clinica, id_conservadora, observaciones, fecha_emision)

    def _crear_remito(self, con, id_clinica, id_conservadora, observaciones, fecha_emision) -> int:
        if id_clinica is None or id_conservadora is None:
            raise ErrorNegocio("Seleccione la clínica de origen y una conservadora.")
        clinica = ClinicaDAO(con).obtener_por_id(id_clinica)
        conservadora = ConservadoraIsotermicaDAO(con).obtener_por_id(id_conservadora)
        if clinica is None or conservadora is None:
            raise ErrorNegocio("La clínica o la conservadora no existen.")
        if not conservadora.esta_disponible():
            raise ErrorNegocio("La conservadora seleccionada no está disponible.")
        remito = RemitoBiologico(self._siguiente_id(con, "remito_biologico"), clinica,
                                 conservadora, fecha_emision or ahora(),
                                 (observaciones or "").strip())
        RemitoBiologicoDAO(con).crear(remito)         # persiste también la conservadora EN_USO
        return remito.id_remito

    def agregar_muestras_a_remito(self, id_remito, ids_muestra, fecha_hora: datetime | None = None,
                                  observaciones=""):
        """RN07: al empaquetar, la muestra pasa de EXTRAIDA a EMPAQUETADA."""
        with self._tx() as con:
            self._agregar_muestras(con, id_remito, ids_muestra, fecha_hora, observaciones)

    def _agregar_muestras(self, con, id_remito, ids_muestra, fecha_hora, observaciones,
                         muestras_validadas=None):
        remito_dao = RemitoBiologicoDAO(con)
        remito = remito_dao.obtener_por_id(id_remito)
        if remito is None:
            raise ErrorNegocio("El remito no existe.")
        muestras = muestras_validadas if muestras_validadas is not None else \
            self._validar_clinica_muestras(con, remito.clinica_origen.id_clinica, ids_muestra)
        for muestra in muestras:
            id_muestra = muestra.id_muestra
            if remito.estado != EstadoRemito.GENERADO:
                raise ErrorNegocio("El remito ya fue despachado: no admite más muestras.")
            if not remito.agregar_muestra(muestra, fecha_hora or ahora(),
                                          (observaciones or "").strip()):
                estado = muestra.estado.obtener_nombre()
                if estado == "EXTRAIDA":
                    raise ErrorNegocio(
                        f"La muestra #{id_muestra} no puede empaquetarse: la fecha de empaquetado "
                        "no puede ser anterior a la extracción."
                    )
                raise ErrorNegocio(
                    f"La muestra #{id_muestra} no puede empaquetarse "
                    f"(estado {estado}; debe estar EXTRAIDA)."
                )
            remito_dao.guardar_muestra_asociada(remito, muestra)

    @staticmethod
    def _validar_clinica_muestras(con, id_clinica, ids_muestra):
        """Valida el lote completo antes de empaquetar o persistir sus muestras."""
        if not ids_muestra:
            raise ErrorNegocio("Seleccione al menos una muestra.")
        dao = MuestraBiologicaDAO(con)
        muestras = []
        for id_muestra in ids_muestra:
            muestra = dao.obtener_por_id(id_muestra)
            if muestra is None:
                raise ErrorNegocio(f"La muestra #{id_muestra} no existe.")
            if dao.obtener_id_clinica_origen(id_muestra) != id_clinica:
                raise ErrorNegocio(
                    f"La muestra #{id_muestra} pertenece a otra clínica de origen."
                )
            muestras.append(muestra)
        return muestras

    def asignar_precinto(self, id_remito, codigo) -> int:
        with self._tx() as con:
            return self._asignar_precinto(con, id_remito, codigo)

    def _asignar_precinto(self, con, id_remito, codigo) -> int:
        codigo = requerir_texto(codigo, "Código del precinto")
        remito = RemitoBiologicoDAO(con).obtener_por_id(id_remito)
        if remito is None:
            raise ErrorNegocio("El remito no existe.")
        precinto = PrecintoSanitario(self._siguiente_id(con, "precinto_sanitario"), codigo)
        if not remito.asignar_precinto(precinto):
            raise ErrorNegocio("El remito ya tiene un precinto sanitario.")
        PrecintoSanitarioDAO(con).crear(precinto, id_remito)
        return precinto.id_precinto

    def empaquetar(self, id_clinica, id_conservadora, ids_muestra, codigo_precinto="",
                   fecha: datetime | None = None, observaciones="") -> dict:
        """Genera el remito, empaqueta las muestras y coloca el precinto en un solo paso."""
        if not ids_muestra:
            raise ErrorNegocio("Seleccione al menos una muestra.")
        fecha = fecha or ahora()
        with self._tx() as con:
            muestras = self._validar_clinica_muestras(con, id_clinica, ids_muestra)
            id_remito = self._crear_remito(con, id_clinica, id_conservadora, observaciones, fecha)
            self._agregar_muestras(con, id_remito, ids_muestra, fecha, "", muestras)
            codigo = (codigo_precinto or "").strip() or \
                f"PRE-{self._siguiente_id(con, 'precinto_sanitario'):05d}"
            self._asignar_precinto(con, id_remito, codigo)
            return {"id_remito": id_remito, "precinto": codigo, "muestras": len(ids_muestra)}

    def romper_precinto(self, id_remito):
        """Registra la rotura del precinto durante el traslado (antes de la recepción)."""
        with self._tx() as con:
            self._romper_precinto(con, id_remito)

    def _romper_precinto(self, con, id_remito):
        remito = RemitoBiologicoDAO(con).obtener_por_id(id_remito)
        if remito is None or remito.obtener_precinto() is None:
            raise ErrorNegocio("El remito no existe o no tiene precinto.")
        if remito.estado == EstadoRemito.RECIBIDO:
            raise ErrorNegocio("El remito ya fue recibido.")
        precinto = remito.obtener_precinto()
        if not precinto.marcar_roto():
            raise ErrorNegocio("El precinto ya está roto.")
        PrecintoSanitarioDAO(con).actualizar(precinto)

    def listar_remitos(self) -> list[dict]:
        with self._lectura() as con:
            envio_dao = EnvioDAO(con)
            filas = []
            for r in RemitoBiologicoDAO(con).listar():
                p, envio = r.obtener_precinto(), envio_dao.obtener_por_remito(r.id_remito)
                filas.append({
                    "id": r.id_remito, "id_conservadora": r.conservadora.id_conservadora,
                    "fecha": fmt_fecha_hora(r.fecha_emision),
                    "clinica": r.clinica_origen.nombre, "conservadora": r.conservadora.codigo,
                    "estado": r.estado.name, "muestras": len(r.obtener_muestras()),
                    "precinto": f"{p.codigo} ({p.estado.name})" if p else "—",
                    "puede_despacharse": r.puede_despacharse(),
                    "id_envio": envio.id_envio if envio else None,
                    "estado_envio": envio.estado.name if envio else None,
                    "etiqueta": f"Remito #{r.id_remito} - {r.clinica_origen.nombre} ({r.estado.name})",
                })
            return sorted(filas, key=lambda f: f["id"])

    # ------------------------------------------------------------ envío (RN08/09)
    def despachar_remito(self, id_remito, fecha_salida: datetime | None = None,
                         observaciones="") -> int:
        with self._tx() as con:
            remito = RemitoBiologicoDAO(con).obtener_por_id(id_remito)
            if remito is None:
                raise ErrorNegocio("El remito no existe.")
            motivo = self._motivo_no_despachable(remito)
            if motivo:
                raise ErrorNegocio(motivo)
            envio = Envio(self._siguiente_id(con, "envio"), remito, (observaciones or "").strip())
            envio_dao = EnvioDAO(con)
            envio_dao.crear(envio)
            if not envio.iniciar(fecha_salida or ahora()):
                raise ErrorNegocio("No se pudo despachar: revise las fechas de las muestras.")
            envio_dao.guardar_despacho(envio)
            return envio.id_envio

    @staticmethod
    def _motivo_no_despachable(remito) -> str | None:
        if remito.estado != EstadoRemito.GENERADO:
            return "El remito ya fue despachado."
        if remito.conservadora is None:
            return "El remito no tiene conservadora isotérmica."
        if not remito.obtener_muestras():
            return "El remito no tiene muestras."
        precinto = remito.obtener_precinto()
        if precinto is None:
            return "El remito no tiene precinto sanitario."
        if not precinto.esta_intacto():
            return "El precinto sanitario está roto: el remito no puede despacharse."
        return None

    def registrar_llegada(self, id_envio, fecha_llegada: datetime | None = None):
        with self._tx() as con:
            self._registrar_llegada(con, id_envio, fecha_llegada)

    def _registrar_llegada(self, con, id_envio, fecha_llegada):
        dao = EnvioDAO(con)
        envio = dao.obtener_por_id(id_envio)
        if envio is None:
            raise ErrorNegocio("El envío no existe.")
        if not envio.registrar_llegada(fecha_llegada or ahora()):
            raise ErrorNegocio(
                "No se pudo registrar la llegada (el envío debe estar en tránsito y la "
                "llegada no puede ser anterior a la salida)."
            )
        dao.actualizar(envio)

    def listar_envios(self) -> list[dict]:
        with self._lectura() as con:
            envio_dao, recepcion_dao = EnvioDAO(con), RecepcionDAO(con)
            filas = []
            for r in RemitoBiologicoDAO(con).listar():
                e = envio_dao.obtener_por_remito(r.id_remito)
                if e is None:
                    continue
                rec = recepcion_dao.obtener_por_envio(e.id_envio)
                p = r.obtener_precinto()
                filas.append({
                    "id": e.id_envio, "id_remito": r.id_remito, "estado": e.estado.name,
                    "salida": fmt_fecha_hora(e.fecha_hora_salida),
                    "llegada": fmt_fecha_hora(e.fecha_hora_llegada) or "—",
                    "precinto": p.estado.name if p else "—",
                    "recepcion": fmt_fecha_hora(rec.fecha_hora) if rec else "—",
                    "recibido": rec is not None,
                    "etiqueta": f"Envío #{e.id_envio} (remito #{r.id_remito}) - {e.estado.name}",
                })
            return sorted(filas, key=lambda f: f["id"])

    # -------------------------------------------------------- recepción (RN10-12)
    def registrar_recepcion(self, id_envio, fecha_hora: datetime | None = None,
                            observaciones="") -> dict:
        """Verifica el precinto: INTACTO → RECIBIDA; ROTO → RECHAZADA."""
        with self._tx() as con:
            return self._registrar_recepcion(con, id_envio, fecha_hora, observaciones)

    def _registrar_recepcion(self, con, id_envio, fecha_hora, observaciones) -> dict:
        envio = EnvioDAO(con).obtener_por_id(id_envio)
        if envio is None:
            raise ErrorNegocio("El envío no existe.")
        if RecepcionDAO(con).obtener_por_envio(id_envio) is not None:
            raise ErrorNegocio("El envío ya fue recepcionado.")
        if envio.fecha_hora_llegada is None:
            raise ErrorNegocio("Registre primero la llegada del envío.")
        recepcion = Recepcion(self._siguiente_id(con, "recepcion"), envio,
                              fecha_hora or ahora(), (observaciones or "").strip())
        intacto = recepcion.verificar_precinto()
        if not recepcion.procesar_recepcion():
            raise ErrorNegocio(
                "No se pudo procesar la recepción (la fecha no puede ser anterior a la llegada)."
            )
        RecepcionDAO(con).guardar_recepcion(recepcion)
        return {
            "precinto_intacto": intacto,
            "resultado": "ACEPTADO" if intacto else "RECHAZADO",
            "muestras": [(m.id_muestra, m.estado.obtener_nombre())
                         for m in envio.remito.obtener_muestras()],
        }

    def recibir_remito(self, id_envio, precinto_integro: bool, fecha: datetime | None = None,
                       observaciones="") -> dict:
        """Recepción en un paso: registra la llegada, anota el estado real del precinto
        (si llegó roto queda ROTO) y verifica el precinto (RN10-RN12)."""
        fecha = fecha or ahora()
        with self._tx() as con:
            envio = EnvioDAO(con).obtener_por_id(id_envio)
            if envio is None:
                raise ErrorNegocio("El envío no existe.")
            if envio.fecha_hora_llegada is None:
                self._registrar_llegada(con, id_envio, fecha)
            if not precinto_integro:
                self._romper_precinto(con, envio.remito.id_remito)
            return self._registrar_recepcion(con, id_envio, fecha, observaciones)

    # ------------------------------------------------------------ resultados (RN13)
    def registrar_resultado(self, id_muestra, resultado, observaciones="",
                            fecha_resultado: datetime | None = None) -> int:
        contenido = requerir_texto(resultado, "Resultado")
        with self._tx() as con:
            muestra = MuestraBiologicaDAO(con).obtener_por_id(id_muestra)
            if muestra is None:
                raise ErrorNegocio("La muestra no existe.")
            estado = muestra.estado.obtener_nombre()
            if estado == "RECHAZADA":
                raise ErrorNegocio("La muestra fue RECHAZADA (precinto roto): no puede analizarse.")
            if estado != "RECIBIDA":
                raise ErrorNegocio(f"La muestra está {estado}; debe estar RECIBIDA para analizarse.")
            res = ResultadoAnalisis(self._siguiente_id(con, "resultado_analisis"), muestra,
                                    fecha_resultado or ahora(), contenido,
                                    (observaciones or "").strip())
            if not res.registrar_resultado():
                raise ErrorNegocio("No se pudo registrar el resultado (revise la fecha).")
            ResultadoAnalisisDAO(con).guardar_resultado(res)
            self._actualizar_orden_de(con, id_muestra)
            return res.id_resultado

    @staticmethod
    def _actualizar_orden_de(con, id_muestra):
        """Pasa la orden a EN_PROCESO y, si todas sus muestras se analizaron, a COMPLETADA."""
        orden_dao, muestra_dao = OrdenDerivacionLaboratorioDAO(con), MuestraBiologicaDAO(con)
        for a in AtencionDAO(con).listar():
            for orden in orden_dao.listar_por_atencion(a.id_atencion):
                muestras = muestra_dao.listar_por_orden(orden.id_orden)
                if not any(m.id_muestra == id_muestra for m in muestras):
                    continue
                for m in muestras:
                    orden.agregar_muestra(m)
                if orden.estado == EstadoOrden.PENDIENTE:
                    orden.iniciar_proceso()
                if all(m.estado.obtener_nombre() == "ANALIZADA" for m in muestras):
                    orden.completar()
                orden_dao.actualizar(orden)
                return

    def listar_resultados(self) -> list[dict]:
        """Muestras analizadas con los datos de su resultado."""
        filas = []
        for m in self.listar_muestras():
            if m["estado"] != "ANALIZADA":
                continue
            r = self.obtener_resultado(m["id"])
            if r is not None:
                filas.append({**m, "id_txt": f"M-{m['id']:04d}", "fecha_resultado": r["fecha"],
                              "resumen": r["resultado"][:60]})
        return filas

    def obtener_comprobante_resultado(self, id_muestra) -> dict:
        """Datos del comprobante de resultados de una muestra analizada (para el PDF)."""
        from veterinaria.servicios.atencion_servicio import AtencionServicio
        from veterinaria.servicios.clinica_servicio import ClinicaServicio

        muestra = next((m for m in self.listar_muestras() if m["id"] == id_muestra), None)
        if muestra is None:
            raise ErrorNegocio("La muestra no existe.")
        resultado = self.obtener_resultado(id_muestra)
        if resultado is None:
            raise ErrorNegocio("La muestra todavía no tiene un resultado registrado.")
        recepcion = next((h["fecha"] for h in self.historial_muestra(id_muestra)
                          if h["estado"] == "RECIBIDA"), "")
        atencion = next(a for a in AtencionServicio(self._ruta).listar_atenciones()
                        if a["id"] == muestra["id_atencion"])
        mascota = next(m for m in ClinicaServicio(self._ruta).listar_mascotas()
                       if m["id"] == atencion["id_mascota"])
        remito = next((r for r in self.listar_remitos() if r["id"] == muestra["id_remito"]), {})
        return {
            "numero": f"RES-{resultado['id']:04d}", "fecha_emision": fmt_fecha_hora(ahora()),
            "muestra": f"M-{muestra['id']:04d}", "tipo_muestra": muestra["tipo"],
            "estudio": muestra["estudio"], "mascota": mascota["etiqueta"].split(" [#")[0],
            "responsable": mascota["responsable"], "clinica": muestra["clinica"],
            "veterinario": atencion["veterinario"], "remito": f"R-{remito['id']:04d}" if remito else "—",
            "precinto": remito.get("precinto", "—"), "extraccion": muestra["extraccion"],
            "recepcion": recepcion, "fecha_resultado": resultado["fecha"],
            "resultado": resultado["resultado"], "observaciones": resultado["observaciones"],
        }

    def obtener_resultado(self, id_muestra) -> dict | None:
        with self._lectura() as con:
            r = ResultadoAnalisisDAO(con).obtener_por_muestra(id_muestra)
            if r is None:
                return None
            return {"id": r.id_resultado, "fecha": fmt_fecha_hora(r.fecha_resultado),
                    "resultado": r.resultado, "observaciones": r.observaciones}
