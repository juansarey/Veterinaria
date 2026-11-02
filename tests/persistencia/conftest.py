from datetime import date, datetime, time, timedelta
from contextlib import closing

import pytest

from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.clinica.atencion import Atencion, TipoAtencion
from veterinaria.dominio.clinica.comprobante_atencion import ComprobanteAtencion
from veterinaria.dominio.clinica.historia_clinica import HistoriaClinica
from veterinaria.dominio.clinica.mascota import Mascota
from veterinaria.dominio.clinica.agenda_medica import AgendaMedica, DiaSemana
from veterinaria.dominio.clinica.turno import Turno
from veterinaria.dominio.clinica.veterinario import Veterinario
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.laboratorio.orden_derivacion_laboratorio import (
    OrdenDerivacionLaboratorio,
)
from veterinaria.dominio.laboratorio.resultado_analisis import ResultadoAnalisis
from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
)
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.envio import Envio
from veterinaria.dominio.transporte.recepcion import Recepcion
from veterinaria.dominio.transporte.remito_biologico import RemitoBiologico
from veterinaria.dominio.vacunacion.aplicacion_vacuna import AplicacionVacuna
from veterinaria.dominio.vacunacion.vacuna import Vacuna
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
from veterinaria.persistencia.inicializar_bd import inicializar_bd
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


@pytest.fixture
def conexion():
    conexion = abrir_conexion(":memory:")
    try:
        inicializar_bd(conexion)
        yield conexion
    finally:
        conexion.close()


@pytest.fixture
def cliente_dao(conexion):
    return ClienteDAO(conexion)


@pytest.fixture
def mascota_dao(conexion):
    return MascotaDAO(conexion)


@pytest.fixture
def clinica_dao(conexion):
    return ClinicaDAO(conexion)


@pytest.fixture
def veterinario_dao(conexion):
    return VeterinarioDAO(conexion)


@pytest.fixture
def agenda_medica_dao(conexion):
    return AgendaMedicaDAO(conexion)


@pytest.fixture
def turno_dao(conexion):
    return TurnoDAO(conexion)


@pytest.fixture
def historia_clinica_dao(conexion):
    return HistoriaClinicaDAO(conexion)


@pytest.fixture
def atencion_dao(conexion):
    return AtencionDAO(conexion)


@pytest.fixture
def vacuna_dao(conexion):
    return VacunaDAO(conexion)


@pytest.fixture
def aplicacion_vacuna_dao(conexion):
    return AplicacionVacunaDAO(conexion)


@pytest.fixture
def orden_derivacion_laboratorio_dao(conexion):
    return OrdenDerivacionLaboratorioDAO(conexion)


@pytest.fixture
def muestra_biologica_dao(conexion):
    return MuestraBiologicaDAO(conexion)


@pytest.fixture
def conservadora_isotermica_dao(conexion):
    return ConservadoraIsotermicaDAO(conexion)


@pytest.fixture
def precinto_sanitario_dao(conexion):
    return PrecintoSanitarioDAO(conexion)


@pytest.fixture
def remito_biologico_dao(conexion):
    return RemitoBiologicoDAO(conexion)


@pytest.fixture
def envio_dao(conexion):
    return EnvioDAO(conexion)


@pytest.fixture
def recepcion_dao(conexion):
    return RecepcionDAO(conexion)


@pytest.fixture
def resultado_analisis_dao(conexion):
    return ResultadoAnalisisDAO(conexion)


@pytest.fixture
def comprobante_atencion_dao(conexion):
    return ComprobanteAtencionDAO(conexion)


@pytest.fixture
def atencion_persistida(
    cliente_dao, mascota_dao, clinica_dao, veterinario_dao,
    historia_clinica_dao, atencion_dao, cliente, mascota, clinica,
    veterinario, historia_clinica, atencion,
):
    cliente_dao.crear(cliente)
    mascota_dao.crear(mascota)
    clinica_dao.crear(clinica)
    veterinario_dao.crear(veterinario, clinica.id_clinica)
    historia_clinica_dao.crear(historia_clinica, mascota.id_mascota)
    atencion_dao.crear(atencion, historia_clinica.id_historia)
    return atencion


@pytest.fixture
def muestra_recibida_persistida(
    atencion_persistida, orden_derivacion_laboratorio_dao,
    orden_derivacion_laboratorio, muestra_biologica_dao, muestra_biologica,
):
    orden_derivacion_laboratorio_dao.crear(
        orden_derivacion_laboratorio, atencion_persistida.id_atencion
    )
    muestra_biologica_dao.crear(
        muestra_biologica, orden_derivacion_laboratorio.id_orden
    )
    fecha = muestra_biologica.fecha_extraccion
    assert muestra_biologica.empaquetar(fecha + timedelta(minutes=1))
    assert muestra_biologica.despachar(fecha + timedelta(minutes=2))
    assert muestra_biologica.recibir(fecha + timedelta(minutes=3))
    assert muestra_biologica_dao.actualizar(muestra_biologica)
    return muestra_biologica


@pytest.fixture
def cliente():
    return Cliente(10, "Laura", "García", "30111222", "351-123456", "laura@test.com")


@pytest.fixture
def mascota(cliente):
    return Mascota(20, "Luna", "Perro", cliente, "Mestiza", date(2020, 5, 10), "Hembra")


@pytest.fixture
def clinica():
    return Clinica(30, "Centro Veterinario", "San Martín 100", "351-555555")


@pytest.fixture
def veterinario():
    return Veterinario(40, "Ana", "Pérez", "MP-100", "Clínica general")


@pytest.fixture
def agenda_medica():
    return AgendaMedica(
        {DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.VIERNES},
        time(8, 30, 15, 123456),
        time(13, 45, 30, 654321),
    )


@pytest.fixture
def turno(mascota):
    return Turno(
        50,
        datetime(2026, 11, 2, 9, 15, 10, 123456),
        datetime(2026, 11, 2, 10, 30, 20, 654321),
        mascota,
        "Control anual",
    )


@pytest.fixture
def historia_clinica():
    return HistoriaClinica(
        60,
        date(2026, 1, 2),
        "Sin antecedentes",
    )


@pytest.fixture
def atencion(veterinario):
    return Atencion(
        70,
        datetime(2026, 11, 3, 10, 20, 30, 456789),
        TipoAtencion.CONSULTA,
        "Control general",
        veterinario,
        "Paciente estable",
        "Repetir control anual",
    )


@pytest.fixture
def vacuna():
    return Vacuna(80, "Antirrábica", "Perro", True)


@pytest.fixture
def aplicacion_vacuna(vacuna):
    return AplicacionVacuna(
        90,
        vacuna,
        date(2026, 2, 3),
        date(2027, 2, 3),
    )


@pytest.fixture
def orden_derivacion_laboratorio():
    return OrdenDerivacionLaboratorio(
        100,
        datetime(2026, 11, 3, 11, 22, 33, 456789),
        "Hemograma completo",
        "Procesar con prioridad",
    )


@pytest.fixture
def muestra_biologica():
    return MuestraBiologica(
        110,
        "Sangre",
        datetime(2026, 11, 3, 11, 45, 12, 654321),
        "Tubo con EDTA",
    )


@pytest.fixture
def conservadora_isotermica():
    return ConservadoraIsotermica(120, "CONS-120")


@pytest.fixture
def precinto_sanitario():
    return PrecintoSanitario(140, "PREC-140")


@pytest.fixture
def remito_biologico(clinica, conservadora_isotermica):
    return RemitoBiologico(
        130,
        clinica,
        conservadora_isotermica,
        datetime(2026, 11, 3, 12, 30, 45, 123456),
        "Traslado al laboratorio central",
    )


@pytest.fixture
def circuito_persistido(
    tmp_path, cliente, mascota, historia_clinica, clinica, veterinario,
    agenda_medica, vacuna, aplicacion_vacuna, atencion,
    orden_derivacion_laboratorio, muestra_biologica,
    conservadora_isotermica, precinto_sanitario,
):
    """Construye un circuito por test y devuelve la ruta con la conexión cerrada."""
    def persistir(*, precinto_roto=False):
        ruta = tmp_path / "veterinaria.db"
        assert mascota.asignar_historia_clinica(historia_clinica)
        assert clinica.agregar_veterinario(veterinario)
        veterinario.asignar_agenda(agenda_medica)
        turno = Turno(
            50, atencion.fecha_hora,
            atencion.fecha_hora + timedelta(minutes=30), mascota,
            "Control anual",
        )
        veterinario.agregar_turno(turno)
        turno.confirmar()
        assert mascota.agregar_aplicacion_vacuna(aplicacion_vacuna)
        assert mascota.registrar_atencion(atencion, [vacuna])
        turno.marcar_atendido()
        orden = orden_derivacion_laboratorio
        muestra = muestra_biologica
        assert atencion.agregar_orden_derivacion(orden)
        assert orden.agregar_muestra(muestra)
        assert orden.iniciar_proceso()

        with closing(abrir_conexion(ruta)) as conexion_circuito:
            inicializar_bd(conexion_circuito)
            ClienteDAO(conexion_circuito).crear(cliente)
            MascotaDAO(conexion_circuito).crear(mascota)
            HistoriaClinicaDAO(conexion_circuito).crear(
                historia_clinica, mascota.id_mascota
            )
            ClinicaDAO(conexion_circuito).crear(clinica)
            VeterinarioDAO(conexion_circuito).crear(
                veterinario, clinica.id_clinica
            )
            AgendaMedicaDAO(conexion_circuito).crear(
                agenda_medica, veterinario.id_veterinario
            )
            TurnoDAO(conexion_circuito).crear(turno, veterinario.id_veterinario)
            VacunaDAO(conexion_circuito).crear(vacuna)
            AplicacionVacunaDAO(conexion_circuito).crear(
                aplicacion_vacuna, mascota.id_mascota
            )
            AtencionDAO(conexion_circuito).crear(
                atencion, historia_clinica.id_historia
            )
            OrdenDerivacionLaboratorioDAO(conexion_circuito).crear(
                orden, atencion.id_atencion
            )
            MuestraBiologicaDAO(conexion_circuito).crear(muestra, orden.id_orden)
            ConservadoraIsotermicaDAO(conexion_circuito).crear(
                conservadora_isotermica
            )
            remito = RemitoBiologico(
                130, clinica, conservadora_isotermica,
                datetime(2026, 11, 3, 12, 30, 45, 123456),
                "Traslado al laboratorio central",
            )
            remito_dao = RemitoBiologicoDAO(conexion_circuito)
            remito_dao.crear(remito)
            assert remito.agregar_muestra(
                muestra, datetime(2026, 11, 3, 12, 45), "Acondicionada"
            )
            assert remito_dao.guardar_muestra_asociada(remito, muestra)
            assert remito.asignar_precinto(precinto_sanitario)
            PrecintoSanitarioDAO(conexion_circuito).crear(
                precinto_sanitario, remito.id_remito
            )
            envio = Envio(150, remito, "Traslado central")
            envio_dao = EnvioDAO(conexion_circuito)
            envio_dao.crear(envio)
            salida = datetime(2026, 11, 3, 13, 0, 0, 123456)
            assert envio.iniciar(salida)
            assert envio_dao.guardar_despacho(envio)
            if precinto_roto:
                assert precinto_sanitario.marcar_roto()
            assert envio.registrar_llegada(salida + timedelta(hours=1))
            recepcion = Recepcion(
                160, envio, salida + timedelta(hours=1, minutes=15),
                "Control de ingreso",
            )
            assert recepcion.procesar_recepcion()
            RecepcionDAO(conexion_circuito).guardar_recepcion(recepcion)
            resultado = ResultadoAnalisis(
                170, muestra, recepcion.fecha_hora + timedelta(minutes=90),
                "Hemograma dentro de parámetros", "Validado por laboratorio",
            )
            registrado = resultado.registrar_resultado()
            assert registrado is (not precinto_roto)
            if registrado:
                ResultadoAnalisisDAO(conexion_circuito).guardar_resultado(
                    resultado
                )
                assert orden.completar()
                assert OrdenDerivacionLaboratorioDAO(
                    conexion_circuito
                ).actualizar(orden)
            else:
                assert ResultadoAnalisisDAO(
                    conexion_circuito
                ).obtener_por_muestra(muestra.id_muestra) is None
            comprobante = ComprobanteAtencion(
                180, atencion, atencion.fecha_hora + timedelta(minutes=30)
            )
            ComprobanteAtencionDAO(conexion_circuito).crear(comprobante)
            conexion_circuito.commit()
        return ruta

    return persistir
