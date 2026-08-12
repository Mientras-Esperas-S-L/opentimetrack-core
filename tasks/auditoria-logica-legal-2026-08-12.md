# Auditoría de lógica de negocio, legalidad y alcance — 12/08/2026 (tarde)

Revisión transversal tras cerrar catálogo de permisos, ausencias por horas,
topes consumidos y suspensiones. Cada hallazgo está **verificado en código y,
los tres primeros, reproducidos con datos** antes de escribirse aquí. Al final,
el análisis de si el producto se ha extralimitado.

Estado: **hallazgos abiertos, sin arreglar**. Cada uno lleva su severidad.

---

## 1. Fallos de lógica de negocio

### GRAVE — Un ERTE parcial bloquea cualquier otra ausencia durante meses

`_overlapping` (apps/absences/services.py) trata toda ausencia sin horas como
«el día entero está ocupado». Un ERTE de reducción del 40 % es una ausencia de
meses sin horas, así que mientras dura **no se puede pedir nada más**: ni una
visita médica, ni vacaciones, ni fuerza mayor.

Reproducido: Nuria (ERTE 40 % hasta +70 días) pide 3 días de vacaciones →
`overlapping_absence`. En la realidad la gente en ERTE parcial trabaja el 60 %
y sigue teniendo médicos, exámenes y vacaciones.

**Arreglo:** una suspensión con `reduction_share < 100` no reclama el día
entero: debe convivir con otras ausencias (y probablemente también una parcial
de horas con una reducción, ya que se trabaja parte del día).

### GRAVE — `rostered_on_leave` acusa en falso a quien debe estar planificado

`_check_leave_clashes` (apps/shifts/services.py) no distingue:

- **ERTE de reducción**: Nuria debe estar en el cuadrante (al 60 %), y el
  cuadrante le suelta 21 avisos de «planificada en día de ausencia aprobada»
  este mes. Todos falsos.
- **Permisos de horas**: Rocío (3 h de fuerza mayor) y Nerea (1 h de lactancia)
  también avisadas. Trabajan el resto del día; estar planificadas es correcto.

Reproducido: 30 avisos este mes, 23 falsos (Nuria 21, Rocío 1, Nerea 1). Los de
Paco y Elena (ausencias de días completos) son los únicos legítimos.

Un aviso que se equivoca 23 de 30 veces entierra los 7 buenos: es el mismo
razonamiento por el que se arregló el relevo de turnos.

**Arreglo:** excluir del choque las ausencias con `start_time` (quizá avisar
solo si el turno no deja hueco para la ausencia) y las suspensiones con
`reduction_share < 100`.

### GRAVE — Aviso falso de tope para permisos contados en semanas

`overAllowance` en MyLeave.jsx compara **días naturales pedidos contra el tope
en su unidad** sin convertir: solo excluye HOURS. El permiso parental (8
semanas, por evento) avisa «da 8 · semanas y estás pidiendo 42» a cualquiera
que pida más de 8 *días*. También infla el aviso en permisos de días
laborables (compara naturales contra laborables).

**Arreglo:** convertir a la unidad del permiso (semanas × 7; laborables
excluyendo finde) o limitar el aviso a DAYS_CALENDAR.

### MEDIO — El que aprueba no ve avisos en permisos «por evento»

`leave_over_the_limit` devuelve `None` para `period=EVENT` (remaining es None
por diseño). Reproducido: boda de 30 días —el 37.3.a da 15— y la tarjeta del
aprobador no dice nada. El que **pide** sí ve el aviso (el front lo calcula
aparte). Incoherencia: la advertencia existe donde menos decide y falta donde
más.

**Arreglo:** para EVENT, comparar la duración de *esa* solicitud contra el
tope (misma conversión de unidad que el punto anterior) en
`leave_over_the_limit`.

### MEDIO — Cuadrante y registro miden el ERTE con varas distintas

Lo **planificado** se mide contra el contrato reducido (`_check_weekly_hours`
aplica `_reduced_share`); lo **trabajado** no (`_check_time_actually_worked`
compara contra el contrato entero). Nuria, contratada a 25 h y reducida al
60 % (15 h): el cuadrante avisa por encima de 15, el registro solo por encima
de 25. Las horas entre 15 y 25 trabajadas durante un ERTE son exactamente las
que una inspección de un ERTE busca.

**Arreglo:** aplicar `_reduced_share` también al contraste con lo fichado.

### MEDIO — Quien aprueba un ERTE no ve el porcentaje

`reduction_share` viaja en el serializer pero ni la tarjeta de Decisiones ni el
historial de MyLeave lo pintan. Se aprueba «ERTE · 91 días» sin saber si
suspende entero o reduce el 10 %. Es el dato que define la solicitud.

### MEDIO — Vacaciones infracontadas con cuadrante a medio publicar

`_days_within` (unidad laborable): si hay **algún** turno dentro del rango de
la ausencia, cuenta solo los días con turno. Vacaciones del 1 al 14 con
cuadrante publicado solo la primera semana → descuenta 5 en vez de 10. Es el
caso normal: las vacaciones se piden a meses vista y el cuadrante se publica a
semanas vista. (Sin ningún turno cae a lunes-viernes, que sí es razonable.)

**Arreglo:** usar el cuadrante solo para los días que cubre y lunes-viernes
para el resto del rango; o exigir cobertura completa para fiarse de él.

### MEDIO — El art. 36.3 se aplica a quien no va a turnos

`_check_night_work` lanza `consecutive_night_weeks` sin comprobar
`person.rotating_shifts`. Álvaro (vigilante de noches fijas, sin turnos)
aparece como infractor permanente de un artículo que regula «el trabajo a
turnos». La semilla ya lo muestra. Además, a quien la empresa declaró
`night_worker=YES` por contrato (contratado para noches) se le podría tratar
como adscripción voluntaria en vez de pedirle la casilla.

**Arreglo:** condicionar a `rotating_shifts`; valorar que `night_worker=YES`
implique adscripción.

### MEDIO — El bloqueo del fichaje usa la fecha de la empresa, no de la persona

`register_punch` calcula `today` con `company.tzinfo` mientras que
`punches_of_the_day` ya usa `employee.tzinfo`. Para Canarias, entre las 23:00 y
las 24:00 Madrid la ausencia de «mañana» bloquea o deja de bloquear una hora
mal. Mismo error que ya se corrigió para partir el día, un nivel más arriba.

### MENORES

- **`LeaveType.code` editable por PATCH** (no está en `read_only_fields` del
  serializer de escritura): cambiarlo rompe el resembrado (recrea el original)
  o choca con la restricción única.
- **`leave-usage` no se invalida** tras pedir una ausencia en MyLeave: el aviso
  de «llevas X» queda desactualizado hasta recargar.
- **Reducción permitida en cualquier suspensión**: una excedencia «al 40 %» no
  existe; restringir a ERTE/RED (la huelga parcial es real, pero se expresa
  mejor por horas).
- **Decimales con punto** en el aviso del aprobador («lleva 5.38 de 4»).
- **N+1 asumidos**: `over_the_limit` por fila pendiente, `holidays_for` por
  persona, `_reduced_share` por persona-semana. Irrelevante a esta escala;
  anotado para cuando duela.
- **Latente**: `leave_usage` con unidad WEEKS y periodo acumulable sumaría días
  contra un tope en semanas. Ningún tipo actual lo pisa (los de semanas son
  todos por evento).
- **Festivos autonómicos/locales no sombrean el cuadrante** (solo los de
  empresa entera). Decisión consciente —sombrear la columna diría que libra
  gente que no libra— pero con un solo centro resulta rara; sombrear cuando
  todas las personas visibles comparten centro sería lo fino.

---

## 2. Cuestiones legales

1. **Exámenes (23.1.a) sembrado como retribuido.** El artículo da el permiso;
   la retribución la suele dar (o no) el convenio. `paid=True` por defecto es
   generoso sin base. Cambiar a no retribuido con nota, o nota más explícita.
2. **Los 5 días del 37.3.b en días naturales.** Hay doctrina (SAN) y muchos
   convenios que los cuentan laborables y desde el primer día laborable. Como
   suelo estatal es defendible, pero la nota debería avisar de que el convenio
   suele mejorarlo, porque es de los que más se consultan.
3. **Huelga como solicitud «aprobable».** El ejercicio de huelga no se pide ni
   se aprueba: se comunica. Modelarla como PENDING→APPROVED invierte el
   derecho (art. 28.2 CE). Igual el cierre patronal: lo decide la empresa. Ver
   §4.
4. **ERTE sin rango 10–70.** El art. 47 acota la reducción entre el 10 y el
   70 %; aceptamos 1–100. Coherente con «avisar, no impedir», pero ni siquiera
   avisamos fuera de rango. Nota o aviso suave.
5. Verificado y correcto (para que conste): el promedio nocturno se calcula
   sobre la jornada total y no solo las horas nocturnas (así lo dice el 36.1);
   el máximo del 34.1 no se reduce con el ERTE (corregido hoy); las citas no
   pasan por gettext; los suelos de menores no son configurables.

---

## 3. Incoherencias menores de producto

- El aviso de tope aparece al pedir pero no al aprobar (EVENT) — cubierto
  arriba.
- `measured_in_hours` no incluye la fuerza mayor (unidad laborable con tope),
  cuya nota dice «se pide por horas»: el formulario arranca en días completos
  para el permiso más pensado para horas.
- docs/cobertura-legal.md declara «Suspensiones: cubiertas»; con los fallos del
  ERTE parcial la calidad real es «cubiertas con dos defectos conocidos».
  Actualizar al arreglar.

---

## 4. ¿Nos hemos extralimitado?

La vara sigue siendo la de docs/cobertura-legal.md: *¿el registro necesita esto
para leerse y defenderse ante una inspección?* Y los ADR-0011/0012 del repo
privado, que meten expresamente en el Core «jornada y fichajes · ausencias y
permisos · vacaciones · turnos y cuadrantes · horas extraordinarias · saldos ·
informes» y dejan fuera «nóminas · contratos · desempeño · selección ·
formación · prevención».

**Veredicto: no hay extralimitación estructural.** Todo lo construido esta
semana (catálogo, horas, topes, suspensiones, festivos, centros, alcance de
responsables) cae dentro de esa lista o es su consecuencia directa. No se ha
construido nómina, ni tramitación ante la Seguridad Social, ni PRL, ni
gestión documental.

**Zonas ámbar, a vigilar (declarativas hoy; cruzarían la línea si calculan):**

| Qué | Dónde está la línea |
|---|---|
| `paid` y «quién paga» en cada permiso | Declarar sí; calcular importes o cotización, nunca |
| Topes y consumos | Contar tiempo sí; generar liquidaciones, no |
| Nota del 36.4 (evaluación de salud del nocturno) | Avisar de que existe sí; programar reconocimientos es PRL |
| Excedencias | Fechas y efecto sobre jornada sí; derechos de reingreso, no |

**Una extralimitación real, pero de modelado y no de alcance:** el flujo
solicitar→aprobar trata **actos del empresario o hechos consumados como
permisos que pide el trabajador**. Un empleado puede hoy «solicitarse» un ERTE,
una suspensión disciplinaria o un cierre patronal, y la huelga queda como algo
que la empresa «aprueba». El dato pertenece al registro (por eso el catálogo
está bien); el *flujo* no encaja para esos tipos.

**Propuesta:** un campo `initiated_by` en LeaveType (persona / empresa). Los de
empresa no aparecen en el diálogo del trabajador ni pasan por la cola: los
registra dirección directamente como aprobados (con su auditoría). La huelga,
además, sin estado de aprobación.

---

## 5. Orden de arreglo propuesto

1. Los tres GRAVES (ERTE bloquea ausencias · rostered_on_leave falsos · aviso
   de semanas del front): rompen el uso real y ensucian la demo.
2. Tope por evento visible para el aprobador + % de reducción visible.
3. Coherencia planificado/trabajado bajo ERTE y fecha del bloqueo por persona.
4. `initiated_by` en el catálogo (la corrección de modelado del §4).
5. Vacaciones con cuadrante parcial y art. 36.3 solo a rotativos.
6. Los menores, en lote.
