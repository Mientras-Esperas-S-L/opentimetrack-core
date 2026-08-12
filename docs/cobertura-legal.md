# Alcance y cobertura

Qué situaciones de la legislación laboral española afectan al tiempo de trabajo,
cuáles entran en OpenTimeTrack y qué hace hoy con cada una.

Va junto al [manual](manual/README.md): el manual dice cómo se usa lo que hay;
esto dice qué hay, qué no, y por qué algunas cosas no van a estar nunca.

---

## Dónde está la línea

OpenTimeTrack es **el registro de jornada** y lo que hace falta para que ese
registro se lea y se sostenga. No es un programa de recursos humanos.

La prueba que decide si algo entra:

> ¿El registro necesita esto para leerse y defenderse ante una inspección?

**Entra** lo que el art. 34.9 obliga a contener, y lo que explica un hueco en él:

- El régimen de jornada de cada persona, porque el art. 3.b del proyecto de real
  decreto lo pide expresamente en el registro.
- Las ausencias, porque explican por qué no hay fichaje ese día.
- El cuadrante, porque dice qué se esperaba.
- Los límites de descanso y de jornada, porque son contra lo que se contrasta.
- Quién puede leer el registro de quién.

**No entra**, y no por falta de tiempo:

| Fuera | Por qué |
|---|---|
| Nóminas y cotización | El registro alimenta la nómina; no la calcula |
| Retribución: pluses, complementos, valor de la hora extra | Se pacta en convenio y se paga en nómina. Aquí solo consta si una hora extra se salda con dinero o con descanso, porque eso sí lo pide el art. 3.f |
| Selección, evaluación del desempeño, formación | Otra herramienta |
| Gestión documental de contratos y su firma | Otra herramienta |
| Prevención de riesgos y vigilancia de la salud | El art. 36.4 obliga a evaluar la salud de quien trabaja de noche. Nosotros avisamos de que esa condición existe; el reconocimiento lo lleva el servicio de prevención |
| Tramitación ante la Seguridad Social: partes de baja, ERTE, altas | Se hace en el sistema RED. Aquí solo consta el efecto sobre la jornada |
| Organigrama, centros de coste, matriciales | Los departamentos existen aquí para acotar quién ve qué, no para dibujar la empresa |

Y una consecuencia de la línea: **OpenTimeTrack no debería ser el maestro de
datos de personal.** Quien ya tiene la plantilla en una gestoría o en un ERP
debería poder importarla y que aquí se quede lo que se usa.

---

## 1. Modalidades de contrato

Del contrato guardamos tres cosas, y son las tres que cambian cómo se mide la
jornada: el **régimen** (qué límites aplican), las **fechas** (indefinido o
temporal) y **fijo discontinuo**.

La modalidad en sí —por qué causa se contrató— no se guarda, y no hace falta: el
registro no la pide. Sí importan las dos que traen límites propios.

| Modalidad | Base | Estado |
|---|---|---|
| Indefinido ordinario | art. 15.1 | **Cubierto.** Fechas vacías al final |
| Temporal por circunstancias de la producción | art. 15.2 | **Cubierto**, como fecha de fin |
| Temporal por sustitución | art. 15.3 | **Cubierto**, como fecha de fin |
| Tiempo parcial | art. 12 | **Cubierto**, con horas y periodo |
| Indefinido adscrito a obra | Ley 32/2006 | **Cubierto.** A efectos de jornada es un indefinido |
| Fijo discontinuo | art. 16 | **A medias.** Hay casilla, pero no hay llamamiento ni periodos de actividad: fuera de temporada el sistema no sabe que no se espera jornada |
| Formativo en alternancia | art. 11.2 | **A medias.** Falta el tope del art. 11.2.b: 65 % de la jornada máxima el primer año, 85 % el segundo, formación incluida |
| Formativo para práctica profesional | art. 11.3 | **A medias.** Comparte régimen con el anterior y son cosas distintas |
| Contrato de relevo | art. 12.7 | **Falta.** La jornada del relevista debe cubrir al menos la reducción de quien se jubila parcialmente |
| Jubilación parcial | art. 12.6 | **Falta.** Es una jornada reducida con regla propia |

**Relaciones laborales especiales** (art. 2 ET): once, cada una con su real
decreto y su jornada. Ninguna está modelada. La que más se va a dar es la de
**alta dirección**, y es justo la que no tiene jornada máxima legal (RD
1382/1985): meterla como relación común produce avisos de incumplimiento que no
lo son.

Fuera de alcance: la **puesta a disposición por ETT**. El registro lo lleva la
empresa de trabajo temporal.

---

## 2. Tipos de jornada

| Situación | Base | Estado |
|---|---|---|
| Jornada completa | art. 34.1 | **Cubierto** |
| Jornada parcial | art. 12 | **Cubierto** |
| Jornada continuada o partida | — | **Cubierto**, por los tramos del turno |
| Trabajo a turnos rotativos | art. 36.3 | **Cubierto**, con la reducción del relevo y su devolución |
| Trabajo nocturno | art. 36.1 | **Cubierto**: la condición, el promedio de 8 h en 15 días y el tope de dos semanas |
| Jornada reducida por guarda legal | art. 37.6 | **A medias.** Hay régimen; la fracción reducida y las fechas, no |
| Distribución irregular | art. 34.2 | **A medias.** Se marca el fichaje, pero no hay saldo: el 10 % se compensa en 12 meses y nadie lleva la cuenta |
| Adaptación de jornada | art. 34.8 | **A medias.** Se marca en el fichaje; la solicitud y su respuesta no se tramitan |
| Horas extraordinarias | art. 35 | **A medias.** Se marcan y se dice cómo se saldan; el tope de 80 al año no se contrasta con lo trabajado |
| Horas complementarias | art. 12.5 | **A medias.** El cuadrante avisa; el tope mensual del 30 % no se acumula |
| Trabajo a distancia | Ley 10/2021 | **A medias.** El fichaje registra la modalidad; el acuerdo y el umbral del 30 %, no |
| Guardias y atención continuada | RD 1561/1995 | **Falta.** Sanidad: presencia frente a trabajo efectivo |
| Tiempo de presencia | RD 1561/1995 | **Falta.** Transporte: hasta 20 h semanales de promedio que no son jornada ordinaria |
| Jornadas especiales por sector | RD 1561/1995 | **Falta.** Hoy la empresa ajusta las cifras a mano, lo cual funciona, pero no deja dicho **por qué** se apartó de la regla general |

Las jornadas especiales del RD 1561/1995 son de dos clases. **Ampliaciones**:
fincas urbanas, guardas y vigilantes, campo, comercio y hostelería, transporte
por carretera, ferroviario, mar, aéreo, trabajo a turnos. **Limitaciones**:
riesgos ambientales, cámaras frigoríficas, minería y trabajos subterráneos,
construcción, campo con temperaturas extremas.

Fuera de alcance: la **desconexión digital** (Ley 3/2018) es una política de
empresa, no un dato del registro. Y el **pluriempleo** —el tope de ocho horas de
un menor suma empleadores— no lo podemos ver: solo conocemos una relación
laboral.

---

## 3. Permisos retribuidos

**El hueco más grande que hay.** Existen cuatro tipos de ausencia —vacaciones,
baja médica, permiso personal y otros— así que los ocho permisos del art. 37.3
caben todos en «permiso personal». Eso es como no tenerlos: no se puede contar
cuántos se han usado, ni comprobar la duración, ni justificar nada.

| Permiso | Duración | Base | Estado |
|---|---|---|---|
| Matrimonio o registro de pareja de hecho | 15 días naturales | 37.3.a | **A medias** |
| Accidente o enfermedad grave, hospitalización, o intervención con reposo domiciliario | 5 días | 37.3.b | **A medias** |
| Fallecimiento de cónyuge, pareja o pariente hasta 2.º grado | 2 días, +2 con desplazamiento | 37.3.b bis | **A medias** |
| Traslado del domicilio habitual | 1 día | 37.3.c | **A medias** |
| Deber inexcusable de carácter público y personal | El indispensable | 37.3.d | **A medias** |
| Funciones sindicales o de representación | Según convenio | 37.3.e | **A medias** |
| Exámenes prenatales, preparación al parto, sesiones de adopción | El indispensable | 37.3.f | **A medias** |
| Fuerza mayor familiar | Horas equivalentes a 4 días al año | 37.9 | **A medias** |

Dos detalles del RDL 5/2023 que un catálogo hecho a ojo se salta: el permiso de
cinco días alcanza también a **quien conviva en el mismo domicilio** y requiera
cuidado efectivo, aunque no haya parentesco; y los cuatro días de fuerza mayor
se cuentan **en horas**, no en días.

### Reducciones y ausencias por cuidados

| Situación | Base | Estado |
|---|---|---|
| Reducción por guarda legal, entre ⅛ y ½ de la jornada | 37.6 | **A medias.** El régimen sí, la fracción no |
| Lactancia: 1 h de ausencia o ½ h de reducción hasta los 9 meses, acumulable | 37.4 | **Falta** |
| Nacimiento prematuro u hospitalización tras el parto | 37.5 | **Falta** |
| Cuidado de menor con cáncer o enfermedad grave: reducción de al menos la mitad | 37.6 | **Falta** |
| Permiso parental de 8 semanas, **no retribuido**, hasta los 8 años | 48 bis | **Falta** |
| Víctimas de violencia de género o sexual: reducción, reordenación, horario flexible | 37.8 | **Falta** |
| Crédito horario de representantes | 68.e | **Falta.** Hay casilla de representante, pero no horas |
| Búsqueda de empleo durante el preaviso de despido objetivo, 6 h/semana | 53.2 | **Falta** |
| Exámenes de formación reglada | 23.1.a | **Falta** |

---

## 4. Ausencias de parte del día

Una ausencia va hoy de una fecha a otra, sin horas. Eso significa que **irse a
las once por enfermedad no se puede registrar**: el fichaje de salida queda a
las 11:00, el día suma tres horas y no hay nada que diga por qué.

Es el caso más frecuente de toda esta lista, y afecta a cosas que el Estatuto ya
cuenta en horas.

| Situación | Base | Estado |
|---|---|---|
| Ausencia de parte del día | — | **Falta.** Irse a media mañana, llegar tarde con permiso, salir dos horas y volver |
| Permisos contados en horas y no en días | 37.9, 37.4, 23.1.a | **Falta** |
| Baja médica que empieza a media jornada | 45.1.c | **Falta.** Las horas trabajadas antes de irse son jornada efectiva |
| Visita médica | Convenio | **Falta.** No está en el Estatuto: sale del convenio, y casi siempre en horas |

Técnicamente falta poco —horas de inicio y fin en la ausencia, y que el cotejo
entre lo previsto y lo trabajado las descuente—. De producto falta más: una
ausencia por horas cambia el saldo de vacaciones, la lectura del cuadrante y lo
que sale en el informe.

---

## 5. Suspensiones del contrato

No son permisos: el contrato queda suspendido y no hay obligación de trabajar.
Entran porque durante ellas **no debe esperarse jornada**, y hoy casi todas
caerían en «baja médica» u «otros».

Lo que entra es el **efecto sobre la jornada**. La tramitación —el parte al
INSS, el expediente del ERTE— se hace en otro sitio.

| Suspensión | Base | Estado |
|---|---|---|
| IT por enfermedad común o accidente no laboral | 45.1.c | **A medias.** Como «baja médica», sin distinguir contingencia |
| IT por accidente de trabajo o enfermedad profesional | 45.1.c | **Falta.** Otra contingencia, y otra entidad la que paga |
| Nacimiento y cuidado del menor, 16 semanas ampliables | 48.4 | **Falta** |
| Riesgo durante el embarazo | 45.1.e | **Falta** |
| Riesgo durante la lactancia natural | 45.1.e | **Falta** |
| Adopción, guarda con fines de adopción, acogimiento | 48.5 | **Falta** |
| Excedencia voluntaria | 46.2 | **Falta** |
| Excedencia por cuidado de hijos, hasta 3 años | 46.3 | **Falta** |
| Excedencia por cuidado de familiares, hasta 2 años | 46.3 | **Falta** |
| Excedencia forzosa por cargo público o sindical | 46.1 | **Falta** |
| ERTE por causas ETOP o fuerza mayor | 47 | **Falta** |
| Mecanismo RED | 47 bis | **Falta** |
| Suspensión de empleo y sueldo | 45.1.h | **Falta** |
| Huelga | 45.1.l | **Falta** |
| Cierre patronal | 45.1.m | **Falta** |
| Privación de libertad sin sentencia | 45.1.g | **Falta** |
| Violencia de género | 45.1.n | **Falta** |

El ERTE de **reducción de jornada** es el que más duele que falte: no suspende
el contrato, reduce el porcentaje durante un periodo. Sin eso, el cuadrante
entero de una empresa en ERTE parcial se lee como incumplimiento.

---

## 6. Vacaciones

| Regla | Base | Estado |
|---|---|---|
| Mínimo de 30 días naturales, 22 laborables en semana de cinco días | 38.1 | **Cubierto.** Configurable, con el suelo comprobado en la ficha de convenio |
| Días laborables o naturales, y el consumo en la misma unidad | 38.1 | **Cubierto.** Un día laborable es un día que esa persona tenía que trabajar, leído de su cuadrante |
| Periodo de referencia distinto del año natural | 38.1 | **Cubierto.** Mes de inicio configurable |
| Días distintos para una persona concreta | — | **Cubierto** |
| No sustituibles por dinero | 38.1 | **Cubierto** por omisión: no hay forma de pagarlas |
| Calendario con dos meses de antelación | 38.3 | **Falta.** No existe el calendario de vacaciones como documento |
| Coincidencia con embarazo, parto o lactancia | 38.3 | **Falta.** Se disfrutan en otra fecha |
| Coincidencia con IT por otra contingencia | 38.3 | **Falta.** Hasta 18 meses después del fin del año en que se originaron |
| Devengo proporcional al tiempo trabajado | — | **Falta.** Quien entra en julio tiene hoy el mismo saldo que quien lleva el año entero |
| Liquidación al finalizar el contrato | — | **Falta** |
| Días adicionales por antigüedad | Convenio | **Falta** |
| Asuntos propios y libre disposición | Convenio | **Falta.** No son vacaciones y hoy no hay dónde ponerlos |

---

## 7. Festivos

**No existen en el sistema.** Ni el calendario laboral, ni el efecto sobre el
cuadrante, ni la compensación por trabajarlos. Hoy un festivo aparece como un
día laborable cualquiera, y quien trabaja el 1 de mayo no se distingue de quien
trabaja un martes.

- Catorce al año como máximo, de las cuales **dos son locales**.
- Cuatro son irrenunciables de ámbito nacional: Año Nuevo, 1 de mayo, 12 de
  octubre y Navidad.
- Las comunidades autónomas fijan las suyas y pueden sustituir algunas.

**De dónde saldrán los datos**, porque decide el diseño:

| Nivel | Quién lo fija | Automatizable |
|---|---|---|
| Nacional | Resolución anual del Ministerio en el BOE, en octubre para el año siguiente | **Sí**, hay datos abiertos |
| Autonómico | Decreto de cada comunidad, recogido en esa misma resolución | **Sí**, misma fuente |
| Local | Lo propone el ayuntamiento, lo aprueba la autoridad laboral autonómica | **No de forma fiable.** Repartido por medio centenar de boletines y 8.100 municipios, muchos solo en PDF |

Así que el reparto va a ser: **traemos los doce nacionales y autonómicos** como
ficheros versionados en el repositorio, uno por año, igual que las fichas de
convenio; y **los dos locales los pone el administrador** en su centro de
trabajo. Que es también lo que hace el resto del sector.

---

## 8. Descansos y devoluciones

Lo que se debe y hay que devolver. Aquí es donde el producto se queda a medias
con más frecuencia: la regla se comprueba, pero **el saldo no se lleva**.

| Concepto | Base | Plazo | Estado |
|---|---|---|---|
| Descanso entre jornadas, 12 h | 34.3 | — | **Cubierto** |
| Descanso semanal, 1,5 días acumulable en 14 | 37.1 | — | **Cubierto** |
| Descanso semanal de menores, 2 días | 37.1 | — | **Cubierto** |
| Descanso en jornada continuada, 15 min desde 6 h | 34.4 | — | **Cubierto** |
| Descanso de menores, 30 min desde 4,5 h | 34.4 | — | **Cubierto** |
| Acumulación del descanso semanal a turnos | 19.b RD 1561/1995 | 4 semanas | **Cubierto** |
| Reducción del descanso en relevo de turno | 19.a RD 1561/1995 | 4 semanas | **A medias.** Se avisa de la diferencia; no se lleva el saldo |
| Compensación de horas extra con descanso | 35.1 | 4 meses | **A medias.** Se marca cómo se salda, no si se saldó |
| Compensación de la distribución irregular | 34.2 | 12 meses | **Falta** |
| Compensación de nocturnidad con descansos | 36.2 | Convenio | **Falta** |
| Compensación por festivo trabajado | 37.2 | Convenio | **Falta** |
| Descanso compensatorio por ampliación sectorial | RD 1561/1995 | Según sector | **Falta** |

El patrón se repite: sabemos decir «esto se aparta de la regla» y no sabemos
decir «y quedan cuatro horas por devolver antes del 9 de septiembre». Lo segundo
es lo que una empresa necesita para cumplir; lo primero solo sirve para saber
que no cumple.

> Los días de descanso de más que suele tener un turno de noche no salen del
> Estatuto: salen del convenio, o del art. 36.2, que permite compensar la
> nocturnidad con descansos en lugar de con un plus. No los inventamos; se
> planifican en el cuadrante como cualquier otro descanso.

---

## 9. Organización del personal

Entra solo hasta donde acota **quién ve el registro de quién** y **dónde se
trabaja**. Un modelo de organización completo es otra herramienta.

| Situación | Estado |
|---|---|
| Perfiles: persona trabajadora, responsable, administración | **Cubierto.** Tres, fijos: no son configurables y no deberían serlo |
| Departamentos | **Cubierto.** Con quién los lleva, que es lo que decide el alcance de lectura |
| Un responsable lee solo lo suyo | **Cubierto.** Los departamentos que lleva, más él mismo. Con un ajuste de empresa para volver al alcance total |
| Representación legal de las personas trabajadoras | **Cubierto.** Es a quien se avisa en el art. 4.b |
| Centro de trabajo | **Falta.** El registro se lleva y se inspecciona por centro, y sin él no se pueden aplicar los dos festivos locales |
| Historia de la adscripción | **Falta.** Si alguien cambia de departamento en septiembre, el informe de julio dirá el de ahora |
| Jerarquía de departamentos | **Falta**, y probablemente deba seguir faltando: acotar la lectura no la necesita |

---

## Por dónde seguir

Ordenado por lo que más se nota en un cliente real, no por dificultad.

1. **Ausencias por horas.** Que una ausencia pueda empezar y acabar a una hora y
   no solo en una fecha. Es lo que más ocurre y hoy no se puede registrar.
2. **Catálogo de permisos retribuidos**, con duración, base legal, si consume
   vacaciones y si exige justificante. Sin esto no se puede decir cuántos días
   de permiso lleva alguien, que es la primera pregunta de una gestoría.
3. **Centro de trabajo**, que además desbloquea lo siguiente.
4. **Festivos**: nacionales y autonómicos como datos del repositorio, locales
   por centro.
5. **Suspensiones del contrato**, empezando por la IT con su contingencia, el
   nacimiento y cuidado del menor, y el ERTE de reducción de jornada.
6. **Saldos de devolución**: horas extra compensadas, relevo de turno,
   distribución irregular. Convertir los avisos en una cuenta.
7. **Vacaciones**: devengo proporcional y traslado por IT.
8. **Llamamiento del fijo discontinuo** (art. 16), ya señalado en el código.
9. **Topes que se guardan y no se comprueban**: 80 horas extra al año, 30 % de
   complementarias al mes, 65/85 % del contrato formativo.
10. **Historia de la adscripción a departamento**, cuando el informe empiece a
    mentir.

---

Al cubrir una situación hay que mover su fila aquí y, si toca una pantalla,
actualizar el [manual](manual/README.md).
