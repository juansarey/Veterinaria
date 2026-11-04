"""Datos de demostración creados a través de los servicios (no con INSERT directos).

Sirven para presentar el sistema: clínicas, veterinarios con agenda, clientes, mascotas con
historia clínica, vacunas, atenciones y todo el circuito de laboratorio, con remitos aceptados,
uno rechazado por precinto roto, uno despachado y uno listo para despachar.
"""

from datetime import date, datetime, time, timedelta

from veterinaria.dominio.clinica.agenda_medica import DiaSemana
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.servicios.fachada import Servicios

HABILES = {DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES, DiaSemana.JUEVES, DiaSemana.VIERNES}


def _dia_habil(atras: int) -> date:
    """Un día hábil de hace ``atras`` días hábiles (0 = hoy o el último hábil)."""
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    while atras > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            atras -= 1
    return d


def _proximo_habil() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def hay_datos(servicios: Servicios) -> bool:
    return bool(servicios.clinica.listar_clientes())


def cargar_demo(servicios: Servicios) -> None:
    clin, aten, lab = servicios.clinica, servicios.atencion, servicios.laboratorio

    # --- clínicas, veterinarios y agendas
    centro = clin.crear_clinica("Clínica Centro", "Colón 450, Córdoba", "351 422-1000")
    nueva = clin.crear_clinica("Clínica Nueva Córdoba", "Bv. Illia 220, Córdoba", "351 422-2000")
    vets = [clin.crear_veterinario(centro, "Luis", "Gómez", "MP-1001", "Clínica general"),
            clin.crear_veterinario(centro, "Marta", "Ruiz", "MP-1002", "Cirugía"),
            clin.crear_veterinario(nueva, "Pablo", "Díaz", "MP-2001", "Clínica general")]
    for v in vets:
        clin.guardar_agenda(v, HABILES, time(8, 0), time(16, 0))

    # --- clientes y mascotas (con historia clínica)
    clientes = [clin.crear_cliente(*d) for d in [
        ("Ana", "Pérez", "30111222", "351 555-0101", "ana@correo.com"),
        ("Bruno", "Sosa", "28333444", "351 555-0102", "bruno@correo.com"),
        ("Carla", "Medina", "35777888", "351 555-0103", "carla@correo.com"),
        ("Diego", "Luna", "31222333", "351 555-0104", "diego@correo.com"),
        ("Elena", "Vega", "27444555", "351 555-0105", "elena@correo.com")]]
    datos_mascotas = [
        (0, "Firulais", "Perro", "Labrador", date(2019, 3, 10), "Macho"),
        (0, "Michi", "Gato", "Siamés", date(2020, 7, 2), "Hembra"),
        (1, "Rocky", "Perro", "Bulldog", date(2018, 11, 21), "Macho"),
        (2, "Luna", "Gato", "Común europeo", date(2021, 1, 15), "Hembra"),
        (3, "Toby", "Perro", "Caniche", date(2022, 5, 5), "Macho"),
        (4, "Mora", "Perro", "Mestizo", date(2017, 9, 30), "Hembra")]
    mascotas = [clin.crear_mascota(clientes[i], n, e, r, f, s, abrir_historia=True)
                for i, n, e, r, f, s in datos_mascotas]

    # --- vacunas: Toby y Mora quedan con pendientes (para el reporte y el bloqueo)
    rabia = aten.crear_vacuna("Antirrábica", "Perro", True)
    quintuple = aten.crear_vacuna("Quíntuple", "Perro", True)
    triple_felina = aten.crear_vacuna("Triple felina", "Gato", True)
    aten.crear_vacuna("Leucemia felina", "Gato", False)
    hace_6m, en_6m = date.today() - timedelta(days=180), date.today() + timedelta(days=185)
    for m in (mascotas[0], mascotas[2]):
        aten.registrar_aplicacion(m, rabia, hace_6m, en_6m)
        aten.registrar_aplicacion(m, quintuple, hace_6m, en_6m)
    for m in (mascotas[1], mascotas[3]):
        aten.registrar_aplicacion(m, triple_felina, hace_6m, en_6m)
    aten.registrar_aplicacion(mascotas[5], rabia, date.today() - timedelta(days=500),
                              date.today() - timedelta(days=135))     # vencida

    # --- atenciones (los pacientes con vacunas al día)
    def hora(dia, h, m=0):
        return datetime.combine(dia, time(h, m))

    d = {k: _dia_habil(k) for k in (6, 5, 4, 3, 2)}
    atenciones = [
        aten.registrar_atencion(mascotas[0], vets[0], hora(d[6], 9), TipoAtencion.CONSULTA,
                                "Decaimiento y falta de apetito", "A confirmar con laboratorio"),
        aten.registrar_atencion(mascotas[1], vets[0], hora(d[6], 10), TipoAtencion.CONSULTA,
                                "Vómitos recurrentes", "Posible gastritis"),
        aten.registrar_atencion(mascotas[2], vets[2], hora(d[5], 11), TipoAtencion.CONTROL,
                                "Control anual", "Paciente sano"),
        aten.registrar_atencion(mascotas[3], vets[1], hora(d[4], 9, 30), TipoAtencion.URGENCIA,
                                "Dificultad para orinar", "Sospecha de infección urinaria"),
        aten.registrar_atencion(mascotas[0], vets[0], hora(d[3], 10), TipoAtencion.CONTROL,
                                "Seguimiento", "Evolución favorable"),
    ]
    for id_at in atenciones[:4]:
        aten.emitir_comprobante(id_at, datetime.now() - timedelta(days=1))

    # --- derivaciones a laboratorio
    def derivar(i, estudio, tipo, dia, h, m=0):
        return lab.derivar(atenciones[i], estudio, tipo, hora(dia, h, m))["id_muestra"]

    m1 = derivar(0, "Hemograma completo", "Sangre", d[6], 9, 30)
    m2 = derivar(1, "Perfil hepático", "Sangre", d[6], 10, 30)
    m3 = derivar(3, "Urianálisis", "Orina", d[4], 10)
    m4 = derivar(2, "Coprocultivo", "Materia fecal", d[5], 11, 30)
    m5 = derivar(4, "Hemograma de control", "Sangre", d[3], 10, 30)
    m6 = derivar(3, "Urocultivo", "Orina", d[4], 10, 10)

    # --- remito A (Clínica Centro): aceptado y analizado
    c1, c2, c3, c4 = (lab.crear_conservadora(f"CONS-{i:03d}") for i in (1, 2, 3, 4))
    ra = lab.empaquetar(centro, c1, [m1, m2], "PRE-A-0001", hora(d[6], 12))
    ea = lab.despachar_remito(ra["id_remito"], hora(d[6], 13))
    lab.recibir_remito(ea, True, hora(d[6], 15))
    lab.registrar_resultado(m1, "Leve anemia; leucocitos normales", "Repetir en 15 días", hora(d[5], 9))
    lab.registrar_resultado(m2, "Enzimas hepáticas dentro de lo normal", "", hora(d[5], 9, 30))

    # --- remito B (Clínica Centro): precinto roto en el traslado → muestras rechazadas
    rb = lab.empaquetar(centro, c2, [m3, m6], "PRE-B-0001", hora(d[4], 12))
    eb = lab.despachar_remito(rb["id_remito"], hora(d[4], 13))
    lab.recibir_remito(eb, False, hora(d[4], 16), "Precinto roto al llegar")

    # --- remito C (Clínica Nueva Córdoba): ya despachado, pendiente de recepción
    rc = lab.empaquetar(nueva, c3, [m4], "PRE-C-0001", hora(d[3], 9))
    lab.despachar_remito(rc["id_remito"], hora(d[3], 10))

    # --- queda una muestra extraída pendiente de empaquetar (m5) y una conservadora libre (c4)
    assert m5 and c4

    # --- turnos para la próxima jornada hábil
    prox = _proximo_habil()
    clin.agendar_turno(vets[0], mascotas[4], hora(prox, 9), hora(prox, 9, 30), "Primera vacuna")
    clin.agendar_turno(vets[0], mascotas[5], hora(prox, 9, 30), hora(prox, 10), "Control general")
    clin.agendar_turno(vets[2], mascotas[2], hora(prox, 11), hora(prox, 11, 30), "Control de peso")
