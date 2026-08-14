# Auditoría continua — cuaderno

Vueltas dadas: 19 · Vueltas seguidas sin hallazgos: 0

El estado de cada área no es una opinión: «limpia» significa que se ejercitó
entera en una pasada y no salió nada. Mientras quede una «sin tocar», no se
vuelve a una limpia.

## Áreas

### Pantallas

| Área | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Fichar (`/`) | limpia | 13/08 v1 | **doble pulsación = jornada en cero** |
| Resumen (`/panel`) | limpia | 13/08 v2 | **decía 2 de 57 esperando decisión** |
| Mi jornada (`/mi-jornada`) | limpia | 14/08 v16 | **«la hora no es la real» fallaba siempre**; descarga del propio registro (v10) |
| Mis ausencias (`/mis-ausencias`) | limpia | 14/08 v17 | **el justificante no se podía adjuntar nunca**, y el diálogo prometía que sí |
| Personas | limpia | 13/08 | filtros, selección múltiple, `?department=` roto |
| Departamentos | limpia | 13/08 | miembros desde el diálogo |
| Centros | limpia | 13/08 | zona horaria de texto libre |
| Calendario del equipo | limpia | 13/08 | filtros; cuatro manos |
| Cuadrante | limpia | 13/08 | formulario no enviable; días vacíos = todos |
| Turnos | limpia | 13/08 | — |
| Fichajes | limpia | 13/08 | filtros de tipo y origen |
| Por decidir | limpia | 13/08 v2 | resolver en bloque; **contadores truncados a 50** |
| Informes | limpia | 13/08 | zip con nombre de PDF; CSV con CRLF |
| Aplicaciones | limpia | 13/08 | — |
| Ajustes | limpia | 13/08 | límites legales sin aviso; cambios sin guardar |
| Registro de actividad | limpia | 13/08 | IP de un compañero |
| Entrar / recuperar contraseña | limpia | 13/08 v3 | **el aviso de demasiados intentos, traducido a máquina** |

### API sin pantalla

| Área | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Fichaje delegado (terminal, lector) | limpia | 13/08 v4 | **evidencia sin tope de tamaño** |
| `applications/people` (integración Geosian) | limpia | 13/08 v5 | **lectura truncada a 500 en silencio**; el cursor se rompía con el `+` del huso |
| `applications/attendance` | limpia | 13/08 v6 | **el día salía del reloj del contenedor, no de la empresa** |
| Avisos push y correo | limpia | 13/08 v7 | — en el área; salió **una plural sin traducir que se veía en blanco** |
| Importación de datos (festivos) | limpia | 13/08 v9 | **solo leía un país**; no comprobaba el fichero; el resumen contaba días que no escribía |

### Ley

| Punto | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Art. 34.9 — registro objetivo, fiable, conservado | limpia | 13/08 v10 | **el informe de empresa borraba a quien se fue**; nadie podía descargar el suyo desde la interfaz |
| Art. 34.2 — distribución irregular | limpia | 13/08 v12 | **el preaviso de 5 días no lo leía nadie**; el 10 % anual, descartado a propósito |
| Art. 34.3/34.4 — jornada, descansos | limpia | 13/08 | avisos con cita |
| Art. 35 — horas extra y su tope | limpia | 13/08 | — |
| Art. 36 — nocturno y turnos | limpia | 14/08 v15 | **el turno de noche no cerraba la jornada**; el veto de horas extra del 36.1 no se comprobaba |
| Art. 37.1/37.2 — descanso semanal y festivos | limpia | 13/08 | — |
| Art. 37.3 — permisos retribuidos | limpia | 13/08 v11 | **una empresa nueva se quedaba sin un solo permiso**; el catálogo cuadra con el articulado |
| Art. 38 — vacaciones y recuperación | limpia | 13/08 | — |
| Art. 4.b — consentimiento de las dos partes | limpia | 13/08 | — |
| Constancia de la consulta a la RLT | limpia | 14/08 v13 | **no había dónde declararlo**; ahora consta la vía, cuál, desde cuándo y la consulta |
| Calendario con dos meses de antelación (38.3) | limpia | 13/08 v9 | **estaba solo citado**; ahora se avisa, y solo cuando las pone la empresa |
| RGPD / art. 88 LOPDGDD | limpia | 14/08 v14 | **una empresa de baja guardaba las IP para siempre**; y el rastro había dejado de ser inmutable |

## Hallazgos abiertos

- **`max_employees`, `max_admins` y `max_storage_mb` no los aplica nada.** Son
  campos de `Tenant` con pinta de cuota de plan y ningún código los lee. No están
  expuestos en la API, así que nadie los puede poner y creerse protegido --- es
  esquema muerto, no una trampa. Huelen a preocupación de Cloud dentro del Core:
  **por decidir**, y encaja con la línea Core/Cloud que está sin cerrar.

- **Tres exportaciones del cliente que nadie llama, y son decisiones abiertas.**
  El barrido al revés de la vuelta 18 dejó estas: `signUp` ---no hay pantalla de
  alta de empresa, así que un cliente nuevo solo se da de alta por API---,
  `createLeaveType` y `updateLeaveType` ---el catálogo no se puede editar, que ya
  estaba anotado--- y `getEmployee`, que probablemente sobra. Ninguna es un fallo
  por sí sola; las tres son «¿esto tenía que existir?».

- **La jornada de noche no se atribuye a ningún día.** Arreglada la deducción
  del tipo, las marcas ya salen bien ---entrada a las 22:00, salida a las
  06:00--- pero la reconciliación y el informe siguen partiendo el tramo por la
  medianoche: el día 8 sale «entrada sin salida», el 9 «salida sin entrada
  previa», y las ocho horas **no aparecen en ningún sitio**. Consecuencias
  encadenadas: esa jornada no genera nunca fila de horas extra, y el estado del
  día se lee mal a un lado y a otro de las doce.

  Lo que falta es una **decisión de convenio, no un arreglo**: a qué día
  pertenecen las horas de un turno que cruza la medianoche. Lo natural es el día
  en que empezó ---es como está montado el cuadrante--- pero hay convenios que
  parten por la medianoche a efectos de nocturnidad. Afecta a informes,
  reconciliación, horas extra y estado del día, así que conviene decidirlo antes
  de tocar nada.

- **El tope de dieciséis horas de `MAX_OPEN_HOURS`.** Es la frontera entre
  «cerró tarde» y «se olvidó de fichar», y no la fija ningún artículo. Elegido
  por ser más largo que cualquier jornada de un tirón y bastante más corto que
  un olvido de un día. **Conviene confirmarlo con la asesoría.**

- **La IP del rastro de auditoría no caduca, y por diseño no puede caducar.**
  El fichaje suelta la suya al año; la entrada del rastro que describe ese mismo
  hecho la conserva indefinidamente, y el razonamiento de la purga ---«pasada
  esa ventana no hay base para tenerla»--- no distingue entre las dos.

  Intenté purgarla y **no se puede**: la tabla es *append-only* por tres
  triggers, que rechazan UPDATE, DELETE y TRUNCATE. Esa restricción es una
  decisión más fuerte que mi mejora y no la voy a saltar por mi cuenta.

  Es una tensión real entre dos principios correctos, y la salida limpia no es
  borrar después sino **no guardarla**: minimizar al recoger, que además es lo
  que el RGPD prefiere. Si se decide, la pregunta es qué se pierde para
  investigar un incidente. **Por decidir, no por arreglar.**

- **`app/attendance` hace tres consultas por persona.** Medido: 604 consultas y
  215 ms con doscientas personas, 68 y 142 ms con veinte. Con mil serán tres mil
  consultas. Reconciliar el día persona a persona no escala, y esto lo pide un
  conector que puede llamarlo a menudo. Hace falta una consulta agregada.
- **Ejecutar las pruebas con ventana de vez en cuando.** El favicon ausente
  llevaba ahí desde siempre con la suite entera en verde: Chrome sin ventana no
  lo pide. Lo mismo puede pasar con tipografías, impresión o consultas de medios.

- **«Por decidir» no tiene paginador.** Las colas de correcciones llegan de
  cincuenta en cincuenta y ahora al menos se avisa del recorte, pero a las que
  faltan solo se llega filtrando. Con una plantilla grande eso no basta. El
  componente `Pager` ya existe; es cablearlo en las tres colas paginadas.
- **Contar las horas extra pendientes cuesta medio segundo** con veinte
  personas, porque reconcilia cada día de cada una. Por eso el Resumen dice que
  las hay sin decir cuántas. Con cien personas serán dos segundos y medio y la
  pantalla de decisiones se notará. Hace falta una consulta agregada, no un
  bucle por persona y día.
- **El catálogo de permisos no se puede editar desde ninguna pantalla.** Se
  siembra con la empresa y se puede recargar desde Ajustes, pero cada permiso
  tiene su cifra, su unidad y su periodo, y el convenio mejora cualquiera de
  ellos --- que es la razón entera de que el catálogo se copie en vez de leerse
  del marco. Hoy esa mejora solo se puede aplicar por API. El `LeaveTypeViewSet`
  ya es un ModelViewSet completo: falta la pantalla.
- **Fichar no ofrece pausa ni modo de trabajo.** El modelo los soporta
  ---`PunchInterval.BREAK`, `work_mode`--- y la pantalla solo tiene un botón.
  Puede ser deliberado (un toque, sin decisiones) pero entonces el descanso del
  art. 34.4 no se puede registrar desde el sitio donde se ficha. **Por decidir,
  no por arreglar**: preguntarlo antes de tocar nada.

  Mirado el `timetrack/` de Geosian el 13/08: **allí tampoco existe**. Su regla
  es «una entrada y una salida por día» y su guía de migración dice literalmente
  que «pausas y ausencias llegarán en OpenTimeTrack, no aquí». Así que no hay
  nada que copiar: el hueco es de OTT desde el principio.

## Cerrado

**Vuelta 19 — Segunda pasada, barriendo las dos clases que ya dieron fallos.**

Dos barridos, uno por cada familia con antecedentes.

**Ajustes que nadie lee.** El de `roster_notice_days` en la vuelta 12 hacía
sospechar de más. No los hay: los veintinueve ajustes de empresa y de reglas
tienen lector. Solo quedan tres campos de cuota ---`max_employees`,
`max_admins`, `max_storage_mb`--- que nada aplica, y que ni siquiera están
expuestos: esquema muerto, arriba anotado.

La primera versión del barrido dio **todos muertos**, incluidos `weekly_hours` y
`daily_rest_hours`, que evidentemente se leen. Era un `grep -oP` sobre varios
ficheros, que antepone el nombre del fichero a cada resultado. Un barrido que
acusa a todo el mundo no es un barrido: se calibra mirando que lo conocido salga
donde debe.

**Cálculos que no sobreviven a la medianoche.** Aquí sí había uno, y es el mismo
supuesto que dejó el turno de noche sin cerrar: **la guarda del doble toque
miraba «los fichajes de hoy»**, así que pulsar a las 23:59:58 y otra vez a las
00:00:01 daba dos fichajes --- el día nuevo estaba vacío. Tres segundos entre uno
y otro, que es justo lo que esa guarda existe para evitar, y un turno que empieza
a las 00:00 es corriente donde se trabaja de noche.

Los demás sitios que acotan por día están bien, y conviene dejarlo escrito:
`timestamp__date` con USE_TZ convierte a la zona activa, que el middleware fija a
la de la empresa; y el gráfico del Resumen cuenta **eventos** y lo dice en su
propia documentación, así que partir una noche en dos días es correcto ahí.

**Vuelta 18 — Segunda pasada, con la comprobación al revés.**

Sin áreas sin tocar ni a medias, la vuelta se hace por técnica en vez de por
pantalla: coger lo que el backend ofrece y buscar **quién lo llama**. Es la que
salió de la vuelta 17 y cuesta dos minutos.

**Las setenta y dos rutas de la API tienen cliente**, salvo las tres de
integración externa, que es como debe ser. Ahí no había nada.

Al revés sí: seis funciones exportadas en `services/api.js` que ninguna pantalla
usa. Una era un fallo de producto --- **el resumen que acompaña a la nómina**.
Estaba entero en el servidor, con su periodo, sus cifras, su huella y su descarga
en PDF; su documentación dice «read for the person concerned»; y ninguna pantalla
se lo daba a esa persona. Quien lleva la nómina podía generarlos desde Informes y
quien trabaja no podía verlos --- con `generatePayrollSummaries` usada y
`getPayrollSummary` muerta, la una al lado de la otra.

Van tres fallos encontrados con la misma técnica en dos vueltas.

Y una prueba que **solo funcionaba la primera vez**: fijaba el tope de horas
extra en 72, y si una tanda anterior se cortó antes de restaurarlo, ya valía 72
--- nada que guardar, botón desactivado, treinta segundos de espera. Ahora elige
un valor distinto del que hay.

**Vuelta 17 — «Solicitar», y el tramo que faltaba. Última área a medias.**

**El justificante no se podía adjuntar.** La API lo aceptaba desde el principio,
el modelo lo guarda con sus validadores ---PDF o imagen, hasta 10 MB---, la lista
enseñaba un distintivo de «tiene justificante» y hay un endpoint para
descargarlo con su control de acceso probado. Y ninguna pantalla lo subía nunca.

Peor que el hueco: el propio diálogo prometía que «se puede adjuntar después», y
no se podía ni antes ni después. Todo el camino de vuelta montado menos la ida.

Es la misma forma que el catálogo de permisos de la vuelta 11 y que
`roster_notice_days` de la 12: **la pieza existe, está bien hecha, y nadie la
llama**. Tres veces en siete vueltas. Merece buscarse a propósito.

Con dos cuidados que no son cosméticos: nunca en una baja ---desde el RD
1060/2022 el parte no se le entrega a la empresa y el servidor rechaza el
fichero, así que ofrecerlo sería invitar a subir un dato de salud que no debe
estar--- y el fichero se olvida al cerrar el diálogo, porque adjuntar el
justificante de un permiso a la solicitud siguiente sería peor que no tenerlo.

**Vuelta 16 — «Pedir una corrección», y una lección cara sobre la base compartida.**

**La opción «la hora registrada no es la real» fallaba siempre.** El servidor
exige decir qué fichaje se corrige ---sin eso el consentimiento del art. 4.b no
significa nada--- y el diálogo no ofrecía dónde indicarlo: se recibía «Indica qué
fichaje se corrige» y ningún sitio donde hacerlo. La otra mitad, «olvidé
fichar», sí funcionaba, y por eso llevaba ahí sin verse.

Y un fallo de sesión que salió **de sufrirlo**: de tanto correr la suite en un
día se agotó el límite de peticiones por persona, y la pantalla de Ajustes se
volvió el formulario de entrada con la sesión buena guardada al lado. Media hora
buscando una regresión que no existía. En la vuelta 6 se arregló que el testigo
dejara de borrarse con un 429; lo que veía la persona seguía siendo lo mismo,
porque sin sesión en memoria la aplicación cae al formulario. Ahora distingue
«no vale» de «no he podido comprobarla».

Lo que más me ha costado de esta vuelta no fue encontrar nada: fue **el estropicio
que hice yo**. Mi primera versión de la prueba creaba fichajes con dos POST
seguidos, la protección del doble toque rechazaba el segundo, y Ana se quedó
fichada: dieciséis pruebas de otros ficheros en rojo. Y varios sondeos por
consola dejaron ocho empresas de mentira donde debía haber tres, que tumbaron
setenta y cuatro. Ambas cosas estaban en `lessons.md` desde ayer.

**Vuelta 15 — El art. 36, y el fallo más grave de toda la auditoría.**

Empezó como una vuelta pequeña. El hueco que el cuaderno traía ---«falta la
fecha de la evaluación de salud»--- **no es un hueco**: `docs/cobertura-legal.md`
lo excluye a propósito, «nosotros avisamos de que esa condición existe; el
reconocimiento lo lleva el servicio de prevención». Anotado, y a mirar lo que sí
nos toca.

**El veto de horas extra del art. 36.1 no se comprobaba.** El aviso del
cuadrante lo nombraba ---«trae una media de ocho horas, una prohibición de horas
extra y una evaluación de salud»--- y luego la cola de «Por decidir» las
autorizaba sin mencionarlo. `holds_night_worker_status` existía y se usaba en un
solo sitio. Al lado están sus dos hermanas, que sí se comprobaban desde hacía
tiempo: el veto a los menores (art. 6.3) y el de jornada parcial (art. 12.4.c).
Faltaba la tercera.

Y escribiendo la prueba de eso salió lo gordo: **un turno de noche daba dos
entradas y ninguna salida**. La deducción del tipo miraba solo los fichajes del
día local, así que al salir a las 06:00 el día nuevo no tenía ninguno y decía
«entrada». La jornada no se cerraba nunca, el día quedaba en cero horas y la
persona figuraba trabajando indefinidamente. En vigilancia, limpieza o
residencias eso es el registro entero mal, todos los días, para toda la
plantilla de noche --- y es justo la gente sobre la que el producto más avisa.

La misma raíz mordía en otro sitio: quien entró a las diez no podía empezar una
pausa a las tres de la mañana, porque la guarda preguntaba «¿está abierta la
jornada?» por días locales.

Las dos arregladas. La tercera capa ---a qué día pertenecen esas horas--- queda
arriba, en los hallazgos abiertos, porque es una decisión y no un arreglo.

**Vuelta 14 — La purga de metadatos, y una garantía que se había evaporado.**

El área estaba bien cuidada de partida: doce pruebas, cron documentado, tarea de
Celery, y el purgado de `evidence` razonado por escrito ---no entra en el hash
justo para que se pueda borrar, que es el error que `_hash_v1` cometió con la
IP---. Aun así salieron dos cosas.

**Una empresa de baja conservaba las IP para siempre.** El bucle recorría solo
las activas, y el comando terminaba diciendo «Purged 0 events»: todo iba bien.
El plazo no deja de correr porque una empresa deje de usar el producto, y esos
son justo los datos que ya no mira nadie.

Y lo gordo, que salió de intentar arreglar otra cosa: **el rastro había dejado
de ser inmutable**. La migración que crea los tres triggers figuraba aplicada y
su función existía, pero los triggers no estaban en la base de desarrollo. Se
podía editar y borrar el rastro sin que nada chistara --- lo contrario de lo que
esa misma migración declara: «un rastro que puede editar aquel a quien incrimina
no es prueba».

Lo descubrí porque la **prueba** rechazaba el UPDATE y la base no. Ahí está lo
que hay que quedarse: las pruebas corren sus migraciones enteras y siempre ven
los triggers, o sea que son el único sitio donde este fallo **no podía** salir.
Por eso la comprobación vive ahora en `/api/health/`, que le pregunta a la base
que está sirviendo, con `ensure_append_only` para reponerlos --- una sonda que
avisa sin dar salida deja al operador leyendo migraciones.

De rebote, `seed_demo --reset` estaba roto y nadie lo sabía: borraba entradas
del rastro, y solo funcionaba porque los triggers faltaban.

**Vuelta 13 — La constancia de cómo se organizó el registro. Última área.**

El art. 34.9 pide dos cosas y el producto hacía una. Llevar el registro, sí.
**Documentar con qué amparo se organizó ese registro**, no: no había dónde
escribirlo. Es lo primero que una inspección pide después de los propios
registros, antes que ningún fichaje, porque decide si el sistema tiene respaldo.

Las tres vías son excluyentes y están ordenadas ---la decisión del empresario es
la de «en su defecto» y solo esa arrastra la consulta previa---, así que se
guardan como opciones y no como texto libre: esa diferencia es justo la que
decide si faltaba una consulta. Una decisión de empresa sin fecha de consulta se
señala; un convenio **con** fecha de consulta se rechaza, porque un acuerdo es
la negociación y sugerir un trámite que no existe confunde a quien lo lea
después.

Se guarda la constancia, no el acta: que exista un documento, de qué fecha y con
qué referencia es el hecho comprobable. Un almacén de documentos traería su
propia decisión de conservación ---esto no es registro de jornada, así que los
cuatro años no le aplican--- y esa no se toma de pasada.

Tres cosas más salieron por el camino, todas de comprobaciones que ya estaban:

- **El barrido de aislamiento cazó la ruta nueva** antes de que se me olvidara
  meterla, que es exactamente para lo que está.
- **El registro de actividad imprimía «null»** donde el campo estaba vacío
  ---«consulted_on: null → 2024-01-10»---. Le pasaba a cualquier entrada con un
  campo opcional; no había salido porque ninguna de las que había guardaba un
  nulo. Lo vio la prueba que vigila `undefined`, `NaN` y `null` en todas las
  pantallas.
- **Cinco entradas del catálogo estaban marcadas `fuzzy`**, o sea saliendo en
  inglés. Una la metí yo en la vuelta 10 y se fue a `main`: al cambiar el texto
  de un error, `makemessages` lo marcó fuzzy con la traducción vieja. Ya lo mira
  una prueba.

Y tres pruebas que **caducaban a medianoche**: congelaban el reloj para fichar y
preguntaban por «hoy» fuera del bloque congelado. La tercera, que no era mía,
usaba `date.today()` ---la fecha UTC del contenedor--- mientras el producto mira
el día de la empresa: entre las doce y las dos de la madrugada en Madrid no
coinciden. La trampa de `apps/common/clock.py`, esta vez dentro de una prueba,
donde el aviso del módulo no lo lee nadie.

**Vuelta 12 — El art. 34.2: un ajuste que no leía nadie.**

`roster_notice_days` vivía en el modelo, en el marco legal con su cita, y en la
pantalla de ajustes para que la empresa lo subiera si su convenio lo mejora.
**Y no lo miraba ni una línea de código.** Es la misma familia que los
`search_fields` declarados sin el filtro puesto: un ajuste que no lee nadie es
peor que no tenerlo, porque quien lo configura se queda convencido de que el
producto lo vigila.

Ahora el cuadrante avisa con su cita, como los otros nueve. Tres decisiones que
salieron de **medir** y no de suponer:

- El plazo se cuenta desde que el turno se puso o se cambió, no desde hoy.
  Contra hoy, uno planificado en enero para julio se volvería «de última hora»
  solo por acercarse la fecha.
- `updated_at` y no `created_at`: mover un turno de las siete a las quince es un
  dato nuevo, y el artículo pide el día **y la hora**.
- Un turno anotado **después** del día no cuenta. Eso no es poco preaviso, es
  rellenar el cuadrante de la semana pasada --- y eran **94 de los 128** avisos
  que salían en un mes de datos reales. Sin medirlo, el aviso habría nacido
  siendo ruido.

Y un falso positivo de cosecha propia: la comprobación de plurales de la vuelta
7 daba por vacía toda traducción larga, porque gettext las parte y la primera
línea es siempre `msgstr[N] ""` con el texto debajo. Ladrar sin motivo hace el
mismo daño que callarse, porque a la segunda vez se desactiva; lleva ya su
contraste para que siga cazando el fallo que la trajo.

**Vuelta 11 — El art. 37.3, y un fallo que solo se veía fuera de desarrollo.**

Lo que cuadraba, y merece decirse porque es donde más fácil habría sido
equivocarse: **el catálogo está bien contra el articulado**. El RDL 5/2023
partió la antigua letra b en dos, subió la hospitalización de dos días a cinco y
sacó el fallecimiento a una letra nueva, «b bis», sin correr las demás --- y el
catálogo cita b, b bis, c, d, e, f exactamente así. Los quince días del
matrimonio son naturales, el fallecimiento guarda dos más dos de desplazamiento
en vez de un cuatro que no distinguiría los casos, y los del «tiempo
indispensable» no llevan tope inventado.

Y el fallo: **una empresa recién dada de alta se quedaba con cero permisos**. Se
creaba la empresa, se creaba su administradora, y el catálogo no se sembraba. El
desplegable de «Qué pides» salía vacío y nadie podía pedir un matrimonio, un
fallecimiento ni una hospitalización.

Lo interesante es por qué no se había visto: el endpoint que siembra el catálogo
existía, `seedLeaveTypes` estaba exportado en el frontend, y **no lo llamaba
ninguna pantalla**. Lo único que lo usaba era el comando de datos de
demostración --- o sea que funcionaba en desarrollo y en ningún sitio más, que es
la forma más cara de que algo esté roto, porque parece que está bien. Todas las
pruebas, las de backend y las de navegador, corren sobre la base sembrada.

**Vuelta 10 — El art. 34.9, que es el producto entero.**

Lo que aguantó, y conviene decirlo porque marca dónde no volver: el fichaje está
protegido contra el borrado ---`PROTECT` en la persona, «a person with clock
events is never deleted»---, la retención de cuatro años no se puede bajar por
ajuste, y la purga de metadatos se lleva la IP y el dispositivo sin tocar el
fichaje ni su hash.

**El informe de toda la empresa borraba a quien se había ido.** Filtraba por
`is_active`, así que el de marzo salía sin la persona que se marchó en abril, y
no lo decía: un zip con doscientos documentos y uno menos. Lo que el artículo
pone a disposición de la Inspección es el registro **del periodo**, no el de
quien siga en plantilla el día que se pide --- y en una empresa con rotación esto
pasa todos los meses, porque una inspección se pide justo del periodo en el que
alguien se fue. Ahora entra quien está de alta más quien fichó en el rango; dos
de las seis pruebas son el contraste que impide que el arreglo sea «meter a todo
el mundo».

**Y «a disposición de las personas trabajadoras» no se cumplía.** La API dejaba
a cualquiera pedir el suyo desde el principio, pero la única pantalla que lo
ofrecía estaba detrás del panel de gestión: a su disposición lo tenía quien
administra, y no la persona de la que habla el artículo. Poder mirarlo en
pantalla no es poder llevárselo --- lo que se enseña a un juzgado es el documento
con su huella. Ahora hay un botón en «Mi jornada», y baja el mes que se está
mirando, no el corriente.

Dos fallos míos, los dos cazados por pruebas que acababa de escribir: el rótulo
del botón decía «Invalid Date» ---`monthName` toma un objeto, no dos números---
y la comprobación de que un operario no puede pedir el informe de otro **pasaba
sin comprobar nada**, porque con una URL relativa la petición se la queda el
servidor de desarrollo del frontend y devuelve el `index.html` con un 200.

**Vuelta 9 — La importación de festivos, y los dos meses del art. 38.3.**

El comando escribe días en todas las empresas del país de un tirón y **no tenía
ni una prueba**. Lo que escribe no es un dato cualquiera: un festivo dentro de
un permiso no gasta día de vacaciones, y decide si el cuadrante señala trabajo
en fiesta.

Tres fallos. **Solo se podía importar un país**: se quedaba con el primer
directorio por orden alfabético, así que con `es/` y `pt/` publicando el mismo
año, las empresas portuguesas no recibían nada y el comando decía que había
terminado --- mientras la cabecera del módulo presumía de que añadir un país es
un fichero y no un cambio de código. **No comprobaba nada de lo que leía**, y
`HOLIDAYS_DIR` existe justo para que un despliegue traiga el suyo: sin país daba
un `KeyError` pelado, y una fecha del año equivocado ---la errata natural al
copiar el fichero del año anterior--- se escribía y **no se podía deshacer
reimportando**, porque la limpieza va por el rango del año que pides. Y **el
resumen contaba días que no se escribían**, porque `ignore_conflicts` se traga
en silencio lo que choque.

Diecinueve pruebas donde no había ninguna; nueve se ponen rojas con el comando
de antes.

Y el punto legal de la misma área, que llevaba desde el 13/08 como «solo
citado»: el art. 38.3 pide que las vacaciones se conozcan con dos meses. Ahora
se avisa ---no se impide, como con el resto de los mínimos--- y **solo cuando
las pone la empresa**: quien pide las suyas conoce las fechas por definición, y
un aviso que saltara también ahí saldría en la mitad de las solicitudes y en dos
semanas nadie lo miraría. Para distinguirlo hacía falta un dato que la fila no
tenía: quién la metió. Decía de quién son las vacaciones y quién las aprobó, y
se callaba lo del medio.

**Vuelta 8 — La CI, que llevaba roja, y una intermitente que era un fallo.**

Dos cosas, y las dos salieron de correr las comprobaciones enteras antes de
empujar en vez de dar por hecho el estado.

**El paso del esquema fallaba desde que entró la API de integración.** Dos
avisos, y `--fail-on-warn` los convierte en error. Comprobado que venían de
antes poniendo el fichero de entonces y viéndolos salir igual. Uno era una
colisión de nombres de operación ---las dos lecturas de personas se llamaban
igual y el generador las desempataba con un número, así que qué método era cuál
en un cliente generado dependía del orden en que se recorrieran las rutas---; el
otro, un juego de valores con dos nombres, el mismo caso ya resuelto dos veces
ahí al lado.

**Y `npm run lint` daba 739 errores en local**, todos del informe HTML de
Playwright, que eslint entraba a leer. En la CI no se veía porque el checkout es
limpio y ese directorio no existe: se rompía solo en local, y justo para quien
acababa de correr las pruebas.

Lo gordo salió de una prueba que fallaba **una de cada tantas** y pasaba al
ejecutarla sola. La tentación era llamarla frágil. Era un fallo del producto:
**la búsqueda del servidor no ignoraba los acentos**, así que `garcia` devolvía
cero y `ibanez` no daba con Rocío Ibáñez. Con una plantilla española eso es la
mitad de los apellidos, y vale igual para los centros («Almacén») y los
departamentos («Jardinería»).

Lo tapaba el recorte que hace el navegador sobre la lista ya cargada, que sí los
ignora: mientras la respuesta anterior siguiera en pantalla, la encontraba
igual. Solo se veía cuando la lista llegaba antes de teclear. **En cuanto la
plantilla no cabe en una página deja de ser intermitente y pasa siempre**, que
es lo que lo hace serio.

Y el comentario de esa misma prueba, escrito por mí, afirmaba que el servidor
también los ignoraba. No lo comprobé al escribirlo.

**Vuelta 7 — Avisos push y correo. Nada en el área, y un fallo mío al salir.**

El área aguantó: los recordatorios de fichar, el aviso de jornada abierta y los
correos de decisión ya estaban bien montados. Faltaban tres casos por cubrir y
ahora están: que la ventana de silencio se mida en el reloj de cada persona ---a
las 21:30 de Madrid en Las Palmas son las 20:30, y callarse ahí es perder
justo el aviso que sirve---, que una jornada de noche todavía abierta pertenezca
a ayer y se recuerde por la mañana, y que el correo salga en el idioma de quien
lo recibe, que sale de cron y allí no hay idioma activo. Cada uno con su
contraste, porque un vacío sin caso conocido no prueba nada.

El hallazgo salió **releyendo el diff para comitear**, no probando: la plural
del aviso de demasiados intentos ---el que traduje en la vuelta 3--- tenía la
tercera forma vacía. El catálogo declara la regla de CLDR, `nplurals=3`, donde
la forma 1 es la de los millones y **la 2 es la corriente**: 1 usa la 0, un
millón la 1, y todo lo demás la 2. Rellené la 0 y la 1. Y gettext con una forma
vacía no cae al inglés: devuelve la cadena vacía. O sea que el mensaje se veía
en «1 minuto» y en blanco en «5 minutos», que es por donde se pasa al agotar el
cupo por hora.

Dos cosas que apuntar de aquí. Una, `msgfmt --statistics` **no lo ve**: contaba
615 mensajes traducidos con esa forma vacía dentro, así que la comprobación
limpia no valía. Dos, arreglar la entrada no impide que la siguiente plural
nazca igual, así que la prueba que queda lee las tres formas de cada plural del
catálogo entero.

**Vuelta 6 — La asistencia para integraciones, y dos de regalo.**

En el área: **el día salía de `date.today()`**, que es la fecha UTC del
contenedor. A las 00:30 de Madrid decía que era ayer mientras los tramos ya eran
de hoy --- la aplicación que pinta esto ponía la fecha de un día y los fichajes
de otro, y quien más lo cruza es el turno de noche, todas las madrugadas.
`apps/common/clock.py` existe justo por esta trampa y avisa de que ya se había
colado cuatro veces; esta era la quinta, y el último `date.today()` del código.
Había otro en el inspector de convenios, con menos daño (un convenio verificado
hoy se marcaba «con fecha futura» durante dos horas), corregido también.

**Fuera del área, de un uso real:** con la aplicación abierta y la sesión
caducada, `tokens.clear()` vaciaba el almacén y **React no se enteraba**. La
pantalla seguía puesta, su consulta seguía pidiendo cada minuto y cada una daba
401. Un 401 por minuto para siempre, sin arreglarse ni llevar a entrar. Ninguna
prueba lo cubría porque todas **navegaban**, y al navegar se revisa la sesión y
todo funciona: lo roto era quedarse quieto dentro. Validado revirtiendo el
arreglo.

**Y mirando una tanda con ventana:** dos pruebas fallaban solo así. Era un
**404 del favicon** --- que no existía. Chrome sin ventana no lo pide, de modo
que la suite entera estaba en verde mientras cada visita real se llevaba un 404
y una pestaña con el globo genérico. Hay `service worker`, así que además la
aplicación se podía instalar sin nombre y con un cuadrado en blanco. Añadidos
icono SVG, `.ico`, versiones con margen para Android y manifiesto, con pruebas
de que el manifiesto no promete ficheros que no están.

**Vuelta 5 — La integración de personas.** Dos fallos encadenados, y el segundo
solo aparece si se prueba el primero de verdad.

**La lectura masiva devolvía quinientas personas y no decía que hubiera más.**
Un conector de una empresa de seiscientas daba la plantilla por leída: las otras
cien no existían para él, ni sus altas ni sus bajas. Un recorte callado en una
integración es peor que en una pantalla, porque no hay nadie mirando que
sospeche. Ahora la respuesta trae `count`, `has_more` y `next_since`, y el
cursor es `updated_at`, que ya hacía falta para la lectura incremental.

**Y el cursor no funcionaba.** `next_since` sale con el huso pegado
---«…123456+00:00»--- y en una URL el `+` significa espacio: llegaba
«…123456 00:00», no parseaba, y la respuesta era un 409. Cualquier conector que
siguiera el cursor de la forma más obvia se quedaba con la primera tanda. Lo
cazó la prueba que recorre hasta el final en vez de comprobar solo que
`has_more` era cierto --- esa habría pasado con el cursor roto.

De paso: el endpoint salía en el esquema con la respuesta descrita como «un
objeto cualquiera». Quien escribiera el conector tenía que leerse el código o
adivinar, y adivinando no se descubre `has_more`. Ahora el esquema dice los
cuatro campos y explica cómo seguir el cursor, con el aviso de codificar el
`+`.

**Vuelta 4 — Fichaje delegado.** El área mejor construida de las cuatro
revisadas, y conviene decirlo: ya estaban cubiertos el aislamiento entre
empresas, los permisos, las credenciales revocadas, las referencias
desconocidas, que la delegación llegue al informe y que las credenciales no se
guarden en claro. El servidor sigue poniendo la hora aunque delegue el botón.

Un hallazgo: **`evidence` no tenía tope de tamaño**. Lo escribe una integración
desde fuera, con seis mil peticiones por hora de cupo, y esos fichajes viven
cuatro años y salen en cada informe. Un conector honesto que vuelque la traza
GPS entera en cada fichaje llena la base sin hacer nada prohibido. Ahora caben
cuatro mil caracteres, que es de sobra para lo que el campo existe ---unas
coordenadas, una red, el identificador de un evento--- con una prueba del
rechazo y otra de que lo normal sigue pasando: validar solo el rechazo dejaría
pasar un tope de cero.

Y siete casos que faltaban por cubrir, ahora en verde: pasar la tarjeta dos
veces en un lector ---el caso más común de una puerta, y el que antes dejaba la
jornada en cero---, el turno entero fichando en el mismo minuto sin estorbarse,
una referencia que señala a dos personas, quien está de baja, y que lo que
detectó el sensor llegue al registro con su prueba.

Un susto que no era: la línea `except User.DoesNotExist, ValidationError, ...`
sin paréntesis parece sintaxis de Python 2, y es válida en 3.14 (PEP 758).
Comprobado antes de «arreglarla».

**Vuelta 3 — La puerta.** Lo importante estaba bien y conviene decirlo, porque
marca dónde no volver: **no hay enumeración**. Recuperar la contraseña de una
cuenta que existe y de una que no da el mismo 204 con el mismo cuerpo, y entrar
da el mismo error se equivoque uno en el correo o en la contraseña. El backend
de autenticación además cifra una contraseña de mentira cuando la cuenta no
existe, para que el tiempo de respuesta tampoco lo delate, y está comentado. El
enlace de recuperación es de un solo uso por construcción ---sale del hash de la
contraseña--- y caduca en veinticuatro horas.

Lo que sí salió: **el aviso al agotar los cinco intentos por minuto era la
traducción automática de DRF**. «Solicitud fue regulada (throttled). Se espera
que esté disponible en 58 segundos.» Sin artículo, con una palabra en inglés
entre paréntesis, y lo lee quien acaba de fallar cinco veces la contraseña ---el
peor momento para pedirle que descifre nada---. Ahora dice «Demasiados intentos.
Vuelve a probar en 58 segundos», en minutos cuando pasa del minuto, y conserva
el plazo, que era lo único accionable del mensaje viejo.

Y uno pequeño de la misma familia que los de ayer: **el correo del enlace
prometía «24 horas» escritas a mano** mientras el plazo se configura por
entorno. Coincidían hoy; bajarlo a cuatro habría dejado el correo mintiendo.
Ahora sale del ajuste.

De paso, un fallo del banco de pruebas que un bucle destapa y una tanda suelta
no: **dos tandas seguidas se estrellaban**, porque la última prueba agota a
propósito el cupo de intentos y el arranque de sesiones lo comparte ---va por
IP---. Ahora el arranque espera lo que el propio aviso dice que falta. Validado
agotando el cupo a mano y lanzando la suite acto seguido: entra al minuto.

**Vuelta 2 — Resumen.** La tarjeta «esperando decisión» contaba dos de las
cinco colas ---ausencias y correcciones pendientes--- y se dejaba fuera las
propuestas sin contestar, que era la más grande: decía **2** habiendo **57**. No
es un número de adorno: es lo que decide si alguien entra en «Por decidir», y
entre lo que no contaba estaban las horas extra, con cuatro meses de plazo para
compensarse con descanso (art. 35.1).

Ahora suma las cuatro colas que se pueden contar barato y dice aparte que hay
horas extra, sin número: calcularlas cuesta medio segundo y esto se refresca
cada minuto. Un «hay» honesto antes que un número caro o un cero falso.

Contrastando la portada con las pestañas salió el segundo: **los contadores de
«Por decidir» venían de las filas recibidas, no del total**, y las colas de
correcciones llegan de cincuenta en cincuenta. La pestaña decía 50 habiendo 55,
y a las cinco que faltaban no se llegaba desde ninguna parte. Ahora el número
sale de `count` y una lista recortada lo dice. Cinco pruebas en
`e2e/16-resumen.spec.js`, todas comparando pantalla contra servidor y no contra
cifras escritas a mano.

De camino, y a raíz de mirar el `timetrack/` de Geosian: **la pantalla de fichar
tiraba el estado que el POST ya devuelve** y pedía un segundo GET. La guía de
Geosian lo dice con todas las letras ---«reutilizar `today_status` del 201, sin
segundo GET»--- y es el peor sitio para un viaje de más: la persona está delante
del botón esperando a ver si el fichaje entró.

**Vuelta 1 — Fichar.** Dos pulsaciones seguidas no creaban dos entradas: creaban
**una entrada y una salida**. Medido con milisegundo y medio entre ellas, el día
quedaba con cero segundos trabajados y en estado «fuera», y quien había pulsado
se iba convencido de haber fichado. Un doble toque en un móvil, una pantalla que
tarda y se vuelve a pulsar, o un cliente que reintenta: en una obra, con
guantes, es un martes.

Arreglado en `register_punch`, que es por donde entran también el terminal, la
aplicación y el conector --- el botón ya se desactivaba mientras la petición
viajaba, y eso no cubre ninguno de esos tres. Se rechaza en vez de ignorarse:
tragarse el segundo dejaría el registro bien y a la persona sin saber qué pasó.
Cinco segundos, y la ventana es por persona y por tipo de intervalo, así que un
terminal compartido con la plantilla entera en el mismo minuto sigue
funcionando. Cinco pruebas en `apps/punches/tests/test_double_tap.py`.

De paso: tres pruebas existentes se apoyaban en fichar dos veces seguidas y
ahora mueven el reloj con `freeze_time`, que es lo que pasa de verdad; y la
prueba de decidir en bloque estrena personas en cada pasada, porque aprobaba
ausencias que ya no se pueden cancelar e iba llenando el calendario hasta
chocar consigo misma.

Lo del 13/08/2026, antes de arrancar el bucle, está en
`tasks/revision-ux-2026-08-13.md` y `tasks/revision-legal-2026-08-13.md`.

## Descartado a propósito

- **El 10 % anual del art. 34.2.** «En defecto de pacto, la empresa podrá
  distribuir de manera irregular a lo largo del año el diez por ciento de la
  jornada.» No se calcula, y es una decisión, no un olvido.

  Dos motivos. Uno: el tope solo rige **en defecto de pacto**, y el producto no
  sabe si hay convenio o acuerdo de empresa que regule la distribución --- que es
  el caso normal. Enseñar «has usado el 40 % de tu margen» a una empresa cuyo
  convenio lo tiene pactado es decir algo falso con aire de dato.

  Dos: para medirlo haría falta la distribución **ordinaria** de la jornada
  contra la que comparar, y eso no está en el modelo: el cuadrante *es* la
  distribución. Habría que inventarse la referencia, y un porcentaje construido
  sobre una referencia inventada se lee como un hecho.

  Lo que sí se hace es la otra mitad del artículo, que es la comprobable: el
  preaviso. Si algún día se aborda, hace falta antes un sitio donde la empresa
  declare si tiene pacto, y ese sitio es el mismo que el de la consulta a la
  RLT.

- **Selección múltiple en Fichajes.** Un asiento del registro se corrige de uno
  en uno (art. 4.b). Hay una prueba que se pone roja si aparece una casilla.
- **«Aplicar sin acuerdo» en bloque.** Es la excepción del art. 4.b: en bloque
  dejaría de ser excepción. Retirar sí, aplicar no.
- **Impedir un descanso entre jornadas menor de 12 h.** El RD 1561/1995 lo baja
  en sectores concretos. Se avisa citando el artículo; no se impide.
- **Cancelar una ausencia ya aprobada.** El producto responde
  `already_resolved`. Queda anotado como pregunta de diseño en la revisión de
  UX, no como fallo.
