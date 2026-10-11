# TP Veterinaria

Trabajo Práctico Integrador 2026 — Desarrollo de Aplicaciones con Objetos.
Sistema para una red de clínicas veterinarias y derivación de muestras a un laboratorio central.

## Estado actual

Los seis primeros incrementos están implementados en Python, funcionan en memoria
y están validados:

- Primer incremento: `Clinica`, `Veterinario`, `AgendaMedica` y `Turno`.
- Segundo incremento: `Cliente`, `Mascota`, `HistoriaClinica`, `Atencion`,
  `TipoAtencion` y la asociación de cada `Turno` con una `Mascota`.
- Tercer incremento: `Vacuna`, `AplicacionVacuna`, registro de aplicaciones en
  `Mascota` y validación de vacunas obligatorias al registrar una atención.
- Cuarto incremento: `OrdenDerivacionLaboratorio`, `EstadoOrden`,
  `MuestraBiologica`, `HistorialEstadoMuestra` y patrón State para el ciclo de
  vida de las muestras.
- Quinto incremento: `ConservadoraIsotermica`, `EstadoConservadora`,
  `PrecintoSanitario`, `EstadoPrecinto`, `RemitoBiologico`, `EstadoRemito`,
  empaquetado de muestras mediante el remito y consulta de sus condiciones de
  despacho.
- Sexto incremento: `Envio`, `EstadoEnvio`, `Recepcion`, despacho y recepción del
  remito, registro de llegada, verificación del precinto y transición de las muestras
  a `EN_TRANSITO`, `RECIBIDA` o `RECHAZADA`.

Resultado de la suite: **251 tests passed**. La persistencia y los demás módulos
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

## Órdenes, muestras y trazabilidad

- Una `Atencion` puede registrar varias `OrdenDerivacionLaboratorio`, y cada orden
  mantiene su colección de `MuestraBiologica`. La navegación es unidireccional:
  `Atencion -> OrdenDerivacionLaboratorio -> MuestraBiologica`.
- Las órdenes comienzan en `PENDIENTE`, pueden pasar a `EN_PROCESO` y finalizar
  como `COMPLETADA` o `CANCELADA`. `completar()` controla solamente el ciclo de
  la orden y no inspecciona el estado de sus muestras.
- Toda muestra comienza en `EXTRAIDA`. Su ciclo de vida se implementa mediante
  State: `EXTRAIDA -> EMPAQUETADA -> EN_TRANSITO -> RECIBIDA -> ANALIZADA`, con
  la alternativa `EN_TRANSITO -> RECHAZADA`.
- La transición a `ANALIZADA` existe en el State de la muestra, pero el registro
  funcional mediante `ResultadoAnalisis` todavía no está implementado.
- `ANALIZADA` y `RECHAZADA` son estados finales. Una operación inválida devuelve
  `False` sin cambiar el estado ni agregar historial.
- La muestra mantiene registros inmutables de `HistorialEstadoMuestra`. El primer
  registro corresponde a `EXTRAIDA` y cada transición exitosa agrega uno nuevo.
  Las fechas anteriores al último registro son rechazadas; las iguales o
  posteriores se admiten cuando la transición también es válida.
- Los estados reciben temporalmente la muestra durante una operación, pero no la
  almacenan. Tampoco existen referencias inversas desde orden, muestra o historial.

## Remitos, envío y recepción

- Una `ConservadoraIsotermica` comienza `DISPONIBLE`. Al crear un
  `RemitoBiologico`, la conservadora requerida queda `EN_USO`; mientras esté
  ocupada no puede utilizarse para crear otro remito. `liberar()` está disponible,
  pero todavía no forma parte de un flujo automático del remito.
- El remito conserva referencias unidireccionales hacia la `Clinica` de origen,
  la conservadora, un precinto opcional y sus muestras. Ninguna de esas entidades
  almacena una referencia inversa al remito en el modelo de objetos.
- `agregar_muestra()` evita registrar dos veces la misma instancia y delega en
  `MuestraBiologica.empaquetar()`. La muestra se incorpora solamente si la
  transición `EXTRAIDA -> EMPAQUETADA` tiene éxito; la propia muestra administra
  su State y agrega el registro correspondiente a su historial.
- La primera asignación de un `PrecintoSanitario` devuelve `True`. Asignar `None`
  o intentar reemplazar el precinto devuelve `False`. En el comportamiento actual
  se permite asignar un precinto a un remito sin muestras, asignar uno que ya esté
  roto y agregar muestras después de haberlo asignado.
- Un precinto comienza `INTACTO` y puede pasar una sola vez a `ROTO`. Romperlo no
  modifica inmediatamente las muestras; su estado se verifica al procesar la
  recepción.
- `puede_despacharse()` es una consulta sin efectos laterales. Devuelve `True`
  solamente si el remito sigue `GENERADO`, tiene conservadora, al menos una
  muestra y un precinto intacto. No despacha el remito ni cambia estados.
- `Envio` mantiene una referencia unidireccional al remito. Al iniciar un envío,
  el remito pasa de `GENERADO` a `DESPACHADO`, sus muestras pasan de
  `EMPAQUETADA` a `EN_TRANSITO` y el envío pasa de `PENDIENTE` a `EN_TRANSITO`.
- Registrar la llegada guarda su fecha y cambia el envío a `ENTREGADO`; no procesa
  las muestras ni cambia el remito.
- `Recepcion` mantiene una referencia unidireccional al envío y verifica el precinto
  a través de `Recepcion -> Envio -> RemitoBiologico`. Si está `INTACTO`, las
  muestras pasan de `EN_TRANSITO` a `RECIBIDA`; si está `ROTO`, pasan a
  `RECHAZADA` y no pueden continuar hacia `ANALIZADA`. En ambos casos, el remito
  pasa de `DESPACHADO` a `RECIBIDO`.
- `RemitoBiologico` y `Recepcion` usan `despachar()`, `recibir()` y `rechazar()` de
  `MuestraBiologica`; no modifican directamente su State ni su historial. Antes de
  procesar el lote validan estados y fechas para evitar cambios parciales. El
  historial continúa siendo inmutable.
- La conservadora permanece `EN_USO` después de la recepción. No existe liberación
  automática y todavía no está definido cuándo debe liberarse.

El flujo del remito implementado termina en `RECIBIDO`; `CERRADO` permanece en el
enum, pero `cerrar()` todavía no está implementado.

## Pruebas

Desde la raíz del repositorio, con Python y pytest disponibles:

```console
python -m pytest
```

`pytest.ini` permite resolver los imports desde `src`. Los tests cubren disponibilidad
semanal, límites horarios, superposición, cancelaciones, estados de turnos, registro
de veterinarios, responsables de mascotas, asignación de historias clínicas,
registro de atenciones, tipos de atención, vigencia de aplicaciones y control de
vacunas obligatorias, ciclos de órdenes, State de muestras y trazabilidad temporal.
También cubren estados de conservadoras y precintos, reserva de conservadoras,
empaquetado y despacho de remitos, envíos, registro de llegada, recepción según el
estado del precinto, rechazo de muestras y prevención de cambios parciales.

## Documentación

- [UML editable](docs/uml/DG_TP_Veterinaria.puml) y [diagrama SVG](docs/uml/DG_TP_Veterinaria.svg).
- [DER editable](docs/der/BD_TP_Veterinaria.dbml) y [diagrama SVG](docs/der/BD_TP_Veterinaria.svg).

Los diagramas también incluyen el diseño previsto para incrementos posteriores.
El DER conserva `id_agenda` como identificador técnico de persistencia; el objeto
de dominio no lo utiliza. `agenda_medica.id_veterinario` es único y los días laborales
se almacenarán en `agenda_medica_dia`, con clave compuesta `(id_agenda, dia)`.

## Siguiente incremento

El próximo incremento funcional incorporará `ResultadoAnalisis`, su integración con
`MuestraBiologica` y el registro que coordine la transición `RECIBIDA -> ANALIZADA`.
Antes de implementarlo se analizará su alcance exacto contra el enunciado, sin
agregar reglas innecesarias.

Continúan pendientes para etapas posteriores: cierre del remito, liberación
automática de la conservadora, `ResultadoAnalisis`, registro funcional del resultado,
`ComprobanteAtencion`, reportes Strategy y persistencia.
