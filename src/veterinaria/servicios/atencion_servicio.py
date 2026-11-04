"""Historias clínicas, vacunación, atenciones y comprobantes (procesos 2, 3 y 7)."""

from datetime import date, datetime

from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.comprobante_atencion import ComprobanteAtencion
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna
from veterinaria.persistencia.aplicacion_vacuna_dao import AplicacionVacunaDAO
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.comprobante_atencion_dao import ComprobanteAtencionDAO
from veterinaria.persistencia.historia_clinica_dao import HistoriaClinicaDAO
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.persistencia.orden_derivacion_laboratorio_dao import (
    OrdenDerivacionLaboratorioDAO,
)
from veterinaria.persistencia.vacuna_dao import VacunaDAO
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO
from veterinaria.servicios.base import ServicioBase, fmt_fecha_hora, requerir_texto
from veterinaria.servicios.errores import ErrorNegocio


class AtencionServicio(ServicioBase):
    # --------------------------------------------------------------- vacunas
    def crear_vacuna(self, nombre, especie, obligatoria: bool) -> int:
        nombre = requerir_texto(nombre, "Nombre")
        especie = requerir_texto(especie, "Especie")
        with self._tx() as con:
            id_vacuna = self._siguiente_id(con, "vacuna")
            VacunaDAO(con).crear(Vacuna(id_vacuna, nombre, especie, bool(obligatoria)))
        return id_vacuna

    def listar_vacunas(self) -> list[dict]:
        with self._lectura() as con:
            return [
                {"id": v.id_vacuna, "nombre": v.nombre, "especie": v.especie,
                 "obligatoria": "Sí" if v.obligatoria else "No",
                 "etiqueta": f"{v.nombre} ({v.especie})"}
                for v in VacunaDAO(con).listar()
            ]

    def registrar_aplicacion(self, id_mascota, id_vacuna, fecha_aplicacion: date,
                             fecha_proxima_dosis: date | None = None) -> int:
        with self._tx() as con:
            mascota = MascotaDAO(con).obtener_por_id(id_mascota)
            vacuna = VacunaDAO(con).obtener_por_id(id_vacuna)
            if mascota is None or vacuna is None:
                raise ErrorNegocio("La mascota o la vacuna no existen.")
            if vacuna.especie != mascota.especie:
                raise ErrorNegocio(f"La vacuna {vacuna.nombre} es para {vacuna.especie} "
                                   f"y {mascota.nombre} es {mascota.especie}.")
            id_aplicacion = self._siguiente_id(con, "aplicacion_vacuna")
            aplicacion = AplicacionVacuna(id_aplicacion, vacuna, fecha_aplicacion,
                                          fecha_proxima_dosis)
            mascota.agregar_aplicacion_vacuna(aplicacion)
            AplicacionVacunaDAO(con).crear(aplicacion, id_mascota)
        return id_aplicacion

    def listar_aplicaciones(self, id_mascota, fecha_referencia: date | None = None) -> list[dict]:
        ref = fecha_referencia or date.today()
        with self._lectura() as con:
            filas = []
            for a in AplicacionVacunaDAO(con).listar_por_mascota(id_mascota):
                if a.esta_vencida(ref):
                    estado = "VENCIDA"
                elif a.esta_vigente(ref):
                    estado = "VIGENTE"
                else:
                    estado = "FUTURA"
                filas.append({
                    "id": a.id_aplicacion, "vacuna": a.vacuna.nombre,
                    "fecha_aplicacion": fmt_fecha_hora(a.fecha_aplicacion),
                    "proxima_dosis": fmt_fecha_hora(a.fecha_proxima_dosis) or "—",
                    "estado": estado,
                })
            return filas

    def vacunas_pendientes(self, id_mascota, fecha_referencia: date | None = None) -> list[str]:
        """RN05: nombres de las vacunas obligatorias sin aplicación vigente."""
        ref = fecha_referencia or date.today()
        with self._lectura() as con:
            mascota = self._mascota_con_aplicaciones(con, id_mascota)
            return [v.nombre for v in
                    mascota.obtener_vacunas_pendientes(VacunaDAO(con).listar(), ref)]

    @staticmethod
    def _mascota_con_aplicaciones(con, id_mascota):
        mascota = MascotaDAO(con).obtener_por_id(id_mascota)
        if mascota is None:
            raise ErrorNegocio("La mascota no existe.")
        for aplicacion in AplicacionVacunaDAO(con).listar_por_mascota(id_mascota):
            mascota.agregar_aplicacion_vacuna(aplicacion)
        return mascota

    # ------------------------------------------------------ historia clínica
    def abrir_historia(self, id_mascota, observaciones="", fecha_apertura: date | None = None) -> int:
        with self._tx() as con:
            mascota = MascotaDAO(con).obtener_por_id(id_mascota)
            if mascota is None:
                raise ErrorNegocio("La mascota no existe.")
            dao = HistoriaClinicaDAO(con)
            if dao.obtener_por_mascota(id_mascota) is not None:
                raise ErrorNegocio("La mascota ya tiene una historia clínica.")
            id_historia = self._siguiente_id(con, "historia_clinica")
            historia = HistoriaClinica(id_historia, fecha_apertura or date.today(),
                                       (observaciones or "").strip())
            mascota.asignar_historia_clinica(historia)
            dao.crear(historia, id_mascota)
        return id_historia

    def obtener_historia(self, id_mascota) -> dict | None:
        with self._lectura() as con:
            h = HistoriaClinicaDAO(con).obtener_por_mascota(id_mascota)
            if h is None:
                return None
            return {"id": h.id_historia, "fecha_apertura": fmt_fecha_hora(h.fecha_apertura),
                    "observaciones": h.observaciones}

    # ------------------------------------------------------------- atenciones
    def registrar_atencion(self, id_mascota, id_veterinario, fecha_hora: datetime,
                           tipo: TipoAtencion, motivo, diagnostico="", observaciones="") -> int:
        """Registra la atención sólo con historia abierta y vacunas obligatorias al día."""
        motivo = requerir_texto(motivo, "Motivo")
        with self._tx() as con:
            mascota = self._mascota_con_aplicaciones(con, id_mascota)
            historia = HistoriaClinicaDAO(con).obtener_por_mascota(id_mascota)
            if historia is None:
                raise ErrorNegocio("La mascota no tiene historia clínica: ábrala primero.")
            mascota.asignar_historia_clinica(historia)
            vet = VeterinarioDAO(con).obtener_por_id(id_veterinario)
            if vet is None:
                raise ErrorNegocio("El veterinario no existe.")

            atencion = Atencion(self._siguiente_id(con, "atencion"), fecha_hora, tipo, motivo,
                                vet, (diagnostico or "").strip(), (observaciones or "").strip())
            vacunas = VacunaDAO(con).listar()
            if not mascota.registrar_atencion(atencion, vacunas):
                pendientes = mascota.obtener_vacunas_pendientes(vacunas, fecha_hora.date())
                if pendientes:
                    nombres = ", ".join(v.nombre for v in pendientes)
                    raise ErrorNegocio(f"Vacunas obligatorias pendientes: {nombres}.")
                raise ErrorNegocio("No se pudo registrar la atención.")
            AtencionDAO(con).crear(atencion, historia.id_historia)
            return atencion.id_atencion

    def listar_atenciones(self, id_mascota=None) -> list[dict]:
        with self._lectura() as con:
            historia_dao, atencion_dao = HistoriaClinicaDAO(con), AtencionDAO(con)
            orden_dao, comprobante_dao = OrdenDerivacionLaboratorioDAO(con), ComprobanteAtencionDAO(con)
            filas = []
            for m in MascotaDAO(con).listar():
                if id_mascota is not None and m.id_mascota != id_mascota:
                    continue
                historia = historia_dao.obtener_por_mascota(m.id_mascota)
                if historia is None:
                    continue
                for a in atencion_dao.listar_por_historia(historia.id_historia):
                    v = a.veterinario
                    filas.append({
                        "id": a.id_atencion, "fecha_hora": a.fecha_hora,
                        "fecha_txt": fmt_fecha_hora(a.fecha_hora), "tipo": a.tipo.value,
                        "id_mascota": m.id_mascota, "mascota": m.nombre,
                        "id_veterinario": v.id_veterinario,
                        "veterinario": f"{v.apellido}, {v.nombre}",
                        "motivo": a.motivo, "diagnostico": a.diagnostico,
                        "derivaciones": len(orden_dao.listar_por_atencion(a.id_atencion)),
                        "comprobante": "Sí" if comprobante_dao.obtener_por_atencion(a.id_atencion)
                        else "No",
                        "etiqueta": f"#{a.id_atencion} {m.nombre} - {fmt_fecha_hora(a.fecha_hora)}",
                    })
            return sorted(filas, key=lambda f: f["fecha_hora"])

    # ------------------------------------------------------------ comprobantes
    def emitir_comprobante(self, id_atencion, fecha_emision: datetime | None = None) -> int:
        with self._tx() as con:
            atencion = AtencionDAO(con).obtener_por_id(id_atencion)
            if atencion is None:
                raise ErrorNegocio("La atención no existe.")
            dao = ComprobanteAtencionDAO(con)
            if dao.obtener_por_atencion(id_atencion) is not None:
                raise ErrorNegocio("La atención ya tiene un comprobante emitido.")
            id_comprobante = self._siguiente_id(con, "comprobante_atencion")
            dao.crear(ComprobanteAtencion(id_comprobante, atencion,
                                          fecha_emision or datetime.now()))
        return id_comprobante

    def obtener_comprobante(self, id_atencion) -> dict | None:
        """Datos completos del comprobante (para mostrarlo o exportarlo a PDF)."""
        with self._lectura() as con:
            comp = ComprobanteAtencionDAO(con).obtener_por_atencion(id_atencion)
            if comp is None:
                return None
            a = comp.atencion
            mascota = cliente = None
            historia_dao = HistoriaClinicaDAO(con)
            for m in MascotaDAO(con).listar():
                h = historia_dao.obtener_por_mascota(m.id_mascota)
                if h is not None and any(
                    x.id_atencion == a.id_atencion
                    for x in AtencionDAO(con).listar_por_historia(h.id_historia)
                ):
                    mascota, cliente = m, m.responsable
                    break
            return {
                "numero": comp.id_comprobante,
                "fecha_emision": fmt_fecha_hora(comp.fecha_emision),
                "id_atencion": a.id_atencion, "fecha_atencion": fmt_fecha_hora(a.fecha_hora),
                "tipo": a.tipo.value, "motivo": a.motivo, "diagnostico": a.diagnostico,
                "observaciones": a.observaciones,
                "veterinario": f"{a.veterinario.apellido}, {a.veterinario.nombre} "
                               f"(Mat. {a.veterinario.matricula})",
                "mascota": f"{mascota.nombre} ({mascota.especie})" if mascota else "",
                "responsable": f"{cliente.apellido}, {cliente.nombre} - DNI {cliente.dni}"
                               if cliente else "",
            }
