from contextlib import closing
from datetime import date, datetime, time, timedelta

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.turno import EstadoTurno
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import EstadoOrden
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.dominio.transporte.conservadora_isotermica import EstadoConservadora
from veterinaria.dominio.transporte.envio import EstadoEnvio
from veterinaria.dominio.transporte.precinto_sanitario import EstadoPrecinto
from veterinaria.dominio.transporte.remito_biologico import EstadoRemito
from veterinaria.persistencia.agenda_medica_dao import AgendaMedicaDAO
from veterinaria.persistencia.aplicacion_vacuna_dao import AplicacionVacunaDAO
from veterinaria.persistencia.atencion_dao import AtencionDAO
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.clinica_dao import ClinicaDAO
from veterinaria.persistencia.comprobante_atencion_dao import ComprobanteAtencionDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.persistencia.conservadora_isotermica_dao import (
    ConservadoraIsotermicaDAO,
)
from veterinaria.persistencia.envio_dao import EnvioDAO
from veterinaria.persistencia.historia_clinica_dao import HistoriaClinicaDAO
from veterinaria.persistencia.mascota_dao import MascotaDAO
from veterinaria.persistencia.muestra_biologica_dao import MuestraBiologicaDAO
from veterinaria.persistencia.orden_derivacion_laboratorio_dao import (
    OrdenDerivacionLaboratorioDAO,
)
from veterinaria.persistencia.precinto_sanitario_dao import PrecintoSanitarioDAO
from veterinaria.persistencia.recepcion_dao import RecepcionDAO
from veterinaria.persistencia.remito_biologico_dao import RemitoBiologicoDAO
from veterinaria.persistencia.resultado_analisis_dao import ResultadoAnalisisDAO
from veterinaria.persistencia.turno_dao import TurnoDAO
from veterinaria.persistencia.vacuna_dao import VacunaDAO
from veterinaria.persistencia.veterinario_dao import VeterinarioDAO


def _verificar_tras_reabrir(ruta, *, precinto_roto):
    assert ruta.name == "veterinaria.db"
    assert ruta.is_file()
    with closing(abrir_conexion(ruta)) as conexion:
        # DAO nuevos sobre una conexión nueva: nunca se reutilizan objetos previos.
        assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conexion.execute("PRAGMA foreign_key_check").fetchall() == []
        cliente = ClienteDAO(conexion).obtener_por_id(10)
        mascota_dao = MascotaDAO(conexion)
        mascota = mascota_dao.obtener_por_id(20)
        assert mascota.responsable.id_cliente == cliente.id_cliente == 10
        assert mascota.responsable.nombre == cliente.nombre == "Laura"
        assert mascota.nombre == "Luna"
        assert not hasattr(cliente, "mascotas")
        assert mascota.obtener_historia_clinica() is None
        historia = HistoriaClinicaDAO(conexion).obtener_por_mascota(20)
        assert historia.id_historia == 60
        assert historia.fecha_apertura == date(2026, 1, 2)
        assert historia.obtener_atenciones() == []
        assert not hasattr(historia, "mascota")

        clinica = ClinicaDAO(conexion).obtener_por_id(30)
        veterinarios = VeterinarioDAO(conexion).listar_por_clinica(30)
        assert clinica.id_clinica == 30
        assert [v.id_veterinario for v in veterinarios] == [40]
        veterinario = veterinarios[0]
        assert not hasattr(veterinario, "clinica")
        agenda = AgendaMedicaDAO(conexion).obtener_por_veterinario(40)
        assert agenda.dias_trabajo == {
            DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.VIERNES,
        }
        assert agenda.hora_desde == time(8, 30, 15, 123456)
        assert agenda.hora_hasta == time(13, 45, 30, 654321)
        turnos = TurnoDAO(conexion).listar_por_veterinario(40)
        assert [t.id_turno for t in turnos] == [50]
        turno = turnos[0]
        assert turno.estado is EstadoTurno.ATENDIDO
        assert turno.mascota.id_mascota == mascota.id_mascota
        assert agenda.contiene(turno)
        assert not hasattr(turno, "veterinario")

        vacuna = VacunaDAO(conexion).obtener_por_id(80)
        aplicaciones = AplicacionVacunaDAO(conexion).listar_por_mascota(20)
        assert [a.id_aplicacion for a in aplicaciones] == [90]
        assert aplicaciones[0].vacuna.id_vacuna == vacuna.id_vacuna == 80
        assert aplicaciones[0].fecha_aplicacion == date(2026, 2, 3)
        assert aplicaciones[0].fecha_proxima_dosis == date(2027, 2, 3)
        assert aplicaciones[0].esta_vigente(date(2026, 11, 3))
        vacunada = mascota_dao.listar(cargar_aplicaciones=True)[0]
        assert vacunada.vacunas_obligatorias_al_dia([vacuna], date(2026, 11, 3))
        assert not hasattr(aplicaciones[0], "mascota")

        atencion_dao = AtencionDAO(conexion)
        atenciones = atencion_dao.listar_por_historia(historia.id_historia)
        assert [a.id_atencion for a in atenciones] == [70]
        atencion = atenciones[0]
        assert atencion.veterinario.id_veterinario == veterinario.id_veterinario
        assert atencion.fecha_hora == datetime(2026, 11, 3, 10, 20, 30, 456789)
        assert turno.fecha_hora_inicio == atencion.fecha_hora
        ordenes = OrdenDerivacionLaboratorioDAO(conexion).listar_por_atencion(70)
        assert [o.id_orden for o in ordenes] == [100]
        assert ordenes[0].estado is (
            EstadoOrden.EN_PROCESO if precinto_roto else EstadoOrden.COMPLETADA
        )
        con_ordenes = atencion_dao.listar(cargar_ordenes=True)[0]
        assert [o.id_orden for o in con_ordenes.obtener_ordenes_derivacion()] == [100]
        assert not hasattr(ordenes[0], "atencion")
        muestra_dao = MuestraBiologicaDAO(conexion)
        assert [m.id_muestra for m in muestra_dao.listar_por_orden(100)] == [110]

        remito = RemitoBiologicoDAO(conexion).obtener_por_id(130)
        assert remito.estado is EstadoRemito.RECIBIDO
        assert remito.clinica_origen.id_clinica == clinica.id_clinica
        conservadora = ConservadoraIsotermicaDAO(conexion).obtener_por_id(120)
        assert remito.conservadora.id_conservadora == conservadora.id_conservadora
        assert conservadora.estado is EstadoConservadora.EN_USO
        precinto = PrecintoSanitarioDAO(conexion).obtener_por_remito(130)
        assert remito.obtener_precinto().id_precinto == precinto.id_precinto == 140
        assert precinto.estado is (
            EstadoPrecinto.ROTO if precinto_roto else EstadoPrecinto.INTACTO
        )
        assert [m.id_muestra for m in remito.obtener_muestras()] == [110]
        assert not hasattr(remito, "envio")
        assert not hasattr(precinto, "remito")

        envio = EnvioDAO(conexion).obtener_por_remito(130)
        assert envio.id_envio == 150
        assert envio.estado is EstadoEnvio.ENTREGADO
        assert envio.remito.id_remito == remito.id_remito
        salida = datetime(2026, 11, 3, 13, 0, 0, 123456)
        assert envio.fecha_hora_salida == salida
        assert envio.fecha_hora_llegada == salida + timedelta(hours=1)
        recepcion = RecepcionDAO(conexion).obtener_por_envio(150)
        assert recepcion.id_recepcion == 160
        assert recepcion.envio.id_envio == envio.id_envio
        assert recepcion.fecha_hora == salida + timedelta(hours=1, minutes=15)
        assert not hasattr(envio, "recepcion")

        muestra = muestra_dao.obtener_por_id(110)
        assert muestra.estado.obtener_nombre() == (
            "RECHAZADA" if precinto_roto else "ANALIZADA"
        )
        estados = [h.nombre_estado for h in muestra.obtener_historial()]
        esperados = ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO"]
        esperados += ["RECHAZADA"] if precinto_roto else ["RECIBIDA", "ANALIZADA"]
        assert estados == esperados
        assert remito.obtener_muestras()[0].obtener_historial() == (
            muestra.obtener_historial()
        )
        assert muestra.obtener_historial()[0].fecha_hora == muestra.fecha_extraccion
        assert muestra.obtener_historial()[2].fecha_hora == salida
        assert muestra.obtener_historial()[3].fecha_hora == recepcion.fecha_hora
        assert muestra.obtener_historial()[-1].nombre_estado == (
            muestra.estado.obtener_nombre()
        )
        assert not hasattr(muestra, "resultado_analisis")
        assert not hasattr(muestra, "remito")

        resultado_dao = ResultadoAnalisisDAO(conexion)
        resultado = resultado_dao.obtener_por_muestra(110)
        if precinto_roto:
            assert resultado is None
            assert resultado_dao.obtener_por_id(170) is None
            intento = ResultadoAnalisis(
                170, muestra, salida + timedelta(hours=3), "No debe registrarse"
            )
            assert intento.registrar_resultado() is False
            assert [h.nombre_estado for h in muestra.obtener_historial()] == esperados
        else:
            assert resultado.id_resultado == 170
            assert resultado.muestra.id_muestra == muestra.id_muestra
            assert resultado.fecha_resultado == salida + timedelta(hours=2, minutes=45)
            assert resultado.resultado == "Hemograma dentro de parámetros"
            assert resultado.observaciones == "Validado por laboratorio"
            assert muestra.obtener_historial()[-1].fecha_hora == (
                resultado.fecha_resultado
            )

        comprobante = ComprobanteAtencionDAO(conexion).obtener_por_atencion(70)
        assert comprobante.id_comprobante == 180
        assert comprobante.atencion.id_atencion == atencion.id_atencion
        assert comprobante.fecha_emision == turno.fecha_hora_fin
        assert not hasattr(comprobante.atencion, "comprobante")
        assert conexion.execute(
            "SELECT COUNT(*) FROM resultado_analisis"
        ).fetchone()[0] == (0 if precinto_roto else 1)
        assert conexion.execute(
            "SELECT COUNT(*) FROM historial_estado_muestra"
        ).fetchone()[0] == len(esperados)


def test_circuito_intacto_se_reconstruye_desde_otra_conexion(circuito_persistido):
    ruta = circuito_persistido()
    _verificar_tras_reabrir(ruta, precinto_roto=False)


def test_circuito_roto_se_reconstruye_desde_otra_conexion(circuito_persistido):
    ruta = circuito_persistido(precinto_roto=True)
    _verificar_tras_reabrir(ruta, precinto_roto=True)
