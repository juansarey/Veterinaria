"""Validaciones definitivas de entrada, invocadas sin Flet y con SQLite temporal."""

from datetime import datetime, time
import unicodedata

import pytest

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.dominio.clinica.cliente import Cliente
from veterinaria.persistencia.cliente_dao import ClienteDAO
from veterinaria.persistencia.conexion import abrir_conexion
from veterinaria.servicios.errores import ErrorNegocio
from veterinaria.servicios.fachada import Servicios


@pytest.fixture
def s(tmp_path):
    return Servicios(tmp_path / "vet.db")


@pytest.mark.parametrize("nombre", [
    "María José", "Muñoz", "Jean-Luc", "O’Connor", "D'Angelo", "Łukasz", "李明",
    "Jose\u0301", "  Ana  María  ",
])
def test_nombres_unicode_en_clientes_y_veterinarios(s, nombre):
    cliente = s.clinica.crear_cliente(nombre, "de la Cruz", "00123456")
    clinica = s.clinica.crear_clinica("Vet & Cía. Nº 2", "Av. 9 de Julio 100")
    vet = s.clinica.crear_veterinario(clinica, nombre, "Pérez", "MP-2/26")
    esperado = " ".join(unicodedata.normalize("NFC", nombre).split())
    assert next(c for c in s.clinica.listar_clientes() if c["id"] == cliente)["nombre"] == esperado
    assert next(v for v in s.clinica.listar_veterinarios() if v["id"] == vet)["nombre"] == esperado


@pytest.mark.parametrize("operacion", ["cliente", "modificar_cliente", "veterinario"])
@pytest.mark.parametrize("campo, valor", [
    ("Nombre", "Ana2"), ("Apellido", "Pérez!"), ("Nombre", "   "),
    ("Nombre", "Anne\nMarie"), ("Nombre", "--Ana"), ("Apellido", "O''Connor"),
    ("Nombre", "A" * 81), ("Apellido", "P" * 81),
])
def test_nombre_invalido_no_se_persiste(s, operacion, campo, valor):
    nombre, apellido = (valor, "Pérez") if campo == "Nombre" else ("Ana", valor)
    if operacion == "modificar_cliente":
        cliente = s.clinica.crear_cliente("Ana", "Pérez", "12345678")
        accion = lambda: s.clinica.modificar_cliente(cliente, nombre, apellido, "12345678")
    elif operacion == "veterinario":
        clinica = s.clinica.crear_clinica("Centro", "Colón 100")
        accion = lambda: s.clinica.crear_veterinario(clinica, nombre, apellido, "MP-1")
    else:
        accion = lambda: s.clinica.crear_cliente(nombre, apellido, "12345678")

    with pytest.raises(ErrorNegocio) as error:
        accion()
    assert error.value.campo == campo
    assert s.clinica.listar_veterinarios() == []
    clientes = s.clinica.listar_clientes()
    if operacion == "modificar_cliente":
        assert len(clientes) == 1 and clientes[0]["nombre"] == "Ana" and clientes[0]["apellido"] == "Pérez"
    else:
        assert clientes == []


@pytest.mark.parametrize("dni", ["123", "1234567", "12345678", "00123456"])
def test_dni_cadena_y_edicion_del_propio_registro(s, tmp_path, dni):
    cliente = s.clinica.crear_cliente("Ana", "Pérez", dni)
    s.clinica.modificar_cliente(cliente, "María", "Pérez", dni)
    recuperado = Servicios(tmp_path / "vet.db").clinica.listar_clientes()[0]
    assert recuperado["dni"] == dni and isinstance(recuperado["dni"], str)
    assert recuperado["nombre"] == "María"


@pytest.mark.parametrize("modificar", [False, True])
@pytest.mark.parametrize("dni", ["", "12", "123456789", "12a", "12 34", "12.345", "１２３", "١٢٣", 123])
def test_dni_invalido_rechazado_en_alta_y_edicion(s, modificar, dni):
    if modificar:
        cliente = s.clinica.crear_cliente("Ana", "Pérez", "00123456")
        accion = lambda: s.clinica.modificar_cliente(cliente, "Ana", "Pérez", dni)
    else:
        accion = lambda: s.clinica.crear_cliente("Ana", "Pérez", dni)
    with pytest.raises(ErrorNegocio) as error:
        accion()
    assert error.value.campo == "DNI"
    assert [c["dni"] for c in s.clinica.listar_clientes()] == (["00123456"] if modificar else [])


def test_dni_de_otro_cliente_rechazado_sin_alterar_datos(s):
    uno = s.clinica.crear_cliente("Ana", "Pérez", "12345678")
    dos = s.clinica.crear_cliente("Eva", "Gómez", "87654321")
    for accion in (
        lambda: s.clinica.crear_cliente("Luis", "Ruiz", "12345678"),
        lambda: s.clinica.modificar_cliente(dos, "Eva", "Gómez", "12345678"),
    ):
        with pytest.raises(ErrorNegocio, match="Ya existe") as error:
            accion()
        assert error.value.campo == "DNI"
    assert [(c["id"], c["dni"]) for c in s.clinica.listar_clientes()] == [(uno, "12345678"), (dos, "87654321")]


@pytest.mark.parametrize("telefono, email", [
    ("", ""), (None, None), ("+54 (351) 555-0101", "ana+vet@correo.com"),
    ("351-1", "ana@x"), ("351", "ana@mañana.ar"),
])
def test_contacto_opcional_y_formatos_validos(s, telefono, email):
    s.clinica.crear_cliente("Ana", "Pérez", "12345678", telefono, email)
    cliente = s.clinica.listar_clientes()[0]
    assert cliente["telefono"] == (telefono or "") and cliente["email"] == (email or "")


@pytest.mark.parametrize("campo, valor", [
    ("Teléfono", "teléfono?"), ("Teléfono", "++54351"), ("Teléfono", "123/456"),
    ("Teléfono", "(" * 10), ("Teléfono", "1" * 31),
    ("Email", "sin-arroba"), ("Email", "a@@b"), ("Email", "a b@correo.com"),
    ("Email", "a@-dominio.com"), ("Email", "a" * 115 + "@x.com"),
    ("Email", "ana\x7f@correo.com"),
])
def test_contacto_invalido_en_alta_y_modificacion(s, campo, valor):
    telefono, email = (valor, "") if campo == "Teléfono" else ("", valor)
    with pytest.raises(ErrorNegocio) as error:
        s.clinica.crear_cliente("Ana", "Pérez", "12345678", telefono, email)
    assert error.value.campo == campo and s.clinica.listar_clientes() == []
    cliente = s.clinica.crear_cliente("Ana", "Pérez", "12345678")
    with pytest.raises(ErrorNegocio):
        s.clinica.modificar_cliente(cliente, "Ana", "Pérez", "12345678", telefono, email)
    assert s.clinica.listar_clientes()[0]["telefono"] == ""
    assert s.clinica.listar_clientes()[0]["email"] == ""


@pytest.fixture
def base(s):
    cliente = s.clinica.crear_cliente("Ana", "Pérez", "12345678")
    mascota = s.clinica.crear_mascota(cliente, "R2-D2", "Perro", abrir_historia=True)
    clinica = s.clinica.crear_clinica("Vet & Cía. Nº 2", "Colón 100")
    vet = s.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1/26")
    s.clinica.guardar_agenda(vet, set(DiaSemana), time(8), time(18))
    fecha = datetime(2026, 11, 2, 9)
    atencion = s.atencion.registrar_atencion(mascota, vet, fecha, TipoAtencion.CONSULTA, "Control")
    orden = s.laboratorio.crear_orden(atencion, "Hemograma", fecha_emision=fecha)
    cons = s.laboratorio.crear_conservadora("CONS-1")
    remito = s.laboratorio.crear_remito(clinica, cons, fecha_emision=fecha)
    return dict(cliente=cliente, mascota=mascota, clinica=clinica, vet=vet, atencion=atencion,
                orden=orden, remito=remito, fecha=fecha)


@pytest.mark.parametrize("clave, campo, maximo", [
    ("persona_nombre", "Nombre", 80), ("persona_apellido", "Apellido", 80),
    ("mascota_nombre", "Nombre", 80), ("mascota_especie", "Especie", 50),
    ("mascota_raza", "Raza", 80), ("mascota_sexo", "Sexo", 20),
    ("clinica_nombre", "Nombre", 100), ("direccion", "Dirección", 200),
    ("telefono", "Teléfono", 30), ("email", "Email", 120),
    ("matricula", "Matrícula", 30), ("especialidad", "Especialidad", 100),
    ("vacuna_nombre", "Nombre", 100), ("vacuna_especie", "Especie", 50),
    ("motivo_turno", "Motivo", 200), ("motivo_atencion", "Motivo", 200),
    ("estudio", "Estudio solicitado", 200), ("tipo_muestra", "Tipo de muestra", 80),
    ("conservadora", "Código", 50), ("precinto", "Código del precinto", 50),
])
def test_longitudes_limite_y_rechazo_sin_escrituras(s, base, tmp_path, monkeypatch, clave, campo, maximo):
    b = base
    if clave == "motivo_turno":
        monkeypatch.setattr("veterinaria.servicios.clinica_servicio.ahora", lambda: b["fecha"].replace(hour=8))
    acciones = {
        "persona_nombre": lambda v: s.clinica.crear_cliente(v, "Pérez", "23456789"),
        "persona_apellido": lambda v: s.clinica.crear_cliente("Ana", v, "23456789"),
        "mascota_nombre": lambda v: s.clinica.crear_mascota(b["cliente"], v, "Perro"),
        "mascota_especie": lambda v: s.clinica.crear_mascota(b["cliente"], "Luna", v),
        "mascota_raza": lambda v: s.clinica.crear_mascota(b["cliente"], "Luna", "Perro", raza=v),
        "mascota_sexo": lambda v: s.clinica.crear_mascota(b["cliente"], "Luna", "Perro", sexo=v),
        "clinica_nombre": lambda v: s.clinica.crear_clinica(v, "Colón 100"),
        "direccion": lambda v: s.clinica.crear_clinica("Centro", v),
        "telefono": lambda v: s.clinica.crear_clinica("Centro", "Colón 100", v),
        "email": lambda v: s.clinica.crear_cliente("Ana", "Pérez", "23456789", email=v),
        "matricula": lambda v: s.clinica.crear_veterinario(b["clinica"], "Ana", "Pérez", v),
        "especialidad": lambda v: s.clinica.crear_veterinario(b["clinica"], "Ana", "Pérez", "MP-2", v),
        "vacuna_nombre": lambda v: s.atencion.crear_vacuna(v, "Perro", True),
        "vacuna_especie": lambda v: s.atencion.crear_vacuna("Antirrábica", v, True),
        "motivo_turno": lambda v: s.clinica.agendar_turno(
            b["vet"], b["mascota"], b["fecha"], b["fecha"].replace(hour=10), v),
        "motivo_atencion": lambda v: s.atencion.registrar_atencion(
            b["mascota"], b["vet"], b["fecha"], TipoAtencion.CONSULTA, v),
        "estudio": lambda v: s.laboratorio.crear_orden(b["atencion"], v),
        "tipo_muestra": lambda v: s.laboratorio.registrar_muestra(b["orden"], v, b["fecha"]),
        "conservadora": lambda v: s.laboratorio.crear_conservadora(v),
        "precinto": lambda v: s.laboratorio.asignar_precinto(b["remito"], v),
    }
    valor = "X" * maximo
    if clave == "telefono":
        valor = "1" * maximo
    elif clave == "email":
        valor = "a" * (maximo - 6) + "@x.com"
    acciones[clave](valor)

    def conteos():
        con = abrir_conexion(tmp_path / "vet.db")
        try:
            tablas = [f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
        finally:
            con.close()

    antes = conteos()
    with pytest.raises(ErrorNegocio, match="máximo") as error:
        acciones[clave](valor + "X")
    assert error.value.campo == campo
    assert conteos() == antes


def test_mascotas_repetidas_ids_historias_y_edicion_independientes(s, tmp_path):
    cliente = s.clinica.crear_cliente("Ana", "Pérez", "00123456")
    una = s.clinica.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    otra = s.clinica.crear_mascota(cliente, "Luna", "Gato", abrir_historia=True)
    tercera = s.clinica.crear_mascota(cliente, "Nina", "Gato")
    s.clinica.modificar_mascota(tercera, "Luna", "Gato")
    reabierto = Servicios(tmp_path / "vet.db")
    mascotas = reabierto.clinica.listar_mascotas()
    assert {m["id"] for m in mascotas} == {una, otra, tercera}
    assert len({m["etiqueta"] for m in mascotas}) == 3
    assert all(f"[#{m['id']}]" in m["etiqueta"] for m in mascotas)
    assert reabierto.atencion.obtener_historia(una)["id"] != reabierto.atencion.obtener_historia(otra)["id"]


def test_consultar_registro_historico_no_lo_valida_ni_lo_modifica(s, tmp_path):
    con = abrir_conexion(tmp_path / "vet.db")
    try:
        ClienteDAO(con).crear(Cliente(90, "Ana2", "P!", "1", "texto?", "sin-arroba"))
        con.commit()
    finally:
        con.close()
    esperado = s.clinica.listar_clientes()
    reabierto = Servicios(tmp_path / "vet.db")
    assert reabierto.clinica.listar_clientes() == esperado
    assert esperado[0]["dni"] == "1" and esperado[0]["nombre"] == "Ana2"
