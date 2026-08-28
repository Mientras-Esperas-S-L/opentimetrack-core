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
| Fijo discontinuo | art. 16 | **Cubierto.** Periodos de actividad con su fecha de llamamiento, que se cargan desde la ficha de la persona. Fuera de ellos no se espera jornada, el cuadrante avisa si se asigna un turno y la cobertura pendiente lo distingue de quien dejó la empresa |
| Formativo en alternancia | art. 11.2 | **Cubierto.** Régimen propio, y el tope del art. 11.2.b contrastado contra **la jornada máxima** ---no contra lo que el contrato pactara---: 65 % el primer año, 85 % el segundo, según la fecha de inicio |
| Formativo para práctica profesional | art. 11.3 | **Cubierto.** Régimen propio y separado del anterior, que es lo que permite **no** aplicarle un tope que no tiene |
| Contrato de relevo | art. 12.7 | **Cubierto.** En la ficha se dice **a quién releva**, que es el dato que la ley compara, y se avisa si su jornada no cubre lo que el otro deja de trabajar. Un relevo sobre alguien sin jubilación parcial registrada también se dice: no hay contra qué medirlo |
| Jubilación parcial | art. 12.6 | **Cubierto.** Se registra como reducción de jornada con sus fechas, y la horquilla del artículo se avisa: del 25 % al 50 %, o hasta el 75 % **si el relevo es a jornada completa e indefinido** ---el mismo 60 % está bien o mal según cómo sea el contrato de la otra persona--- |

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
| Jornada reducida por guarda legal | art. 37.6 | **Cubierto.** Se pide como cualquier otra solicitud, con **cuánto se reduce** y entre qué fechas. El cuadrante y el cotejo pasan a medirse contra la jornada reducida, y **se acaba sola** el día que termina el derecho. Si la reducción se sale de la horquilla del artículo ---de un octavo a la mitad--- se avisa, no se impide |
| Distribución irregular | art. 34.2 | **A medias.** El **saldo** ya se lleva: las diferencias de un año cuyo plazo venció se avisan, por exceso y por defecto, con el plazo que declare la empresa ---12 meses en defecto de pacto---. Solo con jornada pactada **por año**, que es la única cifra que viene neta de vacaciones. El **10 % del párrafo primero** sigue sin calcularse a propósito |
| Adaptación de jornada | art. 34.8 | **Cubierto.** Se pide desde «Mi jornada» y se contesta desde «Por decidir», con el plazo de quince días a la vista. La respuesta que no es un sí ---también la alternativa--- **pide el motivo antes de mandarla**, y el servidor lo exige igual. Retirar la propia es de quien la pidió |
| Horas extraordinarias | art. 35 | **Cubierto.** Se marcan, se dice cómo se saldan y el tope anual se contrasta con lo autorizado: la pantalla de decisiones avisa al pasarse, descontando las compensadas con descanso y las de fuerza mayor |
| Horas complementarias | art. 12.5 | **Cubierto.** El tope se acumula contra lo trabajado y se avisa al pasarse. Va sobre **el periodo del contrato** ---semana, mes o año---, que es lo que dice el art. 12.5.c: el 30 % de «las horas ordinarias objeto del contrato». Un contrato de 800 h al año tiene 240 complementarias al año, no 20 al mes |
| Trabajo a distancia | Ley 10/2021 | **Cubierto.** El umbral del art. 1 se calcula ---el 30 % de la jornada en tres meses--- y se avisa a quien lo pasa sin acuerdo, o con uno firmado después de empezar (art. 5.1). El acuerdo se registra desde la ficha de la persona, con sus fechas y su porcentaje. Lo que no se guarda aquí es el contenido del art. 7: eso es el documento firmado |
| Guardias y atención continuada | RD 1561/1995 | **Cubierto.** Con el régimen de sanidad declarado, la **guardia de presencia física** cuenta como tiempo de trabajo para el tope de cuarenta y ocho horas semanales ---SIMAP (C-303/98) y Jaeger (C-151/02)---, y se avisa al pasarse. No se toca ningún total: el registro sigue separando jornada de presencia, que es lo que obliga el art. 3.g. La guardia **localizada** no cuenta, salvo la atención efectiva, que ya se ficha como jornada |
| Tiempo de presencia | RD 1561/1995 | **Cubierto.** El promedio del art. 8.b ---20 h semanales en un mes--- se cuenta sobre lo marcado como espera (art. 3.g) y se avisa al pasarse. **Solo si la empresa declara el régimen de transporte por carretera**: aplicárselo a una oficina sería inventarle un límite de otro sector |
| Jornadas especiales por sector | RD 1561/1995 | **Cubierto.** La empresa declara su régimen ---trece, de ampliación y de limitación--- **desde la pantalla de ajustes**, y a partir de ahí cada aviso de cifra apartada lo nombra: un descanso de diez horas se lee «por debajo de las doce del art. 34.3 ET, y la empresa trabaja en transporte por carretera, donde el RD 1561/1995 aparta algunas de estas cifras». El aviso **no se calla** por tener régimen ---el real decreto no quita el límite, lo aparta en artículos concretos--- y **no dice cuál**: mapear trece regímenes contra cada cifra es donde se acaba citando la ley equivocada. Para la cita exacta ya existe la ficha de convenio, que guarda la procedencia cifra por cifra. Y en dos sectores se comprueba además una cifra concreta: el tiempo de presencia en transporte y las guardias en sanidad. Las cifras de los trece regímenes **siguen fuera a propósito**: son quince números por sector que además tienen su convenio, y uno nuestro pisando el suyo se leería como la ley |

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

**Cubiertos.** Hay un catálogo por empresa, sembrado del que trae el país, con
la duración de cada permiso, su unidad, su periodo, el artículo del que sale y
si pide justificante. Antes eran cuatro tipos de ausencia y los ocho permisos
del art. 37.3 caían todos en «permiso personal», que es como no tenerlos.

Se **copia**, no se referencia: el convenio mejora cualquiera de estas cifras,
la empresa edita su copia, y una corrección nuestra no puede reescribir lo que
alguien negoció.

| Permiso | Duración | Base |
|---|---|---|
| Matrimonio o registro de pareja de hecho | 15 días naturales, cada vez | 37.3.a |
| Accidente o enfermedad graves, hospitalización, o intervención con reposo | 5 días naturales, cada vez | 37.3.b |
| Fallecimiento de familiar hasta 2.º grado | 2 días naturales, +2 con desplazamiento | 37.3.b bis |
| Traslado del domicilio habitual | 1 día natural | 37.3.c |
| Deber inexcusable de carácter público y personal | El tiempo indispensable | 37.3.d |
| Funciones sindicales o de representación | Crédito horario, al mes | 37.3.e |
| Exámenes prenatales, preparación al parto, sesiones de adopción | El tiempo indispensable | 37.3.f |
| Fuerza mayor familiar | 4 días laborables al año, **en horas** | 37.9 |
| Lactancia | 1 hora al día | 37.4 |
| Exámenes de formación reglada | El tiempo indispensable | 23.1.a |
| Búsqueda de empleo durante el preaviso | 6 horas a la semana | 53.2 |
| Permiso parental, **no retribuido** | 8 semanas | 48 bis |
| Visita médica y asuntos propios | Del convenio | — |

Los dos detalles del RDL 5/2023 que un catálogo hecho a ojo se salta están en la
nota de cada uno: el permiso de cinco días alcanza a **quien conviva en el mismo
domicilio** aunque no haya parentesco, y los cuatro días de fuerza mayor se
cuentan **en horas**.

**Y se lleva la cuenta.** Cuánto va consumido de cada permiso con tope, en su
propia unidad y su propio periodo: año natural para los del art. 37.9, semana
para las seis horas del art. 53.2, día para la lactancia. Una parte de día
contra un tope en días cuenta como fracción. El aviso sale al elegir el permiso
y en la tarjeta de quien lo aprueba, y **nunca impide**: todos los topes son el
suelo legal y el convenio mejora cualquiera.

### Reducciones y ausencias por cuidados

| Situación | Base | Estado |
|---|---|---|
| Reducción por guarda legal, entre ⅛ y ½ de la jornada | 37.6 | **Cubierto.** Se solicita con la fracción y las fechas; el cuadrante mide contra la jornada reducida y el derecho caduca solo. Fuera de la horquilla se avisa, no se impide |
| Lactancia: 1 h de ausencia o ½ h de reducción hasta los 9 meses, acumulable | 37.4 | **Falta** |
| Nacimiento prematuro u hospitalización tras el parto | 37.5 | **Falta** |
| Cuidado de menor con cáncer o enfermedad grave: reducción de al menos la mitad | 37.6 | **Falta.** La maquinaria de la fracción y las fechas ya está; falta su fila en el catálogo, con la regla propia ---aquí el suelo es la mitad, no el techo--- |
| Permiso parental de 8 semanas, **no retribuido**, hasta los 8 años | 48 bis | **Falta** |
| Víctimas de violencia de género o sexual: reducción, reordenación, horario flexible | 37.8 | **Falta** |
| Crédito horario de representantes | 68.e | **Falta.** Hay casilla de representante, pero no horas |
| Búsqueda de empleo durante el preaviso de despido objetivo, 6 h/semana | 53.2 | **Falta** |
| Exámenes de formación reglada | 23.1.a | **Falta** |

---

## 4. Ausencias de parte del día

**Cubierto.** Una ausencia puede llevar hora de inicio y de fin, y entonces es
de un solo día. Irse a las once con fiebre ya se registra, que era el caso más
frecuente de toda esta lista y no se podía guardar de ninguna manera.

| Regla | Estado |
|---|---|
| Ausencia de parte del día | **Cubierto** |
| Permisos contados en horas | **Cubierto** — el formulario los ofrece por horas antes que por días cuando esa es su forma |
| Una parcial **no** bloquea el fichaje | **Cubierto** — quien se fue a las once trabajó la mañana, e impedirle fichar la salida dejaría el día abierto |
| Una parcial no toca el saldo de vacaciones | **Cubierto** |
| Las vacaciones siguen siendo de días completos | **Cubierto** — se rechaza medio día: el saldo está en días y redondear regalaría o se comería uno |
| Parte de un día es **un** día | **Cubierto** — «del lunes a las dos al miércoles a las once» se rechaza |

---

## 5. Suspensiones del contrato

**Cubiertas.** No son permisos: el contrato se para y no hay obligación de
trabajar. Entran porque durante ellas **no debe esperarse jornada**, que es lo
que explica el hueco en el registro. La tramitación —el parte al INSS, el
expediente del ERTE— se hace en otro sitio.

Las quince del art. 45 están en el catálogo: nacimiento y cuidado del menor,
adopción, riesgo durante el embarazo y durante la lactancia, las cuatro
excedencias, ERTE, mecanismo RED, suspensión de empleo y sueldo, huelga, cierre
patronal, privación de libertad y violencia de género.

Ninguna va marcada como retribuida, porque la empresa no paga: lo hace la
Seguridad Social, la mutua, o nadie. Quién paga en cada caso está en su nota.

### El ERTE que reduce en vez de parar

La única que no encajaba. El art. 47 permite **suspender el contrato o reducir
la jornada** entre un 10 y un 70 %, durante meses. La segunda forma no es «no se
espera jornada»: la persona sigue viniendo, por menos tiempo.

| | |
|---|---|
| Se pide con un porcentaje | Vacío o 100 suspende entero; 40 significa que se sigue trabajando el 60 % |
| No bloquea el fichaje | Quien tiene la jornada reducida un 40 % viene por el otro 60 % |
| El cuadrante se mide contra la jornada reducida | Sin esto, el cuadrante entero de una empresa en ERTE parcial se leía como que todo el mundo se pasa de sus horas todas las semanas |
| El **máximo legal no se reduce** | El art. 34.1 es un techo para todos; el ERTE reduce lo pactado, no lo que la ley permite |

---

## 6. Vacaciones

| Regla | Base | Estado |
|---|---|---|
| Mínimo de 30 días naturales, 22 laborables en semana de cinco días | 38.1 | **Cubierto.** Configurable, con el suelo comprobado en la ficha de convenio |
| Días laborables o naturales, y el consumo en la misma unidad | 38.1 | **Cubierto.** Un día laborable es un día que esa persona tenía que trabajar, leído de su cuadrante |
| Periodo de referencia distinto del año natural | 38.1 | **Cubierto.** Mes de inicio configurable |
| Días distintos para una persona concreta | — | **Cubierto** |
| No sustituibles por dinero | 38.1 | **Cubierto** por omisión: no hay forma de pagarlas |
| Calendario con dos meses de antelación | 38.3 | **A medias.** El **plazo sí se comprueba**: unas vacaciones puestas por la empresa con menos de sesenta días de aviso salen marcadas, con su artículo. Solo cuando las pone otro ---quien las pide conoce las fechas por definición---. Lo que no existe es el **calendario como documento**, que es lo que el artículo manda exponer en la empresa |
| Coincidencia con embarazo, parto o lactancia | 38.3 | **Cubierto.** El régimen **sin plazo** del párrafo 2.º: se disfrutan al terminar la suspensión, «aunque haya terminado el año natural a que correspondan». Los días vuelven al saldo cuando un responsable lo confirma, no solos |
| Coincidencia con IT por otra contingencia | 38.3 | **Cubierto.** El régimen de **dieciocho meses** del párrafo 3.º, y solo por los días que coinciden ---«total o parcialmente», dice la ley---. Da igual que la baja empezara antes: el precepto solo dice «coincida» (TJUE, ANGED C-78/11; STS del Pleno de 3/10/2012) |
| Devengo proporcional al tiempo trabajado | — | **Cubierto.** Quien no ha trabajado el periodo entero devenga la parte proporcional, por días naturales de contrato y **redondeando hacia arriba** ---a la baja el peor caso es incumplir un mínimo legal; al alza, dar medio día de más---. Medido en la demostración: quien entra el 1 de julio tiene 12 de 23, no 23 |
| Liquidación al finalizar el contrato | 38.1 | **Cubierto.** Los días devengados y no disfrutados al terminar el contrato ---y los disfrutados de más, que se descuentan---, en la ficha de la persona y **mientras se escribe la fecha de baja**, no después de guardarla. Lo pendiente de decidir no resta: se cuenta aparte, porque ni está disfrutado ni liquidado. **Días, no importe**: lo que vale un día es una nómina y eso está fuera del producto |
| Días adicionales por antigüedad | Convenio | **Falta** |
| Asuntos propios y libre disposición | Convenio | **Falta.** No son vacaciones y hoy no hay dónde ponerlos |

---

## 7. Festivos

| Regla | Base | Estado |
|---|---|---|
| Calendario de festivos, por centro de trabajo | 37.2 | **Cubierto** |
| Nacionales y autonómicos | 37.2 | **Cubierto** — se transcriben del BOE a `holidays/<país>/<año>.yaml` y los trae `import_holidays` |
| Los dos locales | 37.2 | **Cubierto** — a mano por centro, que es la única forma: no hay registro nacional legible |
| Un festivo no consume vacaciones | 38.1 | **Cubierto** — una semana con un festivo dentro cuesta cuatro días |
| Trabajar un festivo se avisa | 37.2 | **Cubierto** — no se impide: es lícito y genera compensación |
| Compensación por festivo trabajado | 37.2 | **Falta** — se avisa de la deuda, no se lleva el saldo. Ver §8 |

El calendario de 2026 que viene en el repositorio lleva los ocho nacionales con
las fechas comprobadas y **está marcado como no verificado**: falta transcribir
la resolución del BOE, que es la que dice qué ha hecho cada comunidad con los
festivos que caen en domingo. El comando lo avisa al importar.

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
| Centro de trabajo | **Cubierto.** Con municipio, comunidad y zona horaria propia: una delegación en Canarias mide su jornada una hora antes que la central |
| Historia de la adscripción | **Falta.** Si alguien cambia de departamento en septiembre, el informe de julio dirá el de ahora |
| Retirar un alta equivocada | **Cubierto desde el 27/08/2026.** Se puede borrar de verdad a quien no dejó nada que explicar: ni trabajo suyo ni decisiones sobre el de otras personas. Con cualquiera de las dos cosas se niega y dice qué encontró, y hay que dar de baja |
| Jerarquía de departamentos | **Falta**, y probablemente deba seguir faltando: acotar la lectura no la necesita |

---

## 10. Conservación del registro

No es una situación laboral, pero entra por la misma prueba: sin plazo de
conservación el registro no se sostiene ante una inspección ---no hay nada que
enseñar de hace tres años--- y guardado para siempre no se sostiene ante la
Agencia de Protección de Datos.

| Situación | Norma | Hoy |
|---|---|---|
| Conservar el registro cuatro años | 34.9 ET | **Cubierto.** El plazo es un campo de la empresa y no puede bajar de cuatro años: lo rechaza el formulario y lo vuelve a rechazar el código que borra, porque un número escrito por consola o por importación nunca pasó por el formulario |
| Borrar cuando el plazo se cumple | 5.1.e RGPD | **Cubierto desde el 27/08/2026.** Un trabajo diario borra los fichajes que pasaron el plazo de su empresa y deja asiento de cuántos y hasta qué fecha. Antes de esa fecha el campo declaraba una política que nadie aplicaba |
| Metadatos de red con su propio plazo | 5.1.e RGPD | **Cubierto.** La IP, el dispositivo y el agente salen al año, y el fichaje sigue verificando su firma: por eso la firma no los incluye |
| Acceso de la persona a su propio registro | 34.9 ET, 15 RGPD | **Cubierto desde el 27/08/2026.** Quien trabaja allí lo tiene entero en su pantalla. A quien ya no trabaja allí la administración le manda un **enlace de entrega**: descarga su registro completo, en PDF o en hoja de cálculo, y no abre sesión ni da acceso a nada más |

Tres cosas que el borrado **no** toca, y cada una por su razón:

- **Las ausencias y los contratos.** Una vacación de hace cinco años sigue siendo
  lo que explica un hueco en una nómina de hace cinco años. No son el registro de
  jornada y no viven de este plazo.
- **Las decisiones sobre horas extra.** Son un acuerdo entre la empresa y la
  persona, no un fichaje, y el art. 35 tiene su propia cuenta.
- **El rastro de auditoría.** Es la prueba de que el borrado ocurrió, y no se
  puede borrar ni corregir: lo impide la base de datos. Guarda el número de
  fichajes que se fueron, nunca sus horas, así que conservarlo no deshace el
  borrado ---que es lo que habría que comprobar antes de dar por buena cualquier
  purga: si el rastro guardase una copia, la purga sería decorativa---.

Y las dos caras del plazo usan **la misma definición**: el día desde el que se
conserva lo decide una sola función, y de ella salen tanto lo que la purga borra
como lo que el enlace de entrega incluye. Con dos definiciones, un día habría
registro entregable que ya no existe, o registro guardado que no se entrega.

Y un corte que importa: **el plazo se cumple por días enteros, en el huso de la
empresa**, no a la hora exacta de hace cuatro años. Cortar por instante se llevaría
la mañana de un día y dejaría la tarde, y un día con solo la salida registrada no
es un dato incompleto: se lee como una jornada de cuatro horas.

---

## Por dónde seguir

Ordenado por lo que más se nota en un cliente real, no por dificultad. El tamaño
es una estimación en días de trabajo, contando la prueba que impida la regresión:
sirve para comparar entre líneas, no para prometer una fecha.

| | Qué | Tamaño |
|---|---|---|
| 1 | **Transcribir la resolución del BOE de 2026**, que es lo único que le falta al calendario para estar completo | **½ día.** Es copiar un boletín a un YAML versionado y verificarlo |
| 2 | **Saldos de devolución**: horas extra compensadas, relevo de turno, distribución irregular. Convertir los avisos en una cuenta | **5-8 días.** Es una pieza, no tres: un saldo con su plazo por concepto ---4 meses el art. 35.1, 4 semanas el relevo, 12 meses la distribución irregular---, su pantalla y su columna en el informe. Arregla **tres filas del inventario de golpe** |
| 3 | **Vacaciones**: devengo proporcional y traslado por IT | **3-4 días.** El devengo por fecha de alta y el traslado con el tope de 18 meses del art. 38.3 |
| 4 | **Historia de la adscripción a departamento**, cuando el informe empiece a mentir | **2-3 días.** Una tabla de vigencias y los informes leyendo de ella |
| 5 | **Las otras reducciones por cuidados** (arts. 37.4, 37.5 y 37.8): lactancia, hospitalización de un recién nacido y cuidado de menor con enfermedad grave. La mecánica de la fracción y las fechas **ya está** ---la puso el art. 37.6---; falta que cada una entre en el catálogo con su regla propia | **2-3 días.** Son tres artículos con cifras distintas sobre la misma maquinaria |
| 6 | **Las cifras de cada sector** (RD 1561/1995). Lo que quedaba de esta fila y sigue fuera a propósito: quince cifras por cada uno de los trece regímenes, cada sector con su convenio encima. Que los avisos citen el régimen declarado **ya está** desde el 28/08 | **Semanas**, y conviene partirlo por sector empezando por el que tenga un cliente esperando. No es trabajo pendiente sino una decisión de producto: mientras no haya un cliente de un sector concreto, traer sus cifras es inventar |

### Hecho desde que se escribió esta lista

- **La liquidación de vacaciones al terminar el contrato** (art. 38.1,
  28/08/2026), y con ella **cuatro filas de esta misma familia que ya estaban
  hechas y seguían marcadas como pendientes**.

  Clasificar antes de implementar volvió a ahorrar la vuelta entera. El
  enunciado decía «quien entra en julio tiene hoy el saldo entero», y medido en
  la demostración: **12 de 23**. El devengo proporcional se hizo el 13/08 y el
  inventario no se movió. Lo mismo con los dos regímenes del art. 38.3 ---la
  coincidencia con baja, con y sin plazo--- y con el plazo de dos meses del
  calendario, que tienen su código, sus pruebas y hasta una prueba de navegador.
  El inventario estaba **contando el producto peor de lo que está**, que es la
  dirección en la que un documento público equivoca a quien decide comprarlo.

  Lo que sí faltaba es la liquidación, y va con dos decisiones que se ven mejor
  en las pruebas que en el código. **Lo pendiente de decidir no resta**: no está
  disfrutado ni liquidado, así que restarlo daría una cifra a pagar más baja que
  la real; se cuenta aparte. Y **la cifra se enseña mientras se escribe la fecha
  de baja**, no después de guardarla: la primera versión solo sabía contestar por
  la fecha ya guardada, de modo que el número aparecía tras guardar, cerrar la
  ficha y volver a abrirla, o sea cuando ya no servía para decidir.

  **Días, no importe.** Lo que vale un día depende del salario, de los
  complementos y del prorrateo de pagas: eso es una nómina y está fuera de lo
  que hace este producto.

- **Que los avisos citen el régimen declarado** (28/08/2026), y con esto quedan
  cubiertas **las trece situaciones** que Francisco marcó el 28/08.

  Al clasificarla salió lo que faltaba de verdad: el régimen se podía declarar
  **por la API y en ningún otro sitio**. El campo estaba en el modelo desde la
  vuelta anterior, el serializador lo exponía, y la pantalla de ajustes no tenía
  selector. Una frase que nombra el sector no sirve de nada si el sector no se
  puede decir, así que la vuelta incluyó el selector.

  Las opciones las manda el servidor ya traducidas, por lo mismo que las citas:
  escribirlas en la pantalla habría dejado dos listas que mantener y la
  traducción de cada etiqueta lejos del sitio que la define.

- **Las guardias de sanidad** (28/08/2026). Con el régimen declarado, la guardia
  de presencia en el centro suma para el tope semanal de la Directiva 2003/88,
  que es lo que SIMAP y Jaeger llevan veinte años diciendo. Lo que había: una
  guardia de veinticuatro horas no contaba **nada**, y quien hacía cuarenta de
  jornada y dos guardias figuraba con cuarenta horas habiendo pasado ochenta y
  ocho en el hospital.

  El diseño se cambió a mitad de camino y conviene dejarlo escrito: la primera
  versión leía cada día con la pieza que ya sabe leerlo ---descuenta pausas,
  separa la presencia--- y era la opción limpia salvo por un detalle que es el
  caso entero: **una guardia cruza la medianoche**, esa pieza recorta al día, y
  la guardia no contaba en ninguno de los dos. Se empareja sobre el rango
  completo.

- **El tiempo de presencia del transporte** (art. 8.b RD 1561/1995, 28/08/2026),
  y con él **el régimen especial declarado**, que era lo que faltaba para las
  jornadas por sector. Es la única comprobación de toda la revisión que **no** es
  para todo el mundo: las veinte horas son de un sector, y avisar a quien no lo
  tiene sería inventarle una norma ajena ---el error contrario al que esta
  auditoría persigue, y uno igual de malo---.

- **El saldo de la distribución irregular** (art. 34.2, 28/08/2026), *la mitad
  que se puede calcular*. Estaba descartado por dos motivos y uno se ha caído:
  el plazo ahora lo declara la empresa, así que ya no hay que suponerlo. El otro
  ---que falta la distribución ordinaria contra la que comparar--- sigue en pie
  para el 10 %, y no alcanza al saldo **si la jornada se pactó por año**: esa
  cifra ya viene neta de vacaciones y festivos, y restarla es honesto. Con
  jornada semanal no se contesta, porque 40 × 52 son 2.080 horas que no trabaja
  nadie y la resta convertiría las vacaciones en una deuda.

- **El relevo y la jubilación parcial** (arts. 12.7 y 12.6, 28/08/2026), que son
  una sola pieza: la cifra que el 12.7 compara ---la jornada del relevo contra lo
  que el otro deja de trabajar--- **sale de la jubilación del otro**. Lo que
  faltaba no era la mecánica de reducir la jornada, que ya la puso el art. 37.6,
  sino el **vínculo** entre las dos personas. El tope que sube al 75 % es el
  ejemplo más claro de por qué van juntos.

- **La adaptación de jornada** (art. 34.8, 28/08/2026), en dos tandas. El producto sabía la consecuencia ---un fichaje puede
  marcarse como trabajado bajo una adaptación, art. 3.i--- y no tenía dónde
  mirar la obligación: quince días de negociación como máximo y respuesta por
  escrito, motivada si no es un sí. El plazo se avisa y la motivación se exige,
  y la diferencia sale del artículo.

- **Los dos contratos formativos** (arts. 11.2 y 11.3, 28/08/2026). Eran el
  mismo régimen, y por eso no se le podía poner el tope a uno sin ponérselo al
  otro: las dos filas eran el mismo problema. Ahora cada uno tiene el suyo, y el
  de alternancia lleva el tope del art. 11.2.b contra la jornada máxima. **El
  valor viejo se queda a propósito**: los contratos ya guardados no dicen cuál
  de los dos son, repartirlos sería decidirlo por quien los firmó, y la revisión
  pide que se concrete.

- **El trabajo a distancia** (Ley 10/2021, 28/08/2026), en dos tandas. La ley no regula «el teletrabajo» en general: fija
  cuándo se aplica, y por debajo del 30 % de la jornada en tres meses no exige
  nada. Cruzado el umbral entra entera, y lo primero que pide es acuerdo por
  escrito y previo. El producto ya sabía si cada tramo fue presencial o a
  distancia (art. 3.e) y no hacía la cuenta; ahora la hace y avisa de las dos
  cosas que pueden fallar, que se arreglan de manera distinta: no tener acuerdo,
  y tenerlo firmado después de haber empezado.

- **La reducción de jornada por guarda legal** (art. 37.6, 28/08/2026). El
  mecanismo para reducir la jornada existía entero desde el ERTE, y estaba
  cerrado a lo que **registra la empresa**. El razonamiento era bueno ---una
  excedencia voluntaria «al 40 %» no existe--- y dejaba fuera la reducción más
  corriente de todas, que la pide quien trabaja. La única forma de apuntarla era
  escribirla en el horario contratado, donde no hay fracción, no hay fechas y el
  derecho no se acaba nunca. Ahora lo decide el catálogo tipo a tipo.

- **El tope de horas complementarias** (art. 12.5.c, 28/08/2026). El aviso del
  cuadrante llevaba tiempo diciendo que las horas por encima del contrato
  «cuentan para su propio límite» y **ese límite no lo llevaba nadie**. Ahora se
  acumula contra lo trabajado y se avisa al pasarse, sobre el periodo del
  contrato y no sobre el mes. Las personas salen del registro y no del cuadrante,
  para que no se quede fuera quien no tiene turnos planificados ---que es quien
  más fácilmente se pasa sin que nadie mire---.

- **El llamamiento del fijo discontinuo** (art. 16, 28/08/2026). Estaba
  estimado en 2-3 días y salió en dos tandas. Periodos de actividad con su fecha
  de llamamiento, cargados desde la ficha de la persona; fuera de ellos no se
  espera jornada, el cuadrante avisa si se asigna un turno y la cobertura
  pendiente lo distingue de quien dejó la empresa ---que no se resuelven igual:
  a quien se fue hay que reasignarle el turno, a quien está entre campañas a lo
  mejor basta con moverlo unos días---.

- **La interfaz en catalán y gallego** (28/08/2026). Estaba estimada en 4-6 días
  para unas 330 cadenas; fueron **898 en 917** y doce tandas, porque la cuenta
  de partida no veía ni los párrafos partidos ni los rótulos compartidos.
  Termina con un guard que exige el catálogo completo
  ---`npm run i18n:check`--- y con las diecinueve cadenas que **no** se traducen
  declaradas una a una con su motivo. **Le falta que la revise alguien que hable
  el idioma**, y eso no es trabajo de programación.

---

Al cubrir una situación hay que mover su fila aquí y, si toca una pantalla,
actualizar el [manual](manual/README.md).
