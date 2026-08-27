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
| Horas extraordinarias | art. 35 | **Cubierto.** Se marcan, se dice cómo se saldan y el tope anual se contrasta con lo autorizado: la pantalla de decisiones avisa al pasarse, descontando las compensadas con descanso y las de fuerza mayor |
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
| Calendario con dos meses de antelación | 38.3 | **Falta.** No existe el calendario de vacaciones como documento |
| Coincidencia con embarazo, parto o lactancia | 38.3 | **Falta.** Se disfrutan en otra fecha |
| Coincidencia con IT por otra contingencia | 38.3 | **Falta.** Hasta 18 meses después del fin del año en que se originaron |
| Devengo proporcional al tiempo trabajado | — | **Falta.** Quien entra en julio tiene hoy el mismo saldo que quien lleva el año entero |
| Liquidación al finalizar el contrato | — | **Falta** |
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

Ordenado por lo que más se nota en un cliente real, no por dificultad.

1. **Transcribir la resolución del BOE de 2026**, que es lo único que le falta
   al calendario para estar completo.
2. **Saldos de devolución**: horas extra compensadas, relevo de turno,
   distribución irregular. Convertir los avisos en una cuenta.
3. **Vacaciones**: devengo proporcional y traslado por IT.
4. **Llamamiento del fijo discontinuo** (art. 16), ya señalado en el código.
5. **Topes que se guardan y no se comprueban**: 30 % de complementarias al mes y
   65/85 % del contrato formativo. El de 80 horas extra al año ya se contrasta.
6. **Historia de la adscripción a departamento**, cuando el informe empiece a
   mentir.
7. **Borrar de verdad a quien no tiene ni un fichaje.** Un alta equivocada no se
   puede quitar: solo darse de baja, y se queda en la lista para siempre. Con
   fichajes es correcto que no se pueda; sin ellos, no.

---

Al cubrir una situación hay que mover su fila aquí y, si toca una pantalla,
actualizar el [manual](manual/README.md).
