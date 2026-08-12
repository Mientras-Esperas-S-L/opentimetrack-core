# Segunda auditoría — 12/08/2026 (noche)

Sobre el trabajo del propio día: los arreglos de la auditoría de la tarde,
`initiated_by`, el diálogo compartido, el arrastre del cuadrante y el reloj.
Método: sondas **ejecutadas contra la API** (no lectura de código), greps
dirigidos y verificación en navegador. Todo lo encontrado quedó **arreglado y
con test en la misma sesión**; este documento es el registro.

---

## Arreglado antes de la auditoría (los cuatro MEDIOS pendientes de la tarde)

1. **Lo fichado se mide contra el contrato reducido**, como lo planificado.
   `_check_time_actually_worked` aplica `_reduced_share`; el máximo legal del
   34.1 sigue quieto, como en el cuadrante. Test con fichajes reales: 30 h
   trabajadas con contrato de 40 reducido al 60 % → avisa contra 24.
2. **El cuadrante habla solo hasta donde llega.** `_days_within` usa el
   horizonte (último día con turno de esa persona): dentro, sus huecos son
   descansos reales; más allá, lunes-viernes. Una quincena con una semana
   publicada vuelve a costar diez días, y una rotación con cuadrante largo
   sigue costando solo los días rotados.
3. **El art. 36.3 exige rotación.** `consecutive_night_weeks` solo con
   `rotating_shifts`: el vigilante de noches fijas deja de ser un infractor
   permanente de una regla sobre rotaciones.
4. **El «hoy» es el de la persona.** Nuevo `apps/common/clock.py:local_today`.
   El bloqueo por ausencia, el endpoint de «hoy» del cuadrante y el consumo de
   permisos usan la zona del centro de la persona; los tres `date.today()` de
   informes pasan a `timezone.localdate()` (zona de la empresa vía middleware).
   `date.today()` era la fecha UTC del contenedor: ayer, para toda España,
   entre las 00:00 y la 01:00.

## Hallazgos de la segunda pasada

### GRAVE — La suspensión sin tipo rodeaba `initiated_by` entero

Sonda: una trabajadora hace `POST /api/absences/` con
`absence_type=SUSPENSION`, **sin** `leave_type`, y `reduction_share=70`.
Resultado: **201**. Sin tipo no hay `initiated_by` que respetar, así que la
regla «un ERTE lo registra la empresa» se rodeaba con dejar el tipo en blanco
— y encima con reducción, que puso su cuadrante a medirse contra el 30 %.

**Arreglo (en el servicio, no en la vista, para que ninguna vía lo salte):**
una suspensión tiene que decir cuál de las quince es
(`suspension_needs_its_kind`). Cruda no lleva artículo ni nombre para el
informe. Re-sonda: **409**.

### GRAVE — La excedencia «al 40 %» existía

Sonda: la misma trabajadora pide excedencia voluntaria (tipo que sí puede
pedir) con `reduction_share=40`. Resultado: **201**, pendiente. Si un
responsable la aprueba sin fijarse en un campo que no espera, el cuadrante
pasa a medir a esa persona contra un contrato que nadie redujo lícitamente.

**Arreglo:** la reducción es de las suspensiones que registra la empresa
(`reduction_is_company_recorded`): ERTE y RED. El formulario tampoco la ofrece
ya fuera de esas. Re-sonda: **409**.

### MEDIO — El Deshacer del cuadrante se ofrecía antes de guardar

`setUndo` corría antes de que `paint.mutate` tuviera éxito, en el pincel y en
el movimiento: un trazo que fallara (permiso, red) dejaba una barra ofreciendo
«deshacer» celdas que nunca cambiaron. Ahora el deshacer aparece en el
`onSuccess` de cada trazo.

### Del formulario, cazado en la verificación en navegador (ya en el commit anterior)

Elegir una suspensión arrancaba el formulario en «parte de un día»: el ERTE,
al no tener tope fijo, caía en la heurística de «se pide por horas». Meses
ofrecidos por horas. Excluida la familia SUSPENSION de esa heurística.

## Anotado, sin tocar (con motivo)

- **Agrupación semanal de lo fichado en zona de la empresa**
  (`_check_time_actually_worked`): para un canario, un fichaje entre las 23:00
  y las 24:00 del domingo cae en la semana ISO siguiente según Madrid. Afecta
  a en qué semana se suma una hora, no a si se suma; arreglarlo exige agrupar
  por persona-zona y no compensa hoy.
- **`es-ES` en 8 formatos del frontend y artículos en los hints de
  People.jsx**: deuda de internacionalización ya registrada en la auditoría de
  la tarde. El frontend entero es español-solo de momento.
- **N+1 conocidos**: el horizonte del cuadrante añade una consulta por
  ausencia contada. A esta escala, irrelevante; anotado junto a los demás.
- **Cerrar antes de tiempo una suspensión en vigor** (un ERTE que acaba antes)
  no tiene flujo: hoy sería editarla por administración. Falta de producto,
  no fallo; va a la cobertura como pendiente.

## Verificación final

- 582 tests en verde (incluye los 2 de las sondas y los 4 de los MEDIOS).
- Sondas re-ejecutadas contra la API: 409 y 409.
- 533 cadenas traducidas, ninguna suelta.
- eslint y build limpios; migraciones al día; navegador comprobado
  (formulario, cuadrante con movimiento y deshacer, tarjeta del aprobador).
