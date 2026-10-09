# TP Veterinaria

## Trabajo Práctico Integrador 2026

**Materia:** Desarrollo de Aplicaciones con Objetos
**Carrera:** Ingeniería en Sistemas de Información
**Tema 2:** Veterinaria — Red de Clínicas y Derivación de Laboratorio

---

## 1. Descripción

El proyecto consiste en el desarrollo de un sistema para una red de clínicas veterinarias que permita integrar la atención clínica de mascotas con la derivación de muestras biológicas hacia un laboratorio central.

El sistema deberá gestionar el circuito completo desde la atención veterinaria hasta la obtención del resultado de laboratorio, garantizando la trazabilidad de las muestras durante su extracción, empaquetado, transporte, recepción y análisis.

Uno de los ejes principales del proyecto es el seguimiento del ciclo de vida de `MuestraBiologica`, incluyendo el rechazo automático de muestras cuando el precinto sanitario utilizado durante el transporte llega roto.

---

## 2. Objetivos principales

El sistema permitirá:

- administrar clientes;
- administrar mascotas y sus responsables;
- mantener la historia clínica de cada mascota;
- registrar atenciones veterinarias;
- administrar la agenda médica de los veterinarios;
- registrar turnos evitando superposiciones;
- controlar vacunas obligatorias;
- emitir órdenes de derivación al laboratorio;
- registrar muestras biológicas;
- gestionar el empaquetado y transporte de las muestras;
- generar remitos biológicos;
- administrar conservadoras isotérmicas;
- registrar precintos sanitarios;
- registrar envíos hacia el laboratorio;
- registrar la recepción de las muestras;
- rechazar muestras cuando el precinto llegue roto;
- registrar resultados de análisis;
- emitir comprobantes de atención;
- mantener la trazabilidad completa de los estados de las muestras;
- generar reportes de gestión.

---

## 3. Alcance del MVP

La primera versión del proyecto se concentra en los procesos obligatorios del trabajo práctico.

### Funcionalidades incluidas

#### Gestión clínica

- Clientes.
- Mascotas.
- Historias clínicas.
- Veterinarios.
- Clínicas.
- Atenciones veterinarias.
- Comprobantes de atención.

#### Agenda médica

Cada veterinario puede tener una o más franjas horarias definidas mediante `AgendaMedica`.

Un turno sólo podrá registrarse si:

1. la fecha y hora de finalización es posterior a la fecha y hora de inicio;
2. el turno se encuentra completamente dentro de una franja de `AgendaMedica`;
3. no se superpone con otro turno activo del mismo veterinario.

Dos turnos consecutivos son válidos.

Ejemplo:

```text
09:00 - 09:30
09:30 - 10:00
```

Un turno en estado `CANCELADO` no bloquea la franja horaria.

#### Vacunación

Se modelan:

- `Vacuna`: representa un tipo de vacuna.
- `AplicacionVacuna`: representa la aplicación concreta de una vacuna a una mascota.

Al registrar una atención se deberá poder verificar el estado de las vacunas obligatorias de la mascota.

#### Derivación de laboratorio

Una atención veterinaria puede generar una o más órdenes de derivación al laboratorio.

Cada `OrdenDerivacionLaboratorio` podrá originar muestras biológicas para los estudios solicitados.

#### Transporte de muestras

Las muestras podrán ser agrupadas en un `RemitoBiologico`.

Cada remito utilizará:

- una `ConservadoraIsotermica`;
- un `PrecintoSanitario`;
- una o más muestras biológicas.

El remito será utilizado para registrar el transporte desde la clínica de origen hacia el laboratorio central.

#### Recepción

Al recibir un envío se deberá verificar el precinto sanitario.

Si el precinto está:

```text
INTACTO
```

las muestras podrán pasar a:

```text
RECIBIDA
```

Si el precinto está:

```text
ROTO
```

las muestras pasarán a:

```text
RECHAZADA
```

Una muestra rechazada no podrá ser procesada ni analizada.

---

## 4. Entidad central del proceso

`MuestraBiologica` constituye una de las entidades principales del sistema.

Su ciclo de vida es:

```text
EXTRAIDA
    ↓
EMPAQUETADA
    ↓
EN_TRANSITO
    ↓
RECIBIDA
    ↓
ANALIZADA
```

Existe además el camino alternativo:

```text
EN_TRANSITO
    ↓
RECHAZADA
```

Cada cambio de estado deberá generar un registro de `HistorialEstadoMuestra`.

Los registros del historial son considerados inmutables.

---

## 5. Reglas de negocio principales

### RN01 — Responsable de mascota

Toda mascota debe tener un cliente responsable asociado.

### RN02 — Agenda médica

Todo turno debe encontrarse dentro de una franja horaria definida en la agenda médica del veterinario.

### RN03 — Superposición de turnos

Un veterinario no puede tener dos turnos activos cuyos intervalos horarios se superpongan.

Se considera superposición cuando:

```text
nuevo_inicio < turno_existente_fin
AND
nuevo_fin > turno_existente_inicio
```

Los turnos consecutivos no se consideran superpuestos.

### RN04 — Agenda médica válida

Las franjas horarias de `AgendaMedica` de un mismo veterinario no deben superponerse.

Además:

```text
hora_hasta > hora_desde
```

### RN05 — Vacunación

Al registrar una atención se deberán controlar las vacunas obligatorias correspondientes a la mascota.

### RN06 — Estado inicial de muestra

Toda muestra se crea inicialmente en estado:

```text
EXTRAIDA
```

### RN07 — Empaquetado

Cuando una muestra es asociada a un remito y empaquetada pasa a:

```text
EMPAQUETADA
```

### RN08 — Despacho

Al despacharse el envío, las muestras pasan a:

```text
EN_TRANSITO
```

### RN09 — Condiciones del remito

Un remito sólo puede despacharse si dispone de:

- una conservadora isotérmica;
- un precinto sanitario;
- al menos una muestra.

### RN10 — Recepción

En la recepción debe verificarse obligatoriamente el estado del precinto.

### RN11 — Precinto intacto

Si el precinto está intacto, las muestras pasan a:

```text
RECIBIDA
```

### RN12 — Precinto roto

Si el precinto está roto, las muestras pasan a:

```text
RECHAZADA
```

y no pueden continuar hacia el análisis.

### RN13 — Resultado

Al registrar el resultado de una muestra válida, su estado pasa a:

```text
ANALIZADA
```

### RN14 — Trazabilidad

Cada cambio de estado debe generar un nuevo registro de `HistorialEstadoMuestra`.

### RN15 — Historial inmutable

Los registros históricos de estado no deben modificarse.

---

## 6. Patrones de diseño

El proyecto utilizará al menos dos patrones de diseño.

### State

Se utilizará el patrón **State** para administrar el ciclo de vida de `MuestraBiologica`.

Estados previstos:

```text
EstadoExtraida
EstadoEmpaquetada
EstadoEnTransito
EstadoRecibida
EstadoAnalizada
EstadoRechazada
```

El objetivo es evitar que las reglas de transición dependan de una gran cantidad de condiciones `if/elif`.

Las transiciones inválidas deberán ser rechazadas explícitamente.

### Strategy

Se utilizará el patrón **Strategy** para implementar los diferentes reportes.

La interfaz principal será:

```text
EstrategiaReporte
```

y el contexto:

```text
GeneradorReportes
```

Estrategias previstas:

```text
ReporteAtencionesDerivaciones
ReporteMuestrasRechazadas
ReporteVacunasPendientes
ReporteTiemposTransitoProcesamiento
```

Por el momento no se implementará Observer.

---

## 7. Reportes previstos

El sistema deberá implementar al menos cuatro reportes no triviales.

### 1. Atenciones y derivaciones

Permitirá analizar:

- atenciones realizadas;
- tipo de atención;
- veterinario;
- mascota;
- clínica;
- derivaciones generadas.

### 2. Muestras rechazadas

Permitirá analizar:

- muestras rechazadas;
- tipo de muestra;
- fecha de rechazo;
- remito;
- clínica de origen;
- estado del precinto.

### 3. Vacunas pendientes

Permitirá identificar:

- mascotas con vacunas obligatorias pendientes;
- vacunas vencidas;
- próximas dosis;
- responsable de la mascota.

### 4. Tiempos de tránsito y procesamiento

Permitirá calcular, entre otros:

```text
Tiempo de tránsito =
fecha/hora de llegada - fecha/hora de salida
```

y:

```text
Tiempo de procesamiento =
fecha/hora del resultado - fecha/hora de recepción
```

---

## 8. Procesos opcionales fuera del MVP inicial

Por el momento no se desarrollarán:

- recordatorios automáticos;
- internaciones;
- stock completo de insumos;
- agenda de profesionales del laboratorio;
- derivaciones para cirugías de alta complejidad;
- facturación completa;
- autenticación de usuarios;
- interfaces web complejas;
- patrón Observer.

Estas funcionalidades podrán incorporarse posteriormente si el alcance del proyecto lo requiere.

---

## 9. Documentación del proyecto

La documentación actual se encuentra en:

```text
docs/
│
├── der/
│   ├── BD_TP_Veterinaria.dbml
│   └── BD_TP_Veterinaria.svg
│
├── enunciado/
│   └── Enunciado.pdf
│
└── uml/
    ├── DG_TP_Veterinaria.puml
    └── DG_TP_Veterinaria.svg
```

### DER

Fuente editable:

```text
docs/der/BD_TP_Veterinaria.dbml
```

Representación gráfica:

```text
docs/der/BD_TP_Veterinaria.svg
```

### Diagrama de clases UML

Fuente editable:

```text
docs/uml/DG_TP_Veterinaria.puml
```

Representación gráfica:

```text
docs/uml/DG_TP_Veterinaria.svg
```

---

## 10. Estructura prevista del proyecto

```text
Veterinaria/
│
├── AGENTS.md
├── README.md
├── requirements.txt
├── .gitignore
│
├── docs/
│   ├── der/
│   ├── enunciado/
│   └── uml/
│
├── src/
│   └── veterinaria/
│       │
│       ├── dominio/
│       │   ├── clinica/
│       │   ├── vacunacion/
│       │   ├── laboratorio/
│       │   └── transporte/
│       │
│       ├── patrones/
│       │   ├── state/
│       │   └── strategy/
│       │
│       ├── servicios/
│       ├── persistencia/
│       └── main.py
│
└── tests/
```

La estructura podrá evolucionar durante la implementación siempre que se mantenga la separación de responsabilidades definida por el modelo.

---

## 11. Tecnología prevista

Lenguaje principal:

```text
Python
```

Entorno de desarrollo:

```text
Visual Studio Code
```

Control de versiones:

```text
Git + GitHub
```

Pruebas:

```text
pytest
```

Modelado DER:

```text
DBML / dbdiagram.io
```

Modelado UML:

```text
PlantUML
```

La tecnología de persistencia será definida durante una etapa posterior del proyecto.

---

## 12. Estrategia de implementación

El desarrollo se realizará de forma incremental.

Orden previsto:

```text
1. Clínica + Veterinario + AgendaMedica + Turno
                    ↓
2. Cliente + Mascota + HistoriaClinica + Atencion
                    ↓
3. Vacuna + AplicacionVacuna
                    ↓
4. OrdenDerivacionLaboratorio
                    ↓
5. MuestraBiologica + patrón State
                    ↓
6. Remito + Conservadora + Precinto
                    ↓
7. Envio + Recepcion
                    ↓
8. ResultadoAnalisis
                    ↓
9. Persistencia
                    ↓
10. Strategy + reportes
                    ↓
11. Integración final
```

Cada incremento deberá incluir pruebas de las reglas de negocio correspondientes.

---

## 13. Primer incremento

El primer módulo a implementar será:

```text
Clinica
Veterinario
AgendaMedica
Turno
```

Las primeras pruebas deberán validar:

```text
✓ turno dentro de agenda
✓ turno fuera de agenda
✓ turnos consecutivos
✓ turnos superpuestos
✓ turno cancelado libera horario
✓ agenda médica superpuesta
✓ hora de fin posterior a hora de inicio
```

Inicialmente estas clases funcionarán en memoria.

La persistencia se incorporará posteriormente.

---

## 14. Persistencia

El esquema de persistencia deberá respetar el DER definido en:

```text
docs/der/BD_TP_Veterinaria.dbml
```

La implementación de la base de datos no forma parte del primer incremento.

Primero se implementarán y probarán las reglas del dominio orientado a objetos.

---

## 15. Tests

Se utilizará `pytest`.

Las principales reglas que deberán estar cubiertas por pruebas incluyen:

```text
Agenda y turnos
Vacunas obligatorias
Estados de MuestraBiologica
Transiciones inválidas
Trazabilidad
Precinto roto
Muestra rechazada
Remitos
Recepción
Resultados
Reportes
```

---

## 16. Estado actual del proyecto

### Completado

```text
✓ Análisis inicial del enunciado
✓ Definición del alcance del MVP
✓ Identificación de entidades principales
✓ DER inicial estable
✓ Incorporación de AgendaMedica al DER
✓ Diagrama de clases UML
✓ Incorporación de AgendaMedica al UML
✓ Definición de reglas de negocio principales
✓ Selección del patrón State
✓ Selección del patrón Strategy
✓ Definición de cuatro reportes
✓ Organización inicial del repositorio
✓ Definición de AGENTS.md
```

### Próximo paso

```text
Implementar el primer incremento:

Clinica
Veterinario
AgendaMedica
Turno

junto con sus tests.
```

---

## 17. Flujo de trabajo con Git

El proyecto se desarrollará utilizando Git.

Flujo básico:

```bash
git add .
git commit -m "descripcion del cambio"
git push
```

Después de cada commit deberá revisarse si `README.md` necesita ser actualizado.

Los cambios relevantes de funcionalidad, estructura, dependencias o estado del proyecto deberán reflejarse en este documento.

---

## 18. Convenciones generales

Se buscará mantener:

- código simple y legible;
- clases con responsabilidades claras;
- nombres coherentes con el UML;
- encapsulamiento;
- separación entre dominio y persistencia;
- tests para reglas de negocio;
- desarrollo incremental;
- documentación sincronizada con el código.

No se agregarán nuevas entidades, patrones o dependencias sin una necesidad concreta.

---

## 19. Estado del proyecto

**Estado:** en desarrollo.

Actualmente se encuentra establecida una primera versión consistente del análisis, DER y diagrama de clases.

La siguiente etapa corresponde a la implementación del modelo de dominio en Python.