# TP Veterinaria

Trabajo Práctico Integrador 2026 — Desarrollo de Aplicaciones con Objetos.
Sistema para una red de clínicas veterinarias y derivación de muestras a un laboratorio central.

## Estado actual

Los nueve primeros incrementos del dominio están implementados en Python, funcionan
en memoria y están validados. Persistencia 1, Persistencia 2, Persistencia 3,
Persistencia 4 y Persistencia 5 incorporan almacenamiento para `Cliente`,
`Mascota`, `Clinica`, `Veterinario`, `AgendaMedica`, `Turno`, `HistoriaClinica`,
`Atencion`, `Vacuna`, `AplicacionVacuna`, `OrdenDerivacionLaboratorio` y
`MuestraBiologica`. El historial de estados se persiste como parte interna de
`MuestraBiologicaDAO`:

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
- Séptimo incremento: `ResultadoAnalisis`, relación unidireccional con
  `MuestraBiologica`, registro de resultados y transición de muestras recibidas a
  `ANALIZADA`.
- Octavo incremento: `ComprobanteAtencion`, emisión mediante construcción y relación
  unidireccional con `Atencion`.
- Noveno incremento: patrón Strategy mediante `EstrategiaReporte` y
  `GeneradorReportes`, con cuatro estrategias concretas para generar reportes de
  atenciones y derivaciones, muestras rechazadas, vacunas pendientes y tiempos
  promedio de tránsito y procesamiento.

La persistencia utiliza SQLite mediante `sqlite3` y el patrón DAO. Incluye una
conexión compartida con claves foráneas activas, SQL parametrizado y control
externo de las transacciones. Persistencia 1 cubre `Cliente` y `Mascota`;
Persistencia 2 agrega `Clinica`, `Veterinario`, `AgendaMedica` y `Turno`, y
Persistencia 3 incorpora `HistoriaClinica` y `Atencion`; Persistencia 4 agrega
`Vacuna` y `AplicacionVacuna`; Persistencia 5 incorpora
`OrdenDerivacionLaboratorio`, `MuestraBiologica` y su historial de estados.

Resultado de la suite: **585 tests passed** (309 de dominio y patrones, 49 de
Persistencia 1, 81 de Persistencia 2, 43 de Persistencia 3, 42 de Persistencia 4
y 61 de Persistencia 5).

Los procesos obligatorios principales del enunciado ya cubren clientes, mascotas e
historias clínicas, atenciones, órdenes de laboratorio, empaquetado, envío, recepción,
rechazo por precinto roto, resultados de análisis y comprobantes de atención.
También están implementados los dos patrones de diseño obligatorios, State y
Strategy, y cuatro reportes no triviales. Las entidades que no se enumeraron como
persistidas todavía funcionan exclusivamente en memoria.

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
- `ComprobanteAtencion` conserva una referencia unidireccional a la `Atencion` y una
  fecha de emisión explícita. Su construcción representa la emisión del comprobante;
  no existe un método `emitir()` ni una referencia inversa desde `Atencion`.
- La relación conceptual admite como máximo un comprobante persistido por atención
  porque el DER declara `id_atencion` como único. Esa unicidad global todavía no se
  controla en memoria.
- Cada `Turno` corresponde obligatoriamente a una `Mascota`.

Las relaciones del modelo de objetos son unidireccionales:
`Mascota -> Cliente`, `Mascota -> HistoriaClinica`,
`HistoriaClinica -> Atencion`, `Atencion -> Veterinario` y `Turno -> Mascota`.
No se almacenan referencias inversas.

## Persistencia 1: clientes y mascotas

La persistencia sigue la separación:

```text
Dominio
   ↓ utilizado por
DAO
   ↓
sqlite3
   ↓
SQLite
```

Las entidades no conocen SQLite, conexiones ni DAO, y no contienen SQL. Los DAO
conocen las entidades que persisten y reciben una `sqlite3.Connection` ya abierta.
La conexión se crea a partir de una ruta, admite `:memory:`, activa
`PRAGMA foreign_keys = ON` y configura `sqlite3.Row` para acceder a las columnas
por nombre. No existen conexiones globales.

`ClienteDAO` y `MascotaDAO` implementan exactamente estas operaciones:

- `crear()`;
- `obtener_por_id()`;
- `listar()`;
- `actualizar()`;
- `eliminar()`.

Todos los datos variables se envían mediante parámetros `?`. Los DAO conservan los
IDs explícitos de los objetos y no asignan identificadores mediante `lastrowid`.
Tampoco ejecutan `commit`: el código que coordina una operación decide si confirma
con `conexion.commit()` o revierte con `conexion.rollback()`, por lo que ambos DAO
pueden participar en una misma transacción.

La relación se persiste mediante la clave foránea
`mascota.id_cliente -> cliente.id_cliente`, obtenida de
`mascota.responsable.id_cliente`. Al recuperar una mascota, `MascotaDAO` utiliza
`ClienteDAO` para reconstruir su responsable. El sentido del modelo de objetos se
mantiene como `Mascota -> Cliente`; no se agrega una colección de mascotas en
`Cliente`.

`fecha_nacimiento` se guarda como texto ISO mediante `date.isoformat()` y se
recupera explícitamente con `date.fromisoformat()`. Los valores opcionales se
conservan como `NULL` cuando corresponde. Las restricciones de PK, `UNIQUE`, FK y
`NOT NULL` provienen del DER. Los DAO dejan que `sqlite3.IntegrityError` se propague
ante una violación y no convierten esos errores en un resultado `False`.

Los archivos incorporados son:

```text
src/veterinaria/persistencia/
    conexion.py
    inicializar_bd.py
    cliente_dao.py
    mascota_dao.py

tests/persistencia/
    conftest.py
    test_conexion.py
    test_inicializar_bd.py
    test_cliente_dao.py
    test_mascota_dao.py
```

Persistencia 1 incorporó las tablas `cliente` y `mascota` mediante
`CREATE TABLE IF NOT EXISTS`. Los tests de persistencia utilizan bases aisladas,
principalmente `:memory:`, y no comparten una base real entre ejecuciones.

## Persistencia 2: clínica, profesionales, agenda y turnos

Persistencia 2 continúa con la misma arquitectura: SQLite mediante `sqlite3`,
DAO que reciben una conexión compartida, SQL parametrizado, claves foráneas
activas, IDs explícitos para las entidades y transacciones controladas por el
código que coordina la operación. La inicialización agrega las tablas `clinica`,
`veterinario`, `agenda_medica`, `agenda_medica_dia` y `turno`.

Los DAO implementan estas operaciones:

- `ClinicaDAO`: `crear()`, `obtener_por_id()`, `listar()`, `actualizar()` y
  `eliminar()`. Recupera solamente los datos propios de la clínica y no carga sus
  veterinarios.
- `VeterinarioDAO`: `crear(veterinario, id_clinica)`, `obtener_por_id()`,
  `listar()`, `listar_por_clinica()`, `actualizar(veterinario, id_clinica)` y
  `eliminar()`. `id_clinica` es contexto de persistencia; el objeto recuperado no
  incorpora una referencia a `Clinica`, una agenda ni turnos.
- `AgendaMedicaDAO`: `crear(agenda, id_veterinario)`,
  `obtener_por_veterinario()`, `actualizar(agenda, id_veterinario)` y
  `eliminar_por_veterinario()`. Administra conjuntamente `agenda_medica` y
  `agenda_medica_dia`; no existe un DAO separado para los días.
- `TurnoDAO`: `crear(turno, id_veterinario)`, `obtener_por_id()`, `listar()`,
  `listar_por_veterinario()`, `actualizar(turno, id_veterinario)` y `eliminar()`.
  Obtiene `id_mascota` desde `turno.mascota` y utiliza `MascotaDAO` al reconstruir
  esa asociación. `id_veterinario` permanece como contexto de persistencia y no se
  agrega una referencia desde `Turno` hacia `Veterinario`.

Las relaciones del modelo de objetos continúan siendo unidireccionales:
`Clinica -> Veterinario`, `Veterinario -> AgendaMedica`,
`Veterinario -> Turno`, `Turno -> Mascota` y `Mascota -> Cliente`. La carga de un
objeto por su DAO no reconstruye automáticamente las colecciones o referencias
que pertenecen a otro agregado. No se incorporan las relaciones inversas
`Veterinario -> Clinica`, `AgendaMedica -> Veterinario`,
`Turno -> Veterinario` ni `Mascota -> Turno`.

Las claves foráneas del modelo relacional se resuelven mediante los IDs de las
entidades y los parámetros que reciben los DAO; no representan nuevas relaciones
en el modelo de objetos.

`agenda_medica.id_agenda` es un identificador técnico generado por SQLite y se usa
internamente mediante `lastrowid` para asociar los días. No forma parte de
`AgendaMedica`, cuyas instancias se consultan por `id_veterinario`. Los valores de
`DiaSemana` se guardan mediante `dia.name`, por ejemplo `LUNES`, `MARTES` o
`MIERCOLES`, y se reconstruyen mediante `DiaSemana[nombre]`; no se persisten sus
valores numéricos de 0 a 6.

Los valores `time` y `datetime` se guardan como texto ISO y se recuperan con
`fromisoformat()`, conservando segundos y microsegundos. El estado del turno se
persiste mediante el nombre de `EstadoTurno`: `PENDIENTE`, `CONFIRMADO`, `ATENDIDO`
o `CANCELADO`. El mapper privado lo restaura directamente; la lectura desde la
base no ejecuta una transición de negocio ni llama a `confirmar()`, `cancelar()` o
`marcar_atendido()`.

SQLite garantiza las claves primarias y foráneas, los campos `NOT NULL`, la
matrícula única, una sola agenda por veterinario y los valores permitidos mediante
restricciones `CHECK`. Los DAO dejan que `sqlite3.IntegrityError` se propague. Las
reglas de horario válido, pertenencia a la agenda y superposición de turnos se
validan en el dominio y no se atribuyen a SQLite.

Ningún DAO ejecuta `commit()` ni `rollback()`. La agenda y sus días forman una
unidad lógica que debe confirmarse o revertirse en una misma transacción externa.
Los archivos incorporados en este incremento son:

```text
src/veterinaria/persistencia/
    clinica_dao.py
    veterinario_dao.py
    agenda_medica_dao.py
    turno_dao.py

tests/persistencia/
    test_clinica_dao.py
    test_veterinario_dao.py
    test_agenda_medica_dao.py
    test_turno_dao.py
```

## Persistencia 3: historias clínicas y atenciones

Persistencia 3 mantiene SQLite, `sqlite3`, el patrón DAO, la conexión compartida,
las claves foráneas activas, el SQL parametrizado, los IDs explícitos y el control
externo de las transacciones. La inicialización agrega las tablas
`historia_clinica` y `atencion`.

Los DAO implementan estas operaciones:

- `HistoriaClinicaDAO`: `crear(historia, id_mascota)`, `obtener_por_id()`,
  `obtener_por_mascota()`, `actualizar(historia)` y `eliminar()`. `id_mascota` se
  establece al crear y no se modifica durante una actualización, que cambia
  solamente `fecha_apertura` y `observaciones`. La restricción
  `UNIQUE(id_mascota)` garantiza como máximo una historia por mascota.
- `AtencionDAO`: `crear(atencion, id_historia)`, `obtener_por_id()`, `listar()`,
  `listar_por_historia()`, `actualizar(atencion)` y `eliminar()`. `id_historia` se
  establece al crear y no se modifica durante una actualización. El
  `id_veterinario` se obtiene desde `atencion.veterinario` y sí puede actualizarse
  junto con los demás datos propios de la atención.

Las relaciones del dominio permanecen en un solo sentido:
`Mascota -> HistoriaClinica`, `HistoriaClinica -> Atencion` y
`Atencion -> Veterinario`. Las claves foráneas inversas se resuelven mediante los
parámetros de los DAO; no se agregan referencias `HistoriaClinica -> Mascota`,
`Atencion -> HistoriaClinica` ni `Veterinario -> Atencion`.

`HistoriaClinicaDAO` recupera solamente los datos de la historia y deja su colección
de atenciones vacía. Cuando se necesitan, se consultan con
`AtencionDAO.listar_por_historia()`. `AtencionDAO` reconstruye la atención y utiliza
`VeterinarioDAO` para obtener el profesional básico, sin cargar su clínica, agenda o
turnos. Tampoco carga órdenes de derivación.

La lectura desde SQLite reconstruye hechos existentes y no vuelve a ejecutar las
reglas usadas para registrarlos. En particular, no llama a
`Mascota.registrar_atencion()` ni a `HistoriaClinica._agregar_atencion()`.

`TipoAtencion` se guarda mediante `atencion.tipo.name` y se recupera con
`TipoAtencion[nombre]`. Los valores admitidos son `CONSULTA`, `CONTROL` y
`URGENCIA`, respaldados por una restricción `CHECK`. `fecha_apertura` se almacena
en formato ISO y se recupera con `date.fromisoformat()`; `fecha_hora` usa formato
ISO y `datetime.fromisoformat()`, conservando la precisión disponible.

Los campos opcionales conservan su valor: `None` se almacena como `NULL` y no se
normaliza como una cadena vacía, ni una cadena vacía se convierte en `NULL`.
SQLite garantiza PK, FK, `NOT NULL`, la unicidad de `id_mascota` y el `CHECK` de
`TipoAtencion`. Los DAO propagan `sqlite3.IntegrityError` y no agregan controles de
reglas de negocio ajenos al DER.

Ningún DAO ejecuta `commit()` ni `rollback()`. La conexión compartida permite
confirmar o revertir externamente la creación de una historia y sus atenciones como
parte de una misma transacción. Los archivos incorporados son:

```text
src/veterinaria/persistencia/
    historia_clinica_dao.py
    atencion_dao.py

tests/persistencia/
    test_historia_clinica_dao.py
    test_atencion_dao.py
```

## Persistencia 4: vacunas y aplicaciones

Persistencia 4 continúa con SQLite, `sqlite3`, el patrón DAO, una conexión
compartida, claves foráneas activas, SQL parametrizado, IDs explícitos y
transacciones externas. La inicialización agrega las tablas `vacuna` y
`aplicacion_vacuna`.

Los DAO implementan estas operaciones:

- `VacunaDAO`: `crear()`, `obtener_por_id()`, `listar()`, `actualizar()` y
  `eliminar()`. Conserva `id_vacuna` explícito y actualiza solamente `nombre`,
  `especie` y `obligatoria`.
- `AplicacionVacunaDAO`: `crear(aplicacion, id_mascota)`, `obtener_por_id()`,
  `listar_por_mascota()`, `actualizar(aplicacion)` y `eliminar()`. Conserva
  `id_aplicacion` como identidad explícita del dominio. `id_mascota` se establece
  al crear y `id_vacuna` se obtiene desde `aplicacion.vacuna`.

Una actualización de `AplicacionVacuna` modifica exclusivamente
`fecha_aplicacion` y `fecha_proxima_dosis`; no reasigna `id_mascota` ni
`id_vacuna`. El modelo de objetos mantiene la navegación
`Mascota -> AplicacionVacuna -> Vacuna`, sin referencias inversas desde la
aplicación hacia la mascota ni desde la vacuna hacia aplicaciones o mascotas.

`AplicacionVacunaDAO` utiliza `VacunaDAO` con la misma conexión para reconstruir la
vacuna asociada. La recuperación no llama a
`Mascota.agregar_aplicacion_vacuna()` ni modifica la mascota. `MascotaDAO` continúa
recuperando mascotas básicas con su colección de aplicaciones vacía; cuando se
necesitan aplicaciones se consultan mediante `listar_por_mascota()`.

`fecha_aplicacion` y `fecha_proxima_dosis` se almacenan con `date.isoformat()` y se
recuperan con `date.fromisoformat()`. Una próxima dosis ausente se conserva como
`NULL` en SQLite y `None` en Python. La regla que exige una próxima dosis posterior
a la aplicación continúa en el dominio y no se duplica como restricción SQL.

`obligatoria` se representa como `INTEGER NOT NULL`: `False` corresponde a `0` y
`True` a `1`. Una restricción `CHECK (obligatoria IN (0, 1))` impide otros valores;
no se utilizan cadenas `TRUE` o `FALSE`.

SQLite garantiza PK, FK, `NOT NULL` y el `CHECK` booleano, y los DAO propagan
`sqlite3.IntegrityError`. La base no duplica reglas de vigencia, vencimiento,
especie, vacunas pendientes ni `vacunas_obligatorias_al_dia()`, que permanecen en
el dominio.

No se agregaron cascadas. Una vacuna referenciada o una mascota con aplicaciones
no pueden eliminarse por las FK; una vacuna sin aplicaciones y una aplicación
concreta sí pueden eliminarse. Ningún DAO ejecuta `commit()` ni `rollback()`; el
código coordinador controla la transacción sobre la conexión compartida.

Los archivos incorporados son:

```text
src/veterinaria/persistencia/
    vacuna_dao.py
    aplicacion_vacuna_dao.py

tests/persistencia/
    test_vacuna_dao.py
    test_aplicacion_vacuna_dao.py
```

## Persistencia 5: órdenes, muestras y trazabilidad

Persistencia 5 mantiene SQLite, `sqlite3`, el patrón DAO, la conexión compartida,
el SQL parametrizado, los IDs explícitos y el control externo de las transacciones.
La inicialización agrega las tablas `orden_derivacion_laboratorio`,
`muestra_biologica` e `historial_estado_muestra`.

Los DAO implementan estas operaciones:

- `OrdenDerivacionLaboratorioDAO`: `crear(orden, id_atencion)`,
  `obtener_por_id()`, `listar_por_atencion()`, `actualizar(orden)` y `eliminar()`.
  `id_atencion` se establece al crear y no cambia al actualizar. `EstadoOrden` se
  almacena por nombre. La recuperación restaura el estado sin ejecutar
  `iniciar_proceso()`, `completar()` ni `cancelar()`, y deja vacía la colección de
  muestras.
- `MuestraBiologicaDAO`: `crear(muestra, id_orden)`, `obtener_por_id()`,
  `listar_por_orden()` y `actualizar(muestra)`. `id_orden` se establece al crear y
  no se modifica al actualizar. El DAO no expone una operación de eliminación.

Los estados persistibles de una muestra son `EXTRAIDA`, `EMPAQUETADA`,
`EN_TRANSITO`, `RECIBIDA`, `ANALIZADA` y `RECHAZADA`. El DAO usa un diccionario
explícito para reconstruir la clase State concreta. No serializa objetos State ni
utiliza `pickle`. Las reglas `EXTRAIDA -> EMPAQUETADA`,
`EMPAQUETADA -> EN_TRANSITO`, `EN_TRANSITO -> RECIBIDA / RECHAZADA` y
`RECIBIDA -> ANALIZADA` permanecen exclusivamente en el patrón State; el DAO no
decide ni ejecuta transiciones.

La reconstrucción de una muestra sigue estos pasos:

1. recupera la fila de `muestra_biologica`;
2. consulta el historial en orden estable por `fecha_hora, id_historial`;
3. construye los objetos `HistorialEstadoMuestra`;
4. reconstruye la clase State concreta;
5. utiliza el constructor normal de `MuestraBiologica` para sus datos estructurales;
6. el mapper privado reemplaza controladamente `_estado` y `_historial` con los
   valores persistidos.

Este mecanismo es interno al mapper, no una operación pública del dominio. No
ejecuta transiciones, no inserta registros al leer, no genera un evento persistido
y no duplica el registro inicial `EXTRAIDA`.

`HistorialEstadoMuestra` continúa siendo inmutable y no incorpora un ID al dominio.
`id_historial` es una clave técnica administrada exclusivamente por SQLite. No
existe un `HistorialEstadoMuestraDAO` público: `MuestraBiologicaDAO` inserta y
consulta los registros históricos, pero no los actualiza ni ofrece eliminarlos de
forma individual.

Al recuperar una muestra se valida que el estado actual y todos los estados del
historial sean conocidos, que el historial no esté vacío, que comience en
`EXTRAIDA`, que sus fechas sean no decrecientes y que el último registro coincida
con `estado_actual`. Una inconsistencia produce `ValueError`; no se corrigen datos
históricos silenciosamente.

La actualización conserva la trazabilidad mediante una comparación de prefijo.
Antes de escribir, los registros persistidos deben constituir un prefijo idéntico
del historial del objeto, comparando `nombre_estado`, `fecha_hora` y
`observaciones`. Después se actualizan los datos propios y `estado_actual`, y se
insertan solamente los eventos nuevos. No se borra ni se reconstruye el historial
anterior. Una segunda llamada a `actualizar()` sin transiciones nuevas no agrega
registros duplicados.

`muestra_biologica.id_remito` existe como columna nullable y permanece siempre en
`NULL` durante Persistencia 5. Todavía no se asigna un `RemitoBiologico` ni existe
una FK activa hacia `remito_biologico`, porque esa tabla no forma parte del esquema
SQLite implementado. El DER conserva la relación final esperada. Cuando
Persistencia 6 incorpore la tabla, el inicializador deberá usar un orden de creación
compatible y declarar la FK
`muestra_biologica.id_remito -> remito_biologico.id_remito`.

No se agregaron cascadas. Una orden sin muestras puede eliminarse; una orden con
muestras queda protegida por la FK. `MuestraBiologicaDAO` no expone eliminación y
el historial no ofrece eliminación individual. Ningún DAO ejecuta `commit()` ni
`rollback()`: el llamador puede confirmar o revertir como una unidad tanto la
creación de la muestra con su historial inicial como la actualización del estado
con sus nuevos eventos.

Las relaciones del dominio siguen siendo unidireccionales:
`Atencion -> OrdenDerivacionLaboratorio -> MuestraBiologica`,
`MuestraBiologica -> HistorialEstadoMuestra` y
`MuestraBiologica -> EstadoMuestra`. Las FK no agregan relaciones inversas al
modelo de objetos.

Los archivos incorporados son:

```text
src/veterinaria/persistencia/
    orden_derivacion_laboratorio_dao.py
    muestra_biologica_dao.py

tests/persistencia/
    test_orden_derivacion_laboratorio_dao.py
    test_muestra_biologica_dao.py
```

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
- `ResultadoAnalisis` mantiene una referencia unidireccional a `MuestraBiologica`.
  `registrar_resultado()` delega en `MuestraBiologica.analizar()` usando la fecha y
  las observaciones del resultado. Una muestra `RECIBIDA` pasa a `ANALIZADA` y
  registra el cambio en su historial sin que el resultado modifique directamente el
  State ni la colección histórica.
- `ANALIZADA` y `RECHAZADA` son estados finales. Una operación inválida devuelve
  `False` sin cambiar el estado ni agregar historial. Como solamente `RECIBIDA`
  admite `analizar()`, una muestra `RECHAZADA` no puede registrar un resultado.
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

## Reportes y patrón Strategy

- `EstrategiaReporte` define la operación común `generar()`. Las cuatro estrategias
  concretas reciben en su constructor las colecciones que necesitan y devuelven
  listas de diccionarios.
- `GeneradorReportes` conserva una estrategia intercambiable. `generar_reporte()`
  delega exclusivamente en `estrategia.generar()` y no conoce la lógica particular
  de ningún reporte. `establecer_estrategia()` permite cambiarla y devuelve `False`
  si recibe `None`, sin reemplazar la estrategia vigente.
- `ReporteAtencionesDerivaciones(atenciones)` relaciona cada atención con su
  veterinario y sus órdenes obtenidas mediante `obtener_ordenes_derivacion()`,
  agrupa los datos de las derivaciones y calcula su cantidad. Las órdenes canceladas
  también se incluyen.
- `ReporteMuestrasRechazadas(remitos)` recorre las muestras públicas de los remitos
  e incluye únicamente las que se encuentran efectivamente en `RECHAZADA`. Obtiene
  la fecha del historial y agrega el contexto del remito, la clínica y el precinto.
  Un precinto roto por sí solo no incorpora una muestra: debe haberse producido la
  transición `EN_TRANSITO -> RECHAZADA`.
- `ReporteVacunasPendientes(mascotas, vacunas, fecha_referencia)` llama a
  `Mascota.obtener_vacunas_pendientes()` y relaciona cada pendiente con su mascota,
  responsable y fecha de referencia. No vuelve a implementar las reglas de
  obligatoriedad, especie, vigencia o vencimiento.
- `ReporteTiemposTransitoProcesamiento(envios)` devuelve un resumen con cantidad y
  promedio de envíos con tránsito completo, calculado como llegada menos salida, y
  cantidad y promedio de muestras procesadas, calculado entre los registros
  `RECIBIDA` y `ANALIZADA`. Cada envío y cada muestra se cuentan una sola vez. Las
  etapas incompletas y las muestras rechazadas no participan del promedio de
  procesamiento; sin datos suficientes, la cantidad es cero y el promedio es
  `None`. Las duraciones se conservan como `timedelta`.

Los cuatro reportes son consultas en memoria y no modifican entidades, estados ni
historiales. Las entidades del dominio no conocen al generador ni a las estrategias;
los reportes aprovechan exclusivamente las relaciones unidireccionales y las APIs
públicas existentes.

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
estado del precinto, rechazo de muestras, prevención de cambios parciales y registro
de resultados con transición de muestras recibidas a `ANALIZADA`. También cubren la
construcción y las referencias de los comprobantes de atención. Los 39 tests del
noveno incremento verifican el cambio y la delegación de estrategias, los cuatro
reportes, sus casos vacíos y múltiples, los promedios de tiempos y que las consultas
no modifiquen el dominio. Los 49 tests de Persistencia 1 verifican conexión e
inicialización, ABMC, reconstrucción de responsables, fechas ISO, SQL parametrizado,
restricciones de integridad, claves foráneas y control externo de transacciones.
Los 81 tests de Persistencia 2 verifican la inicialización de sus cinco tablas, el
ABMC de clínicas, veterinarios, agendas y turnos, los filtros por clínica o
veterinario, las conversiones ISO, la restauración de enums, la carga independiente
de asociaciones, las restricciones de integridad y las transacciones externas.
Los 43 tests de Persistencia 3 verifican las tablas de historias y atenciones, sus
operaciones DAO, filtros, orden determinista, conversiones ISO, valores opcionales,
integridad, carga simple, reconstrucción sin ejecutar reglas de registro, FK
hacia mascota e historia sin reasignación y control externo de transacciones.
Los 42 tests de Persistencia 4 verifican las tablas y DAO de vacunas y aplicaciones,
IDs explícitos, orden de listados, mapeo booleano, fechas ISO, valores opcionales,
integridad, reconstrucción de vacunas, carga simple de mascotas, relaciones fijas,
eliminaciones protegidas por FK y transacciones externas.
Los 61 tests de Persistencia 5 verifican sus tres tablas, ambos DAO, todos los
estados de orden y muestra, reconstrucción sin transiciones ni nuevos eventos,
historial inmutable y orden estable, consistencia State/historial, comparación de
prefijo, actualizaciones incrementales sin duplicados, claves foráneas, eliminación
protegida y transacciones externas.

## Documentación

- [UML editable](docs/uml/DG_TP_Veterinaria.puml) y [diagrama SVG](docs/uml/DG_TP_Veterinaria.svg).
- [DER editable](docs/der/BD_TP_Veterinaria.dbml) y [diagrama SVG](docs/der/BD_TP_Veterinaria.svg).

La fuente UML incluye los DAO de Persistencia 5. Su SVG queda pendiente de
regeneración porque PlantUML no está disponible en el entorno actual.

Los diagramas también incluyen el diseño previsto para incrementos posteriores.
El DER conserva `id_agenda` como identificador técnico de persistencia; el objeto
de dominio no lo utiliza. `agenda_medica.id_veterinario` es único y los días
laborales se almacenan en `agenda_medica_dia`, con clave compuesta
`(id_agenda, dia)`. El DER no requiere cambios para Persistencia 2, Persistencia 3,
Persistencia 4 ni Persistencia 5. El DER ya representa la relación final entre
`muestra_biologica.id_remito` y `remito_biologico.id_remito`, aunque esa FK todavía
no está activa en el esquema SQLite parcial.

## Próximas etapas

La próxima etapa potencial es Persistencia 6 para `ConservadoraIsotermica`,
`PrecintoSanitario` y `RemitoBiologico`, junto con la activación de la FK
`muestra_biologica.id_remito -> remito_biologico.id_remito`. No está implementada.
También permanecen pendientes la persistencia de `Envio`, `Recepcion`,
`ResultadoAnalisis` y `ComprobanteAtencion`, el cierre de `RemitoBiologico`, la
liberación de `ConservadoraIsotermica` y la revisión e integración final.
