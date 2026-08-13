# Auditoría continua — cuaderno

Vueltas dadas: 11 · Vueltas seguidas sin hallazgos: 0

El estado de cada área no es una opinión: «limpia» significa que se ejercitó
entera en una pasada y no salió nada. Mientras quede una «sin tocar», no se
vuelve a una limpia.

## Áreas

### Pantallas

| Área | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Fichar (`/`) | limpia | 13/08 v1 | **doble pulsación = jornada en cero** |
| Resumen (`/panel`) | limpia | 13/08 v2 | **decía 2 de 57 esperando decisión** |
| Mi jornada (`/mi-jornada`) | a medias | 13/08 | interruptor de recordatorios; falta el mes y «Pedir una corrección» |
| Mis ausencias (`/mis-ausencias`) | a medias | 13/08 | filtros; falta el diálogo de «Solicitar» |
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
| Art. 34.2 — distribución irregular del 10 % | sin tocar | — | «solo citado» en la revisión del 13/08 |
| Art. 34.3/34.4 — jornada, descansos | limpia | 13/08 | avisos con cita |
| Art. 35 — horas extra y su tope | limpia | 13/08 | — |
| Art. 36 — nocturno y turnos | a medias | 13/08 | falta la fecha de la evaluación de salud |
| Art. 37.1/37.2 — descanso semanal y festivos | limpia | 13/08 | — |
| Art. 37.3 — permisos retribuidos | limpia | 13/08 v11 | **una empresa nueva se quedaba sin un solo permiso**; el catálogo cuadra con el articulado |
| Art. 38 — vacaciones y recuperación | limpia | 13/08 | — |
| Art. 4.b — consentimiento de las dos partes | limpia | 13/08 | — |
| Constancia de la consulta a la RLT | sin tocar | — | «ausente» en la revisión del 13/08 |
| Calendario con dos meses de antelación (38.3) | limpia | 13/08 v9 | **estaba solo citado**; ahora se avisa, y solo cuando las pone la empresa |
| RGPD / art. 88 LOPDGDD | a medias | 13/08 | IP ajena cerrada; falta repasar la purga de metadatos |

## Hallazgos abiertos

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

- **Selección múltiple en Fichajes.** Un asiento del registro se corrige de uno
  en uno (art. 4.b). Hay una prueba que se pone roja si aparece una casilla.
- **«Aplicar sin acuerdo» en bloque.** Es la excepción del art. 4.b: en bloque
  dejaría de ser excepción. Retirar sí, aplicar no.
- **Impedir un descanso entre jornadas menor de 12 h.** El RD 1561/1995 lo baja
  en sectores concretos. Se avisa citando el artículo; no se impide.
- **Cancelar una ausencia ya aprobada.** El producto responde
  `already_resolved`. Queda anotado como pregunta de diseño en la revisión de
  UX, no como fallo.
