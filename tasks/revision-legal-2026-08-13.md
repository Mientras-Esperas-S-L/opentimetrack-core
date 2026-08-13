# Revisión legal punto por punto — 13/08/2026

Repaso de toda la normativa que le toca a un registro de jornada español,
comprobando **en el código** si está aplicada, solo citada, o ausente. No vale
que una regla esté escrita en `apps/legal/es.py`: eso es el marco, no la
aplicación. Aquí solo cuenta lo que se ejecuta.

Tres estados:

- **Aplicado** — hay código que lo hace cumplir o lo avisa, y hay prueba.
- **Solo citado** — el número está en el marco legal o en un ajuste, pero nada
  lo comprueba. Es lo más peligroso: parece cubierto y no lo está.
- **Ausente**.

---

## 1. Registro de jornada · art. 34.9 ET y RD-ley 8/2019

| Punto | Estado | Dónde |
|---|---|---|
| Registro diario con hora de inicio y fin | **Aplicado** | `Punch`, hora de servidor |
| Objetivo y fiable (no manipulable) | **Aplicado** | hash SHA-256 versionado, borrado lógico, hora del servidor |
| Conservación cuatro años | **Aplicado** | `record_retention_years`, purga solo de metadatos |
| A disposición de la persona | **Aplicado** | «Mi jornada» |
| A disposición de la ITSS | **Aplicado** | Informes, PDF/CSV con huella |
| A disposición de la representación legal | **Parcial** | existe `is_worker_representative` y se le informa de las discrepancias del art. 4.b, pero **no hay una vista propia** ni una entrega periódica |
| Organizado previa negociación o consulta con la RLT | **Ausente** | no se guarda qué acuerdo ampara el modo de registro ni desde cuándo. Es un dato que la Inspección pide |
| Totalización mensual entregada con la nómina | **Aplicado** | «Resumen para la nómina», `payroll_period` |

## 2. Jornada · art. 34 ET

| Punto | Estado | Dónde |
|---|---|---|
| 40 h semanales de promedio anual (34.1) | **Aplicado** | `_check_weekly_hours` |
| Máximo 9 h diarias salvo pacto (34.3) | **Aplicado** | comprobado en el cuadrante |
| 12 h entre jornadas (34.3) | **Aplicado** | `_check_daily_rest` |
| Descanso de 15 min si la jornada continuada pasa de 6 h (34.4) | **Aplicado** | `_check_breaks` |
| Menores: 30 min si pasa de 4,5 h (34.4) | **Aplicado** | `_check_under_eighteen` |
| Distribución irregular del 10 % (34.2) | **Solo citado** | existe `flexibility_measure` en el fichaje, pero **nadie comprueba el 10 %** |
| Adaptación de jornada por conciliación (34.8) | **Parcial** | se puede anotar en el fichaje; no hay solicitud ni resolución |

## 3. Descanso semanal y festivos · art. 37 ET

| Punto | Estado |
|---|---|
| Día y medio ininterrumpido, acumulable a 14 días (37.1) | **Aplicado** (`_check_weekly_rest`) |
| Menores: dos días ininterrumpidos | **Aplicado** |
| 14 festivos al año, con calendario por centro | **Aplicado** (`PublicHoliday` por centro; BOE nacional y autonómico, local a mano) |
| Aviso de turno en festivo | **Aplicado** (`_check_rostered_on_a_holiday`) |

## 4. Horas extraordinarias · art. 35 ET

| Punto | Estado | Nota |
|---|---|---|
| Registro día a día y totalización | **Aplicado** | |
| Compensación en descanso dentro de 4 meses, o pago (35.1) | **Aplicado** | `OvertimeSettlement`, decidido por un responsable |
| **Tope de 80 h al año (35.2)** | **SOLO CITADO — hueco grave** | `annual_overtime_hours` está en los ajustes, en el marco legal y en el validador de convenios. **Nada lo cuenta ni lo avisa.** Ver abajo |
| Las compensadas con descanso no cuentan al tope (35.2) | **Ausente** | consecuencia del anterior |
| Fuerza mayor no computa (35.3) | **Aplicado** | `force_majeure` en el fichaje |
| Prohibidas a trabajadores nocturnos (36.1) | **Aplicado** | aviso en el cuadrante |
| Prohibidas a menores (6.3) | **Aplicado** | |
| A tiempo parcial no hay extras, sí complementarias (12.4.c) | **Aplicado** | `complementary_hours_share` |

## 5. Trabajo nocturno y a turnos · art. 36 ET

| Punto | Estado |
|---|---|
| Franja 22:00–06:00 configurable (36.1) | **Aplicado** |
| Máximo 8 h de promedio en 15 días (36.1) | **Aplicado** (`_check_night_average`) |
| No más de 2 semanas seguidas de noche salvo voluntariedad (36.3) | **Aplicado** |
| Evaluación de salud gratuita (36.4) | **Parcial** | se avisa de que nadie ha dejado constancia; no se guarda la fecha de la evaluación ni se avisa de su caducidad |

## 6. Vacaciones · art. 38 ET

| Punto | Estado |
|---|---|
| Mínimo 30 días naturales / 22 laborables (38.1) | **Aplicado**, y configurable en las dos unidades |
| **Devengo proporcional** en altas y bajas a mitad de periodo | **Aplicado el 13/08/2026** — antes daba el año entero desde el primer día |
| Periodo de cómputo configurable (no tiene por qué ser el año natural) | **Aplicado** |
| Calendario conocido con dos meses de antelación (38.3) | **Solo citado** | la cita está en el marco; nadie comprueba la antelación |
| **IT o maternidad que solapa las vacaciones: se disfrutan después (38.3)** | **AUSENTE — hueco grave** | si alguien cae de baja durante sus vacaciones, hoy pierde esos días. Ver abajo |
| No sustituibles por dinero salvo fin de contrato | **No aplica** | el producto no liquida; no hay forma de «pagarlas» |

## 7. Permisos retribuidos · art. 37.3 ET

**Aplicado** y es de lo más completo: catálogo por país con 32 permisos, cada
uno con su artículo, su cuantía, su unidad y quién lo inicia
(`initiated_by`), topes consumidos, ausencias por horas y justificantes.

Cubiertos: fallecimiento y hospitalización, matrimonio y pareja de hecho,
traslado, deber inexcusable, exámenes, lactancia (37.4), permiso parental,
funciones sindicales, búsqueda de empleo en el preaviso, cuidado de familiar,
fuerza mayor familiar (37.9), y las bajas y suspensiones del art. 45.

## 8. Suspensiones del contrato · art. 45–48 ET

**Aplicado**: IT, nacimiento y cuidado, riesgo durante el embarazo,
excedencias, ERTE con reducción de jornada y su porcentaje. Con `initiated_by`
para que una suspensión que registra la empresa no se pueda pedir como permiso.

## 9. Teletrabajo · Ley 10/2021

| Punto | Estado |
|---|---|
| El registro refleja el tiempo real también a distancia (art. 14) | **Aplicado** (`work_mode` en el fichaje) |
| Acuerdo de trabajo a distancia con su porcentaje | **Ausente** | fuera del alcance declarado, pero el porcentaje afecta a lo que la Inspección mira |

## 10. Protección de datos · RGPD y LOPDGDD

| Punto | Estado |
|---|---|
| Minimización: IP y dispositivo fuera del hash y purgables | **Aplicado** |
| Plazo de conservación de metadatos configurable | **Aplicado** (365 días por defecto) |
| Registro de accesos a la ficha de cada persona (quién ha mirado) | **Aplicado** — y la persona lo ve, que es lo raro |
| Geolocalización proporcional (art. 20 bis ET) | **Parado a propósito** | el *seam* existe; la UI espera al visto bueno jurídico |
| **Desconexión digital (art. 88 LOPDGDD)** | **Hueco menor** | los recordatorios de jornada abierta pueden llegar a cualquier hora de la noche. Ver abajo |

---

## Los tres huecos que hay que cerrar, por orden

### 1. El tope de 80 horas extra al año no se comprueba — GRAVE

`annual_overtime_hours` es un ajuste que nadie lee. Ni el cuadrante avisa, ni la
cola de horas extra dice cuánto lleva esa persona, ni el informe lo totaliza. Una
empresa puede pasarse del tope del art. 35.2 con este producto sin que nada la
avise, que es exactamente lo que la herramienta existe para evitar.

Y va con su matiz: las extras **compensadas con descanso no computan** en el
tope. Como el producto ya guarda cómo se salda cada día (`OvertimeSettlement`),
puede contarlo bien, que es más de lo que hace media hoja de cálculo.

**Dónde ponerlo:** en la tarjeta de la cola de «Horas extra» («lleva 62 h de 80
este año»), y como comprobación del cuadrante.

### 2. La baja que pisa las vacaciones — GRAVE

Art. 38.3 y jurisprudencia asentada del TJUE: si durante las vacaciones aparece
una IT, esos días **no se pierden** y se disfrutan al terminar, incluso en otro
año natural. Hoy el saldo los da por gastados.

**Dónde ponerlo:** al aprobar una baja que solapa vacaciones aprobadas, devolver
los días al saldo y dejar constancia. Necesita una decisión de diseño: si se
devuelven solos o si se avisa y lo confirma un responsable.

### 3. Recordatorios y desconexión digital — MENOR

El aviso de «jornada abierta» se dispara al pasar el fin del turno y su margen,
y ahí se queda hasta que la persona ficha. Si el turno acaba a las 22:00, el
aviso puede sonar a las 23:30. Art. 88 LOPDGDD.

**Dónde ponerlo:** una ventana de silencio configurable por empresa, y no
mandar nada fuera de ella. El recordatorio no se pierde: sale a la mañana
siguiente o simplemente no sale, porque a esa hora ya no recuerda nada.

---

## Lo que está mejor de lo que hace falta

Vale la pena decirlo, porque marca dónde **no** hay que gastar más:

- El catálogo de permisos con artículo y `initiated_by` es más fino de lo que
  pide la norma.
- El registro de accesos visible por la propia persona no lo exige nadie.
- El flujo del art. 4.b —consentimiento de las dos partes para tocar un asiento,
  y constancia de la discrepancia— está entero.
- El barrido de aislamiento, que falla cuando aparece un endpoint sin cubrir.
