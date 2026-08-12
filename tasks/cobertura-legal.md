# Todo lo que puede pasarle a una jornada, y qué cubrimos

Inventario de las situaciones que la legislación laboral española reconoce y que
afectan al tiempo de trabajo, contrastado con lo que OpenTimeTrack sabe hoy.

Tres estados, y el del medio es el importante:

- **Cubierto** — el sistema lo representa y lo aplica.
- **A medias** — se puede guardar, pero pierde información o no se comprueba
  nada. Es peor que faltar, porque parece que está.
- **Falta** — no existe.

Fecha del corte: 12 de agosto de 2026. Legislación: España, Estatuto de los
Trabajadores tras el RDL 32/2021 y el RDL 5/2023.

---

## 1. Modalidades de contrato

Lo que hoy guardamos del contrato son tres cosas: el **régimen de jornada**
(qué límites aplican), las **fechas** (indefinido o temporal) y **fijo
discontinuo**. La modalidad en sí —por qué causa se contrató— no se guarda.

Para el registro de jornada no hace falta: el art. 3 del proyecto de real
decreto no la pide. Sí hace falta para dos de ellas, que traen límites propios.

| Modalidad | Base | Estado | Nota |
|---|---|---|---|
| Indefinido ordinario | art. 15.1 | **Cubierto** | Fechas vacías al final |
| Temporal por circunstancias de la producción | art. 15.2 | **Cubierto** | Como fecha de fin. La causa no se guarda |
| Temporal por sustitución | art. 15.3 | **Cubierto** | Igual. A quién sustituye, no |
| Fijo discontinuo | art. 16 | **A medias** | Hay casilla, pero **no hay llamamiento ni periodos de actividad**: fuera de temporada el sistema no sabe que no se espera jornada |
| Tiempo parcial | art. 12 | **Cubierto** | Con horas y periodo |
| Formativo en alternancia | art. 11.2 | **A medias** | Hay régimen, pero **no se aplica el tope del art. 11.2.b**: 65 % de la jornada máxima el primer año, 85 % el segundo, formación incluida |
| Formativo para práctica profesional | art. 11.3 | **A medias** | Mismo régimen que el anterior, y son cosas distintas |
| Contrato de relevo | art. 12.7 | **Falta** | La jornada del relevista debe cubrir al menos la reducción de quien se jubila parcialmente. Nada lo comprueba |
| Jubilación parcial | art. 12.6 | **Falta** | Es una jornada reducida con una regla propia |
| Indefinido adscrito a obra (construcción) | Ley 32/2006 | **Cubierto** | Es un indefinido a efectos de jornada |
| Puesta a disposición por ETT | Ley 14/1994 | **Falta** | El registro lo lleva la ETT, pero la empresa usuaria controla la jornada efectiva |

### Relaciones laborales especiales (art. 2 ET)

Once, cada una con su real decreto y su jornada. Ninguna está modelada; el
sistema las trataría como una relación común, que para varias es sencillamente
falso.

Alta dirección · servicio del hogar familiar · penados en instituciones
penitenciarias · deportistas profesionales · artistas en espectáculos públicos ·
representantes de comercio · personas con discapacidad en centros especiales de
empleo · estibadores portuarios · menores en centros de internamiento ·
residentes para formación de especialistas en Ciencias de la Salud · abogados en
despachos.

> La de alta dirección es la que más se va a dar en clientes reales, y es
> precisamente la que **no tiene** jornada máxima legal (RD 1382/1985). Meterla
> como relación común produce avisos de incumplimiento que no lo son.

---

## 2. Tipos de jornada

| Situación | Base | Estado |
|---|---|---|
| Jornada completa | art. 34.1 | **Cubierto** |
| Jornada parcial | art. 12 | **Cubierto** |
| Jornada reducida por guarda legal | art. 37.6 | **A medias** — hay régimen, pero no la fracción reducida ni las fechas |
| Jornada continuada / partida | — | **Cubierto** — por los tramos del turno |
| Trabajo a turnos | art. 36.3 | **Cubierto** — desde hoy |
| Trabajo nocturno | art. 36.1 | **Cubierto** — desde hoy |
| Distribución irregular de la jornada | art. 34.2 | **A medias** — se puede marcar el fichaje, pero **no hay saldo**: el 10 % que la empresa puede distribuir se compensa en 12 meses y nadie lleva la cuenta |
| Adaptación de jornada | art. 34.8 | **A medias** — se marca en el fichaje; la solicitud y su respuesta no se tramitan |
| Horas extraordinarias | art. 35 | **A medias** — se marcan y se dice cómo se saldan, pero **el tope de 80 al año no se comprueba contra lo trabajado** |
| Horas complementarias | art. 12.5 | **A medias** — el cuadrante avisa, el registro también; **el tope mensual del 30 % no se acumula** |
| Guardias y atención continuada | RD 1561/1995 | **Falta** — sanidad. Presencia frente a trabajo efectivo |
| Tiempo de presencia | RD 1561/1995 | **Falta** — transporte. Hasta 20 h semanales de promedio que no son jornada ordinaria |
| Trabajo a distancia | Ley 10/2021 | **A medias** — el fichaje registra la modalidad; el acuerdo y el porcentaje mínimo del 30 %, no |
| Desconexión digital | Ley 3/2018 art. 88 | **Falta** |
| Pluriempleo | art. 34.3 (menores) | **Falta** — el tope de 8 h de un menor suma empleadores |

### Jornadas especiales por sector (RD 1561/1995)

No están modeladas. Hoy la empresa configura sus cifras a mano en Ajustes, lo
cual funciona pero no dice **por qué** se apartó de la regla general, que es lo
que una inspección pregunta.

**Ampliaciones**: empleados de fincas urbanas · guardas y vigilantes ·
trabajo en el campo · comercio y hostelería · transporte por carretera ·
ferroviario · trabajo en el mar · aéreo · trabajo a turnos.

**Limitaciones**: trabajos expuestos a riesgos ambientales · cámaras
frigoríficas y de congelación · trabajos subterráneos y minería · construcción
y obras públicas · trabajo en el campo con temperaturas extremas.

---

## 3. Permisos retribuidos (art. 37.3 ET)

**Este es el hueco más grande.** Hoy existen cuatro tipos de ausencia:
vacaciones, baja médica, permiso personal y otros. Los ocho permisos del art.
37.3 caben todos en «permiso personal», que es como no tenerlos: no se puede
contar cuántos se han usado, ni comprobar la duración, ni justificar nada ante
una inspección.

| Permiso | Duración | Base | Estado |
|---|---|---|---|
| Matrimonio o registro de pareja de hecho | 15 días naturales | 37.3.a | **A medias** |
| Accidente o enfermedad grave, hospitalización o intervención con reposo domiciliario | 5 días | 37.3.b | **A medias** |
| Fallecimiento de cónyuge, pareja o pariente hasta 2.º grado | 2 días (+2 si hay desplazamiento) | 37.3.b bis | **A medias** |
| Traslado del domicilio habitual | 1 día | 37.3.c | **A medias** |
| Deber inexcusable de carácter público y personal | El indispensable | 37.3.d | **A medias** |
| Funciones sindicales o de representación | Según convenio | 37.3.e | **A medias** |
| Exámenes prenatales, preparación al parto, sesiones de adopción | El indispensable | 37.3.f | **A medias** |
| Fuerza mayor familiar | Horas equivalentes a 4 días al año | 37.9 | **A medias** |

Dos detalles del RDL 5/2023 que un catálogo hecho a ojo se salta:

- El permiso de cinco días alcanza también a **quien conviva en el mismo
  domicilio** y requiera cuidado efectivo, aunque no haya parentesco.
- Los cuatro días de fuerza mayor se cuentan **en horas**, no en días, y son
  retribuidos.

### Reducciones y ausencias por cuidados

| Situación | Base | Estado |
|---|---|---|
| Lactancia (1 h de ausencia o ½ h de reducción, hasta los 9 meses; acumulable) | 37.4 | **Falta** |
| Nacimiento prematuro u hospitalización tras el parto (1 h + reducción hasta 2 h) | 37.5 | **Falta** |
| Reducción por guarda legal (entre ⅛ y ½ de la jornada) | 37.6 | **A medias** — el régimen sí, la fracción no |
| Cuidado de menor con cáncer o enfermedad grave (reducción de al menos la mitad) | 37.6 | **Falta** |
| Permiso parental de 8 semanas, **no retribuido**, hasta los 8 años | 48 bis | **Falta** |
| Víctimas de violencia de género o sexual: reducción, reordenación, horario flexible | 37.8 | **Falta** |
| Crédito horario de representantes | 68.e | **Falta** — hay casilla de representante, pero no horas |
| Búsqueda de empleo durante el preaviso de despido objetivo (6 h/semana) | 53.2 | **Falta** |
| Exámenes de formación reglada | 23.1.a | **Falta** |

---

## 4. Suspensiones del contrato (art. 45 ET)

No son permisos: el contrato queda suspendido y no hay obligación de trabajar.
Para el registro importan porque durante ellas **no debe esperarse jornada**, y
hoy casi todas caerían en «baja médica» u «otros».

| Suspensión | Base | Estado |
|---|---|---|
| Incapacidad temporal por enfermedad común o accidente no laboral | 45.1.c | **A medias** — como «baja médica», sin distinguir contingencia |
| Incapacidad temporal por accidente de trabajo o enfermedad profesional | 45.1.c | **Falta** — es otra contingencia y otra entidad la que paga |
| Nacimiento y cuidado del menor (16 semanas, ampliables) | 48.4 | **Falta** |
| Riesgo durante el embarazo | 45.1.e / 48.7 | **Falta** |
| Riesgo durante la lactancia natural | 45.1.e | **Falta** |
| Adopción, guarda con fines de adopción, acogimiento | 48.5 | **Falta** |
| Excedencia voluntaria | 46.2 | **Falta** |
| Excedencia por cuidado de hijos (hasta 3 años) | 46.3 | **Falta** |
| Excedencia por cuidado de familiares (hasta 2 años) | 46.3 | **Falta** |
| Excedencia forzosa por cargo público o sindical | 46.1 | **Falta** |
| ERTE por causas ETOP o fuerza mayor | 47 | **Falta** — reducción de jornada o suspensión total |
| Mecanismo RED | 47 bis | **Falta** |
| Suspensión de empleo y sueldo (sanción) | 45.1.h | **Falta** |
| Huelga | 45.1.l | **Falta** |
| Cierre patronal | 45.1.m | **Falta** |
| Privación de libertad sin sentencia | 45.1.g | **Falta** |
| Violencia de género | 45.1.n | **Falta** |

> El ERTE de **reducción de jornada** es el que más duele que falte: no suspende
> el contrato, reduce el porcentaje de jornada durante un periodo. Sin eso, todo
> el cuadrante de una empresa en ERTE parcial se lee como incumplimiento.

---

## 5. Ausencias de parte del día

Una ausencia va hoy de una fecha a otra: `start_date` y `end_date`, sin horas.
Eso significa que **irse a las once por enfermedad no se puede registrar**. El
fichaje de salida queda a las 11:00, el día suma tres horas, y no hay nada que
diga por qué.

No es un detalle: es el caso más frecuente de todos los de esta lista. Y afecta
a cosas que el Estatuto ya cuenta en horas y no en días.

| Situación | Base | Estado | Nota |
|---|---|---|---|
| Ausencia de parte del día | — | **Falta** | Irse a media mañana, llegar tarde con permiso, salir dos horas y volver |
| Permisos contados en horas, no en días | 37.9, 37.4, 23.1.a | **Falta** | La fuerza mayor familiar son **horas equivalentes a cuatro días**; la lactancia, una hora al día; los exámenes, el tiempo indispensable |
| Baja médica que empieza a media jornada | 45.1.c | **Falta** | El parte da la fecha; las horas trabajadas antes de irse son jornada efectiva |
| Visita médica | Convenio | **Falta** | No está en el Estatuto: sale del convenio, y casi siempre en horas |

> Lo que falta técnicamente es poco: horas de inicio y fin en la ausencia, y que
> el cotejo entre lo previsto y lo trabajado las descuente. Lo que falta de
> producto es más: una ausencia por horas cambia cómo se calcula el saldo de
> vacaciones, cómo se lee el cuadrante y qué sale en el informe.

---

## 6. Vacaciones (art. 38 ET)

| Regla | Base | Estado |
|---|---|---|
| Mínimo de 30 días naturales (22 laborables en semana de 5 días) | 38.1 | **Cubierto** — configurable, con suelo comprobado en la ficha de convenio |
| Periodo de referencia distinto del año natural | 38.1 | **Cubierto** — mes de inicio configurable |
| Días distintos para una persona concreta | — | **Cubierto** |
| No sustituibles por dinero | 38.1 | **Cubierto por omisión** — no hay forma de pagarlas |
| Calendario con dos meses de antelación | 38.3 | **Falta** — no hay calendario de vacaciones como documento |
| Coincidencia con embarazo, parto o lactancia: se disfrutan en otra fecha | 38.3 | **Falta** |
| Coincidencia con IT por otra contingencia: hasta **18 meses** después del fin del año en que se originaron | 38.3 | **Falta** |
| Devengo proporcional al tiempo trabajado | — | **Falta** — quien entra en julio tiene el mismo saldo que quien lleva el año entero |
| Liquidación al finalizar el contrato | — | **Falta** |
| Días adicionales por antigüedad | Convenio | **Falta** |
| Asuntos propios / libre disposición | Convenio | **Falta** — no son vacaciones y hoy no hay dónde ponerlos |

---

## 7. Festivos (art. 37.2 ET)

**No existen en el sistema.** Ni el calendario laboral, ni el efecto sobre el
cuadrante, ni la compensación por trabajarlos.

- Catorce al año como máximo, de las cuales **dos son locales**.
- Cuatro son irrenunciables de ámbito nacional: Año Nuevo, 1 de mayo, 12 de
  octubre y Navidad.
- Las comunidades autónomas fijan las suyas y pueden sustituir algunas.
- Trabajar un festivo genera compensación: descanso, retribución o ambas, según
  convenio.

Hoy un festivo aparece en el cuadrante como un día laborable cualquiera, y quien
trabaja el 1 de mayo no se distingue de quien trabaja un martes.

---

## 8. Descansos y devoluciones

Lo que se debe y hay que devolver. Aquí es donde el producto se queda a medias
con más frecuencia: la regla se comprueba, pero **el saldo no se lleva**.

| Concepto | Base | Plazo | Estado |
|---|---|---|---|
| Descanso entre jornadas (12 h) | 34.3 | — | **Cubierto** |
| Descanso semanal (1,5 días, acumulable en 14 días) | 37.1 | — | **Cubierto** |
| Descanso semanal de menores (2 días) | 37.1 | — | **Cubierto** |
| Descanso en jornada continuada (15 min desde 6 h) | 34.4 | — | **Cubierto** |
| Descanso de menores (30 min desde 4,5 h) | 34.4 | — | **Cubierto** |
| Reducción del descanso en relevo de turno, y su devolución | 19.a RD 1561/1995 | 4 semanas | **A medias** — se avisa de la diferencia, **no se lleva el saldo** |
| Acumulación del descanso semanal a turnos | 19.b RD 1561/1995 | 4 semanas | **Cubierto** |
| Compensación de horas extra con descanso | 35.1 | 4 meses | **A medias** — se marca cómo se salda, no si se saldó |
| Compensación de la distribución irregular | 34.2 | 12 meses | **Falta** |
| Compensación de nocturnidad con descansos | 36.2 | Convenio | **Falta** |
| Compensación por festivo trabajado | 37.2 | Convenio | **Falta** |
| Descanso compensatorio por ampliación de jornada sectorial | RD 1561/1995 | Según sector | **Falta** |

> El patrón se repite: sabemos decir «esto se aparta de la regla» y no sabemos
> decir «y quedan cuatro horas por devolver antes del 9 de septiembre». Lo
> segundo es lo que una empresa necesita para cumplir, y lo primero solo sirve
> para saber que no cumple.

---

## 9. Lo que sí está resuelto

Para no leer solo el hueco:

- Registro de jornada con el contenido del art. 34.9 y del proyecto de real
  decreto, incluida la naturaleza de las horas y la modalidad de cada fichaje.
- Trazabilidad: nada se borra, las correcciones dejan las dos versiones y avisan
  a la persona y a su representante (art. 4.b).
- Protecciones de menores, completas y no configurables.
- Nocturnidad y turnos rotativos, con las devoluciones que permite el RD
  1561/1995.
- Régimen de jornada por persona, con la distinción entre parcial y reducida.
- Fichas de convenio con validación contra los suelos legales.
- Marco legal por país, aislado y sustituible.

---

## Por dónde empezar

Ordenado por lo que más se va a notar en un cliente real, no por dificultad.

0. **Ausencias por horas.** Que una ausencia pueda empezar y acabar a una hora,
   no solo en una fecha. Es lo que más ocurre —alguien se va a media mañana— y
   hoy no se puede registrar en absoluto.
1. **Catálogo de permisos retribuidos.** Convertir los cuatro tipos en un
   catálogo con duración, base legal, si consume vacaciones y si exige
   justificante. Sin esto no se puede decir cuántos días de permiso lleva
   alguien, que es la primera pregunta que hace una gestoría.
2. **Festivos.** Calendario nacional, autonómico y local, y su efecto en el
   cuadrante. Hoy falta entero y aparece en cuanto alguien mira un 1 de mayo.
3. **Suspensiones del contrato.** Empezando por IT con su contingencia,
   nacimiento y cuidado del menor, y ERTE de reducción de jornada.
4. **Saldos de devolución.** Horas extra compensadas, relevo de turno,
   distribución irregular. Convertir los avisos en una cuenta.
5. **Vacaciones: devengo proporcional y traslado por IT.** Las dos reglas que
   más se equivocan a mano.
6. **Llamamiento del fijo discontinuo** (art. 16), que hoy está a medias y ya
   está señalado en el código.
7. **Topes que se guardan y no se comprueban**: 80 horas extra al año, 30 % de
   complementarias al mes, 65/85 % del contrato formativo.
