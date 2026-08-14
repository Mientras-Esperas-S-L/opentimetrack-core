# Auditoría continua — cuaderno

Vueltas dadas: 37 · Vueltas seguidas sin hallazgos: 0

El 14/08 Francisco cerró las cinco decisiones que estaban esperándole. Cuatro
están hechas y la quinta ---la capa de i18n del frontend--- está en marcha.

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
| Permisos (`/panel/permisos`) | limpia | 14/08 v23 | **no existía**: el catálogo no se podía editar desde ninguna pantalla |
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

- **La capa de i18n del frontend: DECIDIDO QUE SÍ (14/08), en marcha.** Las
  cadenas están escritas en castellano dentro del JSX. Con catalán elegido, una
  persona recibe en catalán los correos y los errores de la API, y sigue viendo
  «Fichar» y «Mi jornada» en castellano.

  Medido el 14/08, y es menos de lo que decía esta nota: **~460 cadenas**, no
  más de mil. Son 305 literales entrecomillados, 116 nodos de texto suelto en el
  JSX y 37 plantillas con interpolación, repartidas sobre todo en Ajustes (62),
  Personas (53) y Decisiones (37).

  Dos cosas que condicionan el montaje y ya están comprobadas:

  - MUI trae `caES` pero **no** `glES` ni `euES`. Para gallego hay que dejarle
    `esES`, o sus textos internos ---paginación, tablas--- saldrían en inglés,
    que es exactamente el fallo que ya se cazó en el backend.
  - La resolución del idioma **ya existe y es correcta**: `api.js` calcula
    `user.locale || tenant.language || navigator.language` y la manda en
    `Accept-Language`. Lo que falta no es decidir el idioma, es que las cadenas
    de React lo usen.

  Traducir bien 460 cadenas de prosa cuidada a catalán y gallego es trabajo de
  traductor, no mío. Lo que se entrega es la maquinaria montada de punta a
  punta y el catálogo extraído listo para pasárselo a alguien.

- **Los tres catálogos nuevos piden revisión nativa.** Catalán y gallego están
  completos en los 188 mensajes que llegan a las personas. El euskera va con 148
  y le faltan 35 párrafos largos de derecho laboral, que caen al castellano a
  propósito. La cabecera de cada `.po` lo dice en su idioma.

- **Tres exportaciones del cliente que nadie llama, y son decisiones abiertas.**
  El barrido al revés de la vuelta 18 dejó estas: `signUp` ---no hay pantalla de
  alta de empresa, así que un cliente nuevo solo se da de alta por API---,
  `createLeaveType` y `updateLeaveType` ---el catálogo no se puede editar, que ya
  estaba anotado--- y `getEmployee`, que probablemente sobra. Ninguna es un fallo
  por sí sola; las tres son «¿esto tenía que existir?».

- **Ejecutar las pruebas con ventana de vez en cuando.** El favicon ausente
  llevaba ahí desde siempre con la suite entera en verde: Chrome sin ventana no
  lo pide. Lo mismo puede pasar con tipografías, impresión o consultas de medios.

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

### Vuelta 37 --- Instalación desde cero (14/08)

Base de datos vacía de verdad, migrada de cero, y los primeros cinco minutos de
un cliente nuevo.

**Casi todo bien, y una parte con historia.** Los tres disparadores del rastro y
la extensión `unaccent` los pone la migración: aquel incidente en que faltaban
era del entorno, no del código. Sin deriva entre modelos y migraciones, y CI ya
lo comprueba.

El primer día funciona: se da de alta la empresa, recibe sus 32 permisos
sembrados y sus reglas con valores, `record-arrangement` dice honestamente que
no consta nada, y se puede fichar al momento. Ninguna pantalla revienta con cero
datos. Los festivos vienen vacíos y la pantalla lo dice con el camino para
traerlos.

**El hallazgo, pequeño y con causa interesante.** El catálogo de turnos paginaba
sin orden, y no por olvido: su modelo declara `ordering = ["name"]`. Lo que pasa
es que `annotate` con un agregado mete un `GROUP BY` y Django descarta la
ordenación por defecto en las consultas agregadas. La anotación se añadió para
decir cuántos días usan un turno antes de borrarlo y se llevó el orden por
delante. Sin orden, la página 2 puede repetir filas de la 1 y saltarse otras.

La prueba mira **el aviso de DRF** y no el código: buscar `order_by` en los
`get_queryset` habría dado limpio, porque el problema es lo que Django hace
después. Una de doce listas.

### Vuelta 36 --- Cómo escala con el tamaño de la plantilla (14/08)

Solo dos ficheros del proyecto medían consultas, y eran los dos arreglados esa
misma mañana. El resto de la API no tenía ninguna cobertura de esto, y un N+1 no
se ve nunca en desarrollo: con tres personas de prueba son doce consultas y con
doscientas son dos mil, sin ningún aviso entre medias.

Barrido de catorce endpoints con 3 personas y con 12. Trece planos y uno que
crecía: **`/api/shifts/review/`, de 40 consultas a 130**. Es la pantalla que un
responsable abre para ver qué incumple su cuadrante, así que la empresa grande
es justo la que más la necesita.

Dos N+1 en el mismo endpoint. Los festivos, preguntados por persona cuando
dependen solo del centro. Y las reducciones de jornada, preguntadas por persona
**y por semana**.

Queda en 11 consultas, con tres personas y con doce.

La prueba compara en vez de fijar un tope: un número máximo se sube cada vez que
molesta, y «no puede crecer con la plantilla» o se cumple o no.

### Vuelta 35 --- El contrato publicado contra la realidad (14/08)

El producto vende su API de integración como funcionalidad, así que el esquema
OpenAPI **es** contrato. Primera vuelta hecha con un abanico de agentes: siete
dimensiones en paralelo, cada hallazgo con un refutador que intentaba tumbarlo.
57 propuestos, 39 sostenidos. Lo mío por mi cuenta coincidió con una dimensión
entera; las otras seis encontraron cosas que yo no vi.

**Solo contaba el camino feliz.** 200, 201, 204 y poco más: ni un 400, ni un
403, ni un 409 en 119 operaciones, y ningún componente que dijera qué forma
tiene un error. El peor hueco es el 409, que es como este producto rechaza por
regla de negocio: sin documentarlo, un cliente razonable lo trata como fallo
transitorio y reintenta en bucle algo que nunca va a salir. Tampoco se decía que
hay un `code` estable con el que ramificar, así que la alternativa era comparar
mensajes traducidos.

Va como gancho de posprocesado: los códigos se derivan de la operación, así que
la vista 120 nace documentada. Me equivoqué leyendo `security` al revés y el
esquema salió declarando un 401 en la pantalla de entrar; hay prueba que lo fija.

**Cinco operaciones decían no llevar cuerpo y lo leían.** La grave: cerrar
sesión. Sin cuerpo no invalidaba nada **y devolvía 204**, así que un cliente
escrito leyendo el contrato daba la sesión por cerrada mientras el token de
refresco seguía valiendo una semana. Su propio docstring dice «signing out
actually signs out».

**Cinco decían devolver una cosa y devolvían otra.** Entrar, alta y poner
contraseña se publicaban «sin cuerpo» y devuelven los tokens ---la primera
llamada de cualquier integración, y el contrato ni nombraba `access`---.
`auth/me` decía `User` y devuelve `{user, tenant}`. Y `roster`, `calendar` y
`pending` prometían el sobre paginado devolviendo un array, más filtros
heredados que nunca aplican: pedir el cuadrante de una persona devolvía el de la
plantilla entera, en silencio y con la forma correcta.

**Los ámbitos, la parte que existe para integrar.** Los seis se publicaban sin
tipo ni valores, y ninguna operación decía cuál pide. Ahora salen del enrutador
y **por método**: leer una ficha pide `read:people` y borrarla `write:people`, y
publicar el atributo de la clase habría dicho que con permiso de lectura se
puede dar de baja a alguien.

Quedan sostenidos y sin hacer unos veinte hallazgos más, casi todos respuestas
declaradas como objeto libre (`/api/app/attendance/`, `/api/punches/today/`,
`/api/absences/balance/`, la emisión de credencial) y filtros sin documentar en
auditoría. Ninguno rompe nada hoy; todos hacen que quien integre tenga que leer
el código.

### Vuelta 34 --- Responsable contra administración (14/08) · SIN HALLAZGOS

El cuarto corte de permisos, y el único que no estaba barrido. El de aislamiento
cubría sin sesión, entre empresas, y operario contra responsable; faltaba
responsable contra administración, que es una distinción real y con
consecuencias ---emitir la credencial de una aplicación es repartir una llave a
los registros de la empresa entera---.

**Salió limpio.** Veintidós operaciones de administración correctamente negadas
a un responsable y catorce de las suyas que sigue pudiendo hacer.

Lo que queda no es un arreglo, es la guarda. Una vista nueva con la clase de
permiso equivocada no se ve mirando la pantalla, porque el menú ya oculta lo que
no toca ---y ocultar un enlace no es un permiso---. La tercera prueba deriva del
código las rutas con control de rol y exige que cada una esté nombrada, así que
olvidarse rompe la construcción en vez de pasar en silencio. Ya cazó una:
`applications/scopes/`.

Validada saboteando un permiso a propósito: cambiando `IsAdmin` por
`IsManagerOrAdmin` en las aplicaciones, el barrido lo canta al instante.

### Vuelta 33 --- Lo que pasa cuando la entrada no es la esperada (14/08)

Tres ejes en una vuelta, porque los tres preguntan lo mismo: qué hace el
producto cuando lo que llega no es lo que esperaba.

**Rutas de error.** Sonda con basura en cada campo real de cada serializador,
1296 peticiones. Tres 500, y los tres del mismo tipo: código que asume una
cadena y corre **antes** de que valide nadie.

El peor es `POST /api/auth/token/` con `{"email": 12}`: sin sesión, alcanzable
desde Internet, y dentro de la función que existe para registrar los intentos
fallidos ---la forma de un ataque---. En vez de la línea del registro salía una
traza, justo con la entrada que más se parece a uno.

Los otros dos: `source_for` en los fichajes, y `reassign` en los turnos, escrito
ese mismo día.

Método: la primera versión mandaba diccionarios genéricos y dio 71 «basuras
aceptadas» que no eran nada, porque casi ninguna clave coincidía con un campo
real. Sacar los campos del propio serializador es lo que la hizo encontrar algo,
y además la hace crecer sola.

**Datos extremos.** Nombres en su longitud máxima ---100 en un departamento, 120
en un centro, 255 en una empresa--- y sin espacios. Rompían **tres** pantallas:
Departamentos se salía 719 px en el móvil, Centros 675, y Ajustes 1435. Una
línea en el tema las arregla las tres, y la novena pantalla que se añada nace
arreglada.

**Concurrencia.** Ninguna transición de estado estaba protegida: todas miraban
la copia en memoria. Dos responsables a la vez dejaban una ausencia en
`REJECTED` **con `approved_by` puesto**, y el rastro con una aprobación y un
rechazo de la misma solicitud. Vivía en ausencias, correcciones y
recuperaciones. Las horas extra se dejan como están: se pueden redecidir por
diseño.

### Vuelta 32 --- Las cinco decisiones de Francisco (14/08)

Cuatro hechas en el día. La quinta, la capa de i18n, sigue en «Hallazgos
abiertos» porque está en marcha.

**Las horas de un turno de noche cuentan en el día en que empieza.** La otra
mitad del turno de noche: las marcas ya salían bien y la atribución seguía
partiendo por la medianoche, así que esas ocho horas no aparecían en ningún
día. Ni en el estado, ni en el informe, ni en las extras, ni en la
conciliación. La regla y sus artículos, en `apps/punches/workday.py`. Lo que
**no** sigue la regla y queda separado: la nocturnidad, que se cuenta por la
franja 22:00-06:00 vaya al día que vaya.

De regalo: sin día, «la jornada de ahora» ya no es «hoy». A las tres de la
madrugada, quien entró a las 22:00 veía «sin empezar» en su propia pantalla.

**El tope de horas abiertas pasa a ser de cada empresa.** `max_open_hours` en
`WorkingTimeRules`, dieciséis por defecto, con su campo en Ajustes y su prueba
de punta a punta. Lo pidió Francisco por las guardias de veinticuatro horas
---bomberos, residencias, vigilancia---, donde dieciséis parte la guardia por
la mitad.

**La IP sale del rastro de auditoría.** Chocaba con la inmutabilidad de la
tabla: los tres disparadores rechazan UPDATE y DELETE, así que no había forma
de borrarla ni para atender una solicitud del art. 17. Se va la columna, se va
la lógica que decidía a quién enseñársela, y se va el parámetro `request` de
`record()`, que solo estaba para sacarla ---33 llamadas dejan de pasarlo---.

**Los topes de cuota salen del Core.** Y aquí me equivoqué al levantarlos:
`max_employees` **no** estaba muerto, se comprobaba de verdad al dar de alta.
Eso empeora el caso: una instalación propia podía negarse a añadir empleados
con un mensaje que no venía de ningún contrato.

### Vuelta 31 --- El idioma no se activaba en ninguna petición (14/08)

Salió al ir a montar el i18n del frontend y preguntarme cómo se resuelve hoy el
idioma. `LocaleAndTimeZoneMiddleware` colgaba todo su cuerpo de
`request.user.is_authenticated`, y la API autentica por JWT, que DRF resuelve
dentro de la vista. El middleware ve `AnonymousUser` **siempre**: ni idioma ni
zona horaria se activaron nunca.

La clase de dos más arriba tiene el diagnóstico escrito ---«for those the tenant
is set again by the permission class»--- y esta, escrita justo debajo con la
misma forma, nunca recibió el mismo trato.

Debajo había un segundo fallo independiente: la mitad de la empresa leía
`company.settings["language"]`, clave de un JSON que nada escribe nunca, cuando
el idioma vive en `Tenant.language`.

No saltó antes porque la web manda `Accept-Language` por su cuenta. Se rompía
donde no hay navegador: correos, tareas de fondo, integraciones.

**El aviso metodológico vale más que el fallo.** Escribí la prueba con
`force_authenticate`, que deja el `request.user` de Django sin tocar. Fallaron
las dos mitades, también la que yo daba por buena, y eso fue lo que destapó el
problema de fondo. Una prueba hecha desde la interfaz habría dado verde.

### Vuelta 30 --- El zoom del navegador (14/08)

Al 200 % en un portátil de 1280 la página cree que mide 640: por encima de los
600 en que MUI pasa las filas a horizontal, y por debajo de lo que hace falta
para que quepan. Personas se salía 60 px por la derecha y el interruptor de
«ver también las bajas» quedaba fuera de la pantalla.

Se fabricaba su propia fila de filtros en vez de usar `FilterBar`, y la suya no
llevaba `flexWrap`. Es la segunda mitad de un fallo ya conocido: esa misma
pantalla también se fabricaba su propio buscador, y por eso se quedó sin nombre
accesible cuando el común lo recibió.

### Fuera de vuelta --- La baja sin fecha (14/08)

De una pregunta de Francisco: ¿qué pasa si alguien deja la empresa con el
cuadrante ya hecho? Sondeado antes de contestar: **nada**. Los turnos futuros
seguían asignados y la revisión no decía una palabra.

La baja ponía `is_active = False` y nada más. La comprobación del contrato se
salta a quien no tiene fechas, que es toda la plantilla indefinida. Y el
cuadrante es contra lo que se comparan los fichajes, así que quien se fue iba a
salir como ausencia sin justificar todos los días.

Lo que faltaba no era una comprobación sino **una fecha**: `is_active` es un sí
o un no sin día. Ahora la baja escribe el último día que la relación cubre y la
comprobación que ya existía funciona sola.

**Vuelta 29 — El teclado. Nada roto, y una lección de método.**

El eje que quedaba de accesibilidad. Foco visible, diálogos que lo atrapan y lo
devuelven al botón que los abrió, y se llega al botón de fichar tabulando. **La
primera vuelta sin hallazgos.**

Lo que costó fue medirlo. Tres sondas seguidas dijeron que el foco era invisible
---no hay `outline`, no hay `box-shadow`, y añadir `Mui-focusVisible` a mano no
cambia el fondo--- y las tres se equivocaban. Comparando **píxeles** se acabó en
un intento. Van cuatro falsos positivos en dos días, todos por mirar el DOM en
vez de mirar lo que se ve.

**Vuelta 28 — Fichar sin cobertura.**

El escenario de campo del producto. El service worker no guarda cola a propósito
---la hora de un fichaje no se decide en el navegador, y está escrito en él---,
así que sin red no se ficha: eso está bien decidido. Lo que estaba mal era lo
que se decía. El aviso salía **en inglés** y no decía lo único que hace falta
saber: que **no ha quedado nada**. Sin esa frase, quien está en una obra ve un
aviso genérico y se va convencido de haber fichado.

De rebote, **la inicial del avatar era casi invisible en tema claro**: 1.75 de
contraste. No lo vio el barrido de la vuelta 26 y no es culpa del barrido ---
depende del dato: con nadie fichado la lista está vacía y el avatar no existe.
Salió al repetir la prueba con otra gente en pantalla, que es el argumento para
dejarlas puestas en vez de pasarlas una vez.

Y una prueba que se había quedado vieja sin que nadie lo notara: comprobaba el
aviso que el paginador sustituyó en la vuelta 22, y pasaba porque con menos de
cincuenta propuestas tomaba la rama del «no debe aparecer».

**Vuelta 27 — El idioma, y la tercera promesa imposible.**

Dos hallazgos, y el segundo ya es un patrón.

**Los ajustes ofrecían ocho idiomas** y solo hay catálogo de castellano. Elegir
«Catalán» dejaba el producto en castellano sin decir nada. Lo que sí conviene
saber ---y que la sonda aclaró--- es que **no caen en inglés sino en castellano**,
porque `LANGUAGE_CODE` es `es`: o sea que el daño era la promesa, no el
resultado. Quedan los dos que funcionan.

Y la misma pantalla decía **«cada persona puede usar otro distinto»** con el
campo en el modelo, en la API, y sin ningún sitio donde elegirlo. Es la tercera
vez: antes fueron «se puede adjuntar después» (v17) y «usa los filtros de arriba
para llegar al resto» (v22). Tres textos escritos describiendo lo que el
producto *debería* poder hacer en vez de lo que hace.

**Vuelta 26 — El tema oscuro, que nadie había mirado.**

Otro eje sin recorrer, de los que quedaron nombrados en la vuelta anterior. El
conmutador lleva semanas puesto y el oscuro no lo había visto nadie.

Dos colores de estado por debajo del mínimo: el verde de «Aprobada» en **3.26**
de contraste y el terracota de «Aplicada sin acuerdo» en **3.24**, contra el 4.5
que pide la norma. Y justo en los distintivos que dicen en qué estado está algo,
que es para lo que se miran.

La causa es de una línea: `primary` se aclaraba en oscuro y los otros dos se
habían quedado con el color del claro.

Lo que más enseña: **el del terracota no lo vio el barrido**. Su estado no
aparecía en ninguna de las pantallas recorridas; lo vio la cuenta, al mirar por
qué fallaba el otro. Un barrido encuentra lo que se cruza en el camino; el resto
lo encuentra entender la causa y preguntarse quién más está en el mismo caso.

Comprobado además que el modo claro no empeoró, que es lo fácil de romper al
tocar una paleta.

**Vuelta 25 — El móvil, que es donde se ficha y donde nadie miraba.**

Toda la suite corría a ancho de escritorio. Fichar se hace con el teléfono en la
mano, en una obra o en un portal, y esa anchura no la ejercitaba nadie: la misma
forma que el favicon que solo se veía con ventana.

**El producto aguanta bien**, y conviene dejarlo escrito porque no era evidente:
ninguna pantalla se sale, los diálogos caben con sus botones dentro (326 de 390)
y el botón de fichar mide 255×64 en la mitad inferior, donde llega el pulgar. Los
mandos pequeños que salieron ---30 px el conmutador de tema, 26 el paginador---
están por encima del mínimo de 24 que pide la norma, aunque por debajo de lo
cómodo; cambiarlos es una decisión de diseño y no un arreglo.

El único fallo era **mío y de la vuelta anterior**: el buscador de Personas pasó
al componente compartido, que fijaba el ancho en vez de ponerle un tope. 380 px
más el borde en una pantalla de 390. Un día de vida.

Y de rebote, la razón de que la suite entera saliera en rojo dos veces esta
semana: con doscientas pruebas a cinco peticiones cada una, **la suite agota el
cupo por hora de la cuenta que usan todas**, y lo que se ve no es un límite sino
la pantalla de entrar en mitad de otra prueba. `dev.py` ya resolvía esto para
pytest y dejaba fuera el caso del navegador.

**Vuelta 24 — Barrido de nombres accesibles: cinco sitios.**

Salió del tropiezo de ayer: la prueba de Permisos clicaba el conmutador de tema
porque los dos botones se llamaban «Cambiar». Lo que confunde a un localizador
confunde igual a quien navega con lector de pantalla, así que se barrieron las
catorce pantallas.

**47 botones «Corregir»** en Fichajes, 19 «Editar» en Personas, 7 en Turnos, 6
en Departamentos, y 7 «Eliminar» --- donde peor sienta equivocarse. Ninguno decía
de qué fila era.

Y el **buscador compartido no tenía nombre**: un `placeholder` no es una
etiqueta, desaparece al escribir y hay lectores que no lo anuncian. Con dos
detalles que costaron: el `aria-label` va en `slotProps.htmlInput` ---puesto en
el `TextField`, MUI lo reenvía al div de fuera y la sonda lo seguía marcando
después de «arreglarlo»--- y **Personas se fabricaba su propio buscador**, así
que se quedó fuera del arreglo del componente común. Ahora usa el compartido y
hereda el botón de vaciar, que allí tampoco había.

Ningún mando estaba mudo, que era lo que más miedo daba.

La sonda se queda como prueba de las catorce pantallas, contrastada quitando el
`aria-label`: tres pantallas en rojo.

**Vuelta 23 — La pantalla de permisos, y el diseño que no servía sin ella.**

Existía todo lo demás: el modelo con sus unidades y periodos, la siembra por
país, el endpoint completo, y hasta `createLeaveType` y `updateLeaveType`
exportados en el cliente. No había pantalla --- así que la mejora que trae un
convenio solo se podía aplicar por API, y **la decisión de copiar el catálogo en
vez de leerlo del marco legal, tomada justo para permitir esa mejora, no servía
para nada**.

Es la cuarta de la familia «la pieza existe y nadie la llama», y la más cara:
las otras tres eran un hueco; esta dejaba sin efecto una decisión de diseño
entera.

Se edita cuánto da, no de qué artículo sale. Vacío en «cuánto da» significa sin
tope ---«el tiempo indispensable»--- porque mandar 0 sería inventarse un límite
de cero. Y retirar un permiso solo lo quita de las solicitudes nuevas: uno cuyo
motivo deja de renderizarse es un registro que perdió algo.

De paso, un fallo de accesibilidad de cosecha propia: el botón decía «Cambiar» a
secas, y treinta y dos «Cambiar» seguidos no le dicen nada a quien navega con
lector de pantalla. Salió porque la prueba clicaba el «Cambiar entre claro y
oscuro» de la cabecera --- `name` en Playwright casa por subcadena.

**Vuelta 22 — El paginador de «Por decidir», y era peor de lo anotado.**

El cuaderno decía «a las que faltan solo se llega filtrando». Mirándolo: **los
filtros son en cliente sobre lo ya cargado**, así que el aviso ---«se muestran 50
de 137, usa los filtros de arriba para llegar al resto»--- proponía algo que no
podía funcionar. A las 87 restantes no se llegaba desde ninguna parte, y el
mensaje hacía creer que sí. Peor que no decir nada.

Y son **dos** colas, no tres: las ausencias pendientes, las horas extra y las
recuperaciones son acciones que devuelven la cola entera. Eso salió de mirar el
backend en vez de fiarse de la nota de hace nueve vueltas.

La selección se vacía al cambiar de página, porque las acciones en bloque actúan
sobre lo que se ve y arrastrar marcas de una página que ya no está delante es
cómo se aprueba algo sin haberlo mirado.

De paso, la prueba del Resumen que me había mordido dos veces: comparaba una
foto de la API contra la pantalla de después, en una base donde otra prueba
resuelve colas en bloque. Ahora relee las dos cifras juntas hasta que coincidan
--- lo que busca es un truncado, y un truncado no se arregla mirando otra vez.

**Vuelta 21 — Las horas extra: de 1449 consultas a 5, y el número que faltaba.**

Medio segundo en una empresa de veinte, y esto lo pide la pantalla de decisiones
cada vez que se abre. Ahora 48 ms.

Tres causas, y la primera es la que enseña algo. **482 consultas pedían las
mismas reglas de la empresa**: `for_company` hace un `get_or_create` cada vez y
se llama desde dentro de los bucles. Es una función que parece barata ---devuelve
una fila--- y aparece en todas partes; ahí es donde se esconden estas cosas.
**243 volvían a pedir un turno que el bucle ya tenía en la mano.** Y **241
traían los fichajes de un día**, que ahora salen de una vez.

Con el cuidado de siempre: el día es el de **su** centro y no el de la empresa.

Y lo que se abre al arreglarlo: el Resumen ya cuenta las horas extra con número.
Iban aparte y sin cifra justo porque contarlas era caro, y quedarse fuera de la
cifra grande era el fallo de la vuelta 2 en pequeño. Debajo se dice cuántas de
ellas son horas extra, con su plazo de cuatro meses, porque no es lo mismo una
solicitud que espera respuesta que unas horas que caducan.

**Vuelta 20 — La asistencia, de 73 consultas a 2.**

Las dos familias de barrido de la vuelta 19 no dejaron nada más, y las de
seguridad ya estaban cubiertas ---la suite adversarial cubre escribir *y* leer lo
ajeno dentro de la empresa---, así que esta vuelta va al hallazgo de rendimiento
que quedaba abierto desde la 6.

Medido en la empresa de desarrollo, 19 personas: **73 consultas y 27 ms**, casi
cuatro por cabeza. Ahora **2 y 3 ms**, y ya no crece con la plantilla.

Tres cosas, y la tercera solo se ve contando el SQL. `build_day_status` cuesta
dos consultas y ahora se le pueden pasar hechas. Los fichajes del día salen en
una sola para todo el mundo. Y `person.tzinfo` mira el centro, pero **el centro
sin zona propia cae en su empresa**: con `select_related("workplace")` seguía
habiendo una consulta por persona, la de la empresa del centro. La cadena tenía
un eslabón más de los que parece, y eso no se lee, se cuenta.

Lo que más costó fue la prueba. La primera versión medía el ayudante con una
lista que ella misma se traía bien, así que el `select_related` de la vista ---lo
que se estaba arreglando--- no lo tocaba nadie: pasaba igual antes y después.
Medida por el endpoint sí se pone roja con el código de antes.

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
