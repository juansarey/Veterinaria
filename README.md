# TP Veterinaria

Trabajo Práctico Integrador 2026 — Desarrollo de Aplicaciones con Objetos.
Sistema para una red de clínicas veterinarias y derivación de muestras a un laboratorio central.

## Estado actual

Los tres primeros incrementos están implementados en Python, funcionan en memoria
y están validados:

- Primer incremento: `Clinica`, `Veterinario`, `AgendaMedica` y `Turno`.
- Segundo incremento: `Cliente`, `Mascota`, `HistoriaClinica`, `Atencion`,
  `TipoAtencion` y la asociación de cada `Turno` con una `Mascota`.
- Tercer incremento: `Vacuna`, `AplicacionVacuna`, registro de aplicaciones en
  `Mascota` y validación de vacunas obligatorias al registrar una atención.

Resultado de la suite: **122 tests passed**. La persistencia y los demás módulos
del MVP todavía no están implementados.

## Agenda y turnos

- `Clinica` mantiene varios veterinarios. `agregar_veterinario()` devuelve `True`
  cuando agrega una instancia y `False` si esa misma instancia ya estaba registrada.
- Cada veterinario tiene una única agenda semanal, asignada con `asignar_agenda()`.
  Puede crearse sin agenda, pero no registrar turnos hasta asignarle una.
- `AgendaMedica(dias_trabajo, hora_desde, hora_hasta)` selecciona los días laborales
  mediante `DiaSemana`. Un mismo horario se aplica a todos los días seleccionados;
  `hora_hasta` debe ser posterior a `hora_desde`.
- Un turno debe terminar después de comenzar, empezar y terminar en la misma fecha,
  corresponder a un día laboral y quedar completamente dentro del horario, incluidos sus límites.
- Cada veterinario mantiene varios turnos. No pueden superponerse turnos activos
  (para este control, todos los estados excepto `CANCELADO`).
  Los turnos consecutivos son válidos y los cancelados no bloquean el horario.
- La superposición se controla entre turnos, no entre agendas.

Por ejemplo, una agenda con lunes, martes, jueves y viernes de 08:00 a 13:00
permite un turno el lunes de 09:00 a 09:30, pero no el miércoles en ese horario.
Las relaciones almacenadas son unidireccionales: `Clinica -> Veterinario`,
`Veterinario -> AgendaMedica` y `Veterinario -> Turno`.

## Clientes, mascotas e historia clínica

- Toda `Mascota` tiene obligatoriamente un `Cliente` responsable.
- Una mascota puede tener una única `HistoriaClinica`. La primera asignación se
  conserva y no puede reemplazarse con una segunda.
- `HistoriaClinica` almacena sus `Atencion` y evita registrar dos veces la misma
  instancia.
- Cada `Atencion` indica su `TipoAtencion` e identifica al `Veterinario` que la
  realizó.
- Cada `Turno` corresponde obligatoriamente a una `Mascota`.

Las relaciones del modelo de objetos son unidireccionales:
`Mascota -> Cliente`, `Mascota -> HistoriaClinica`,
`HistoriaClinica -> Atencion`, `Atencion -> Veterinario` y `Turno -> Mascota`.
No se almacenan referencias inversas.

## Vacunación

- `Mascota` mantiene una colección de `AplicacionVacuna`; cada aplicación conoce
  la `Vacuna` correspondiente. Las relaciones se almacenan en un único sentido:
  `Mascota -> AplicacionVacuna -> Vacuna`.
- Una vacuna genera un requisito solamente cuando es obligatoria y su especie
  coincide con la especie de la mascota. La cobertura se compara mediante
  `id_vacuna` y requiere al menos una aplicación vigente.
- Una aplicación anterior puede estar vencida sin impedir que otra aplicación
  vigente de la misma vacuna satisfaga el requisito. Las vacunas opcionales y las
  correspondientes a otras especies no generan pendientes.
- Antes de `fecha_aplicacion`, una aplicación no está vigente ni vencida. Está
  vigente desde su aplicación hasta antes de `fecha_proxima_dosis`, y vencida en
  esa fecha o después. Si no tiene próxima dosis, permanece vigente desde su
  aplicación sin vencimiento definido.
- `Mascota.registrar_atencion(atencion, vacunas)` usa
  `atencion.fecha_hora.date()` como fecha de referencia. Requiere una historia
  clínica y todas las vacunas obligatorias al día. Si la validación falla, devuelve
  `False` sin modificar la historia; si pasa, delega el agregado en
  `HistoriaClinica._agregar_atencion()`.

## Pruebas

Desde la raíz del repositorio, con Python y pytest disponibles:

```console
python -m pytest
```

`pytest.ini` permite resolver los imports desde `src`. Los tests cubren disponibilidad
semanal, límites horarios, superposición, cancelaciones, estados de turnos, registro
de veterinarios, responsables de mascotas, asignación de historias clínicas,
registro de atenciones, tipos de atención, vigencia de aplicaciones y control de
vacunas obligatorias.

## Documentación

- [UML editable](docs/uml/DG_TP_Veterinaria.puml) y [diagrama SVG](docs/uml/DG_TP_Veterinaria.svg).
- [DER editable](docs/der/BD_TP_Veterinaria.dbml) y [diagrama SVG](docs/der/BD_TP_Veterinaria.svg).

Los diagramas también incluyen el diseño previsto para incrementos posteriores.
El DER conserva `id_agenda` como identificador técnico de persistencia; el objeto
de dominio no lo utiliza. `agenda_medica.id_veterinario` es único y los días laborales
se almacenarán en `agenda_medica_dia`, con clave compuesta `(id_agenda, dia)`.

## Siguiente incremento

El siguiente incremento incorporará `OrdenDerivacionLaboratorio`.

Continúan pendientes para etapas posteriores: `MuestraBiologica`,
`HistorialEstadoMuestra`, patrón State, `ConservadoraIsotermica`,
`RemitoBiologico`, `PrecintoSanitario`, `Envio`, `Recepcion`, `ResultadoAnalisis`,
`ComprobanteAtencion`, reportes Strategy y persistencia.
