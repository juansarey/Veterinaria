from datetime import datetime, timedelta
import sqlite3

import pytest

from veterinaria.dominio.clinica.clinica import Clinica
from veterinaria.dominio.laboratorio.muestra_biologica import MuestraBiologica
from veterinaria.dominio.transporte.conservadora_isotermica import (
    ConservadoraIsotermica,
    EstadoConservadora,
)
from veterinaria.dominio.transporte.precinto_sanitario import PrecintoSanitario
from veterinaria.dominio.transporte.remito_biologico import (
    EstadoRemito,
    RemitoBiologico,
)


def _fixture(request, nombre):
    return request.getfixturevalue(nombre)


def _crear_remito_persistido(request, id_remito=130, id_conservadora=120):
    clinica = _fixture(request, "clinica")
    clinica_dao = _fixture(request, "clinica_dao")
    conservadora_dao = _fixture(request, "conservadora_isotermica_dao")
    remito_dao = _fixture(request, "remito_biologico_dao")
    if clinica_dao.obtener_por_id(clinica.id_clinica) is None:
        clinica_dao.crear(clinica)
    conservadora = ConservadoraIsotermica(
        id_conservadora, f"CONS-{id_conservadora}"
    )
    conservadora_dao.crear(conservadora)
    remito = RemitoBiologico(
        id_remito,
        clinica,
        conservadora,
        datetime(2026, 11, 3, 12, 30, 45, 123456),
        f"Remito {id_remito}",
    )
    remito_dao.crear(remito)
    return remito


def _persistir_orden_y_muestra(request):
    cliente = _fixture(request, "cliente")
    mascota = _fixture(request, "mascota")
    clinica = _fixture(request, "clinica")
    veterinario = _fixture(request, "veterinario")
    historia = _fixture(request, "historia_clinica")
    atencion = _fixture(request, "atencion")
    orden = _fixture(request, "orden_derivacion_laboratorio")
    muestra = _fixture(request, "muestra_biologica")
    _fixture(request, "cliente_dao").crear(cliente)
    _fixture(request, "mascota_dao").crear(mascota)
    clinica_dao = _fixture(request, "clinica_dao")
    if clinica_dao.obtener_por_id(clinica.id_clinica) is None:
        clinica_dao.crear(clinica)
    _fixture(request, "veterinario_dao").crear(
        veterinario, clinica.id_clinica
    )
    _fixture(request, "historia_clinica_dao").crear(
        historia, mascota.id_mascota
    )
    _fixture(request, "atencion_dao").crear(atencion, historia.id_historia)
    _fixture(request, "orden_derivacion_laboratorio_dao").crear(
        orden, atencion.id_atencion
    )
    _fixture(request, "muestra_biologica_dao").crear(
        muestra, orden.id_orden
    )
    return muestra


def _crear_agregado_con_muestra(request):
    muestra = _persistir_orden_y_muestra(request)
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    _fixture(request, "conservadora_isotermica_dao").crear(conservadora)
    remito = RemitoBiologico(
        130,
        _fixture(request, "clinica"),
        conservadora,
        datetime(2026, 11, 3, 12, 30, 45, 123456),
        "Traslado central",
    )
    _fixture(request, "remito_biologico_dao").crear(remito)
    return remito, muestra


def test_crear_persiste_id_datos_y_conservadora_en_uso(request, conexion):
    clinica = _fixture(request, "clinica")
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    _fixture(request, "clinica_dao").crear(clinica)
    _fixture(request, "conservadora_isotermica_dao").crear(conservadora)
    remito = RemitoBiologico(
        130, clinica, conservadora,
        datetime(2026, 11, 3, 12, 30, 45, 123456), "Prioridad",
    )
    assert conservadora.estado is EstadoConservadora.EN_USO
    _fixture(request, "remito_biologico_dao").crear(remito)
    fila = conexion.execute("""
        SELECT * FROM remito_biologico WHERE id_remito = 130
    """).fetchone()
    assert fila["id_clinica_origen"] == clinica.id_clinica
    assert fila["id_conservadora"] == 120
    assert fila["fecha_emision"] == "2026-11-03T12:30:45.123456"
    assert fila["estado"] == "GENERADO"
    assert fila["observaciones"] == "Prioridad"
    assert conexion.execute("""
        SELECT estado FROM conservadora_isotermica WHERE id_conservadora = 120
    """).fetchone()[0] == "EN_USO"


def test_id_none_es_rechazado(request):
    clinica = _fixture(request, "clinica")
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    remito = RemitoBiologico(
        None, clinica, conservadora, datetime(2026, 11, 3, 12)
    )
    with pytest.raises(ValueError, match="id_remito"):
        _fixture(request, "remito_biologico_dao").crear(remito)


def test_obtener_inexistente_y_listar_vacio(remito_biologico_dao):
    assert remito_biologico_dao.obtener_por_id(999) is None
    assert remito_biologico_dao.listar() == []


def test_obtener_reconstruye_asociaciones_basicas_sin_constructor(request):
    remito = _crear_remito_persistido(request)
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert isinstance(recuperado, RemitoBiologico)
    assert recuperado is not remito
    assert recuperado.id_remito == 130
    assert recuperado.clinica_origen.id_clinica == 30
    assert recuperado.conservadora.id_conservadora == 120
    assert recuperado.conservadora.estado is EstadoConservadora.EN_USO
    assert recuperado.fecha_emision == remito.fecha_emision
    assert recuperado.observaciones == "Remito 130"
    assert recuperado.obtener_precinto() is None
    assert recuperado.obtener_muestras() == []


def test_listar_ordena_por_id(request):
    _crear_remito_persistido(request, 150, 122)
    _crear_remito_persistido(request, 130, 120)
    _crear_remito_persistido(request, 140, 121)
    assert [
        remito.id_remito
        for remito in _fixture(request, "remito_biologico_dao").listar()
    ] == [130, 140, 150]


@pytest.mark.parametrize("estado", list(EstadoRemito))
def test_reconstruye_todos_los_estados_sin_operaciones_de_negocio(
    estado, request, conexion, monkeypatch,
):
    _crear_remito_persistido(request)
    conexion.execute(
        "UPDATE remito_biologico SET estado = ? WHERE id_remito = 130",
        (estado.name,),
    )

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar operaciones de negocio")

    monkeypatch.setattr(RemitoBiologico, "__init__", operacion_prohibida)
    monkeypatch.setattr(RemitoBiologico, "agregar_muestra", operacion_prohibida)
    monkeypatch.setattr(RemitoBiologico, "asignar_precinto", operacion_prohibida)
    monkeypatch.setattr(RemitoBiologico, "despachar", operacion_prohibida)
    monkeypatch.setattr(RemitoBiologico, "marcar_recibido", operacion_prohibida)
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert recuperado.estado is estado


def test_recuperar_no_vuelve_a_reservar_conservadora(
    request, monkeypatch,
):
    _crear_remito_persistido(request)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe reservar la conservadora")

    monkeypatch.setattr(
        ConservadoraIsotermica, "marcar_en_uso", operacion_prohibida
    )
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert recuperado.conservadora.estado is EstadoConservadora.EN_USO


def test_recupera_precinto_opcional_sin_asignarlo_nuevamente(
    request, monkeypatch,
):
    remito = _crear_remito_persistido(request)
    precinto = PrecintoSanitario(140, "PREC-140")
    assert remito.asignar_precinto(precinto)
    _fixture(request, "precinto_sanitario_dao").crear(precinto, 130)

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe asignar el precinto")

    monkeypatch.setattr(RemitoBiologico, "asignar_precinto", operacion_prohibida)
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert recuperado.obtener_precinto().id_precinto == 140
    assert recuperado.obtener_precinto().codigo == "PREC-140"


def test_recupera_una_muestra_con_historial_sin_empaquetar_al_leer(
    request, monkeypatch,
):
    remito, muestra = _crear_agregado_con_muestra(request)
    fecha = datetime(2026, 11, 3, 12, 45)
    assert remito.agregar_muestra(muestra, fecha, "Acondicionada")
    _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
        remito, muestra
    )
    historial = muestra.obtener_historial()

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("La lectura no debe empaquetar ni agregar muestras")

    monkeypatch.setattr(RemitoBiologico, "agregar_muestra", operacion_prohibida)
    monkeypatch.setattr(MuestraBiologica, "empaquetar", operacion_prohibida)
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert len(recuperado.obtener_muestras()) == 1
    assert recuperado.obtener_muestras()[0].obtener_historial() == historial


def test_recupera_varias_muestras_ordenadas(request):
    remito, muestra = _crear_agregado_con_muestra(request)
    segunda = MuestraBiologica(111, "Orina", muestra.fecha_extraccion)
    _fixture(request, "muestra_biologica_dao").crear(
        segunda, _fixture(request, "orden_derivacion_laboratorio").id_orden
    )
    for actual in (segunda, muestra):
        assert remito.agregar_muestra(actual, datetime(2026, 11, 3, 12, 45))
        _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
            remito, actual
        )
    recuperado = _fixture(request, "remito_biologico_dao").obtener_por_id(130)
    assert [m.id_muestra for m in recuperado.obtener_muestras()] == [110, 111]


@pytest.mark.parametrize("invalida", ["clinica", "conservadora"])
def test_fk_clinica_o_conservadora_invalida_propaga_integrity_error(
    invalida, request,
):
    clinica = _fixture(request, "clinica")
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    if invalida == "clinica":
        _fixture(request, "conservadora_isotermica_dao").crear(conservadora)
    else:
        _fixture(request, "clinica_dao").crear(clinica)
    remito = RemitoBiologico(
        130, clinica, conservadora, datetime(2026, 11, 3, 12)
    )
    with pytest.raises(sqlite3.IntegrityError):
        _fixture(request, "remito_biologico_dao").crear(remito)


def test_fecha_emision_obligatoria_rechaza_null(request):
    remito = _crear_remito_persistido(request)
    _fixture(request, "conexion").execute(
        "DELETE FROM remito_biologico WHERE id_remito = 130"
    )
    remito.fecha_emision = None
    with pytest.raises(sqlite3.IntegrityError):
        _fixture(request, "remito_biologico_dao").crear(remito)


def test_estado_fuera_del_enum_es_rechazado_por_check(request, conexion):
    _crear_remito_persistido(request)
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            UPDATE remito_biologico SET estado = 'INVALIDO'
            WHERE id_remito = 130
        """)


def test_actualizar_datos_propios_sin_cambiar_clinica_ni_conservadora(
    request, conexion,
):
    remito = _crear_remito_persistido(request)
    otra_clinica = Clinica(31, "Otra", "Otra dirección")
    otra_conservadora = ConservadoraIsotermica(121, "CONS-121")
    _fixture(request, "clinica_dao").crear(otra_clinica)
    _fixture(request, "conservadora_isotermica_dao").crear(otra_conservadora)
    remito.clinica_origen = otra_clinica
    remito.conservadora = otra_conservadora
    remito.fecha_emision = datetime(2026, 12, 4, 15, 16, 17, 222333)
    remito.observaciones = None
    vars(remito)["_estado"] = EstadoRemito.RECIBIDO
    assert _fixture(request, "remito_biologico_dao").actualizar(remito) is True
    fila = conexion.execute("""
        SELECT * FROM remito_biologico WHERE id_remito = 130
    """).fetchone()
    assert fila["id_clinica_origen"] == 30
    assert fila["id_conservadora"] == 120
    assert fila["fecha_emision"] == "2026-12-04T15:16:17.222333"
    assert fila["estado"] == "RECIBIDO"
    assert fila["observaciones"] is None


def test_actualizar_inexistente_devuelve_false(remito_biologico_dao):
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    remito = RemitoBiologico(
        999, Clinica(999, "X", "X"), conservadora,
        datetime(2026, 11, 3, 12),
    )
    assert remito_biologico_dao.actualizar(remito) is False


def test_no_existe_eliminar_publico(remito_biologico_dao):
    assert not hasattr(remito_biologico_dao, "eliminar")


def test_guardar_muestra_asociada_persiste_estado_historial_y_fk(
    request, conexion,
):
    remito, muestra = _crear_agregado_con_muestra(request)
    fecha = datetime(2026, 11, 3, 12, 45, 30, 654321)
    assert remito.agregar_muestra(muestra, fecha, "Acondicionada")
    assert _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
        remito, muestra
    ) is True
    fila = conexion.execute("""
        SELECT id_remito, estado_actual FROM muestra_biologica
        WHERE id_muestra = 110
    """).fetchone()
    assert tuple(fila) == (130, "EMPAQUETADA")
    historial = conexion.execute("""
        SELECT estado, fecha_hora, observaciones
        FROM historial_estado_muestra WHERE id_muestra = 110
        ORDER BY id_historial
    """).fetchall()
    assert [tuple(fila) for fila in historial] == [
        ("EXTRAIDA", "2026-11-03T11:45:12.654321", ""),
        ("EMPAQUETADA", "2026-11-03T12:45:30.654321", "Acondicionada"),
    ]


def test_guardar_muestra_no_ejecuta_empaquetado(
    request, monkeypatch,
):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))

    def operacion_prohibida(*args, **kwargs):
        raise AssertionError("Persistencia no debe empaquetar")

    monkeypatch.setattr(RemitoBiologico, "agregar_muestra", operacion_prohibida)
    monkeypatch.setattr(MuestraBiologica, "empaquetar", operacion_prohibida)
    assert _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
        remito, muestra
    )


def test_guardar_dos_veces_es_idempotente(request, conexion):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))
    dao = _fixture(request, "remito_biologico_dao")
    assert dao.guardar_muestra_asociada(remito, muestra)
    assert dao.guardar_muestra_asociada(remito, muestra)
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0] == 2


@pytest.mark.parametrize("faltante", ["remito", "muestra", "membresia"])
def test_guardar_muestra_valida_precondiciones(faltante, request):
    if faltante == "remito":
        clinica = _fixture(request, "clinica")
        conservadora = ConservadoraIsotermica(120, "CONS-120")
        remito = RemitoBiologico(
            130, clinica, conservadora, datetime(2026, 11, 3, 12)
        )
        muestra = MuestraBiologica(110, "Sangre", datetime(2026, 11, 3, 11))
        vars(remito)["_muestras"] = [muestra]
    else:
        remito = _crear_remito_persistido(request)
        muestra = MuestraBiologica(110, "Sangre", datetime(2026, 11, 3, 11))
        if faltante == "membresia":
            _persistir_orden_y_muestra(request)
        else:
            vars(remito)["_muestras"] = [muestra]
    with pytest.raises(ValueError):
        _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
            remito, muestra
        )


def test_reasignar_muestra_a_otro_remito_es_rechazado(request):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))
    dao = _fixture(request, "remito_biologico_dao")
    assert dao.guardar_muestra_asociada(remito, muestra)
    otro = _crear_remito_persistido(request, 131, 121)
    vars(otro)["_muestras"] = [muestra]
    with pytest.raises(ValueError, match="otro remito"):
        dao.guardar_muestra_asociada(otro, muestra)


def test_listar_por_remito_y_obtener_muestra_no_agregan_relacion_inversa(request):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))
    _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
        remito, muestra
    )
    muestras = _fixture(request, "muestra_biologica_dao").listar_por_remito(130)
    directa = _fixture(request, "muestra_biologica_dao").obtener_por_id(110)
    assert [m.id_muestra for m in muestras] == [110]
    assert not hasattr(muestras[0], "remito")
    assert not hasattr(directa, "remito")


def test_fk_id_remito_acepta_null_y_valido_y_rechaza_inexistente(
    request, conexion,
):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert conexion.execute("""
        SELECT id_remito FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] is None
    conexion.execute("""
        UPDATE muestra_biologica SET id_remito = 130 WHERE id_muestra = 110
    """)
    assert conexion.execute("""
        SELECT id_remito FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] == remito.id_remito
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("""
            UPDATE muestra_biologica SET id_remito = 999 WHERE id_muestra = 110
        """)
    assert muestra.id_muestra == 110


def test_precinto_roto_persistido_no_modifica_muestras(request, conexion):
    remito, muestra = _crear_agregado_con_muestra(request)
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))
    _fixture(request, "remito_biologico_dao").guardar_muestra_asociada(
        remito, muestra
    )
    precinto = PrecintoSanitario(140, "PREC-140")
    assert remito.asignar_precinto(precinto)
    assert precinto.marcar_roto()
    _fixture(request, "precinto_sanitario_dao").crear(precinto, 130)
    assert conexion.execute("""
        SELECT estado_actual FROM muestra_biologica WHERE id_muestra = 110
    """).fetchone()[0] == "EMPAQUETADA"
    assert conexion.execute("""
        SELECT COUNT(*) FROM historial_estado_muestra WHERE id_muestra = 110
    """).fetchone()[0] == 2


def test_crear_actualizar_y_guardar_muestra_no_hacen_commit(request, conexion):
    clinica = _fixture(request, "clinica")
    conservadora = ConservadoraIsotermica(120, "CONS-120")
    _fixture(request, "clinica_dao").crear(clinica)
    _fixture(request, "conservadora_isotermica_dao").crear(conservadora)
    conexion.commit()
    remito = RemitoBiologico(
        130, clinica, conservadora, datetime(2026, 11, 3, 12)
    )
    dao = _fixture(request, "remito_biologico_dao")
    dao.crear(remito)
    conexion.rollback()
    assert dao.obtener_por_id(130) is None
    assert _fixture(request, "conservadora_isotermica_dao").obtener_por_id(
        120
    ).estado is EstadoConservadora.DISPONIBLE

    remito = RemitoBiologico(
        130,
        clinica,
        _fixture(request, "conservadora_isotermica_dao").obtener_por_id(120),
        datetime(2026, 11, 3, 12),
    )
    dao.crear(remito)
    conexion.commit()
    remito.observaciones = "Cambio"
    dao.actualizar(remito)
    conexion.rollback()
    assert dao.obtener_por_id(130).observaciones == ""

    muestra = _persistir_orden_y_muestra(request)
    conexion.commit()
    assert remito.agregar_muestra(muestra, datetime(2026, 11, 3, 12, 45))
    dao.guardar_muestra_asociada(remito, muestra)
    conexion.rollback()
    fila = conexion.execute("""
        SELECT id_remito, estado_actual FROM muestra_biologica
        WHERE id_muestra = 110
    """).fetchone()
    assert tuple(fila) == (None, "EXTRAIDA")
