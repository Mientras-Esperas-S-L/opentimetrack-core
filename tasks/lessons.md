# Lecciones

Patrones que me han costado un error. Escritos para no repetirlos.

## Comprobar la CI entera antes de empujar, no fichero a fichero

**12/08/2026.** Estuve empujando a main con la CI en rojo sin enterarme, hasta
que llegaron las notificaciones al móvil. Dos causas y las dos evitables.

`ruff format` lo ejecuté sobre los ficheros que había tocado, uno a uno. El
paso de la CI es `ruff format --check .` sobre todo el árbol, y bastó con
olvidar dos ficheros.

**Antes de cada push, correr la secuencia completa tal y como está en
`.github/workflows/ci.yml`**, no una aproximación. Y **comprobar que termina**,
que es la mitad que se me olvidó la segunda vez:

```
set -e
ruff check .                                        && echo "1/5 lint OK"
ruff format --check .                               && echo "2/5 formato OK"
python manage.py makemigrations --check --dry-run   && echo "3/5 migraciones OK"
pytest -q                                           && echo "4/5 pruebas OK"
python manage.py spectacular --fail-on-warn --file /dev/null && echo "5/5 esquema OK"
echo "=== COMPLETADA ==="
```

El `set -e` y el contador no son adorno. La vez que volví a romper la CI fue
encadenando con `&&` y leyendo «458 passed» como éxito: el paso de migraciones
venía después, había fallado, y la cadena se cortó ahí sin que la ausencia de
salida me llamara la atención. **Un paso que no imprime nada no es un paso que
pasó.**

Y el fallo concreto, por si vuelve: cambiar un `help_text` genera migración.
Forma parte de la deconstrucción del campo aunque no toque el esquema.

## Un paso de CI que nunca ha pasado no es un paso de CI

El job de frontend hacía `npm ci` sin que existiera ningún lockfile, ni en el
repositorio ni en disco: llevaba fallando desde el principio, 26 de los 30
últimos runs. El del esquema OpenAPI tampoco había pasado nunca, porque el job
moría antes en el formato.

**Un rojo permanente enseña a ignorar el rojo.** Si un paso lleva fallando
desde siempre, o se arregla o se quita; dejarlo puesto es peor que no tenerlo,
porque cuando falle de verdad nadie lo va a mirar.

Y al mirar por qué falla algo, comprobar **desde cuándo**: `gh run list`. Tres
de los cuatro avisos del esquema eran anteriores a lo que yo había tocado, y
haberlo dado por supuesto me habría llevado a buscarlos en mi propio cambio.

## `set -e` no basta cuando hay tubería (12/08/2026)

`podman exec ... | grep -v "graph driver"` devuelve el código de salida del
**grep**, no el del comando. Con `set -e` puesto y todo, un `KeyError` en la
semilla pasó por delante sin abortar nada, y solo se notó porque la comprobación
de después no imprimió nada.

Es la misma familia que la de encadenar con `&&` y leer «458 passed» como éxito.

**Regla:** `set -eo pipefail` siempre que haya una tubería. Y cuando un paso
imprime cero líneas donde debería imprimir algo, eso **es** el fallo: no seguir
adelante a ver si el siguiente sale bien.

## Insertar algo justo antes de un símbolo deja su comentario huérfano (13/08/2026)

Me ha pasado cuatro veces en la misma sesión, tres en Python y una en JSX.
Escribo una clase o una función nueva y la coloco delante de otra que **ya
tenía encima un decorador o su docstring**. El texto no viaja: se queda pegado
a lo nuevo y lo de siempre se queda desnudo.

En Python es peor porque el decorador *se aplica*:
`@extend_schema` sobre la clase equivocada tumbó 75 tests con un
`AttributeError` que no menciona ni el decorador ni la clase original. En JSX
solo miente la documentación —dos comentarios describiendo un componente que no
es el suyo—, y por eso pasa el lint y llega al commit.

**Regla:** antes de insertar en un fichero, mirar la línea inmediatamente
anterior al punto de inserción. Si es `@decorador`, `*/`, o un comentario, el
sitio correcto está **antes** de ese bloque, no después. Y al terminar, releer
las diez líneas de alrededor del hueco: es el único sitio donde vive este fallo.

## Una prueba que ensucia la base compartida se vuelve verde por el motivo equivocado (13/08/2026)

Tres veces en una tarde, y cada una tardó más en verse que la anterior.

Una prueba de Ajustes puso el descanso entre jornadas en 8 h y **lo guardó**.
La pasada siguiente leyó ese 8 como «lo normal», lo restauró al terminar y se
puso verde: la comprobación seguía ejecutándose y ya no comprobaba nada. Lo
mismo con una ausencia de diciembre que sobrevivió a una prueba caída y hacía
fallar a la siguiente con «ya hay una ausencia registrada» —el rojo apuntaba a
donde no era—, y con 31 turnos de diciembre que hicieron que otra prueba cazara
«un sábado con turno» que no acababa de crear.

**Regla:** limpiar **antes** de crear, no solo después. Limpiar al final es lo
primero que uno escribe y no sirve, porque la prueba que se cae a mitad no
llega. Y nunca leer el valor de partida para restaurarlo: se escribe a mano el
que debe quedar. Si una prueba necesita un mes vacío, lo vacía ella al empezar.

## El asterisco de un campo obligatorio desaparece al rellenarlo (13/08/2026)

`getByLabel('A quién *')` dejó de encontrar el campo en cuanto se elegía a
alguien, porque MUI quita el asterisco cuando el campo deja de ser obligatorio.
Localizadores rotos sin que nada se hubiera roto.

**Regla:** localizar por rol y nombre parcial —`getByRole('combobox', { name:
/A quién/ })`— y no por el rótulo literal. Vale también para los plurales que
cambian con el contador y para los nombres de clase de MUI.

## Escuchar la consola encuentra más fallos que abrir la pantalla (13/08/2026)

De los fallos que aparecieron probando a mano, tres ya estaban gritando en la
consola: el `undefined` del cuadrante, las dos personas con la misma clave de
React, y la consulta de permisos que devolvía indefinido. Ninguno se veía sin
mirar ahí.

**Regla:** en toda prueba de pantalla, un `console.error` es un fallo. Y la
lista de excepciones se mantiene corta y con el motivo escrito al lado: una
consola con ruido de fondo es una consola que nadie mira.

## `[object Object]` dentro de una expresión regular es una clase de caracteres (13/08/2026)

`new RegExp('\\b[object Object]\\b')` casa con cualquier letra suelta de la
pantalla. Veintinueve pantallas en rojo de golpe, todas por el fallo de la
prueba.

**Regla:** veintinueve fallos a la vez no son veintinueve fallos. Antes de leer
el primero como real, comprobar que la prueba no esté rota.

## Una cabecera que el servidor manda no es una cabecera que el navegador deje leer (13/08/2026)

Segunda vez esta semana, y las dos veces tardé en verlo porque **el servidor
hacía lo correcto**. `Content-Disposition` viajaba con su nombre bien puesto y
el JavaScript no lo veía: CORS solo expone unas pocas cabeceras salvo que el
servidor liste las demás en `Access-Control-Expose-Headers`. Sin ella, la
pantalla se inventaba el nombre del fichero, y para la entrega de toda la
empresa ---un zip--- se lo inventaba mal: `informe.pdf` que no abría nada.

La anterior fue `Date`, y produjo un desfase de un segundo en el reloj.

**Regla:** cuando el frontend no ve algo que el servidor manda, mirar
`CORS_EXPOSE_HEADERS` **antes** de buscar el fallo en el frontend. Y probar las
descargas por sus **bytes**, no por su extensión: comprobar que el nombre acaba
en `.pdf` habría estado en verde todo el tiempo que estuvo roto.

## Antes de escribir un mecanismo, buscar si ya está (13/08/2026)

Escribí a mano la selección múltiple de Personas ---estado, casillas, barra de
acciones, ejecutor en serie--- y luego resultó que existía entero y mejor
pensado en `hooks/useSelection.js`, `components/selection.jsx` y
`services/bulk.js`, usado por «Por decidir». El mío perdía la poda de lo que
desaparece de la lista, que es justo lo que evita actuar sobre una fila ya
resuelta.

**Regla:** antes de escribir un mecanismo transversal ---selección, filtros,
paginación, formato, errores--- buscar por su función en `components/`, `hooks/`
y `services/`. Y si la pantalla que lo va a usar se parece a otra, mirar esa
otra primero.

## Una prueba que no se puede deshacer tiene que estrenar datos (13/08/2026)

La prueba de aprobar ausencias en bloque dejaba rastro **por diseño**: una
ausencia aprobada no se puede cancelar, y hace bien el producto —una decisión
tomada no se deshace borrándola—. Con la plantilla de demostración eso significa
ir ocupando el calendario hasta que una pasada choca con lo que dejó otra, y el
rojo apunta a donde no es.

Fechas «únicas» derivadas del reloj no lo arreglan: reducen la probabilidad y la
convierten en intermitente, que es peor.

**Regla:** si una prueba hace algo irreversible, que lo haga sobre datos que ella
misma crea. Con una persona nueva no hay con qué chocar: estrena calendario.
Vale para ausencias aprobadas, para fichajes y para todo lo que el producto se
niega a borrar a propósito.

## Un contador que sale de las filas recibidas miente en cuanto hay paginación (13/08/2026)

Las pestañas de «Por decidir» contaban `rows.length` y las colas llegan de
cincuenta en cincuenta: decían 50 habiendo 55, y a las cinco que faltaban no se
llegaba desde ninguna parte. El mismo día, la portada del panel sumaba dos de
las cinco colas y decía 2 habiendo 57.

Los dos fallos son el mismo: **un número que la gente usa para decidir si entra
a mirar, calculado a la baja y en silencio**. Una cola que la pantalla da por
vacía es una cola que nadie abre, y aquí eso tiene plazos legales detrás.

**Regla:** un contador sale de `count`, nunca de la longitud de la página. Y una
cifra que resume varias fuentes se comprueba contra la suma de esas fuentes, no
contra un número escrito en la prueba —que envejece y acaba desactivándose—.
Cuando dos pantallas cuentan lo mismo, hay que hacerlas discutir.

## Un banco de pruebas que no se puede ejecutar dos veces seguidas está roto (13/08/2026)

La prueba que comprueba el límite de intentos lo agota a propósito, y el límite
va por dirección IP: el mismo que usa el arranque de sesiones. Una tanda pasaba;
dos seguidas dejaban la segunda en rojo desde el primer paso, con un error que
señalaba al arranque y no a la causa.

Una suite suelta no lo enseña. Un bucle sí, y a la primera vuelta.

**Regla:** si una prueba consume un recurso compartido y limitado —cupos de
peticiones, direcciones de correo únicas, fechas ocupadas—, lo que lo consume y
lo que lo necesita tienen que ponerse de acuerdo. Aquí el arranque espera lo que
el propio aviso dice que falta. Y se valida como todo: agotando el recurso a
mano y volviendo a lanzar.

## Lo que parece un error puede ser sintaxis nueva (13/08/2026)

`except User.DoesNotExist, ValidationError, ValueError, TypeError:` sin
paréntesis es un error de sintaxis en Python 3… hasta 3.14, que lo permite
(PEP 758). Este proyecto va en 3.14. Estuve a un paso de «arreglar» código
correcto con toda la confianza del mundo.

**Regla:** antes de corregir algo que parece roto, comprobar que lo esté.
`ast.parse` y un import valen dos segundos. Y vale para todo lo que «sabes» de
una versión del lenguaje o de una biblioteca: lo que era cierto hace dos años
puede no serlo.

## Un tope se valida por los dos lados (13/08/2026)

Al poner un límite al tamaño de `evidence`, la prueba obvia es que un valor
enorme se rechace. Esa prueba también pasa con el límite puesto a cero, y
entonces nadie puede adjuntar nada.

**Regla:** todo límite lleva dos pruebas, la que rechaza lo que sobra y la que
acepta lo normal. Vale igual para validaciones, filtros y permisos: comprobar
solo que algo se niega no demuestra que lo demás funcione.

## Una respuesta que se corta tiene que decirlo, y el modo de seguir tiene que probarse recorriéndolo (13/08/2026)

La lectura masiva de la integración devolvía quinientas personas de seiscientas
y ni una palabra. En una pantalla alguien acaba sospechando; en una integración
no hay nadie mirando, y el conector se queda con media plantilla para siempre.

Al añadir `has_more` y `next_since` apareció el segundo fallo: el `+` del huso
horario viaja como espacio en una URL, así que la segunda llamada del cursor
daba 409. La prueba que lo cazó fue la que **recorre hasta el final y cuenta a
todo el mundo**; una que solo comprobara `has_more === true` habría pasado con
el cursor completamente roto.

**Regla:** cuando una respuesta se pueda cortar, decirlo en la propia respuesta
—`count` y `has_more`, no en la documentación—. Y probar la continuación
recorriéndola hasta el final, no comprobando que la primera página anuncia que
hay más. Vale para paginación, para cursores y para cualquier «y hay más».

## Sin ventana no se ve todo (13/08/2026)

Dos pruebas fallaban con `--headed` y pasaban sin ventana. La causa: **Chrome
sin ventana no pide el favicon**, y el favicon no existía. La suite entera
llevaba semanas en verde mientras cada visita real se llevaba un 404 y una
pestaña con el globo genérico.

Es una categoría, no un caso: lo que solo hace un navegador de verdad —favicon,
manifiesto, tipografías, impresión, consultas de medios, permisos— no aparece en
una tanda sin ventana por mucho que se mire la consola.

**Regla:** de vez en cuando, mirar una tanda con `--headed` y a cámara lenta
(`OTT_SLOW_MO=400`). Y para lo que el navegador no pide en las pruebas, pedirlo
a mano: comprobar que el recurso responde 200, y que un manifiesto no nombre
ficheros que no están.

## Una prueba que navega no prueba quedarse quieto (13/08/2026)

Con la sesión caducada, la aplicación se quedaba dando 401 cada minuto sin
recuperarse ni llevar a entrar. Había tres pruebas de sesión y ninguna lo
cazaba, porque **todas navegaban** —y al navegar se vuelve a comprobar la sesión
y todo funciona—. El caso roto era el más normal: tener la pantalla abierta y no
tocar nada.

**Regla:** para cualquier estado que cambie solo con el tiempo (sesión, datos que
se refrescan, avisos), probar también **sin navegar**: romper lo que haga falta
en el sitio y dejar que actúe el refresco, como le pasa a quien tiene la pestaña
abierta.

## Una plural a medio traducir se ve en blanco, no en inglés (13/08/2026)

Traduje el aviso de demasiados intentos, rellené `msgstr[0]` y `msgstr[1]`, y
dejé `msgstr[2]` vacío. El catálogo declara la regla plural de CLDR
—`nplurals=3`—, donde **la forma 1 es la de los millones y la 2 la corriente**:
1 usa la 0, un millón la 1, y todo lo demás la 2. Es decir: rellené la del
singular y la de los millones, y dejé sin traducir la única que se usa.

Dos cosas que lo hacían invisible. Una, gettext con una forma vacía **no cae al
inglés**: devuelve la cadena vacía, así que el error se veía sin texto en vez de
verse en otro idioma. Dos, `msgfmt --statistics` lo daba por bueno —«615
mensajes traducidos»— con la forma vacía dentro: es un vacío que se comprueba
limpio.

**Regla:** al tocar una plural, leer la cabecera `Plural-Forms` y rellenar
**todas** las formas que declara, sin suponer que son singular y plural. Y
comprobarlo ejecutándola con varios números (1, 2, 5), no leyendo el `.po`.
La comprobación general vive en `apps/common/tests/test_exceptions.py`.

## Una prueba intermitente es un fallo hasta que se demuestre lo contrario (13/08/2026)

`busca sin acentos` fallaba una vez de cada tantas en la tanda entera y pasaba
al ejecutarla sola. La lectura fácil es «prueba frágil, le pongo una espera».
Era un fallo del producto: **la búsqueda del servidor no ignoraba los acentos**,
`?search=garcia` devolvía cero, y con una plantilla española eso es la mitad de
los apellidos.

Lo que lo hacía intermitente es justo lo que lo hacía grave. El navegador
recorta la lista ya cargada por su cuenta y **eso** sí ignora los acentos: si la
respuesta anterior seguía en pantalla, lo tapaba. Solo se veía cuando la lista
llegaba antes de teclear. Y en cuanto la plantilla no cabe en una página, lo que
no esté en la página cargada solo lo puede encontrar el servidor: entonces pasa
siempre.

**Regla:** ante una intermitente, preguntar primero **qué condición la hace
fallar** y si esa condición se da más a menudo en producción que en la tanda.
«Pasa cuando la respuesta del servidor llega a tiempo» no es ruido: es el caso
normal de un usuario. Solo después de descartar el producto se toca la prueba.

Y el corolario, que es el que me pilló: **el comentario de esa prueba, escrito
por mí, afirmaba que el servidor también ignoraba los acentos.** Nunca lo
comprobé. Una afirmación en un comentario no es una comprobación; si merece
estar escrita, merece un `assert`.

## Correr la CI entera también cuando «solo» se comitea (13/08/2026)

Comiteando siete vueltas de trabajo pasé las comprobaciones completas y salieron
dos cosas que llevaban tiempo rotas y que nadie había visto: el paso del esquema
fallaba **desde que entró la API de integración** —`--fail-on-warn` con dos
avisos— y `npm run lint` daba 739 errores en local, todos del informe HTML de
Playwright, que eslint entraba a leer.

Los dos escondidos por el mismo motivo: **el sitio donde se rompe no es el sitio
donde se mira**. El esquema solo se rompía en la CI, y las ramas no se habían
empujado; el lint solo en local, porque en la CI el checkout está limpio y ese
directorio no existe.

**Regla:** antes de empujar, correr la secuencia entera de los dos lados
—backend y frontend—, aunque el trabajo de la sesión no los tocara. Y al
encontrar un fallo así, comprobar si venía de antes poniendo el fichero de
entonces: cambia lo que hay que arreglar y evita buscar en el sitio equivocado.

## Una URL relativa en una prueba de navegador no llega a la API (13/08/2026)

`fetch('/api/...')` desde una página servida por Vite en el 3000 no llega al
backend del 8000: se la queda el servidor de desarrollo y **devuelve el
index.html con un 200**. La comprobación era «pedir el informe de otra persona
da 400» y pasaba sin comprobar nada, porque recibía un 200 de HTML.

Lo cazó que el 200 no cuadraba con lo que yo esperaba. Si hubiera escrito
`expect(status).not.toBe(200)` —o si el producto llegara a devolver 200 de
verdad— habría quedado en verde para siempre.

**Regla:** en las pruebas de navegador, pedir siempre por el ayudante `api()` de
`e2e/apoyo.js`, que apunta al servidor de la API con URL absoluta. Y cuando una
respuesta sorprenda, mirar el **cuerpo** antes que el código: un HTML donde
debería haber JSON dice a quién se le preguntó de verdad.

## Lo que solo pasa en el alta no lo prueba nadie (13/08/2026)

Una empresa recién dada de alta se quedaba con **cero** permisos: nadie podía
pedir un matrimonio ni un fallecimiento. Llevaba así desde siempre y ninguna
prueba lo veía, porque **todas parten de la base sembrada** por el comando de
demostración —que sí llama a la siembra—. En desarrollo funcionaba; en una
empresa real, no.

Es la forma más cara de estar roto, porque parece que está bien. Y tenía la
pista delante: `seedLeaveTypes` estaba exportado en el frontend y **no lo
llamaba nadie**.

**Regla:** para cualquier cosa que solo ocurra una vez —el alta de una empresa,
la primera persona, el primer fichaje— escribir la prueba que **arranca desde
cero**, no desde el estado sembrado. Y cuando aparezca una función exportada
que no llama nadie, no darla por muerta: preguntar quién debería llamarla.

## Un ajuste que no lee nadie es peor que no tenerlo (13/08/2026)

`roster_notice_days` estaba en el modelo, en el marco legal con su cita del art.
34.2 y en la pantalla de ajustes, editable. **Ningún código lo leía.** Quien lo
configuraba se quedaba convencido de que el producto vigilaba el preaviso.

Ya había pasado igual con los `search_fields`: declarados en cuatro vistas con
el `SearchFilter` sin activar, así que el buscador respondía con la plantilla
entera. Y con los `throttle_scope`. Es un patrón, no una casualidad: se añade la
configuración primero, se deja el código para después, y el «después» no deja
rastro de que falta.

**Regla:** al encontrar un ajuste, un campo o un flag, buscar **quién lo lee**
antes de darlo por hecho —`grep` del nombre, y si solo sale en el modelo, la
migración, el serializador y la pantalla, no lo lee nadie—. Y al añadir un
ajuste nuevo, escribir en la misma tanda la prueba que lo cambia y comprueba que
el comportamiento cambia.

## Medir el ruido antes de soltar un aviso nuevo (13/08/2026)

El aviso de preaviso, tal y como lo escribí primero, daba **128 hallazgos** en un
mes de datos reales: el segundo grupo más grande, por delante de todo lo que
importaba. De esos, 94 eran turnos anotados *después* del día —rellenar el
cuadrante de la semana pasada—, que no son un problema de preaviso.

Un aviso que sale 128 veces no se lee: entierra los tres que iban en serio. Y
eso no se ve leyendo el código, solo contando.

**Regla:** antes de dar por bueno un aviso nuevo, ejecutarlo contra los datos de
desarrollo y **contar por código**. Si es de los grandes, mirar caso por caso
qué lo dispara: normalmente hay una clase entera que no debería contar.

## Congelar el reloj y preguntar por «hoy» fuera del bloque (14/08/2026)

Tres pruebas se pusieron rojas al pasar de las doce de la noche, y las tres por
lo mismo: congelaban el reloj para fichar y luego comprobaban el estado del día
**fuera** del `with freeze_time`, donde «hoy» es el día real. Pasaban todo el día
que se escribieron y caducaban esa noche.

La tercera era peor y no la había escrito yo: ponía una ausencia con
`date.today()` —la fecha **UTC** del contenedor— mientras el producto mira el día
de la empresa. Entre medianoche y las dos de la madrugada en Madrid no coinciden,
así que la ausencia caía en el día anterior. Es la trampa que `apps/common/clock.py`
documenta, **dentro de una prueba**, donde ese aviso no lo lee nadie.

**Regla:** si una prueba congela el reloj, todo lo que pregunte por «hoy» va
dentro del mismo bloque. Y en pruebas, `date.today()` está igual de prohibido que
en el producto: `local_today(empresa)`.

## Una traducción `fuzzy` sale en inglés y el fichero dice que está (14/08/2026)

Cambié el texto de un error existente, `makemessages` marcó la entrada `fuzzy`
con la traducción vieja, y ese mensaje salió en inglés en `main` durante dos
vueltas de auditoría. El `.po` parecía completo y `msgfmt --statistics` contaba
la entrada como traducida: solo la marca lo delataba.

Y las adivinanzas de `makemessages` son malas por construcción: «collective
agreement» salió como «Aplicada con acuerdo».

**Regla:** después de `makemessages`, `grep -c '^#, fuzzy'` y revisar **todas**.
Hay una prueba que lo hace en `apps/common/tests/test_exceptions.py`; si se toca
un texto ya traducido, es la que avisa.

## Una garantía que solo vive en una migración se puede evaporar (14/08/2026)

El rastro de auditoría es *append-only* por tres triggers de PostgreSQL. La
migración figuraba aplicada, su función existía, y **los triggers no estaban en
la base**: se podía editar y borrar el rastro sin que nada chistara.

Lo que más enseña es cómo apareció: la **prueba** rechazaba el UPDATE y la base
de desarrollo lo aceptaba. Las pruebas corren sus migraciones desde cero y ven
siempre los triggers, así que eran el único sitio donde este fallo no podía
salir. Una prueba verde era, aquí, la prueba de nada.

**Regla:** lo que vive en el esquema y no en el código —triggers, restricciones,
extensiones, índices parciales— hay que **preguntárselo a la base que está
sirviendo**, no a la de las pruebas. En OTT eso es `/api/health/`, que responde
503 si faltan. Y toda garantía de ese tipo necesita su comando de reparación: sin
él, avisar solo sirve para asustar.

## «Hoy» no vale para quien trabaja de noche (14/08/2026)

El fallo más grave de la auditoría: quien entra a las 22:00 y sale a las 06:00
recibía **dos entradas y ninguna salida**, porque la deducción del tipo miraba
los fichajes del **día local** y al salir el día nuevo estaba vacío. La jornada
no se cerraba nunca y el día quedaba en cero horas.

La misma raíz mordía en la guarda de las pausas, en la reconciliación y en el
informe. Cuatro sitios, un solo supuesto: *una jornada cabe dentro de un día de
calendario*. Para el turno de noche es falso, y el turno de noche no es un caso
raro --- es una industria entera.

**Regla:** en cualquier cálculo sobre jornadas, preguntarse qué pasa si el tramo
**cruza la medianoche** antes de dar el código por bueno. Y al escribir la
prueba, hacerla con un turno de noche de verdad (22:00 → 06:00), no con una
jornada de mañana: una prueba de nueve a cinco nunca verá esta familia de fallos.

Lo encontré de rebote, escribiendo una prueba de otra cosa. Eso también dice
algo: cubrir un caso legal poco frecuente obliga a montar datos poco frecuentes,
y ahí es donde aparecen los fallos que las pruebas cómodas no tocan.

## La base de desarrollo es de todos, y la rompo yo (14/08/2026)

Dos veces en la misma vuelta, y las dos estaban ya escritas aquí arriba.

Una prueba nueva creaba fichajes con **dos POST seguidos**; la protección del
doble toque ---que puse yo en la vuelta 1--- rechazó el segundo, la jornada quedó
abierta y Ana apareció fichada. Dieciséis pruebas de otros ficheros, que miran
contadores en vivo, en rojo.

Y varios sondeos por consola dejaron **ocho empresas de mentira** donde debe
haber tres. Setenta y cuatro pruebas en rojo, y media hora buscando una
regresión inexistente.

**Regla:** un sondeo por consola que crea datos se limpia **en el mismo script**,
con `try/finally`, no «luego». Y una prueba de navegador prefiere **buscar** un
dato que existe ---retroceder de mes hasta encontrar fichajes--- antes que crear
uno: lo que se crea hay que deshacerlo, y en este producto casi nada se deshace.
Antes de dar por buena una tanda en rojo, mirar si la base tiene basura mía:
`Tenant.objects.all()` deben ser tres.

## «La pieza existe y nadie la llama», tres veces en siete vueltas (14/08/2026)

- El **catálogo de permisos** se sembraba con un endpoint que ninguna pantalla
  invocaba: toda empresa nueva se quedaba con cero permisos (vuelta 11).
- **`roster_notice_days`** vivía en el modelo, en el marco legal y en Ajustes, y
  no lo leía ni una línea de código (vuelta 12).
- El **justificante** tenía campo, validadores, distintivo en la lista y endpoint
  de descarga con su control de acceso probado. Nadie lo subía (vuelta 17).

Las tres se ven igual: la mitad difícil está bien hecha, y falta el hilo que la
conecta. Y las tres pasan desapercibidas porque **lo que hay funciona**: lo que
falla es lo que no está.

**Regla:** al auditar un área, hacer la búsqueda al revés. Coger lo que el
backend ofrece —endpoints, campos del serializador, ajustes— y preguntar **quién
lo llama** desde el frontend. `grep` del nombre en `src/`: si solo aparece en
`services/api.js`, está exportado y muerto. Es una comprobación de dos minutos
que ha encontrado tres fallos de producto.

## Un acento grave en `git commit -m "..."` se lo come el shell (14/08/2026)

En zsh, dentro de comillas dobles, `` `algo` `` es sustitución de comandos: el
shell intenta ejecutarlo y deja un hueco en el mensaje. Un commit de esta sesión
quedó con «los demás sitios que acotan están bien:  con USE_TZ convierte…», sin
el nombre del campo y con la frase coja. Se vio porque zsh además escupió
`command not found`, pero si el nombre hubiera coincidido con un comando real
---`date`, `test`, `time`--- habría entrado su salida en el mensaje sin avisar de
nada.

**Regla:** los mensajes de commit con nombres de código van por fichero
(`git commit -F`) o con heredoc en comillas simples. Escapar `\`` funciona pero
se olvida a la tercera.

## Un barrido que acusa a todos no es un barrido (14/08/2026)

La primera versión del barrido de «ajustes que nadie lee» dio **todos muertos**,
incluidos `weekly_hours` y `daily_rest_hours`, que se leen por todas partes. La
causa: `grep -oP` sobre varios ficheros antepone el nombre del fichero a cada
resultado, así que el nombre del campo llevaba pegado `apps/tenants/rules.py:`.

Lo delató que el resultado era absurdo. Si el fallo hubiera afectado solo a la
mitad, me lo habría creído.

**Regla:** un barrido se calibra antes de creérselo, con **los dos extremos**:
que algo conocido-vivo salga como vivo y algo conocido-muerto salga como muerto.
Es el mismo principio que validar una comprobación limpia contra un caso
positivo, y cuesta lo mismo: nada.

## Una prueba de rendimiento que se trae los datos bien no prueba nada (14/08/2026)

Midiendo el arreglo de la asistencia, la primera prueba llamaba al ayudante
pasándole una lista de personas que **ella misma** había traído con el
`select_related` correcto. El arreglo estaba en la **vista**, no en el ayudante,
así que la prueba pasaba idéntica antes y después: verde con el código roto.

Se vio al contrastar ---revertir y ver si se pone roja---, que es lo que hago con
las de comportamiento y no se me había ocurrido hacer con una de coste.

**Regla:** una prueba de consultas se hace **por donde entra la petición**, no
por la función interna: el `select_related`, el `prefetch` y el `only` viven en
la vista y una prueba que los reconstruye por su cuenta mide su propio código. Y
contrastarla igual que las demás: revertir el arreglo y comprobar que se queja.
Además, afirmar **que no crece** (dos tamaños distintos) en vez de un número
mágico, que solo dice algo si no cambia al crecer.

## Las funciones que parecen baratas son las que hay que contar (14/08/2026)

`WorkingTimeRules.for_company(company)` devuelve una fila y se llama desde
dentro de los bucles. En una lectura de horas extra pendientes se ejecutaba
**482 veces** con el mismo argumento: un `get_or_create` cada vez. Es más de la
mitad de las 1449 consultas de esa página.

No se ve leyendo el código, porque en el sitio donde está la llamada es
razonable. Se ve agrupando el SQL por sentencia y mirando el número de la
izquierda.

**Regla:** al mirar el coste de una pantalla, agrupar las consultas por texto y
ordenar por repeticiones. Lo que salga arriba casi nunca es la consulta gorda que
uno sospechaba: es una barata llamada muchas veces. Y para arreglarla, recordarla
en un objeto que viva lo que la petición ---la propia empresa--- en vez de montar
una caché con invalidación, que trae más problemas de los que quita.

## Un aviso que propone una salida que no existe es peor que no avisar (14/08/2026)

«Se muestran 50 de 137. Usa los filtros de arriba para llegar al resto.» Los
filtros son en cliente sobre las cincuenta ya cargadas, así que seguir el consejo
no podía funcionar. Quien leyera el aviso se iba convencido de que había forma de
llegar, y la buscaba.

Escribí ese mensaje yo, en la vuelta 2, al arreglar el contador truncado. Arreglé
la mitad ---decir que faltaban--- y me inventé la otra.

**Regla:** cuando un aviso dice cómo salir del problema, seguir esa instrucción
literalmente antes de darla por buena. Si el remedio está en otra pantalla o en
otro mecanismo, comprobar que ese mecanismo hace lo que uno cree: aquí bastaba
con filtrar y ver que el total no cambiaba.

Y la nota del cuaderno decía «las tres colas paginadas». Son dos: las otras
devuelven la cola entera. Una nota de hace nueve vueltas se comprueba antes de
trabajar sobre ella.

## `getByRole(name)` casa por subcadena (14/08/2026)

`page.getByRole('button', { name: 'Cambiar' })` también acierta al «Cambiar entre
claro y oscuro» de la cabecera. El clic se iba al conmutador de tema, no se abría
ningún diálogo, y la prueba fallaba en la línea siguiente diciendo que no
encontraba un texto --- que es el sitio equivocado para buscar la causa.

Lo bueno es lo que enseña del **producto**: un rótulo que choca con otro para el
localizador choca igual para quien navega con lector de pantalla. Treinta y dos
botones «Cambiar» en una lista no dicen cuál es cuál. La solución es la misma
para los dos: `aria-label` con el nombre de la fila.

**Regla:** un rótulo de botón que se repite en la pantalla, o que es un verbo
suelto, pide un nombre accesible con su contexto. Y en las pruebas, `exact: true`
o un texto que no pueda ser prefijo de otro.

## Un arreglo de accesibilidad hay que verlo en el DOM, no darlo por hecho (14/08/2026)

Puse `aria-label` en el `TextField` del buscador y la sonda lo seguía marcando:
MUI reenvía las props sueltas al **div de fuera**, no al `input`. Va en
`slotProps.htmlInput`. Sin volver a mirar, habría dado por arreglado algo que no
lo estaba --- y la siguiente vez que alguien lo revisara vería el `aria-label` en
el código y pensaría lo mismo.

Y el segundo: el componente compartido ya estaba bien y **Personas se fabricaba
el suyo**, así que la pantalla más usada se quedó fuera del arreglo. Arreglar un
componente común no arregla a quien no lo usa.

**Regla:** después de tocar accesibilidad, comprobarlo **en el navegador**
---`getAttribute('aria-label')` sobre el elemento real--- y buscar quién más hace
lo mismo a mano en vez de usar el componente compartido: `grep` del
`placeholder`, del rótulo o del icono.

## Una anchura que nadie prueba es una anchura que está rota (14/08/2026)

La suite entera corría a ancho de escritorio, y el producto se usa **de pie, con
el móvil**. Barriendo a 390 px salió un desborde, y era de un cambio del día
anterior: un `width` fijo donde antes había un `maxWidth`.

Un día de vida. Sin el barrido habría llegado a producción y se habría visto
como «la lista de personas tiene una barra rara abajo».

**Regla:** lo mismo que con la ventana. Hay ejes que ninguna prueba recorre por
defecto ---anchura, idioma, zona horaria, tema oscuro, impresión--- y en cada uno
cabe una familia de fallos entera. Cuando se descubra uno, la prueba se queda: un
barrido que encontró algo una vez encuentra la regresión la próxima.

Y el corolario del que menos me acordaba: `width` en un `sx` de MUI es una
medida, no un tope. Para que encoja hace falta `width: '100%'` con `maxWidth`.

## Un barrido encuentra lo que se cruza; la causa encuentra el resto (14/08/2026)

Barriendo el contraste en tema oscuro salió **un** color flojo: el verde de
«Aprobada», 3.26. Al mirar por qué, la causa era que `success` no se aclaraba en
oscuro mientras `primary` sí. La pregunta siguiente ---«¿quién más está en ese
caso?»--- destapó el segundo, `secondary` en 3.24, que el barrido **no había
visto** porque su estado no aparecía en ninguna de las diez pantallas recorridas.

Un barrido solo ve lo que se cruza. Lo que estaba en la pantalla número once
sigue ahí.

**Regla:** cuando un barrido devuelva un hallazgo, no arreglarlo y seguir.
Entender **por qué** ocurre y buscar a mano quién más comparte esa causa: suele
ser una lista corta y suele tener a alguien más dentro.

## Los textos de la interfaz se comprueban como el código (14/08/2026)

Tres veces en diez vueltas, un texto ha prometido algo que no existía:

- «Se muestran 50 de 137. **Usa los filtros de arriba** para llegar al resto» ---
  los filtros son en cliente sobre lo cargado (v22).
- «Este permiso pide justificante. **Se puede adjuntar después**» --- no se podía
  ni antes ni después (v17).
- «Idioma. **Cada persona puede usar otro distinto**» --- el campo existía y no
  había dónde elegirlo (v27).

Las tres las escribí describiendo lo que el producto **debería** poder hacer, en
el momento de arreglar la mitad de al lado. Y las tres sobrevivieron porque un
texto no lo comprueba nadie: no falla, no sale en la consola, no rompe una
prueba.

**Regla:** cualquier frase de la interfaz que afirme una capacidad ---«se puede»,
«usa», «cada uno», «después»--- es una aserción. Se comprueba haciéndola:
seguirla literalmente, o escribir la prueba que la ejerce. Si al escribirla uno
descubre que no hay por dónde, ese es el hallazgo.

## No todos los mensajes de un catálogo valen lo mismo (14/08/2026)

Traducir los 627 mensajes a tres idiomas eran ~85.000 caracteres. Separándolos
por dónde nacen resultó que **188 llegan de verdad a una persona** ---vistas,
servicios, correos--- y 343 son etiquetas de modelo que solo se ven en el admin
de Django y en el esquema de la API. Traducir los 188 es el 30 % del trabajo y
casi todo el valor.

Lo que hace viable esa decisión es un detalle que había que **comprobar y no
suponer**: lo no traducido cae al idioma por defecto del proyecto ---castellano,
por `LANGUAGE_CODE`--- y no al inglés de los `msgid`. Si cayera al inglés, medio
catálogo sin traducir daría un producto en dos idiomas extranjeros y la única
salida honesta sería traducirlo entero.

**Regla:** antes de estimar una traducción, separar los mensajes por dónde
aparecen y comprobar a qué idioma cae lo que falta. Las dos cosas cambian el
tamaño del trabajo por un factor de tres.

## Para saber si algo se ve, mirar los píxeles (14/08/2026)

Cuatro falsos positivos en dos días, todos de la misma familia: preguntarle al
DOM por algo que es una pregunta visual.

- «El buscador no tiene etiqueta» --- la tenía, pero MUI la pone en un sitio que
  mi consulta no miraba.
- «El foco no se ve» --- tres sondas distintas: sin `outline`, sin `box-shadow`,
  y añadir `Mui-focusVisible` a mano no cambia nada. Se ve.

Y el que sí acertó, el de contraste, funcionó porque calculaba el color efectivo
subiendo por los padres, no porque leyera una propiedad.

**Regla:** «¿se ve X?» se responde con una captura antes y otra después, y
`Buffer.compare`. Cuesta lo mismo que la consulta al DOM y no depende de saber
cómo lo pinta la biblioteca. Y si no se puede construir el contraste ---apagar X
y ver la prueba en rojo---, al menos validar el instrumento: dos capturas del
mismo estado tienen que salir idénticas.

## Una migración creada no es una migración aplicada (14/08/2026)

Añadí `max_open_hours` y quité tres columnas. Las pruebas siguieron en verde ---830 de
830--- porque pytest levanta su propia base de datos y la migra entera cada vez. La de
desarrollo se quedó atrás, y la aplicación empezó a devolver 500 en `/api/overview/` con
un `column ... does not exist`. Me enteré porque Francisco me pegó el log.

Es primo del envenenamiento de la base compartida que ya tengo apuntado, pero por el otro
lado: allí dejaba datos malos, aquí dejo el esquema viejo. Y es más traicionero, porque el
verde de la suite es exactamente la señal que te hace pensar que has terminado.

**Regla**: `makemigrations` y `migrate` van juntos en la misma tanda de comandos. Si en una
vuelta se toca un modelo, la comprobación final no es «pasan las pruebas», es «pasan las
pruebas **y** la aplicación de desarrollo responde». Un `curl` a un endpoint que use lo
tocado cuesta un segundo y ve lo que la suite no puede ver.

## Quitar un campo es buscarlo por todas sus salidas, no por una (14/08/2026)

Quité `ip_address` del rastro de auditoría. Escribí una prueba que comprobaba dos cosas
---que la columna no está en la tabla y que el JSON de la API no la sirve--- y hasta puse
en su docstring que se comprobaba «por las dos puntas porque son dos formas distintas de
que vuelva». Verde. 838 pruebas verdes.

Y el CSV que se descarga seguía llamando a la función que había borrado, así que la
descarga del registro devolvía un 500. Lo cazó una prueba de punta a punta que se quedó
esperando un fichero que no llegaba nunca.

El fichero no pasa por el serializador: se escribe a mano, columna a columna. O sea que
comprobar el serializador no dice **nada** de él. Lo tenía escrito y no lo hice.

**Regla**: antes de quitar un campo, `grep` de su nombre **y del de las funciones que lo
resolvían**, y de ahí sale la lista de salidas que hay que comprobar. Aquí eran tres:
tabla, JSON y CSV. Escribir «por las dos puntas» en un docstring no es haber mirado las
puntas que hay.

## Instalar en el host no es instalar en el contenedor (14/08/2026)

`npm install i18next` en el host, y Vite ---que corre en el contenedor con su propio
`/app/node_modules`--- devolviendo «Failed to resolve import». La pantalla de entrar dejó
de pintarse y tres de las cuatro sesiones de las pruebas siguieron pasando porque
reutilizaban su testigo guardado: solo fallaba la que entraba de verdad, que es la señal
más fácil de leer como «cosa rara de esa prueba».

Y con la dependencia ya instalada dentro seguía fallando: Vite cachea el prebundle y con
dependencias nuevas hace falta reiniciar el servicio.

**Regla**: dependencia nueva del frontend = `podman compose exec web npm install` **y**
`podman compose restart web`. Y si una prueba de sesión falla sola mientras las demás
pasan, mirar el log del contenedor antes de mirar la prueba.

## Una prueba que crea gente en la base compartida tiene que devolverla como estaba (14/08/2026)

Tercera vez que envenenó la base de desarrollo, y la tercera de una forma distinta.

La prueba de cobertura creaba una persona con correo único por tanda, le ponía un turno,
la daba de baja, y al terminar solo borraba el turno. Como **dar de baja no borra** ---que
es la promesa del producto y está bien--- no hay forma de quitarla por API. A las nueve
tandas había nueve personas de baja con `contract_end` de hoy, y empezaron a fallar dos
pruebas de otros ficheros que contaban filas.

Lo que lo hizo difícil de leer: las que fallaban no eran las mías, y cambiaban de una
ejecución a otra.

Y la limpieza que escribí para arreglarlo tampoco servía: llamaba a
`POST /employees/{id}/reactivate/`, una ruta que **no existe** ---reactivar es un
`PATCH {is_active: true}`---. El ayudante `api` de las pruebas no comprueba el código, así
que el 404 se lo tragaba en silencio y la prueba seguía pasando mientras dejaba a la
persona de baja.

**Regla**: identidad fija y no una por tanda ---se reutiliza y se devuelve a su estado---
y la limpieza **se comprueba**: `expect(vuelta.status).toBe(200)`. Una limpieza que no
verifica su resultado es una limpieza que no sabes si ocurre. Y antes de dar por buena una
tanda, mirar si ha dejado filas: `first_name='...'` cuenta en un segundo.

## Una sonda que no acierta con los nombres reales no está probando nada (14/08/2026)

Primera versión del barrido de entradas malformadas: diccionarios genéricos
---`{"employee": None, "name": [], "day": {...}}`--- contra los 46 endpoints de
escritura. 411 peticiones, y **71 «basuras aceptadas»** que parecían un hallazgo.

No lo eran. Casi ninguna de esas claves era un campo real del endpoint que la recibía, así
que DRF las ignoraba como ignora cualquier campo desconocido. Lo que medía la sonda era
que DRF hace lo que tiene que hacer.

La segunda versión saca los campos **del propio serializador** con `get_fields()`. 1296
peticiones, y aparecieron tres 500 que la primera no vio ---uno de ellos en la pantalla de
entrar, sin sesión---.

**Regla**: una sonda que dispara a ciegas necesita demostrar que acertó. El histograma de
códigos es la forma barata: si no hay cientos de 400, no está llegando a la validación.
Y donde se pueda, los objetivos se sacan del código en vez de escribirlos a mano, que
además hace que la prueba crezca sola.

## El estado de un objeto en memoria no protege de nada (14/08/2026)

Todas las decisiones del producto comprobaban lo mismo antes de escribir: que el objeto
siguiera pendiente. Y lo comprobaban sobre la instancia que la petición había cargado, que
por definición es de **antes** de que nadie escribiera.

Dos responsables pulsando a la vez pasaban los dos. Sobre una ausencia el resultado no era
un duplicado sino algo peor: `REJECTED` con `approved_by` puesto, una fila que se
contradice, y el rastro con las dos decisiones.

**Regla**: si una operación solo puede ocurrir una vez, el estado se relee **bloqueando la
fila** dentro de la transacción, y se trabaja con lo releído. `if objeto.status == X` es
una comprobación de cortesía, no una garantía.

Y el corolario que me pilló: al poner el bloqueo, se rompió una función que fingía el
estado en memoria (`correction.status = PENDING  # so approve_correction accepts it`) para
colarse por la comprobación. Ese truco solo funciona mientras nadie relea. Que se rompa al
arreglar la carrera es la señal de que el arreglo llega al sitio correcto.

## Nada de regex sobre estructuras multilínea de Python (14/08/2026)

Tres veces en la misma sesión. Un `re.sub` sobre decoradores apilados se comió la clase
`AbsenceViewSet` entera; otro dejó `@extend_schema(tags=["auth"])` colgando sobre un
serializador en vez de sobre su vista, y el contenedor se quedó caído hasta que Francisco
me pegó el log ---el recargador de Django **no vuelve solo** de un error de importación en
`urls.py`---. Antes, un script de limpieza de paréntesis rompió trece ficheros.

El patrón: los decoradores, los bloques `class` y las llamadas multilínea no son texto
plano, y un `.*?` con `re.S` se come lo que no debe sin avisar.

**Regla**: para tocar estructura de Python, Read + Edit con el bloque exacto. El regex vale
para líneas sueltas e independientes (un import, una línea `assert`), y ahí hay que
comprobar el número de coincidencias antes de escribir. Y después de tocar `views.py` o
`urls.py`, un `curl` al `/api/health/`: la suite pasa con su propia base y no ve que el
servidor de desarrollo está muerto.

## Un abanico de agentes ve lo que uno no mira (14/08/2026)

En la vuelta del esquema hice mi propia lectura y encontré una cosa: que solo se
documentaba el camino feliz. Lancé además siete agentes, uno por dimensión, cada hallazgo
con un refutador que partía de que estaba mal.

Mi hallazgo coincidió con una de las siete dimensiones. Las otras seis encontraron cosas
que yo no habría mirado: que cinco operaciones declaran «sin cuerpo» y leen el cuerpo ---una
de ellas cerrar sesión, devolviendo 204 sin invalidar nada--- y que tres listas prometen el
sobre paginado devolviendo un array.

Y el refutador ganó su sitio: de 57 propuestos tumbó 18, y varios de los que sostuvo vinieron
con correcciones a las citas del que los propuso.

**Regla**: para auditar algo con varias dimensiones independientes ---un esquema, una
superficie de permisos, una maquetación--- el abanico paga. Lo que NO se delega es la
verificación de lo que sobrevive: los tres que arreglé primero los comprobé yo en el código
antes de tocar nada, y uno venía con la ruta mal citada.

## Una sonda con la ventana corta esconde justo lo que buscas (14/08/2026)

Buscando N+1 monté una sonda con una ventana de cinco días. Encontró uno ---los festivos,
preguntados por persona--- y lo arreglé. Después arreglé un segundo sitio que también olía
a N+1, lo medí, **no quitaba ninguna consulta**, y estuve a punto de revertirlo por peso
muerto.

No lo era. `_check_weekly_hours` se salta las semanas incompletas a propósito, así que con
cinco días su cuerpo no se ejecuta nunca. Con una ventana de un mes, ese segundo N+1 son
diez consultas por persona: 40 contra 130.

O sea que la sonda no medía el endpoint, medía una rama del endpoint. Y el error se
disfrazaba de lo contrario: parecía que mi arreglo sobraba.

**Regla**: los datos de una sonda de rendimiento tienen que cruzar los límites del dominio
que el código mira ---semanas completas, meses, cambios de mes--- o hay código que no se
ejecuta. Y antes de revertir un arreglo por «no mide nada», comprobar que la medición llega
hasta él: poner un `print` en la función supuestamente cara cuesta un minuto y evita
deshacer algo correcto.

## `annotate` se lleva por delante el `Meta.ordering` (14/08/2026)

El catálogo de turnos paginaba sin orden. Mi primera lectura fue «se les olvidó el
`order_by`», y el modelo declaraba `ordering = ["name"]`.

`annotate` con un agregado mete un `GROUP BY`, y Django **descarta la ordenación por
defecto** en las consultas agregadas. La anotación se añadió para poder decir cuántos días
usan un turno antes de borrarlo, y se llevó el orden con ella. La única señal era un
`UnorderedObjectListWarning` que no se ve porque nada convierte los avisos en fallos.

Sin orden, PostgreSQL no promete nada entre páginas: la 2 puede repetir filas de la 1 y
saltarse otras. Silencioso, y solo con más de cincuenta filas.

**Regla**: un `annotate` con agregado sobre un modelo con `Meta.ordering` necesita
`order_by` explícito. Y para buscar esta clase de fallo hay que mirar **el aviso en
ejecución**, no el código: `grep order_by` da limpio porque lo que falla es lo que Django
hace después.

## Comprobar que algo se manda no es comprobar qué pone (14/08/2026)

El correo de invitación saludaba «Hola :» desde siempre. Había pruebas de ese envío: que
se manda, a quién, y que no se manda dos veces. Ninguna miraba **el cuerpo**.

La causa era `{{ user.first_name }}` dentro de un `{% blocktranslate %}`, que no resuelve
accesos a atributos y deja el hueco vacío. No avisa: la plantilla renderiza, el correo
sale, y quien lo recibe lee su nombre en blanco.

Es el primer mensaje que ve un empleado nuevo, y llevaba ahí desde el principio.

**Regla**: de todo lo que se genera para una persona ---correos, PDF, CSV--- hay que
comprobar el contenido y no solo que se produce. Y donde haya plantillas, renderizarlas al
menos una vez en las pruebas: una plantilla que nunca se renderiza es código que nunca se
ejecuta.

## Cuatro veces con la misma piedra: nada de regex sobre Python (14/08/2026)

Ya me lo apunté esta mañana y hoy he vuelto a romper `corrections.py` dos veces más con
sustituciones de cadena sobre bloques multilínea: la primera dejó un `with` con dos
espacios de indentación, la segunda dejó código huérfano tras reemplazar solo la cabecera
de una llamada.

Lo que funciona: `sed -n` para **leer** el bloque exacto, y Edit con el `old_string`
completo. Cuesta una llamada más y no rompe nada. La regla ya estaba escrita; el fallo fue
no seguirla cuando tenía prisa.

## Si no puedes leer lo que generas, no lo estás comprobando (14/08/2026)

El PDF del informe de jornada ---el documento que se le entrega a una inspección--- tenía
una prueba que comprobaba que empieza por `%PDF-` y que pesa más de mil bytes. Nada más,
porque en el proyecto no había con qué abrir un PDF.

Al añadir `pypdf` y leerlo, salieron tres cosas que el código calculaba y ningún
renderizador imprimía, incluida la discrepancia del art. 4.b: una corrección impuesta
sobre la objeción de la persona salía idéntica a una aceptada.

La forma de la prueba **decidió** lo que se podía encontrar. Mientras la única
comprobación posible fuera «es un PDF», el contenido podía ser cualquier cosa.

**Regla**: si el producto genera un formato que las pruebas no saben leer, añadir la
dependencia que lo lea es parte de probarlo, no un lujo. Vale para PDF, para ZIP, para
imágenes. Y el coste es de dependencia de desarrollo, que es el más barato que hay.

## Lo que un renderizador ignora no lo dice nadie (14/08/2026)

`DayRow` tenía `disputed`, `dissent`, `break_seconds` y `standby_seconds`. Se calculaban
en `build_report`, se totalizaban en `ReportData`, y **ninguno de los dos formatos los
imprimía**. No hay error, no hay aviso: los campos existen, tienen el valor correcto, y se
caen por el borde al pintar.

Es primo del patrón que ya llevo cinco veces apuntado ---«la pieza existe y nadie la
llama»--- con una variante: aquí la pieza se calcula y se tira.

**Regla**: para un objeto que se serializa a un documento, comparar los campos que tiene
con los que el renderizador lee. `grep` del nombre del campo en el fichero del
renderizador cuesta un minuto y da la lista de lo que se está tirando. Y si hay dos
formatos, comprobar que dicen lo mismo: aquí los dos ignoraban lo mismo, así que
compararlos entre ellos tampoco lo habría cazado.

## Un `test.skip` condicional puede esconder que la prueba no prueba nada (14/08/2026)

La prueba de «otro llegó antes» empezaba con
`test.skip(!(await boton.count()), 'no hay nada pendiente en esta base')`. Se ejecutó tres
veces seguidas, salió verde las tres, y no comprobó nada: la cola estaba vacía y el skip
se lo tragaba en silencio.

Peor todavía cuando le añadí el montaje del dato: la prueba **creaba** su solicitud y
seguía saltando, porque contaba el botón antes de que la página terminara de recargar. El
skip convertía un fallo de sincronización en un verde.

**Regla**: un `skip` condicional solo vale cuando la condición es del entorno y no del
caso ---un navegador que no existe, una función del sistema que falta---. Si la prueba
monta sus propios datos, la ausencia de lo que espera es un fallo y hay que esperarlo con
`toBeVisible()`. Y un `skip` que se dispara siempre es indistinguible de una prueba
borrada: si la salida dice «skipped», hay que ir a mirar por qué.

## Enseñar el error no siempre es responder al error (14/08/2026)

Todas las mutaciones del frontend hacían `onError: setError`, y para casi todos los
rechazos eso está bien: el servidor dice qué falta y la lista sigue siendo verdad.

Pero unos pocos códigos significan otra cosa: **alguien llegó antes**. Ahí el mensaje solo
es la mitad, porque la fila sigue en pantalla y la persona vuelve a pulsar. La interfaz
tiene que enseñar el mensaje **y** volver a pedir los datos.

**Regla**: al mirar el manejo de errores de una interfaz, separar los que hablan de *lo que
enviaste* de los que hablan de *lo que ya no es cierto*. Los primeros se enseñan; los
segundos se enseñan y se refrescan. Y refrescar en todos es la solución perezosa que se
paga en cada error de validación.

## Valida el instrumento antes de creerte el barrido (14/08/2026)

En una sola vuelta, cuatro sondas seguidas me dieron resultados falsos:

- Un regex para extraer cuerpos de `test(...)` cortaba por la llave equivocada y dijo que
  **166 de 166** pruebas no tenían aserciones.
- El siguiente enganchaba el `({ page })` del parámetro en vez del cuerpo, con el mismo
  resultado.
- El patrón `expect(` no veía `expect.poll(`, y marcó como vacía una prueba que sí afirma.
- Una aserción mía daba por hecho que `User.objects` filtra por la empresa en contexto.
  No lo hace, está documentado por qué, y casi lo reporto como fuga de aislamiento.

Ninguno costó nada arreglarlo. Lo que habría costado caro es haberme creído el primero: un
informe diciendo «la suite entera no comprueba nada» habría sido una mentira con mucha
autoridad.

**Regla**: antes de leer los resultados de un barrido, pásalo por un caso cuya respuesta ya
conoces y comprueba que la da bien. Dos líneas:

    assert "expect(" in cuerpos["una prueba que sé que afirma"], "el instrumento está roto"
    assert total > 500, "no está recorriendo lo que cree"

Y el corolario: cuando un barrido da un número extremo ---todo o nada--- la primera
hipótesis es que el instrumento está mal, no que el código lo esté.

## Una aserción dentro de un `if` que hoy es falso es una aserción que no existe (14/08/2026)

Escribí `if esperado_ca != esperado_es:` alrededor de dos comprobaciones, con un comentario
honesto explicando que el catálogo catalán todavía no traducía esos mensajes y que «si el
catálogo se completa mañana, esta prueba empieza a distinguir sola».

Suena razonable y es falso en la práctica: nadie vuelve. La prueba pasaba en verde sin
ejecutar ni una de sus dos aserciones, y el comentario le daba coartada.

La salida no era escribir mejor la condición: era **quitar la razón de que existiera** —
traducir los dos mensajes, que era lo que el producto necesitaba de todas formas. Después,
la aserción es firme y su contraste lo demuestra.

**Regla**: si te descubres condicionando una aserción a que el producto esté completo,
completa el producto. Y si de verdad no se puede hoy, `pytest.xfail` con motivo, que sale
en el informe; un `if` silencioso, no.

## El `tail -4` de un informe largo se come justo lo que importa (14/08/2026)

Lancé la tanda E2E completa de fondo y leí el final con `tail -4`. Decía «245 passed»
y me lo creí. El resumen entero decía **243 passed, 6 failed**: las líneas de fallo
van *antes* del recuento, y las corté yo.

No es un descuido de teclas: es la misma familia que «un vacío no es prueba de
ausencia». Un recorte de la salida puede convertir un informe rojo en uno verde sin
que nada avise, porque el trozo que queda **es** verde y es cierto.

**Regla**: de un informe de pruebas se lee el bloque de fallos y el recuento, o se
filtra por `failed|passed|skipped`. Nunca `tail -N` a ciegas. Y si el recuento no
cuadra con el total anunciado (245 de 249), eso ya es la señal: hay 4 sin explicar.

## Una prueba que gasta datos de la semilla pasa una vez por base de datos (14/08/2026)

`06-correcciones` tomaba prestado un fichaje existente del operario, y una de sus
propias pruebas ---la que aplica la anulación--- lo dejaba en `is_active=false`. El
filtro de búsqueda pedía activos. Resultado: el fichero verde en la primera tanda y
cuatro rojos en la siguiente, con un `Cannot read properties of undefined` que no
señala al defecto sino a la prueba anterior.

**Regla**: si una prueba **consume** un recurso (lo anula, lo borra, lo cierra), tiene
que **crearlo** ella. Tomarlo prestado solo vale para lo que se lee. Y el contraste de
que está bien arreglado no es que pase: es que pase **dos veces seguidas**.

## Neutralizar código para el contraste: `pass`, no borrar (14/08/2026)

Para probar que las pruebas nuevas fallaban sin el arreglo, quité los `record()` con
una expresión regular. Las cinco pruebas fallaron --- por `IndentationError`. Un `if`
se quedó sin cuerpo, y un contraste que falla por sintaxis no demuestra nada.

**Regla**: para neutralizar una llamada, **sustitúyela por `pass` con su mismo
sangrado** contando paréntesis, no la borres. Y mira el motivo del fallo: si pone
`SyntaxError` o `IndentationError`, el contraste no ha corrido.

## Un manager que filtra por empresa cuenta cero cuando no hay contexto (25/08/2026)

En una prueba de aislamiento escribí `Punch.objects.filter(employee=una).count() == 1`
fuera de `tenant_context`. Devolvió 0, y por un momento pareció que el fichaje no se
había creado. No era eso: `objects` es el manager acotado, y sin contexto acota a nada.
La trampa está en que la aserción **habría pasado** si la hubiera escrito al revés
---`== 0` para las dos empresas--- y yo me habría quedado convencido de haber probado
un aislamiento que no probé.

**Regla**: en una prueba que cuenta filas de varias empresas a la vez, `objects_all_tenants`
y un comentario diciendo por qué. Es el mismo principio que «un vacío no es prueba de
ausencia», un piso más abajo: aquí el vacío lo produce el propio instrumento.

## `makemessages` rellena por parecido, y lo que rellena suele ser mentira (25/08/2026)

Al extraer 21 cadenas nuevas, gettext copió 14 traducciones de mensajes **distintos**
por similitud de texto y las marcó `fuzzy`. «Changed what a leave grants» salió como
«Cambiar la hora de un fichaje»; «An event is either an entry or an exit.» heredó la
frase de otro error. Como `fuzzy` no se usa en tiempo de ejecución, nada falla hoy: la
bomba es para quien limpie los marcadores dando por bueno lo que hay debajo.

**Regla**: después de cada `makemessages`, `grep -c '#, fuzzy'` y **leer las que salgan
una por una**. Si eran cero antes, todas las nuevas son invención. Traducirlas o
vaciarlas, nunca dejarlas. Y en un idioma que no dominas, vaciar: el catálogo cae al
castellano y dice la verdad, que es que está sin traducir.

## Un componente de terceros puede truncar el número que tu código calculó bien (25/08/2026)

`cuantasHay` estaba escrita con cuidado ---lee `count` y no las filas recibidas, con un
comentario explicando que redondear a la baja es peor que no poner número--- y aun así
la pestaña decía «99+» habiendo 125, porque el `Badge` de MUI corta en 99 por defecto.
El Resumen, que pinta el número a pelo, decía 125. Dos pantallas contando lo mismo.

**Regla**: cuando un dato pasa por un componente de una biblioteca antes de verse, el
cuidado que pusiste al calcularlo no basta: mira qué hace ese componente con los valores
del extremo. Y busca el mismo defecto un piso más arriba de donde ya lo arreglaste una
vez ---suele estar ahí---.

## Un rótulo accesible tiene que distinguir en el peor caso, no en el corriente (25/08/2026)

`aria-label` decía «Corregir el fichaje de Marta Ruiz de las 13:06», que distingue de
maravilla hasta que la misma persona tiene cuatro fichajes dentro del mismo minuto. Y
los tiene: entrar, salir y volver caben de sobra en sesenta segundos. Cuatro botones que
se oyen exactamente igual.

**Regla**: el rótulo se diseña contra el caso más apretado que el sistema permite, y esa
cota la fija el propio producto ---aquí, los cinco segundos de la guarda del doble
toque---. Si dos elementos pueden compartir rótulo, comparten defecto.

## Un `msgstr` de varias líneas empieza por `msgstr ""` (25/08/2026)

Escribí un detector de cadenas sin traducir que buscaba `^msgstr ""$`. Toda
traducción larga empieza exactamente así y sigue en las líneas de abajo, de modo
que el detector las contaba como vacías: decía 128 huecos en castellano donde
había 2. Peor todavía, me hizo «arreglar» algo que no estaba roto y me habría
dejado dar por incompleto un catálogo que estaba bien.

**Regla**: un `msgstr` está vacío si `msgstr ""` **no** tiene líneas de cadena
detrás. Y antes de fiarse de cualquier contador escrito para la ocasión,
contrastarlo con un caso conocido en los dos sentidos: una cadena que sabes
traducida tiene que salir traducida, no solo una vacía salir vacía.

## Dos reemplazos y un solo `assert` esconden el que falló (25/08/2026)

Un script hacía dos sustituciones en el cuaderno y comprobaba `s != antes` al
final. La primera se aplicó, la segunda no encontró su texto ---diferían los
saltos de línea--- y el `assert` pasó igualmente. Lo dio por hecho y no lo estaba.

**Regla**: una comprobación por sustitución, con el `assert` dentro y el nombre de
lo que busca en el mensaje. Un `assert` agregado sobre varias operaciones solo
demuestra que **alguna** funcionó.

## `on_commit` no se ejecuta dentro de una prueba (25/08/2026)

Puse la limpieza de ficheros en `transaction.on_commit` ---bien puesta: borrar
antes de confirmar deja una fila viva apuntando a un fichero que ya no está--- y
las pruebas siguieron rojas después del arreglo. Cada prueba corre en una
transacción que se revierte, así que nada confirma nunca y el callback no llega a
correr. Con `django_capture_on_commit_callbacks(execute=True)` pasan.

**Regla**: si el código que pruebas usa `on_commit`, la prueba necesita el
`capture`. Y el contraste vale solo si lo haces con la prueba **en su forma
final**: el rojo que viste antes de añadir el `capture` no es el mismo escenario,
así que hay que volver a neutralizar el arreglo y comprobar que la prueba
definitiva también lo ve.

## Una opción de configuración que el repositorio ofrece tiene que funcionar entera (25/08/2026)

El `compose.yml` parametriza los puertos con `OTT_PORT_*` y lo documenta: existen
para poder levantar la pila junto a otra en la misma máquina. Al usarlo, no se
podía entrar. `CORS_ALLOWED_ORIGINS` seguía escrito a mano con el 3000, y la
suite de navegador tenía la API a fuego en el 8000 en cinco sitios. Ninguno de
los dos avisaba de lo suyo: la pantalla decía «No hay conexión con el servidor» y
la suite fallaba con un `null` en el almacén durante el arranque de sesión.

**Regla**: al añadir una variable de configuración, buscar **todos** los sitios
que asumen su valor viejo ---`grep` del número, no solo del nombre--- incluidas
las pruebas y los ficheros de ejemplo. Un valor por defecto que contradice a otro
valor por defecto del mismo repositorio es peor que no tener la opción, porque
falla lejos de donde se cambió.

## Un aislamiento se comprueba por donde se sirve, no por el manager (25/08/2026)

Escribí una prueba que verificaba que la empresa de al lado no ve una entrada de
auditoría preguntando `AuditLog.objects` dentro de su `tenant_context`. Falló, y
por un momento pareció una fuga. No lo era: `AuditLog` no es un
`TenantOwnedModel` **a propósito** ---su propio docstring lo explica--- y quien
acota es el ViewSet. La prueba comprobaba algo que ese modelo nunca prometió.

**Regla**: antes de dar por buena una prueba de aislamiento, mirar **quién** hace
el filtrado en ese modelo. Si es la vista, la prueba va por la vista con la
sesión de quien no debe ver. Y siempre con el caso positivo al lado: un cero que
no se contrasta no distingue «bien acotado» de «nunca se escribió».

## La suite mira el `h1`; el usuario mira la pantalla entera (25/08/2026)

Dos fallos de la vuelta 47 llevaban meses ahí con 249 pruebas en verde: la
cabecera decía «Resumen» en las trece pantallas de gestión, y en un teléfono no
había forma de llegar a diez de ellas. Ninguna prueba los veía porque todas
entran por la ruta y comprueban el título de la pantalla. Aparecieron en los dos
primeros minutos de mirar con un navegador de verdad.

**Regla**: una suite verde dice que no ha vuelto lo que ya se arregló, no que la
pantalla esté bien. Cada cierto número de vueltas, abrir la aplicación y usarla
---y en el tamaño de un teléfono, que es donde el armazón cambia de forma---.

## Media pieza escrita es una pista, no un descuido (25/08/2026)

`NavSection` aceptaba un `onNavigate` y lo llamaba en cada entrada del menú.
Nadie se lo pasaba nunca. Esa prop no tiene sentido en un cajón permanente: solo
la necesita uno que se cierre al elegir. Era el rastro de un menú móvil previsto
y no montado, y encontrarla convirtió el arreglo en montar lo que faltaba en vez
de inventar un mecanismo nuevo.

**Regla**: cuando algo no se usa ---una prop, una exportación, un parámetro---
antes de borrarlo, preguntar para qué se escribió. A veces señala el hueco.

## Una sonda dice la verdad sobre lo que mira, no sobre lo que hay (25/08/2026)

`29-en-el-movil.spec.js` afirmaba en su cabecera que «ninguna otra pantalla se
sale». Recorría once de las diecisiete. De las seis que no miraba, una se salía
22 px --- y era el Calendario, una de las dos que más ancho piden. La frase era
verdad sobre la lista, y la lista no estaba completa.

**Regla**: cuando una sonda recorre una lista de pantallas, rutas o endpoints, la
lista se genera o se contrasta contra la fuente ---aquí, `navigation.jsx`--- y no
se escribe a mano. Y si se escribe a mano, la cabecera dice **cuántas** son, para
que el hueco se vea al leerlo.

## Buscar la sonda antes de escribirla, de verdad (25/08/2026)

Escribí `40-desde-el-movil.spec.js` con su propia tabla de pantallas sin mirar
que `29-en-el-movil.spec.js` ya tenía una. Lo mismo con `monthName`, que estaba
en `format.js` y dos pantallas reimplementaban a mano. El prompt de la auditoría
ya dice «antes de escribir un mecanismo transversal, busca si ya existe»: el
fallo no fue no saberlo, fue no hacerlo.

**Regla**: el `grep` va **antes** del primer renglón de código, no después de que
algo falle. Dos minutos de búsqueda contra una tabla duplicada que va a divergir.

## `update_fields` rompe la promesa de `auto_now` (25/08/2026)

`save(update_fields=["is_active"])` no escribe `updated_at`, aunque el campo sea
`auto_now`. Django lo pone en la instancia y no lo persiste, porque no está en la
lista. No hay error, no hay aviso, y el código parece correcto. Lo que se rompe
está lejos: una lectura incremental que avanza por esa marca deja de ver los
cambios para siempre.

**Regla**: si un modelo tiene `auto_now` y alguien lee por esa columna, la
promesa se garantiza en `save()` del modelo base, no en cada llamada. Y al
encontrar uno, barrer los demás: había siete en cinco ficheros.

## Una prueba de lectura incremental necesita que el cursor avance de verdad (25/08/2026)

Comprobé que una baja llega al conector pidiendo `?since=<cursor>` y buscando a
la persona en la respuesta. Salía, y la prueba pasaba **con el fallo delante**:
el cursor filtra con `>=` para no perder dos cambios del mismo instante, así que
reenvía la última tanda entera.

**Regla**: en un cursor con `>=`, aparecer en la siguiente tanda no demuestra que
algo cambiara. Hay que mirar el dato que el cursor usa ---aquí `updated_at` en la
fila--- o separar los instantes.

## No tocar el backend mientras corre la suite de navegador (25/08/2026)

Edité `common/models.py` mientras la suite de Playwright iba por la prueba 46. El
recargador de Django reinició el servidor y esa prueba murió con `TypeError:
Failed to fetch`. Aislada pasa. Perdí diez minutos de suite y un rato buscando un
defecto que no existía.

**Regla**: el aviso del cuaderno ---«no lances dos suites a la vez»--- vale
igual para **editar** el backend con la suite en marcha: el recargador es el que
comparte. Si hay que adelantar trabajo, que sea leer o escribir pruebas, no
tocar código que el servidor vigila.

**Reincidido en la vuelta 61**, doce vueltas después de escribir esto. La tanda
murió a los tres minutos con dos fallos inventados. La regla no falla por no
estar escrita, falla por lanzar la suite «en segundo plano» y sentir que el rato
está libre: **no lo está**. Mientras corre, el backend es de la suite.

## «No me han contestado» no es un hecho sobre lo que pasó (25/08/2026)

Dos hallazgos altos de la vuelta 50, en sitios sin relación, eran la misma
equivocación: convertir la ausencia de respuesta en una afirmación. El
interceptor decía «esta sesión ya no vale» cuando lo que sabía era «no he podido
renovarla». La pantalla de fichar decía «no ha quedado nada» cuando lo que sabía
era «no me contestaron a tiempo» --- y esa frase, además, pedía el segundo toque
que estropeaba el registro.

**Regla**: antes de escribir un mensaje o de tirar un estado por un fallo de red,
preguntarse qué se sabe **de verdad**. Sin respuesta, casi nunca se sabe si la
escritura ocurrió. Lo honesto es decirlo y ofrecer cómo comprobarlo, no adivinar
--- y menos adivinar en la dirección que provoca una acción destructiva.

## El estado HTTP no siempre dice lo que crees sobre la sesión (25/08/2026)

Escribí «solo cierro la sesión si el servidor devuelve 401 o 403», que es la
regla correcta en general, y rompí la prueba del caso legítimo: este servidor
trata el refresco caducado como regla de negocio y responde **409
`session_expired`**. La regla general era buena; el mapeo, no.

**Regla**: al ramificar por el estado de un error, mirar **qué contesta este
servidor** en ese caso concreto, no lo que dicta la costumbre. Y ramificar por el
código de error propio cuando exista, que es explícito y no se solapa con los
otros mil motivos de un 409.

## Una jornada de referencia es de la persona, no de la empresa (25/08/2026)

`_whole_day_hours` caía a «la semana de la empresa entre cinco» sin preguntar qué
tenía pactado quien se ausenta. Para media jornada eso duplica el día, y un
permiso medido en días propios se descuadra **en las dos direcciones a la vez**:
al trabajador le dice que agotó lo que no ha agotado, y a la empresa le concede el
doble de lo que debe.

**Regla**: cualquier cifra que diga «un día de trabajo» tiene que salir de esa
persona ---cuadrante primero, contrato después--- y solo caer a la empresa cuando
no haya nada suyo. Y si el dato es una suposición, decirlo: aquí ya existía
`estimated`, y por eso el arreglo no tuvo que inventar nada nuevo.

## Una migración de datos corre en el orden en que la escribes (25/08/2026)

Puse el `RunPython` que vacía los nulos delante del `AlterField`, y se cayó: el
índice único viejo seguía puesto, así que la segunda fila que pasaba a cadena
vacía chocaba con la primera. Hacen falta tres pasos --- quitar la unicidad,
rellenar, y solo entonces poner `NOT NULL` --- y el `AlterField` que genera
Django hace las dos cosas a la vez.

**Regla**: una migración que cambia una restricción **y** los datos se escribe
paso a paso, preguntándose qué restricciones siguen vivas en cada momento. Y se
prueba contra la base de desarrollo con datos, no solo contra la de pruebas, que
está vacía: aquí eran 279 filas de 280 y la de pruebas no habría dicho nada.

## Un parámetro que el esquema publica y el código ignora (26/08/2026)

`?search=` salía en el esquema de las ausencias porque el backend de búsqueda
está en los de por defecto, y no filtraba nada porque el ViewSet no declaraba
`search_fields`. DRF no avisa: devuelve la lista entera. En una lista paginada
eso no se distingue de «tu búsqueda no encontró nada más».

**Regla**: si un filtro se hereda de la configuración global, cada ViewSet tiene
que declarar con qué trabaja o quitárselo. Y la prueba de un buscador no puede
ser «devuelve mi fila»: tiene que ser **«devuelve menos filas que sin buscar»**,
que es lo único que distingue buscar de no buscar.

## Una prueba que se arregló sin entender por qué fallaba vuelve (26/08/2026)

La prueba del calendario ya se había arreglado por este síntoma: se le llenaba la
página de resultados y cambiaron a buscar por una marca propia. Con la búsqueda
rota, ese arreglo solo movió el umbral --- y volvió en cuanto se acumularon
cincuenta y cinco ausencias de prueba. El comentario que explicaba el arreglo
anterior fue justo lo que puso sobre la pista.

**Regla**: cuando una prueba falla por «no encuentro lo que acabo de crear», la
primera pregunta es si se creó, y la segunda si el filtro con el que se busca
funciona. Arreglar la prueba sin contestar las dos deja el defecto en el producto
y la prueba en rojo diferido.

## La concordancia con uno solo se ve cuando hay uno (26/08/2026)

«1 personas de alta» llevaba ahí desde siempre con 264 pruebas en verde: la
semilla crea veinticuatro personas, así que el plural siempre acertaba. Apareció
en el primer minuto de mirar una empresa recién creada --- que es, además, la
primera pantalla que ve un cliente nuevo.

**Regla**: los datos de prueba cómodos esconden los casos de borde por arriba y
por abajo. Cada cierto tiempo, mirar el producto con **lo mínimo** ---una
empresa, una persona, cero de todo lo demás--- y con lo máximo. Y al encontrar un
plural mal, barrer los demás: había doce candidatos y cinco rotos.

## Lo que agrupa bien un modelo puede separarlo mal un informe (26/08/2026)

`Punch.was_delegated` junta `DELEGATED`, `ADMIN` e `IMPORT` con buen criterio:
los tres significan «no lo hizo la persona». El informe reutilizó ese booleano
para escribir una frase, y entonces una corrección hecha por la empresa se le
contaba a la Inspección como «registrado por una aplicación» --- la lectura más
benigna de las tres.

**Regla**: una abstracción que agrupa casos vale para decidir, no para
**describir**. Antes de reutilizar un `bool` en un texto que alguien va a leer
como prueba, comprobar qué casos esconde. Y el sitio donde se nota es el
documento que sale del sistema, no la pantalla.

## `force_authenticate` salta la capa que quieres probar (26/08/2026)

Escribí una prueba de qué pasa al dar de baja usando `force_authenticate`, y
salió un 409 `employee_inactive`. Con un testigo real sale **401**: la
autenticación rechaza antes de llegar a la vista. Los dos números describen
caminos distintos, y el que ve una persona es el segundo.

**Regla**: `force_authenticate` vale para probar lo que hay **detrás** de la
autenticación. Si lo que se prueba es el acceso mismo ---sesión caducada, cuenta
desactivada, permisos de la credencial--- hace falta el testigo de verdad. Y si
una prueba da un código que nunca has visto en el navegador, sospecha de la
prueba antes que del producto.

## Un helper con el aviso escrito no impide que el fallo siga en tres sitios (26/08/2026)

`format.js` tenía `today()` calculado en fecha local **y un comentario
explicando** por qué `toISOString()` está mal: al este de Greenwich devuelve el
día anterior de madrugada. Aun así, tres sitios seguían con `toISOString()`,
incluido el diálogo que más se usa. Escribir el helper y el porqué no basta: hay
que barrer el patrón viejo.

**Regla**: al añadir un helper que corrige un error corriente, el mismo cambio
tiene que incluir el `grep` del patrón que sustituye. Y el `grep` va del patrón
---`toISOString().slice`--- no del nombre del helper, que es lo que no aparece
donde falta.

## Una prueba de fechas a media mañana no prueba nada (26/08/2026)

El fallo de UTC solo se ve en unas horas concretas: de madrugada al este de
Greenwich, por la tarde al oeste. Una prueba escrita con la hora del momento
habría pasado con el defecto delante durante veintidós horas al día.

**Regla**: si algo depende de la hora, la prueba **fija el reloj** en el momento
en que se rompe ---`page.clock.setFixedTime` en Playwright, `freeze_time` en
pytest--- y deja escrito por qué esa hora y no otra.

## Un ajuste que se guarda y no se aplica parece una política (26/08/2026)

`record_retention_years` tiene valor por defecto, validación contra el suelo
legal, endpoint que lo expone y un `help_text` que explica su base jurídica. Todo
menos lo que importa: nada lo lee para borrar. Una empresa lo configura y se
queda tranquila creyendo que hay una purga.

**Regla**: al revisar un ajuste, buscar quién lo **lee**, no solo dónde se
guarda. `grep` del nombre del campo: si solo aparece en el modelo, el serializer
y sus pruebas, no hace nada. Y mientras no lo haga, decirlo en su propia ayuda:
un ajuste mudo es de los «a medias» que el proyecto considera peores que faltar.

## Una optimización sin sonda es una optimización que ya se rompió una vez (26/08/2026)

`_attendance_of` tiene un comentario de nueve líneas explicando cómo se evitó una
consulta por persona, con la cifra de lo que costaba antes. Nadie vigilaba que
siguiera así: la sonda de N+1 del proyecto medía catorce rutas y ninguna era la
de integración, que es la que más se repite.

**Regla**: cuando se arregla un N+1 y se escribe el porqué, el mismo cambio añade
la ruta a la sonda. Un comentario explica; una sonda impide. Y al añadirla,
comprobar que **de verdad mide** ---que la petición contesta 200 y consulta algo---
porque un 403 sale plano y parece perfecto.

## Aislada pasa, en la tanda falla: eso es una carrera (26/08/2026)

La prueba del vaciado del cuadrante falló en la suite completa y pasó sola, tres
veces seguidas. No era contaminación de datos ---nadie más toca diciembre de
2026--- sino tiempo: el diálogo se cierra al pulsar y la petición sigue viajando,
así que en una máquina cargada la comprobación llegaba antes que el borrado.

**Regla**: «aislada pasa, en la tanda falla» tiene dos causas típicas y se
distinguen rápido. Si otra prueba deja datos, el fallo cambia con el orden. Si es
una carrera, el fallo va con la carga y desaparece al repetir. Para lo segundo,
`expect.poll` sobre el estado final, nunca una consulta única después de un
`toBeHidden`: que un diálogo se cierre no significa que el servidor haya
terminado.

## Un fichero que se entrega lo abre alguien, y ese alguien usa Excel (26/08/2026)

El informe de jornada salía como CSV sin neutralizar, así que un nombre que
empiece por `=` se convierte en fórmula al abrirlo. El entrecomillado del CSV no
protege: es sintaxis del fichero y el programa la quita antes de evaluar.

Lo que lo hizo fácil de pasar por alto es que el CSV **estaba bien formado**. La
prueba de que un exportador funciona no es que el fichero se lea: es qué hace el
programa que lo va a abrir.

**Regla**: para cada fichero que el producto entrega, preguntarse con qué se abre
y qué hace ese programa con el contenido. CSV en Excel evalúa fórmulas; un PDF
con enlaces los abre; un nombre de fichero con `../` lo interpreta quien lo
descomprime. Y mirar de dónde viene el texto: aquí una parte la escribe la
persona trabajadora y viaja al documento por obligación legal, así que quitarla
no era opción.

## Un nombre de fichero derivado de datos es una ruta, no una etiqueta (26/08/2026)

El apellido de una persona componía la entrada de un zip y la cabecera de
descarga. Con `../../../evil` la entrada sale como ruta relativa y escapa del
directorio al descomprimir; con una comilla rompe la cabecera. Y sin
identificador, dos personas que se llaman igual generan la misma entrada: la
segunda pisa a la primera y **se entrega un documento menos sin que nada avise**.

**Regla**: todo nombre de fichero compuesto con datos pasa por un saneador, y si
va dentro de un lote lleva algo que lo haga único. El caso de la colisión es el
que más se escapa, porque no falla: produce un fichero menos, en silencio, y solo
se nota contando.

## Al cambiar cómo se nombra algo, las pruebas que fijaban el nombre viejo dicen la verdad a medias (26/08/2026)

Tres pruebas comprobaban `"García_Ana.pdf" in dentro`. Lo que de verdad
verificaban es **quién** aparece en el zip, no cómo se llama su fichero. Al
cambiar el formato se pusieron rojas, y la tentación es actualizar la cadena y
seguir.

**Regla**: cuando una prueba se rompe por un cambio de formato, mirar qué
pretendía comprobar antes de retocarla. Si lo que le importa es el contenido, la
aserción debe hablar de contenido ---un prefijo, una pertenencia--- y así deja de
romperse la próxima vez.

## 98. Que el texto esté en el fichero no es que se vea en la hoja

Un extractor de PDF devuelve lo que hay en el flujo de contenido, no lo que cae
dentro de los márgenes de la página. Una celda de tabla sin ajuste de línea
dibuja la cadena seguida, se sale por la derecha, y `extract_text()` la devuelve
entera igual de contenta.

Pasó con la discrepancia del art. 4.b: mil caracteres que llegaban al PDF y se
imprimían nueve veces más allá del ancho del A4. La prueba de la vuelta 39
---`assert "Yo entré antes." in texto`--- llevaba veintisiete vueltas pasando
con el fallo delante.

**Regla**: en un formato con maquetación ---PDF, imagen, impresión--- una
comprobación de presencia no vale. Mide la **geometría**: dónde arranca el
texto, cuánto ocupa, y compáralo con el ancho útil. Y antes de fiarte de la
medición, pásala por un caso que se sepa malo, porque un medidor que no mide da
verde en todo.

## 99. Envolver en `Paragraph` obliga a escapar, y a rehacer las búsquedas

`Paragraph` de ReportLab arregla el ajuste de línea y abre dos frentes a la vez:

- **Interpreta marcado.** Sin escapar, un `<` en un apellido tumba el documento
  entero y `<font color="white">` esconde texto dentro de una prueba legal.
- **Parte las frases en renglones.** Cualquier prueba que buscaba una cadena
  literal en el texto extraído empieza a fallar sin que falte nada: la frase
  sale cortada por la mitad entre dos líneas. Colapsa los espacios
  ---`" ".join(texto.split())`--- antes de buscar.

## 100. Una prueba que deja basura acaba encontrando un fallo, pero tarde

La prueba de aplicaciones se llamaba «autorizar, emitir un testigo y revocar» y
no revocaba: dejaba una aplicación activa cada vez. Después de 59 ejecuciones la
lista pasó de cincuenta, la nueva cayó en la segunda página, y la prueba se puso
roja por un fallo real que llevaba ahí desde el principio.

Salió bien de casualidad. Lo normal es lo contrario: la basura hace fallar
pruebas por motivos que no son el fallo, y se pierde la tarde persiguiendo el
ruido.

**Regla**: una prueba de extremo a extremo deja el sistema como lo encontró. Si
el producto no borra ---y a menudo no debe: aquí revocar desactiva porque los
fichajes registrados siguen siendo suyos--- entonces la prueba ejercita el
camino que lo retira. Y si el título dice «y revocar», que revoque.

## 101. Un arreglo transversal hay que terminarlo, y la lista está en el código

Dos veces en la misma vuelta: la vuelta 39 hizo llegar la discrepancia al PDF y
no comprobó que se leyera; y el arreglo de la paginación llegó a People y al
rastro de auditoría pero no a los fichajes de la persona --- **teniéndolo escrito
en el comentario de `api.js`**, que decía en qué tres sitios pasaba.

**Regla**: cuando un arreglo vale para varios sitios, enumera los sitios en el
momento, arréglalos todos y deja la lista en el código. Y al leer un comentario
que enumera sitios afectados, comprobar uno por uno que siguen arreglados: ese
comentario es un inventario, no una anécdota.

## 102. Paginar no siempre es la respuesta

Cortar cada cincuenta filas vale para una tabla de personas. No vale para los
fichajes de una jornada, que se pintan agrupados por día: la entrada quedaría en
una página y la salida en la siguiente, y el día se leería mal.

**Regla**: antes de meter un `Pager`, mira cómo se agrupa lo que se pinta. Si la
unidad que el usuario lee es mayor que la fila, trae el periodo entero --- con un
tope, y diciéndolo cuando el tope se alcance. Nunca dar por completo lo que no
se ha comprobado que lo esté.

## 103. Antes de describir un fallo, mira el render

Escribí en el cuaderno que el cuadro de fichajes mostraba «una jornada abierta
que en realidad se cerró», y de ahí deduje que invitaba a corregir un fichaje
sin motivo. Al abrir el componente resultó que esa pantalla no calcula jornadas
ni saldos: solo lista eventos bajo un encabezado de día. El defecto era otro
---el día partido y repetido--- y seguía siendo real, pero la consecuencia que
le había puesto era inventada.

**Regla**: la medición dice qué datos llegan; solo el render dice qué ve la
persona. Describir la consecuencia antes de leer el componente es adivinar, y
en un cuaderno de auditoría una consecuencia adivinada se lee igual que una
comprobada. Si ya está escrita, se corrige donde estaba, no en una nota aparte.

## 104. Dos vistas distintas no son un fallo de una sola vista

El cuadro de fichajes servía para dos cosas: la jornada de una persona y el
volcado de toda la empresa. La paginación correcta no es la misma para las dos
---día en una, fichaje en la otra--- y forzar una sola producía el día partido.

**Regla**: cuando una pantalla no encaja con ninguna paginación, mira si en
realidad son dos usos metidos en un sitio. Separarlos suele salir más barato que
inventar un mecanismo que sirva para los dos, y deja cada uno diciendo la verdad.

## 105. Un módulo bien escrito no protege a quien no lo llama

`apps/common/dst.py` documenta la trampa del cambio de hora mejor que cualquier
comentario del repositorio, tiene sus pruebas y es correcto. Y solo lo usaba uno
de los cuatro sitios que restan turnos: los otros tres seguían haciendo
aritmética de reloj de pared, incluido el que decide si se cumple el suelo de
descanso del art. 34.3.

Leer el módulo tranquiliza. Es exactamente el «solo citado» del que avisa el
guion, con una vuelta de tuerca: aquí ni siquiera estaba citado en el sitio malo,
estaba resuelto **al lado**.

**Regla**: cuando encuentres un módulo que resuelve bien un problema sutil, la
pregunta no es si está bien --- es **quién lo importa**. Un `grep` del nombre
comparado con un `grep` de la operación que arregla (aquí, restar dos datetime de
un turno) da la lista de los que se lo perdieron.

## 106. Un arreglo de fecha se prueba en las dos direcciones

Ese cambio de hora tiene dos noches y van al revés: en marzo el hueco real es
menor que el de reloj, en octubre es mayor. Arreglar solo mirando marzo puede
producir una advertencia falsa cada octubre --- y para toda la plantilla de noche
a la vez, que es peor que el defecto de partida.

**Regla**: toda corrección de huso, cambio de hora o fin de mes lleva tres
pruebas, no una: el caso que falla, el caso simétrico que **no** debe cambiar, y
un día corriente de control. Sin el tercero no sabes si el aviso salta siempre.

## 107. Donde se cuenta y donde se enseña son dos sitios

El producto resolvía la zona horaria por persona en todo lo que cuenta:
`local_day_bounds`, el informe, el resumen semanal. Y la daba por la de la
empresa en todo lo que se enseña: la sesión y la pantalla de fichar. El
resultado es lo peor de los dos mundos --- la pantalla y el PDF entregado ponían
el mismo fichaje en días distintos.

Es fácil de pasar por alto porque revisar el cálculo deja tranquilo, y el
cálculo estaba bien.

**Regla**: cuando compruebes que una magnitud sensible al contexto ---zona
horaria, moneda, idioma, redondeo--- se calcula bien, no cierres ahí. Sigue el
dato hasta lo que ve la persona y hasta lo que sale en el documento, y comprueba
que los tres coinciden. Un cálculo correcto que se enseña mal es un fallo
completo, no medio.

## 108. Añadir un campo derivado a un serializer es tocar el rendimiento

`effective_time_zone` en la ficha de una persona parece gratis: es una propiedad.
Detrás hay una FK al centro de trabajo y otra a la empresa, así que
`/api/employees/` pasó de 10 consultas con tres personas a 19 con doce.

Lo cazó `test_no_crece_con_la_plantilla` en la misma tanda, sin buscarlo. Vale la
pena decirlo al revés de como suele contarse: **el guard funcionó**, y por eso el
N+1 duró cinco minutos en vez de llegar a producción y aparecer como «la pantalla
de personas va lenta en las empresas grandes».

**Regla**: todo campo nuevo de serializer que llame a una propiedad del modelo se
comprueba contra la prueba de consultas antes de darlo por hecho. Y el
`select_related` se pone **por cada salto**: aquí `workplace` no bastaba, porque
quien no tiene centro cae en `tenant`, y ese es el camino de la mayoría.

## 109. El dato que depende del contexto viaja con el dato, no con la sesión

La zona de la persona en la sesión arregla las pantallas donde uno mira lo suyo,
y no arregla ninguna de las que enseñan a varias personas a la vez. Ahí el
contexto cambia **por fila**, así que tiene que ir en la fila.

La alternativa que parecía más barata ---sacarlo del selector de persona, que ya
recibe la ficha entera--- solo cubre el caso con filtro y se pierde al recargar
la página.

**Regla**: si un valor depende de a quién pertenece la fila ---huso, moneda,
convenio, idioma--- va en el serializer de la fila. La sesión sirve de respaldo,
nunca de respuesta. Y comprueba qué expone ya la API antes de diseñar: aquí el
listado de personas traía el campo desde la vuelta anterior y el fichaje no, y
eso decidió dónde tocar.

## 110. Una prueba de N+1 mide un eje, y hay dos

`test_no_crece_con_la_plantilla` compara las consultas con tres personas y con
doce. Es lo que cazó el N+1 de la vuelta 69. Y **no** habría cazado el de la 70:
un listado de fichajes crece con las filas, no con la plantilla, y cuarenta
fichajes de veinte personas pasaban de 6 consultas a 46 sin que esa prueba se
inmutara.

**Regla**: al añadir un campo derivado, pregúntate con qué crece el listado que
lo sirve --- personas, filas, días, adjuntos --- y mide **ese** eje. Un guard verde
en el eje equivocado es peor que no tenerlo, porque tranquiliza.

## 111. Dos falsos hallazgos en una pasada, los dos por medir mal

En la misma vuelta estuve a punto de anotar dos defectos que no existían:

- Conté el rastro de auditoría filtrando por `"document_downloaded"` cuando la
  acción es `DOCUMENT_DOWNLOADED`. Cero resultados leídos como «el producto no
  deja rastro».
- Puse `department=oficina` a un responsable creyendo que eso lo ponía al mando
  de Oficina. `department` es **dónde trabaja**; lo que dirige va en
  `Department.managers`. Sin departamentos al mando el alcance es todo por
  diseño, así que mi «responsable ajeno entra» era un responsable sin
  departamentos.

Los dos tienen la misma forma: **la sonda no montaba el escenario que yo creía
estar montando**, y el resultado era coherente con la hipótesis equivocada.

**Regla**: antes de escribir un hallazgo que nace de un conteo, comprueba que el
conteo sabe contar --- pide el total sin filtro y mira que no sea cero. Y antes de
uno que nace de un rol, comprueba que el rol es el que crees: imprime el
escenario montado (quién dirige qué, quién ve a quién) y léelo, en vez de darlo
por hecho desde el nombre del campo.

## 112. Una lista de extensiones no filtra a quien elige la extensión

`uploads.py` documentaba una defensa en profundidad de dos capas: extensiones
permitidas y `Content-Disposition: attachment`. Contra un HTML llamado
`foto.png` solo funcionaba la segunda, porque `.png` está en la lista. La
primera capa no aportaba nada al caso que decía cubrir.

**Regla**: cuando un módulo afirme tener dos defensas, prueba cada una **sin la
otra**. Si una de las dos no rechaza el ataque por sí sola, no hay dos: hay una
y un comentario que tranquiliza. Para ficheros, eso significa mirar los bytes;
la extensión es un dato que aporta quien ataca.

## 113. Una lente que se agota en un `grep` no es una vuelta perdida

La vuelta 72 empezó por «las demás entradas de fichero» después de que la 71
encontrara lo de los bytes. Duró un `grep`: en todo el producto hay **una sola**
`FileField` y ya estaba cubierta.

Lo correcto ahí no es forzar la lente hasta sacarle algo ---eso produce hallazgos
inventados--- ni dar la vuelta por terminada. Es cambiar de eje con lo que queda
de pasada.

**Regla**: cuando el inventario de una lente sale casi vacío, anótalo como
cobertura confirmada en una línea y pasa a otra cosa. Un inventario vacío es
información: dice que ese eje no tiene superficie, y eso vale para no volver.

## 114. Prohibir la acción y olvidar la inacción

`four_eyes` estaba en aprobar y no en rechazar. Un responsable no podía aprobar
un cambio sobre su propio fichaje y sí podía archivarlo, él solo. La regla
parecía puesta porque el caso que uno imagina ---«se aprueba a sí mismo un
cambio»--- estaba cubierto.

No cambiar nada también es decidir: archivar una propuesta deja el registro como
está, que es un resultado tan elegido como el otro.

**Regla**: al revisar una salvaguarda sobre decisiones, enumera **todas** las
salidas del procedimiento, no solo la que concede. Aprobar, rechazar, archivar,
dejar caducar. Si la regla no está en todas, alguien puede llegar al mismo
destino por la puerta que quedó abierta.

## 115. Una suite verde puede estar apoyándose en el atajo que vas a cerrar

Al cerrar el hueco de los cuatro ojos en `reject`, la suite de backend siguió en
verde ---1005 pruebas--- y la de navegador dio dos rojos. Ninguno era una
regresión: la prueba 22 **limpiaba sus datos usando justo el atajo que el
arreglo prohíbe**, y el segundo rojo era la basura que esa limpieza rota dejaba
atrás, cambiando el render de otra pantalla.

**Regla**: cuando un arreglo cierre una puerta, mira quién la usaba. Que las
pruebas se rompan ahí no significa que el arreglo esté mal --- puede significar
que la prueba tomaba el mismo atajo que la persona a la que quieres impedírselo.
Léelas antes de tocar el arreglo, y arregla la prueba haciendo lo que el
producto ahora exige, no rodeándolo.

## 116. Un borrado puede no perder nada y aun así ser un fallo

La vuelta 73 empezó buscando lo obvio: que retirar un departamento o un centro
no se llevara fichajes por delante. No se los lleva --- `PROTECT` donde toca, baja
en vez de borrado, y ninguna puerta para borrar la empresa.

Lo que sí hacía era **ampliar permisos**. Retirar el único departamento que
alguien dirigía lo dejaba «al mando de nada», y el código lee eso como «nada le
estrecha»: la responsable pasó de ver 2 personas a verlas todas, y un
justificante de otro departamento de 404 a 200.

**Regla**: al auditar un borrado, no preguntes solo qué desaparece. Pregunta
también **qué queda en un estado que significa otra cosa**. Un campo a `None`,
una relación vacía o un contador a cero suelen tener un significado por defecto
escrito para el día del alta, y ese significado casi nunca es el correcto para
algo que existió y se retiró.

## 117. Lo ordenado para unos es lo contrario para otros

`SET_NULL` en el departamento es la respuesta correcta para quien está **en** él:
conserva todo y pierde una etiqueta. Y es la equivocada para quien **responde**
de él. El comentario del centro de trabajo decía en voz alta que para un
departamento `SET_NULL` era «una respuesta ordenada» --- cierto para la población
en la que pensó quien lo escribió, y solo para esa.

**Regla**: cuando una entidad tiene dos poblaciones colgando ---miembros y
responsables, autores y destinatarios, dueños y invitados--- decide el borrado
para **cada una**. Una sola regla que las trate igual va a ser correcta para una
y silenciosa para la otra.

## 118. El botón que ofrece lo que el servidor va a rechazar

Al cerrar el borrado de departamentos con responsables, la pantalla siguió
ofreciendo el botón: se pintaba con `people_count === 0`, que cuenta quién está
**dentro**, no quién **responde**. Un departamento sin gente y con jefa mostraba
«Eliminar» y un texto que prometía que no afectaba a nadie.

**Regla**: cuando añadas una condición de negocio en el servidor, busca en el
frontend qué condición usaba para ofrecer esa acción. Casi nunca es la misma, y
la diferencia se paga en un error que la persona recibe después de decidir.
Mientras las dos no coincidan, la pantalla está mintiendo antes de fallar.

## 119. Un campo que dice «informado» no informa a nadie

El producto guardaba `representatives_notified_at`, una nota con nombre y
apellidos ---«Informados: Fulana»--- y lo mandaba todo al informe de inspección.
No enviaba ningún correo. El `help_text` que la empresa lee al marcar la casilla
prometía lo contrario.

Es el «solo citado» del guion en su forma peor: no es que falte el campo, es que
el campo **está y afirma que la obligación se cumplió**.

**Regla**: cuando un campo, una marca de tiempo o una nota afirmen que se hizo
algo hacia fuera ---informar, avisar, notificar, publicar--- busca la llamada que
lo hace. Si no la encuentras, el campo no es una prueba: es una afirmación sin
respaldo, y en un documento legal eso es peor que el hueco.

## 120. Antes de creerte un canal temporal, calienta y repite

Medí el «he olvidado la contraseña» y salió 142 ms con dirección existente
contra 2 ms sin ella: enumeración de usuarios de manual. Con una llamada de
calentamiento previa y cinco repeticiones, la diferencia real era **2 ms contra
1**. Los 142 eran la primera petición del proceso cargando plantillas y
conexiones.

**Regla**: una medición de tiempo sin calentamiento previo y sin repetición no
es una medición. Y si hay límite de tasa de por medio, vacía su cubeta entre
medidas: si no, a la segunda solo estás cronometrando el 429.

## 121. Quitar el `fuzzy` sin mirar el texto convierte un aviso en una mentira

`makemessages` presta traducciones por parecido y las marca `fuzzy`. La marca
molesta, y la tentación es barrerla con una expresión regular. Al hacerlo en
catalán y gallego, el asunto del aviso nuevo se quedaba como «un canvi en el
registre de jornada» --- texto de otra cadena, ahora sin ninguna marca que
avisara.

**Regla**: `fuzzy` no se quita, se resuelve. Si vas a traducir, traduce; si no,
**vacía** el `msgstr` y deja el hueco. Un hueco se ve en el recuento y en la
pantalla; una traducción equivocada sin marca no la ve nadie hasta que un
cliente lee algo que no viene a cuento.

## 122. Validar contra el fallo también audita la prueba

Al neutralizar la comprobación del sello, dos de mis tres pruebas nuevas se
pusieron rojas y **una siguió verde**. Era la que decía «la huella del informe
cambia cuando aparece el aviso»: yo alteraba la hora del fichaje, y la hora está
dentro de la huella, así que cambiaba igual con el aviso desconectado. La prueba
afirmaba una cosa y comprobaba otra.

Se arregló tocando el **origen** del fichaje: rompe el sello y no entra en la
huella del documento, así que la única diferencia que queda entre las dos huellas
es el aviso.

**Regla**: el paso de «revertir el arreglo y ver que la prueba falla» no es un
trámite de confirmación --- es lo que distingue una prueba que mide de una que
acompaña. Si al revertir una prueba sigue verde, esa prueba está mal, aunque el
arreglo esté bien. Y para aislar un efecto, toca algo que **solo** cambie eso.

## 123. Un barrido tosco da treinta candidatos y ninguno vale

Buscar «métodos públicos que nadie llama» con un `grep` de `.nombre(` dio treinta
resultados y todos eran ruido: los `@action` los llama el enrutador de DRF, las
propiedades se usan sin paréntesis, los filtros los conduce django-filter, los
comandos los invoca `manage.py`.

Refinar el barrido ---excluir decoradores del framework, excluir las clases que
el framework conduce, y buscar el uso con y sin paréntesis--- lo dejó en diez, y
de esos tres eran de verdad.

**Regla**: un detector automático de «código muerto» hay que calibrarlo antes de
leer su salida, igual que cualquier otra medición. Si el primer resultado es una
lista larga de cosas que resultan normales, el detector está mal, no el código --- y
seguir mirando esa lista gasta la pasada en descartar ruido.

## 124. «Solo si cambia» deja fuera el caso que confirma

La primera versión del arreglo anotaba de dónde venía una cifra solo cuando el
convenio **cambiaba** el valor. Y el convenio de jardinería fija el descanso
entre jornadas en doce horas, que es exactamente lo que ya decía el Estatuto: el
número no se mueve y la fuente sí. Los campos que interesaban quedaban todos
fuera.

Salió al medir el resultado, no al razonar el código: la prueba seguía diciendo
«Art. 34.3 ET» después del arreglo.

**Regla**: cuando registres la procedencia, el autor o el motivo de un dato,
regístralo por el hecho de que alguien lo afirme, no por que el valor difiera.
Confirmar lo que ya había es una decisión igual de real que cambiarlo, y en
materia legal suele ser la más frecuente.

## 125. La caché de una petición convierte una sonda en un «está bien»

`WorkingTimeRules.for_company` recuerda las reglas en el objeto `Tenant` para no
pedir la misma fila cuatrocientas ochenta y dos veces. Su comentario avisa: «un
proceso largo que cambie las reglas y siga usando el mismo objeto vería las de
antes».

Mi sonda era ese proceso largo. Cambié el suelo de descanso a cero por la API y
seguí midiendo con la misma instancia: el aviso seguía saliendo, y eso parecía
decir que el cero no apagaba nada. Recargando la empresa, el aviso desaparece.

**Regla**: en una sonda que cambia configuración y luego mide su efecto, **vuelve
a leer** los objetos entre las dos cosas. Una petición real trae su propia
instancia y una sonda no, así que la sonda mide un estado que en producción no
existe --- y lo hace en la dirección optimista.

## 126. «No devuelve un 500» y «acepta cualquier cosa» son dos preguntas

El repositorio tenía un guard exhaustivo de entradas malformadas: saca los campos
del propio serializador y comprueba que nada contesta un 500. Muy bueno, y
completamente ciego a lo que encontró esta vuelta: una jornada semanal de 200
horas, un descanso entre jornadas de cero y un plazo de consentimiento de cero
días se guardan con un 200 impecable.

**Regla**: la robustez frente a la basura y la sensatez de los valores son ejes
distintos. Después de comprobar que nada se rompe con entradas absurdas, pregunta
qué pasa cuando el valor **es del tipo correcto** y no tiene sentido --- y sobre
todo, qué comprobación deja de funcionar por haberlo aceptado.

## 127. El dato ya estaba escrito, en prosa, al lado del campo

El aviso de «esto se sale de lo que fija el artículo» lee `floor` y `ceiling` del
marco legal. Solo cuatro de catorce campos los tenían. Y la nota de cada cita
—el texto que se muestra junto al campo en la pantalla— **ya decía el número**:
«Quince minutos cuando la jornada continuada excede de seis horas», «Cuatro años
como mínimo», «Cinco días de preaviso».

O sea: la información estaba en el fichero correcto, en la línea de al lado, en
un formato que solo lee una persona.

**Regla**: cuando un mecanismo dependa de datos estructurados, mira si esos datos
ya existen en prosa en el mismo sitio. Un comentario o una nota que enuncia una
cifra es una cifra pendiente de declarar, y encontrarla cuesta un `grep` en vez
de una investigación.

## 128. No inventes un número para que encaje en tu mecanismo

El art. 4.b **no fija plazo** para responder a una corrección. La tentación era
declararle `floor=1` y dejar que el aviso genérico lo cubriera: encaja en el
mecanismo, sale gratis, y sería atribuirle a un artículo un número que no dice
—el mismo error de procedencia que la vuelta 76 acababa de arreglar, en la
dirección contraria.

Lo que sí se puede afirmar es qué pasa con el cero: que no hay procedimiento.
Eso va como aviso propio, y con esas palabras.

**Regla**: si un caso no encaja en el mecanismo general porque la ley no dice lo
que el mecanismo necesita, escríbele su propia regla. Forzarlo produce una
afirmación legal falsa, que es peor que un caso especial en el código.

## 129. Una aserción sobre un mensaje traducible se rompe al compilar

Escribí `assert "agree" in aviso["message"]`. Pasó en verde, y se puso roja en
cuanto compilé los catálogos: el mensaje salía ya en castellano.

**Regla**: no aserciones sobre el texto de un mensaje que pasa por gettext.
Comprueba lo que no se traduce —el código del error, el campo, el artículo, un
número— y si de verdad hace falta mirar el texto, actívale un idioma explícito.
El mismo cuidado que con `dateOf` o los formatos de número.

## 130. Una sola ronda de una carrera es una moneda al aire

Probé dos fichajes simultáneos con dos hilos y una barrera: salió un fichaje y un
409. Limpio. Repitiendo quince veces, **catorce dejaban dos fichajes**. La
primera había sido la ronda afortunada.

Y el dato que hace útil la medición no es el resultado, es el **solape**: medir
cuánto se pisan de verdad las dos peticiones (35 ms) es lo que distingue «no se
cuela» de «no he medido una carrera».

**Regla**: una prueba de concurrencia se repite ---diez o quince rondas--- y mide
si las peticiones solapan. Un verde de una sola ronda no dice nada, y un verde
sin solape dice menos todavía. Con la protección quitada, el escenario tiene que
llegar a fallar la mayoría de las veces; si no, el escenario no provoca la
carrera.

## 131. Que dos casos parecidos se traten distinto puede estar bien escrito

Al barrer transiciones sin bloqueo, las horas extra salían como la excepción:
`update_or_create` sin `claim`, decisión rehacible sin límite. Parecía el hueco.

No lo era, y no hacía falta deducirlo: `apps/common/tests/test_dos_a_la_vez.py`
tiene un apartado titulado «Lo que se dejó como estaba» que lo explica --- una
decisión sobre horas extra no toca los fichajes, así que una segunda no es una
carrera perdida sino una decisión nueva, y que el rastro guarde las dos es
correcto.

**Regla**: antes de tratar una asimetría como un defecto, busca si alguien la
documentó como decisión. Un fichero de pruebas con un apartado de «lo que se dejó
así» vale más que releer el código, y saltárselo es proponer que se deshaga algo
que ya se pensó.

## 132. Buscando una carrera se encuentra el defecto que no era una carrera

Fui a comprobar si dos correcciones simultáneas sobre el mismo fichaje se
colaban. Se colaban, doce de doce. Y al validarlo contra el caso conocido ---dos
peticiones **seguidas**--- también pasaban las dos: 201 y 201.

O sea que no había carrera: había un comportamiento normal, deliberado, y detrás
de él un defecto peor. Aprobar las dos dejaba **dos entradas activas** en el
registro, sin necesidad de concurrencia ninguna.

**Regla**: cuando una prueba de concurrencia falla, comprueba el caso secuencial
antes de escribir el bloqueo. Si también falla, el problema no es el bloqueo --- y
el arreglo que ibas a hacer habría tapado el síntoma dejando el defecto entero
en el camino normal.

## 133. Un mecanismo nuevo se reutiliza en la vuelta siguiente o no valía

`hold()` se escribió en la vuelta 79 para fichar. En la 80 sirvió sin tocarlo
para las solicitudes de ausencia: el mismo patrón ---leer una cola y decidir sin
bloquear--- en otro sitio del producto.

**Regla**: cuando arregles una carrera, deja la pieza en el módulo común y con el
porqué escrito, no en línea donde la encontraste. El segundo sitio aparece antes
de lo que parece, y encontrarlo es más fácil si el primero dejó un nombre al que
hacer `grep`.

## 134. Entre «contar mal» y «no contar» suele haber una tercera opción

El cómputo semanal descartaba las semanas que no cabían enteras en el periodo, y
su docstring lo razonaba bien: contar media semana y avisar de un exceso es peor
que callar, porque quien lo lee va a buscar horas que no están.

Las dos opciones que estaban sobre la mesa eran contar mal o no contar. La tercera
---**contar bien**, cargando los días que faltan--- no aparecía, y era la buena:
esos turnos estaban en la base, solo fuera del rango pedido. El resultado del
descarte era que la semana de cada borde de mes no se revisaba nunca.

**Regla**: cuando encuentres un caso descartado «porque los datos están
incompletos», comprueba si de verdad faltan o solo están fuera del filtro. Un
docstring que justifica una omisión suele estar defendiendo la decisión correcta
entre dos malas, y merece que se le ofrezca una tercera.

## 135. Ampliar lo que se lee es seguro solo si todos filtran al reportar

Para contar la semana entera hubo que leer más días de los pedidos. Eso podía
hacer que los otros cinco chequeos empezaran a avisar de días que nadie pidió.

Se comprobó **antes** de tocar la carga: los cinco filtran por `first`/`last`
antes de emitir el hallazgo, así que leer más solo les da contexto. Y quedó una
prueba que lo fija, porque el día que alguien añada un chequeo sin ese filtro, el
fallo aparecerá lejos de aquí.

**Regla**: si amplías la ventana de datos que un proceso lee, enumera todo lo que
consume esa ventana y comprueba que cada consumidor decide **qué reporta** por su
cuenta. Ampliar la lectura es barato; ampliar sin comprobarlo convierte un arreglo
en ruido en cinco sitios a la vez.

## 136. Treinta y cuatro alertas de seguridad pueden ser un paquete

El push devolvió el enlace de Dependabot del repositorio: 34 alertas abiertas, dos
de gravedad alta. Agrupadas por paquete, las treinta y cuatro eran **el mismo**:
`pypdf` en 6.1.3, y todas de ámbito `development`.

Leer «34 alertas» y leer «una dependencia desactualizada» llevan a dos reacciones
distintas, y solo la segunda es cierta. Es la misma regla que ya estaba escrita
para las pruebas ---«muchos fallos a la vez no son muchos fallos»--- aplicada a un
panel de seguridad.

**Regla**: ante un recuento de alertas, agrúpalo por paquete y por ámbito **antes**
de mirar la gravedad. El número que importa es cuántas dependencias hay que tocar
y cuántas de ellas llegan a producción; el total de avisos solo mide cuánto tiempo
llevan sin actualizarse.

## 137. Un control que consume lo que va a medir invalida la medición

Para probar que cambiar la contraseña cierra las sesiones abiertas, empecé
comprobando que la sesión valía antes: `renovar(perdido) == 200`. Y esa llamada
**gasta** el refresco, porque la rotación lo pone en la lista negra. El 409 de
después venía de ahí, así que la prueba pasaba en verde con el arreglo quitado.

Lo peor es que mi propio helper avisaba de esto en su docstring y lo pisé en la
línea siguiente.

**Regla**: cuando un recurso es de un solo uso ---un testigo que rota, una clave
de idempotencia, un enlace de un solo uso--- el control y la medición necesitan
**dos ejemplares**. Si el control usa el mismo, no estás midiendo tu arreglo:
estás midiendo el consumo.

## 138. Varias sustituciones en un script y un `assert` que aborta: se pierden todas

Un script con cuatro `sust()` seguidos y el `write` al final: el tercero falló el
`assert`, el script murió, y los dos cambios anteriores ---que habían impreso
«ok»--- **no se guardaron**. Vi el «ok» y di por hecho que estaban.

Lo detectó ruff con un «imported but unused»: el import se había aplicado en una
pasada posterior y la llamada que lo usaba se había perdido en la abortada.

**Regla**: si un script hace varias sustituciones, o escribe después de cada una,
o comprueba el resultado en el fichero y no en la salida del script. Un «ok»
impreso dice que la cadena se encontró, no que el fichero se haya guardado.

## 139. Una prueba de cobertura se saca del enrutador, no de una lista escrita a mano

La matriz de permisos de la vuelta 83 se barrió a mano y salió limpia. Al
convertirla en prueba, la tentación era escribir la lista de las 51 rutas dentro
del fichero: es más rápido y el verde sale igual.

Sería una prueba que **caduca el día que la escribes**. La ruta que abrirá un
hueco es la que alguien añada dentro de seis meses, y esa no va a estar en una
lista escrita hoy --- justamente porque nadie se acordará de añadirla.

Sacándolas de `get_resolver().url_patterns`, la prueba crece sola y una ruta
nueva sin permisos aparece el día que se escribe. Lleva un `assert len(rutas) >
40` para que, si algún día el enrutador se lee mal y devuelve cuatro rutas, salga
en rojo en vez de dar un verde sobre nada.

**Regla**: cuando una prueba afirma algo sobre *todo* un conjunto ---todas las
rutas, todos los modelos, todos los serializadores---, el conjunto se saca del
sitio donde vive, y se comprueba que no ha salido vacío. Una lista escrita a mano
no prueba «todos», prueba «estos».

## 140. Una vuelta sin hallazgo puede dejar un guard

El bucle pide sumar uno al contador cuando no se encuentra nada, y eso está bien:
una vuelta en blanco es información. Pero acabarla sin tocar nada desaprovecha el
barrido, que es la parte cara.

Los dos guards que más han rendido ---`test_entrada_malformada` con tres 500 y
`test_no_crece_con_la_plantilla` con dos N+1--- encontraron sus fallos **en
vueltas posteriores** a la que los escribió. En la suya salieron verdes.

**Regla**: si una vuelta barre algo ancho y sale limpia, el barrido se deja
escrito como prueba antes de cerrarla. El hallazgo llega después, y llega solo.

## 141. Quitarle un permiso a alguien puede ampliárselo

`visible_people` respondía «sin restricción» a una responsable sin departamentos,
para no romper el día uno de una empresa. El efecto lateral: **ceder tu
departamento a un compañero te daba la plantilla entera**. La operación que
parece restar permisos, sumaba.

Es la segunda vez que aparece el mismo patrón en esta auditoría ---la v73 fue la
primera, por la puerta del borrado--- y las dos veces el estado peligroso era el
mismo: *cero elementos asignados* interpretado como *sin límite*.

**Regla**: donde el alcance se calcula a partir de una lista, escribir a mano qué
pasa cuando la lista queda vacía, y probar los dos caminos hasta el vacío: el que
nunca tuvo nada y el que tenía y se le quitó. Casi siempre quieren respuestas
distintas, y el segundo es el que nadie prueba.

## 142. Al tapar una puerta, buscar las otras que llevan al mismo sitio

La v73 encontró que borrar un departamento ampliaba a su responsable y lo tapó
con un 409 en el `DELETE`. Correcto, y once vueltas después seguían abiertas dos
puertas al **mismo estado**, las dos con un `PATCH` que respondía 200.

Taparlo en el endpoint fue el error: el estado peligroso no lo producía el
borrado, lo producía *quedarse sin departamentos*, y a eso se llega por varios
caminos.

**Regla**: cuando un arreglo consiste en impedir una operación, preguntarse cuál
es el **estado** que se quería evitar y buscar todos los caminos que llevan a él.
Si hay más de uno, el arreglo va donde se lee el estado, no en cada puerta.

## 143. Un arreglo puede dejar mintiendo a un aviso que estaba bien

Al cambiar la regla del alcance, el aviso de Ajustes ---«no lleva ningún
departamento, así que ve a toda la empresa»--- pasó a decir **lo contrario** de lo
que ocurre en el caso más frecuente, y sin romper ninguna prueba: el texto era
una plantilla en el JSX, no una aserción.

**Regla**: después de cambiar una regla de negocio, buscar los textos que la
explican al usuario ---avisos, ayudas, `hint`, docstrings de lo que se muestra---
y comprobar uno por uno si siguen siendo verdad. Un `grep` del concepto, no del
código. Y si la respuesta depende de un estado que conoce el servidor, que la
mande él: recalcularla en la pantalla crea una segunda copia de la regla que se
quedará atrás en el siguiente cambio.

## 144. `objects.create()` no pasa por `full_clean`, así que una sonda puede medir lo imposible

Medí un doble cargo en el saldo de horas creando la ausencia con
`Absence.objects.create(...)`. El modelo prohíbe ese estado en `full_clean`, y
`create()` no lo llama: estaba midiendo algo que por la API no se puede crear.

**Regla**: una sonda que monta datos con el ORM está saltándose las validaciones
del modelo. Antes de dar por bueno un hallazgo montado así, crearlo **por el
endpoint real**. Si el endpoint lo rechaza, el hallazgo era del ORM, no del
producto --- y lo que hay que mirar entonces es con qué código lo rechaza.

## 145. Cuando un arreglo se hace «aquí también», queda un mecanismo sin arreglar

El serializer de ausencias replicaba a mano los validadores del justificante, con
un comentario diciendo por qué: sin ellos, `full_clean` lanzaba la
`ValidationError` de Django, DRF no la traducía y un fichero grande volvía como
**500**. Arreglaron ese caso.

El resto de reglas del modelo siguieron saliendo como traza durante todo ese
tiempo, y una de ellas era una regla con un mensaje escrito y bueno que nadie
llegó a ver nunca.

**Regla**: cuando un arreglo consiste en repetir algo en el sitio donde falló,
preguntarse cuál era el mecanismo que falló y si tiene más clientes. Un comentario
que empieza «los mismos validadores que lleva el modelo, porque si no...» está
describiendo un agujero general y tapando una de sus salidas.

## 146. Antes de reimplementar una regla, mirar si la que existe ya la sabe entera

Para arreglar los cuatro ojos escribí dentro de `four_eyes` la regla de quién
alcanza a quién: administradora sí, responsable si dirige el departamento. Se me
quedó fuera un caso ---la empresa donde nadie lleva ningún departamento y por eso
toda responsable ve a todos--- que **yo mismo había escrito dos vueltas antes**.

Lo cazó una prueba de las líneas rojas al ponerse roja. Delegando en `can_see` el
caso entra solo, y la regla vuelve a vivir en un sitio.

**Regla**: cuando una función necesita saber algo que otra ya decide, llamarla.
Una copia de una regla no nace mal, nace **incompleta**, y se queda atrás en el
siguiente cambio de la original. Si la copia parece necesaria por rendimiento,
medir primero: casi siempre son unas pocas filas.

## 147. Una prueba que se pone roja puede tener razón

Al romperse `test_an_administrator_cannot_either` la primera reacción fue leerla
como una prueba desfasada que había que reescribir ---que es lo que había hecho
con acierto en cuatro vueltas anteriores.

No lo era: defendía una línea que no se cruza y estaba señalando que mi arreglo
la aflojaba en un escenario. El hábito de reescribir la prueba se había vuelto
automático.

**Regla**: cuando una prueba se pone roja, leer su docstring **antes** de decidir
si sobra. Si describe un principio en vez de un detalle ---quién puede reescribir
el registro, qué no puede hacerse en masa---, la carga de la prueba está en el
cambio, no en ella.

## 148. Al cambiar un `msgid`, mirar de qué mensaje presta la traducción

Cambiar el texto del 409 de departamentos dejó tres catálogos marcados `fuzzy`, y
las tres traducciones prestadas eran inservibles de dos maneras distintas:

- **es** prestó la del mismo mensaje antes del cambio, que decía **lo contrario**
  de lo que ahora ocurre.
- **ca** y **gl** prestaron la de un mensaje **completamente distinto** --- el de
  retirar un centro de trabajo, hablando de festivos locales y husos horarios.

Compilar sin mirar habría dejado un aviso mintiendo en tres idiomas.

**Regla**: después de `makemessages`, leer cada `#, fuzzy` con su `#| msgid`
delante. Si la prestada es del mismo mensaje, se retraduce; si es de otro, se
**vacía**. Nunca quitar solo la marca.

## 149. Las sondas comparten base de datos con la suite de navegador

Mientras la tanda de Playwright corría, aproveché la espera para medir la vuelta
siguiente con `podman compose exec`. Evité escribir en `backend/` para no
despertar al recargador --- pasando el script por stdin--- y me quedé tan
tranquilo.

Pero las sondas **escriben en la misma base de datos**. La tanda pasó de once
minutos a más de cuarenta y ocho, y la corté sin resultado. El aviso del cuaderno
dice «no lances dos suites a la vez, comparten servidor y base de datos»: una
sonda no es una suite, y comparte exactamente lo mismo.

**Regla**: mientras corra una suite, la espera es espera. Leer código, escribir el
cuaderno y preparar la vuelta siguiente sí; ejecutar cualquier cosa contra la API
o la base, no. Si la espera se hace larga, es que hay que lanzar la suite antes,
no llenarla de compañía.

## 150. `pkill -f` alcanza a quien nombra el proceso, no solo al proceso

`pkill -f "playwright test"` mató la tanda **y** los tres vigilantes que la
esperaban, porque su línea de órdenes contenía esa misma cadena. Tres tareas de
fondo cayeron con 144 a la vez, y por un momento pareció que se había roto algo
más grande.

**Regla**: antes de un `pkill -f`, listar con `pgrep -fa` el mismo patrón y mirar
la lista. Y elegir un patrón que solo case con el proceso de verdad ---aquí
`node_modules/.bin/playwright test`--- en vez de la frase que también escribieron
quienes lo vigilan.

## 151. El código de salida es del último comando de la línea, no del que importa

Lancé la suite así:

    npx playwright test > log 2>&1; echo "salida: $?"; tail -3 log

y leí «exit code 0». Ese cero era del `tail`. La tanda tenía **dos pruebas
fallando**, y estuve un buen rato dando por bueno un verde que no existía ---y
diciéndoselo a Francisco.

**Regla**: nada detrás del comando cuyo resultado importa. Si hace falta algo más
en la misma línea, el código se guarda antes: `cmd > log 2>&1; echo "EXIT=$?" >>
log`. Y para juzgar una tanda, contar los estados del log ---`✓`, `failed`--- en
vez de fiarse del resumen o del código.

## 152. Cortar una tanda a mitad deja la empresa de demostración a medias

Las pruebas que guardan algo lo **restauran al final**: cambian «Horas extra al
año», comprueban, y lo devuelven a su valor. Al matar una tanda por la mitad, esa
restauración no llega a ocurrir.

La siguiente tanda encontró dos de esas pruebas rojas, y parecían un fallo de mis
cambios ---incluso pareció que un cambio del backend rompía dos pantallas. Con el
mismo árbol y el estado ya recolocado, las 26 del fichero pasan.

**Regla**: después de interrumpir una tanda, la siguiente no es fiable. Correr
primero los ficheros que tocan datos de la demo y verlos verdes antes de leer
nada como hallazgo. Y si dos pruebas de guardar-y-recargar caen a la vez, mirar el
estado de la demo antes que el diff.

## 153. Un `ModelSerializer` hereda los validadores del campo; un `Serializer` no

El validador de texto puesto en los campos del modelo funcionaba en el alta de
personas y no en las correcciones. La diferencia no era el servicio ni el
modelo: `EmployeeSerializer` es un `ModelSerializer` y arrastra los
`validators=[...]` de cada campo, mientras que `CorrectionRequestSerializer` es un
`serializers.Serializer` con los campos escritos a mano, que no heredan nada.

**Regla**: al añadir un validador a un campo de modelo, mirar por qué serializer
entra ese dato. Si es un `Serializer` a mano, hay que declararlo también ahí --- y
si el servicio crea con `objects.create()`, ese es el **único** sitio donde se va
a ejecutar.

## 154. Una prueba de carrera que no fuerza el orden no prueba nada

La prueba de las dos pestañas pasaba con el arreglo **y sin él**. `Promise.all`
sobre dos `page.evaluate` no hace que las dos peticiones colisionen: una acaba
antes, y como las pestañas comparten `localStorage` de verdad, la segunda leía ya
el token renovado por la primera. Es decir, la prueba montaba el caso bueno y
nunca el malo.

Se arregla haciendo el orden **determinista**, no probable: retrasar una de las
dos con `page.route` para que lea antes y llegue después.

**Regla**: en una prueba de carrera, el orden se impone, no se espera. Y la
comprobación obligatoria es la de siempre ---quitar el arreglo y verla roja---,
que aquí fue lo único que reveló que la prueba estaba vacía. Con quince rondas se
cazó la carrera de los fichajes (lección de la vuelta 79); con un retraso
explícito, esta.

## 155. Las sesiones compartidas del arranque tienen el refresco ya rotado

La prueba de las dos pestañas empezó fallando con `token_not_valid` en la
**primera**, lo que no tenía sentido. El motivo: usaba `storageState` de las
sesiones del arranque, y con la rotación activada ese refresco ya lo habían usado
otras pruebas de la tanda. No medía la carrera, medía un refresco en la lista
negra.

**Regla**: una prueba que va a **usar** el refresco ---renovar, cerrar sesión,
revocar--- no puede partir de una sesión compartida. Entra ella misma. Las
compartidas sirven para llegar a una pantalla, no para ejercitar el ciclo de vida
del testigo.

## 156. Un endpoint que solo declara renderers binarios no puede contar sus errores

`PDFRenderer` y `CSVRenderer` devolvían `data` tal cual, que es correcto para el
documento. Siendo los únicos declarados, también renderizaban los errores, y
`HttpResponse` con un diccionario recorre sus claves: **cinco bytes, `error`**.

Cuatro mensajes cuidadosamente escritos ---el tope de doscientas personas, el
rango invertido, «nadie trabajó en ese periodo», el formato de fecha--- no habían
llegado nunca a nadie. Y con `Content-Type: application/pdf`, así que el cliente
tampoco podía parsearlos.

**Regla**: en un endpoint que devuelve un fichero, probar también sus rechazos, y
mirar los **bytes** del cuerpo, no solo el código. Un renderer binario tiene que
distinguir el documento de un cuerpo de error y sacar el segundo como JSON,
corrigiendo el tipo de contenido.

## 157. Un parámetro que se ignora es peor que uno que se rechaza

El periodo se pide como `date_from`/`date_to` en los informes y como `from`/`to`
en las horas extra, del mismo producto. Lo desconocido se ignora, así que pedir un
año con el nombre del vecino devolvía **200 con los últimos treinta días**. Me
pasó a mí midiendo, y creí durante un rato que el informe anual de una empresa
tardaba una centésima de segundo.

**Regla**: cuando dos endpoints nombran distinto el mismo concepto, el que recibe
el nombre ajeno tiene que **fallar**, no responder otra cosa. Se rechaza en el
sitio común ---aquí el `FilterSet` del que heredan los listados--- y no endpoint
por endpoint. Y si un docstring nombra los parámetros, comprobar que dice los que
el código declara: este decía `from`/`to` desde antes del cambio de nombre.

## 158. La primera medición incluye el calentamiento

«200 personas, un mes, CSV» dio **9,69 s** la primera vez y **2,51 s** la
siguiente, con el mismo código y los mismos datos. La diferencia era la primera
petición del proceso: conexiones, cachés y catálogos aún sin cargar.

**Regla**: para un número que se va a escribir en el cuaderno, medir dos veces y
quedarse con la segunda. Una sola medición sobre un proceso recién arrancado
exagera, y un número exagerado en un cuaderno se convierte después en una
decisión mal fundada.

## 159. «Da de baja» y «borra» no son lo mismo, y una suite no puede limpiar lo que el producto conserva

La demo tenía 533 personas donde la semilla monta catorce, y parecía que las
pruebas no limpiaban. Limpian: de las 209 creadas hoy, **ninguna** quedó activa.
Lo que no pueden es borrarlas, porque `perform_destroy` **desactiva** ---para que
los fichajes sobrevivan, que es lo correcto en un registro de jornada.

Estuve a punto de anotar como fallo de la suite algo que era una decisión buena
del producto.

**Regla**: antes de acusar a la limpieza de una suite, comprobar qué hace de
verdad el borrado de ese recurso. Si el producto conserva por diseño, el sedimento
es el precio y lo que hace falta es un reinicio de la semilla entre sesiones, no
más limpieza en las pruebas. Y contar **activas**, no filas.

## 160. Un dato acumulado dice cuándo se arregló algo

Las cuatro personas de prueba que seguían activas eran todas del **14 de agosto**;
las 209 de hoy estaban todas retiradas. Esa fecha no era ruido: marcaba el día en
que la limpieza empezó a funcionar.

**Regla**: cuando aparece sedimento en una base de desarrollo, mirar la **fecha**
de cada resto antes de tratarlo como un problema vivo. Un residuo antiguo con
nada reciente detrás es la prueba de que aquello ya se arregló --- y ahorra
arreglar dos veces lo mismo.

## 161. `re.sub` reinterpreta los escapes de la cadena de reemplazo

Traduciendo catálogos, escapé los saltos de línea a `\n` literal y luego usé
`re.sub(patron, f'msgstr "{escapado}"', ...)`. `re.sub` volvió a convertir esos
`\n` en saltos reales, así que los `msgstr` quedaron partidos en varias líneas
sin comillas y **`msgfmt` dejó de compilar los tres catálogos**.

Se arregla pasando el reemplazo como función ---`lambda _m: nuevo`---, que no
interpreta nada.

**Regla**: en `re.sub`, todo reemplazo que pueda contener `\\` va como función.
Y después de tocar un `.po` a mano, **compilar antes de seguir**: un catálogo roto
no da error hasta que alguien lo compila, y mientras tanto todo parece bien.

## 162. Antes de concluir de un `grep`, mirar si lo has truncado

Concluí que `propose_correction` no tenía ningún endpoint ---una pieza entera
escrita y desconectada, que es el patrón que más ha rendido en esta auditoría---
porque el `grep` solo la mostraba en `seed_demo.py`. La llamada real estaba en la
línea 195 de las vistas: la había cortado con `head -4`.

Estuve a punto de escribir en el cuaderno un hallazgo grande que no existía.

**Regla**: un `head` sobre un `grep` sirve para orientarse, no para concluir.
Antes de afirmar «esto no se llama desde ningún sitio», repetir sin truncar y
contar las apariciones. Lo mismo vale para `count()` en un script: `assert
count == 1` falló por haber **dos** sitios, y ese assert evitó un cambio a medias.

## 163. Conservar una fila y conservar su fichero son dos decisiones distintas

Al cambiar el borrado de una solicitud por un estado `CANCELLED`, se rompieron las
pruebas de la vuelta 45 ---el justificante quedaba huérfano en el almacén. La
tentación era ajustar esas pruebas: la fila ahora se queda, luego el fichero
también.

Su docstring decía lo contrario y tenía razón: un justificante suele ser un dato
del art. 9, y quien retira su solicitud está diciendo que no quiere que siga ahí.
Las dos cosas se pueden cumplir a la vez, y hay que cumplirlas: **queda la
solicitud, no queda el documento**.

**Regla**: al pasar de borrar a marcar, separar qué se conserva por trazabilidad
de qué se borraba por minimización. Casi nunca es lo mismo, y la prueba que se
rompe suele estar defendiendo la segunda.

## 164. El mismo `save(update_fields=[...])` aparece en varias transiciones

Un `assert count == 1` falló al insertar código tras
`absence.save(update_fields=["status", "approved_by", "resolved_at", "updated_at"])`:
la línea es **idéntica** en rechazar y en cancelar, porque las transiciones se
escriben igual.

**Regla**: para editar dentro de una función concreta, acotar primero al bloque
---de `def esa` a `def la_siguiente`--- y sustituir ahí. Buscar la línea en todo el
fichero encuentra a sus hermanas, y en el mejor caso aborta; en el peor, cambia la
transición equivocada.

## 165. Un dato de hoy aplicado a un hecho de entonces reescribe el pasado

El informe leía cada marca UTC con `employee.tzinfo`: el huso del centro **actual**
de la persona. Retirar ese centro, cambiarle el huso o mudar a la persona movían
sus horas de mayo una hora, en el documento del art. 34.9. Y el hash de integridad
seguía cuadrando, porque la fila no cambiaba --- cambiaba cómo se leía.

**Regla**: en un registro con valor probatorio, todo lo que hace falta para
**interpretar** un hecho se congela con el hecho, no se consulta al presente.
Huso, tarifa, jornada pactada, redondeo: si vive en una tabla que alguien puede
editar, el asiento de hace un año se lee distinto mañana. El criterio es el mismo
que ya aplicaba el hash al contenido.

## 166. «Expuesto en la API» no es «guardado»

La vuelta 70 puso el huso en cada fichaje, y al ver el campo dije que esto ya
estaba resuelto. Lo estaba a medias: era un `SerializerMethodField` derivado del
centro actual, así que se movía con la empresa igual que el informe.

**Regla**: cuando un campo aparece en una respuesta de la API, mirar si es una
columna o un método antes de contar con él para nada que tenga que durar. Un
`SerializerMethodField` es una vista del presente; solo una columna congela el
pasado.

## 167. Distinguir el hecho de la regla antes de decidir qué se congela

El huso con el que se vivió una hora es un **hecho**: se congela con el fichaje y
listo. «La pausa cuenta como tiempo de trabajo» es una **regla de cómputo del
convenio**: cambia de verdad, y congelarla sin más impediría aplicar un convenio
nuevo.

Los dos producían el mismo síntoma ---el informe de un mes cerrado cambiaba--- y
piden arreglos distintos: uno es una columna, el otro son reglas con fechas de
vigencia y una decisión sobre desde cuándo aplican.

**Regla**: ante un dato que reescribe el pasado, preguntar primero si es un hecho
o una norma. Si es un hecho, se guarda con el hecho. Si es una norma, hace falta
vigencia temporal, y **eso no lo decide quien audita**: se mide, se escribe con
cifras y se deja la decisión a quien lleva el producto.

## 168. Nunca traducir cadenas de una palabra

Puse `_("yes")` y `_("no")` como valores de una tabla. Al regenerar catálogos,
**`no` venía traducido como «nota»**, y en catalán y gallego los dos valores
opuestos ---«counts as working time» y «does not count»--- heredaron la **misma**
frase: en uno de los dos casos el documento habría dicho lo contrario de lo que
pasa.

**Regla**: los `msgid` de una o dos palabras se prestan traducciones de cualquier
otro contexto y son indistinguibles para quien traduce. Usar la frase entera
---«no computa como trabajo efectivo»--- aunque sea más larga. En un documento que
se entrega, una palabra mal prestada cambia lo que dice.

## 169. Lanzar la suite justo después de editar el backend la hace fallar en el arranque

Tercera vez hoy, y cada una por un sitio distinto: la tanda arrancó mientras el
recargador de Django estaba reiniciando por mis últimas ediciones, y el **setup de
la sesión** agotó sus 120 s esperando el token, con «browser has been closed».
Parecía un fallo del cambio; relanzada sin tocar nada, la misma sesión pasa en
**2,4 s**.

Las tres veces el síntoma engañaba: la primera pareció que un cambio del backend
rompía dos pantallas, la segunda que la suite iba cuatro veces más lenta, esta que
el login estaba roto.

**Regla**: después de tocar el backend, esperar a que responda antes de lanzar la
tanda ---un `curl` al API sirve--- y ante un fallo en el **arranque** (sesiones,
login, timeouts largos) relanzar limpio **antes** de investigar. Un fallo de
arranque casi nunca es del cambio; un fallo en una prueba concreta casi siempre sí.

**Y vale igual para el frontend.** Cuarta vez, ahora por Vite: lancé la tanda
justo después de restaurar un `.jsx` y cayeron tres pruebas ---dos descargas con
timeout de 30 s y una pantalla «not found»--- que aisladas dan 24 verdes. Lo que
lo delató fue medir el servidor: el informe que la descarga esperaba se generaba
en **0,41 s**, así que el timeout no era suyo. Si el backend responde rápido y aun
así la prueba espera treinta segundos, el que está reconstruyendo es el otro lado.

## 170. Una prueba que actúa sobre «los primeros de la lista» falla cuando cambia la lista

`12-acciones-masivas` marcaba las **tres primeras** casillas de personas y las
cruzaba con las tres primeras de la API. Aislada pasa siempre; en la tanda
completa esperaba 3 movidas y encontraba 2, y rompía además a la prueba siguiente
---que buscaba a alguien por su nombre y se lo habían llevado.

La causa estaba dos vueltas atrás: dos cuentas de prueba apellidadas **«Bloque»**
se habían quedado activas y el orden alfabético las ponía primeras.

**Regla**: una prueba que **escribe** no elige sus sujetos de una lista compartida.
Crea los suyos, actúa sobre ellos por nombre propio y los retira. «El primero de
la lista» es una dependencia oculta del estado de toda la base.

## 171. Un residuo inofensivo lo es hasta que ordena primero

En la vuelta 90 conté cuatro cuentas de prueba activas de un mes atrás y las
declaré sedimento histórico sin consecuencias: la limpieza ya funcionaba y el
producto no borra a propósito. Las dos cosas eran ciertas y la conclusión no.

Cuatro vueltas después rompieron la suite, porque su apellido ---«Bloque»--- las
colocaba al principio del orden y se colaban en las pruebas que actúan sobre «los
primeros».

**Regla**: al declarar inofensivo un residuo, mirar **por dónde ordena** y quién lo
lee. Un dato de sobra en el sitio equivocado del orden no es sedimento, es una
trampa con fecha. Si se puede retirar sin perder nada ---dar de baja una cuenta de
prueba--- se retira, aunque parezca inocuo.

## 172. Dos lectores del mismo ajuste con dos resoluciones distintas divergen en el caso raro

El tope de jornada abierta se resolvía con `getattr(rules, ..., None) or DEFAULT`
al fichar y con el campo a pelo en el informe. Para cualquier valor normal dan lo
mismo; con **cero**, uno leía 16 y el otro 0, y un turno de noche bien fichado
aparecía en el documento como «entrada sin salida» mientras la pantalla lo daba por
bueno.

El `or DEFAULT` no era el fallo: era la pista. Un valor que un lector trata de
forma especial y el otro no es una divergencia esperando el dato que la active.

**Regla**: si dos sitios leen el mismo ajuste, uno solo lo resuelve y el otro le
pregunta ---aunque eso obligue a hacer pública una función privada de otra app. Y
al ver un `or DEFAULT` o un `?? valor`, buscar quién más lee ese campo sin esa red.

## 173. Probar el estado imposible escribiéndolo por debajo de la validación

El suelo nuevo impide poner el tope a cero, así que la prueba de la divergencia no
podía crear el caso por la API. Escribirlo con `queryset.update()` ---que se salta
validadores y `full_clean`--- sí, y es lo correcto aquí: **así llegaría un dato
heredado** de antes del suelo, o de una migración a medias.

**Regla**: cuando se añade una validación, la prueba del comportamiento con el
dato malo se monta por debajo de ella. Si no, el arreglo del suelo tapa la prueba
del otro arreglo y se pierde la cobertura del caso que de verdad va a aparecer en
una base con años.

## 174. Una prueba que escribe tampoco puede compartir las fechas

Tercera vez en dos vueltas, y las tres por la misma raíz con distinta cara: una
prueba que escribe compartía sus **sujetos** con las demás (las tres primeras
personas de la lista) y otra compartía sus **fechas** (el 14 y el 15 de diciembre,
fijos).

Con fechas fijas, la ausencia que la prueba deja adrede sin resolver choca con la
que dejó la tanda anterior en cuanto una queda aprobada --- y una aprobada no se
puede cancelar, así que la limpieza no se la lleva nunca.

**Regla**: lo que una prueba escribe lleva su marca en **todo** lo que la
identifica: el nombre de los sujetos y también el día. Si un dato tiene que estar
en un mes concreto porque la navegación depende de él, se varía el día. Y si su
limpieza puede fallar por diseño ---aquí, porque el producto no deja cancelar lo
resuelto, y hace bien--- entonces no basta con limpiar: hay que no chocar.

## 175. Una comprobación con umbral solo ve el fallo cuando hay bastantes filas

La prueba de accesibilidad avisa a partir de **tres** rótulos iguales, y con razón:
dos «Cancelar» de dos diálogos son legítimos. La consecuencia es que un fallo real
---botones de fila que no dicen de qué fila son--- queda invisible mientras la
lista tenga dos elementos. La pantalla de centros lo tuvo así desde siempre, con
los dos centros de la semilla, hasta que una prueba dejó un tercero.

**Regla**: una comprobación con umbral no dice «esto está bien», dice «esto no
tiene bastantes filas todavía». Para saber el alcance, bajar el umbral en una
**sonda** ---no en la prueba--- y leer el inventario: ahí salen los latentes, y
alguno resulta no ser latente sino ya roto en una pantalla que nadie mira.

## 176. Antes de creer una lista de pantallas cubiertas, comprobar qué falta

`/panel/cuadrante` tiene doce botones «Asignar» idénticos, muy por encima del
umbral, y la prueba de accesibilidad no falla: esa pantalla **no está en su
lista**. Lo mismo con `/panel/aplicaciones`.

Una prueba que recorre «todas las pantallas» recorre las que alguien escribió a
mano, y las que se añadieron después no entran solas.

**Regla**: cuando una prueba itera sobre una lista literal de rutas, comparar esa
lista con el enrutador de verdad ---como hace `test_la_matriz_de_permisos`, que
saca las rutas de `get_resolver()`. Si la lista se escribe a mano, lo que no está
en ella no está probado, y eso no se nota nunca.

## 177. Un nombre descriptivo no basta: tiene que ser **distinto**

El primer intento de nombrar los botones del cuadrante puso el turno y a quién
cubre --- descriptivo, correcto, y seguía fallando: cinco botones se llamaban
«Asignar el turno de 07:00 a 15:00 que cubre a Paco Trillo», porque era el mismo
turno de la misma persona en cinco días distintos.

**Regla**: al dar nombre accesible a los mandos de una lista, el criterio no es
«¿describe lo que hace?» sino «¿hay dos iguales?». Meter en el nombre lo que
**varía entre filas**, que casi siempre incluye la fecha --- y suele estar ya
pintado en la fila, así que se calcula una vez y se usa para las dos cosas.

## 178. «La máquina va justa» es una explicación, y hay que comprobarla como cualquier otra

Al ver que cada tanda fallaba en una prueba distinta lo atribuí a la carga de la
máquina tras horas de corridas. Sonaba razonable y era falso: `uptime` daba **4,3
de media con 32 núcleos**, o sea un octavo de la capacidad.

Escribir «es el entorno» sin el dato es lo mismo que escribir «es flaky»: cierra
la investigación sin haberla hecho, y en un cuaderno de auditoría queda como
conclusión.

**Regla**: una causa ambiental ---carga, memoria, red--- se mide antes de
escribirla, con el mismo rigor que un hallazgo del producto. Si el número no la
sostiene, lo honesto es «no sé por qué» más los datos que descartan lo que ya se
ha mirado.

## 179. Restaurar al final del test no restaura cuando el test falla

Dos pruebas cambiaban un ajuste **de la empresa entera** y lo devolvían a su valor
en la última línea. Cuando fallaban a mitad, la última línea no se ejecutaba y la
empresa de demostración se quedaba con el ajuste cambiado --- apareció con el tope
de jornada abierta en 26 en vez de 16, residuo de una corrida rota horas antes,
rompiendo a las pruebas de Ajustes de las corridas siguientes.

Así, **un fallo suelto fabrica los siguientes**, y cada corrida parece caer en un
sitio distinto sin motivo.

**Regla**: lo que una prueba cambia fuera de sí misma se devuelve en `finally`, no
al terminar. Y **por la API**, no repitiendo el gesto en la pantalla: si lo que
falló fue la pantalla, volver a pulsar «Guardar» tampoco va a funcionar. Mejor aún
si además se limpia **al empezar**, que es lo único que sobrevive a que alguien
mate el proceso.

## 180. Un comentario que describe el síntoma señala el mecanismo sin arreglarlo

`08-formularios-gestion` llevaba escrito: «si una tanda anterior se cortó antes de
restaurar, el valor ya era 72, no había nada que guardar y el botón se quedaba
desactivado». Alguien lo sufrió, lo entendió bien, y lo resolvió **eligiendo un
valor distinto del actual**.

El síntoma desapareció de esa prueba y el mecanismo siguió: el ajuste seguía
quedándose sucio y rompiendo a otras.

**Regla**: un comentario que empieza «si una tanda anterior...» o «como a veces
pasa que...» está describiendo un mecanismo, no una peculiaridad de esa prueba.
Antes de esquivarlo ahí, preguntarse a quién más alcanza --- y si la respuesta es
«a cualquiera que use este recurso compartido», el arreglo va en el mecanismo.

## 181. Contar lo que hay es más rápido que forzar el fallo que lo produce

Estuve tres intentos montando `mock`s para provocar que un fichero quedara
huérfano: parchear el almacén, romper el PDF a mitad del lote, hacer fallar el
rastro. Dos de los tres ni siquiera llegaron a aplicarse ---el atributo no
existía, el nombre no era ese.

La comprobación que sirvió fue mirar el disco: **4.403 ficheros, 12
referenciados**. En una consulta estaba el hallazgo, y además con su magnitud, su
reparto por días y sus nombres, que fue lo que señaló el camino real.

**Regla**: cuando se sospecha que algo deja residuos, contarlos antes de intentar
fabricar uno. El estado acumulado de una base de desarrollo es un registro de todo
lo que ha fallado durante meses, y responde de golpe si el fallo existe, cuánto
pasa y desde cuándo.

## 182. Un `FileField` que se reemplaza no borra el fichero anterior

Django asigna el nuevo y deja el viejo en el almacén. Una señal `post_delete`
---que es lo que suele escribirse--- cubre el borrado de la fila y **no** cubre
esto, que es el camino más frecuente: subir el documento bueno después del
equivocado.

**Regla**: al proteger los ficheros de un modelo hay que cubrir los dos caminos, y
el de la sustitución va en `pre_save` comparando el nombre anterior con el nuevo.
Solo ese campo, solo cuando cambia, y en `on_commit` como el otro.

## 183. Una rotación de credenciales sin purga es una tabla que crece para siempre

`ROTATE_REFRESH_TOKENS` deja dos filas por renovación: la nueva registrada y la
vieja en la lista negra. Con accesos de quince minutos son treinta por persona y
jornada, unos dos millones al año en una empresa mediana. Nadie las recogía: el
planificador tenía dos trabajos y ninguno era `flushexpiredtokens`, que simplejwt
trae hecho.

El detalle que lo convierte en algo más que espacio en disco: cada fila dice **de
quién** era la sesión y cuándo empezó.

**Regla**: al activar rotación o lista negra de credenciales, programar su purga en
el mismo cambio. Y al revisar un sistema, contar las tablas que crecen y
compararlas con la lista de trabajos programados --- lo que no aparezca en esa
lista no se recoge nunca.

## 184. Un respaldo «si no hay dato, usa el actual» no vale cuando el actual es lo que cambió

El versionado de reglas leía la vigencia del día y, si no encontraba ninguna, caía
a las reglas de hoy. Parecía razonable y no servía de nada: declarando que la
pausa cuenta desde julio, abril seguía moviéndose, porque abril no encuentra
vigencia y hereda justo el valor que se acababa de cambiar.

El arreglo es anclar el pasado en el momento de cambiarlo: dejar constancia de
cómo se contaba hasta entonces. Y **el ancla tiene que cubrir todo lo anterior**
--- con la fecha de alta de la empresa no bastaba, porque una empresa puede
haberse dado de alta después del periodo que se consulta.

**Regla**: al versionar algo por fecha, el respaldo no puede ser «el valor
vigente», porque el caso que hay que proteger es precisamente aquel en que ese
valor acaba de cambiar. O se ancla el pasado al primer cambio, o el versionado es
decorativo. Y se comprueba con un periodo **anterior** al primer cambio, que es
donde falla.

## 185. Validar el valor antes de exigir el trámite

Al pedir la fecha de efecto antes de validar el número, poner un tope de cero
contestaba «falta la fecha de efecto»: hacía declarar una fecha de convenio para
un valor que se iba a rechazar igual dos líneas después.

**Regla**: cuando una operación gana un requisito nuevo ---una fecha, un motivo,
una confirmación---, ese requisito se comprueba **después** de que lo demás sea
válido. Si no, el primer mensaje que ve alguien es el del trámite y no el del
error que de verdad tiene.

## 186. Un requisito nuevo en la API rompe la pantalla que ya existía

Al exigir la fecha de efecto para cambiar cómo se cuenta el tiempo, el backend
quedó impecable ---1.147 pruebas en verde--- y la pantalla de Ajustes dejó de
guardar: seguía mandando el formulario sin la fecha y el servidor lo rechazaba
con un 400 que nadie enseñaba.

Lo cazó una prueba de navegador. Ninguna del backend podía: todas mandaban la
fecha porque yo acababa de escribirlas.

**Regla**: cuando una operación gana un requisito, buscar **quién la llamaba
antes** ---pantallas, integraciones, comandos--- y actualizarlos en el mismo
cambio. Una suite de backend en verde no dice nada sobre eso, porque sus pruebas
se escriben ya sabiendo el requisito nuevo.

## 187. Una restauración que falla en silencio es peor que no tener restauración

Al exigir la fecha de efecto, el `finally` que devolvía el tope a su valor dejó de
funcionar: mandaba el PATCH sin fecha, el servidor contestaba 400 y **nadie mira
lo que devuelve un `finally`**. El ajuste se quedó en 26 y la corrida siguiente no
tenía nada que cambiar, así que fallaba en un sitio que no tenía que ver.

Arreglé esa misma restauración en la vuelta 97 y la volví a romper en la 100 por
otra vía.

**Regla**: una restauración se comprueba como cualquier otra llamada ---`expect`
sobre su código de respuesta--- porque es la única parte del código que nadie mira
cuando funciona y todos sufren cuando no. Y al añadir un requisito a una
operación, buscar quién la llama **desde las propias pruebas**, que es donde menos
se busca.

## 188. Un prefijo de familia no es un nombre propio

La vuelta 94 arregló una prueba que actuaba sobre «las tres primeras personas de
la lista» haciendo que creara las suyas --- y las localizaba por «Masiva Zzz», el
prefijo común a todas las que crea esa prueba **en todas las tandas**. Con
cincuenta y una acumuladas, marcaba tres de otra corrida.

El mismo fallo que vino a arreglar, con otra cara: elegir sujetos de un conjunto
compartido.

**Regla**: lo que identifica a un sujeto de prueba tiene que ser único **por
ejecución**, no por familia. Si el nombre lleva la marca de la tanda, hay que
usarla entera en el selector: `Masiva Zzz p8x3k 0`, no `Masiva Zzz`.

## 189. Un guard que pasa a la primera todavía no es un guard

La comprobación de residuos de la vuelta 101 se puso verde nada más escribirla.
Verde era el resultado correcto ---acababa de limpiar la base a mano--- y por eso
mismo no demostraba nada: una comprobación que mira el sitio equivocado también
sale verde.

Al plantar un centro y un departamento con marca reconocible y volver a correrla,
falló nombrando exactamente esos dos. Eso sí lo demuestra.

**Regla**: una comprobación nueva no está terminada hasta que se la ha visto
**fallar por lo que tiene que fallar**. Planta el caso, mírala ponerse roja, lee
el mensaje ---tiene que decir qué encontró---, retira el caso. Es la lección 143
aplicada al código que uno mismo acaba de escribir, que es donde más cuesta
acordarse.

## 190. Una respuesta de la API es una página, no la lista

La misma comprobación pedía `/employees/?is_active=true` y recorría `results`
como si fueran todas. Con veintiuna personas activas lo eran, así que pasaba. En
cuanto pasaran de cincuenta ---`PAGE_SIZE` es 50--- habría estado mirando las
cincuenta primeras y **dando por limpio lo que no llegó a ver**, justo cuando el
sedimento que busca ya se había acumulado.

Peor: pedir `page_size=1000` tampoco basta. La API tope ese valor, y sobre las
709 personas de la base la lista seguía viniendo partida. Solo se supo porque la
comprobación miraba `next`.

**Regla**: al recorrer una lista de la API en una prueba, o se filtra en el
servidor hasta que quepa, o se pagina de verdad. Y en cualquier caso se
comprueba `next`: si viene, la prueba tiene que fallar diciendo que no lo ha
visto todo, nunca callarse.

## 191. Lo que distingue un residuo de la semilla tiene que ser estrecho

El primer patrón para reconocer lo que crean las pruebas era `p` seguida de seis
caracteres. Cazó a `parcial@demo.local`, que es de la semilla y tiene que estar
ahí.

Un guard que señala lo que es correcto no se arregla: se ignora, y a la semana
está desactivado. La marca real lleva doce caracteres o más ---el instante en
base 36 más cuatro al azar---, así que el patrón pide doce.

**Regla**: antes de dar por bueno un patrón que separa «lo mío» de «lo del
producto», pásale la lista de lo que **no** debe cazar. Un falso positivo en un
guard cuesta más que el fallo que evita.

## 192. Un documento de carencias envejece al revés de lo que se teme

`docs/cobertura-legal.md` enumera lo que el producto **no** cubre. El miedo
natural es que se quede corto ---que oculte un hueco---, y resultó al revés: la
fila de horas extraordinarias decía que el tope anual del art. 35.2 «no se
contrasta con lo trabajado» cuando lleva tiempo contrastándose, calculado en
`overtime_used()`, servido por la vista y avisado en pantalla citando el
artículo.

Se entiende: la vuelta que implementa algo escribe el código y las pruebas, y la
tabla que decía «falta» se queda como estaba. Nadie la vuelve a leer porque
nadie duda de una lista de carencias.

Cuesta más de lo que parece: sobre esa tabla se decide **qué construir después**,
y una fila desfasada manda a alguien a implementar lo que ya existe.

**Regla**: una tabla de cobertura se verifica **fila a fila contra el código**,
no se lee. Y al implementar algo que una tabla daba por ausente, la tabla entra
en el mismo cambio que el código. De catorce filas comprobadas así en la vuelta
101, trece eran correctas y una llevaba meses mintiendo.

## 193. Un ayudante que avisa de para qué no sirve se está usando justo para eso

`rows()` en `services/api.js` lleva escrito encima: «solo para endpoints que
responden con todo; usarlo en uno paginado tira `count` y `next` --- que es
exactamente lo que pasaba, y hacía que los fichajes, las personas y el rastro
enseñaran las cincuenta primeras filas y no dijeran nada del resto».

El aviso es de cuando se arreglaron esas tres pantallas. Quedaron **cinco
llamadas más** al mismo ayudante sobre endpoints igual de paginados
---departamentos, centros, festivos, tipos de permiso y patrones de turno---, y
ahí siguieron. Ninguna vista del backend desactiva la paginación, así que la
condición del comentario no la cumplía nadie.

Duele más en un catálogo que en una lista: una lista con `Pager` dice «1-50 de
1.284», pero un catálogo llena un **selector**, y lo que no se cargó no se puede
elegir. No hay error, la opción no está.

**Regla**: cuando arregles un fallo en tres sitios y escribas el aviso, **cuenta
los que faltan en el mismo cambio**. Un comentario que dice «no uses esto así»
es una lista de deberes pendiente, no una protección: `grep` de quién llama al
ayudante y decidir uno por uno. Y al revés, al auditar: **los comentarios que
avisan de un mal uso son el mejor sitio donde buscar ese mal uso**.

## 194. La suite miente según la hora a la que se corra

La tanda de backend llevaba semanas en verde y a las 00:10 falló una prueba del
PDF. No era frágil: fallaba **siempre**, aislada, tres de tres. Y con el árbol
limpio en el commit anterior, también.

La causa es de dos husos. El contenedor va en UTC; la empresa de la prueba, en
`Europe/Madrid`. El fixture fichaba con `register_punch()` ---que guarda el día en
la hora de la empresa, el 27--- y pedía el informe de `date.today()` ---la fecha
del contenedor, el 26---. Entre medianoche y las dos de la madrugada en verano
son días distintos: el informe salía de un día sin fichajes y la fila que la
prueba marcaba como discrepada no llegaba a la hoja.

Lo llamativo es que **el producto ya lo tenía resuelto**. `apps/common/clock.py`
existe precisamente para esto, dice que `date.today()` es la trampa y que «se
coló cuatro veces antes de que este módulo existiera», y un comentario de
`attendance_api` celebra haber quitado «el último que quedaba en todo el código».
Las pruebas, que no son código de producción, se quedaron con la trampa: **28
usos**, nueve ficheros de los cuales la mezclan con hora local.

**Regla**: una prueba que crea datos con la hora de la empresa y los consulta con
la del servidor solo funciona diecinueve horas de cada veinticuatro. Si un
fixture ficha, el «hoy» que consulte tiene que ser `local_today(empresa)`. Y
cuando un módulo del producto documenta una trampa, **las pruebas no están
exentas**: son el sitio donde más fácil sobrevive, porque nadie las lee buscando
eso.

**Corolario que vale su peso**: pasada la medianoche es cuando esta clase de
fallo se puede ver. Correr las dos suites enteras dentro de esa franja es una
comprobación que a las once de la mañana no se puede hacer.

## 195. Una espera por reloj es una prueba que solo pasa cuando la máquina va sobrada

Dos pruebas de acciones masivas fallaron en la tanda completa. Aisladas pasaban.
Con los doce primeros ficheros ---ciento veinticuatro pruebas--- también pasaban.
Solo caían dentro de las doscientas ochenta y tres.

La causa estaba escrita a la vista: `await page.waitForTimeout(2500)` entre
pulsar «mover» y preguntar por el resultado. Dos segundos y medio bastan casi
siempre; al final de una tanda larga, no. Y el fallo no se parece en nada a su
causa: decía «esperaba 3, encontré 0», que suena a que no se movió nadie, cuando
lo que pasaba es que **todavía** no se había movido.

Hay **42 esperas así** repartidas en veintiún ficheros de la suite.

**Regla**: entre una acción y su comprobación no va un número de milisegundos, va
la condición. `expect.poll` pregunta hasta que la respuesta llegue y falla con
tope: es más rápido cuando todo va bien y no miente cuando la máquina va cargada.

**Y el diagnóstico**: si una prueba pasa aislada y falla en tanda, la primera
sospecha es la espera fija, no el estado compartido. El estado compartido suele
reproducirse también con un subconjunto; la espera fija necesita la tanda entera
para manifestarse.

## 196. Un guard convierte cuatro fallos en dos, y el resto en un diagnóstico

La tanda dio cuatro rojos: dos pruebas de acciones masivas y dos del guard de
residuos. No eran cuatro problemas: eran dos, y sus consecuencias. Las pruebas
fallaron a mitad y dejaron puestas tres personas y dos departamentos; el guard
los nombró.

Nombrarlos es lo que resolvió el diagnóstico en un minuto: **los cinco residuos
llevaban la marca de la misma tanda**. Si hubieran sido de tandas distintas,
habría sido sedimento acumulado ---la hipótesis con la que empecé---. Al ser de
una sola, quedaba descartado y la causa tenía que estar dentro de esa corrida.

**Regla**: un guard de estado no vale solo por lo que impide, sino por lo que
**dice**. Que liste los elementos con su marca de origen, y no solo su número,
es lo que convierte «algo dejó basura» en «esta corrida, y por tanto la causa es
de aquí dentro».

## 197. Media corrección esconde el resto mejor que el fallo original

`/shifts/today/` preguntaba por `date.today()`, la fecha UTC del contenedor.
Alguien lo vio, lo cambió por `local_today(request.user)` y dejó el porqué
escrito: «*their today*: `date.today()` es la fecha UTC del contenedor, que es
ayer para toda España entre medianoche y la una».

Todo cierto, y la mitad del problema. El huso quedó bien; la **unidad**, no. La
unidad no es el día natural sino la jornada, que es con lo que mide el Estatuto
---y el propio repositorio tiene un módulo, `apps/punches/workday.py`, que lo
explica con sus artículos---. Quien entra a las 22:00 y sale a las 06:00 sigue en
la jornada de ayer, y a la una de la madrugada esta vista contestaba por la de
hoy. Medido:

    /punches/today/   state=WORKING       worked=6398s
    /shifts/today/    state=NOT_STARTED   worked_minutes=0

La misma persona, el mismo instante, las dos pintando la misma pantalla.

Lo que hace esto difícil de encontrar no es el código: es el **comentario**. Un
`date.today()` pelado se caza con `grep`. Un `local_today` con tres líneas
explicando la medianoche se lee y se pasa de largo, porque parece el sitio donde
alguien ya pensó en esto.

**Regla**: al arreglar un fallo de fecha, pregunta las dos cosas por separado
---**qué reloj** y **qué unidad**---, porque se arreglan por separado y la
primera tapa a la segunda. Y al auditar: un comentario que explica un arreglo
parcial es de los sitios donde más tiempo sobrevive un fallo, justo porque
tranquiliza.

## 198. Hay comprobaciones que solo se pueden hacer a cierta hora

El fallo de arriba se encontró a la una de la madrugada, y no por casualidad: es
la única franja en la que existe. Lo mismo pasó con la prueba del PDF de la
vuelta anterior, que llevaba semanas en verde y cayó a las 00:10.

**Regla**: cuando se trabaje pasada la medianoche, aprovecharlo. Correr las dos
suites enteras dentro de la franja, y mirar el producto ---no solo las pruebas---
preguntándose qué día dice ser. A las once de la mañana esa comprobación no se
puede hacer, y ninguna cantidad de repasos la sustituye.

**Y el corolario para las pruebas nuevas**: congelar el tiempo. `freezegun` ya
está en el proyecto y se usa con el patrón `freeze_time("...22:30:00")  # 00:30
en Madrid`. Una prueba que solo dice la verdad de madrugada es lo que dejó pasar
esto durante meses.

## 199. Dos `datetime` de la misma zona se restan como reloj de pared

Python lo hace a propósito y está documentado: si los dos operandos comparten
`tzinfo`, se ignora y la resta es ingenua. Con `zoneinfo` eso significa que

    datetime(2026, 10, 24, 22, 0, tz=Madrid) → 06:00 del día siguiente

da ocho horas **también** la noche en que los relojes se atrasan, cuando de
verdad pasaron nueve. La única forma de que la cuenta sea real es convertir a
UTC antes de restar.

El proyecto ya lo sabía. `apps/common/dst.py` existe para esto, lo explica con
esas palabras y trae `real_gap()` resuelto. Lo importaban `overtime.py`,
`shifts/services.py` y `coverage.py`.

**No lo importaba `reports/services.py`**, que es el que genera el documento del
art. 34.9. Restaba dos horas ya convertidas a la zona local, así que las dos
noches del año que no duran veinticuatro el informe declaraba ocho horas: una
menos de las trabajadas en octubre, una más en marzo. La pantalla daba la cifra
correcta porque `build_day_status` resta instantes tal como salen de la base
---en UTC, que no cambia de offset---. **Dos caminos para el mismo dato, y solo
uno pasaba por el módulo que sabía de esto.**

**Regla**: una resta de fechas solo es de fiar si los dos lados están en UTC.
Cuando el código convierte a hora local para *mostrar*, esa conversión no puede
alimentar además la aritmética: se muestra lo local y se resta lo absoluto.

**Y el corolario que vale para auditar**: un módulo que documenta una trampa
protege únicamente a quien lo importa. La lista de quién lo importa es corta y
se saca con un `grep`; la lista de quién **debería** importarlo es la que hay que
escribir a mano, y es donde estaba el fallo.

## 200. Cuando el código afirma algo de sí mismo, compruébalo

En `reports/services.py`, tres líneas encima del fallo, había escrito esto:

> `build_day_status` asks the same question, and the two must agree: the figure
> on screen and the figure in the document are the same day.

Lo decía y no se cumplía: en la noche del cambio de hora una decía nueve y la
otra ocho. El comentario no era mentira cuando se escribió --- describía una
intención --- pero nadie había puesto una prueba que la sostuviera, así que
quedó como afirmación.

**Regla**: cuando un comentario afirme que dos cosas concuerdan, **esa frase es
una prueba sin escribir**. Escríbela. Y al auditar, esas frases son la mejor
lista de candidatos que hay: dicen exactamente qué comprobar y dónde, y nadie
las ha verificado precisamente porque suenan a que ya lo están.

## 201. Un trigger apagado sigue estando en `pg_trigger`

El producto tiene un guardián de salud que comprueba que los tres triggers que
hacen inmutable el rastro siguen puestos. Existe porque una vez **se perdieron**
en una base real, con la migración marcada como aplicada: «una garantía que solo
vive en una migración se puede evaporar sin ruido», dice su propio comentario.

Preguntaba por el nombre. `ALTER TABLE ... DISABLE TRIGGER` deja el nombre en
`pg_trigger` y el trigger sin disparar --- y eso es exactamente lo que hace
`pg_restore --disable-triggers`, es decir, **la restauración de una copia**, que
el mismo comentario ya citaba entre las formas de perderlos. Medido: con
`audit_log_no_update` apagado, la comprobación contestaba «ok» y una fila del
rastro se dejó reescribir.

`tgenabled` lo dice: `O` dispara siempre, `A` también en réplica, `D` no dispara
nunca y `R` solo en sesiones de replicación. Solo los dos primeros valen.

**Regla**: comprobar que una salvaguarda **existe** no es comprobar que
**actúa**. Cuando la comprobación se hace por catálogo ---`pg_trigger`,
`pg_constraint`, una lista de permisos, un fichero de reglas--- hay que mirar
también el campo que dice si está activa, porque desactivar suele ser más fácil
y más silencioso que borrar.

**Y distinguir las averías**: faltar y estar apagado piden arreglos distintos
---recrearlo contra volver a encenderlo--- así que el aviso tiene que decir cuál
de las dos es.

## 202. Antes de creerte un rechazo, comprueba que preguntaste bien

Al atacar el rastro por SQL, los tres intentos ---UPDATE, DELETE, TRUNCATE---
salieron «rechazados». Parecía la confirmación de que los triggers protegían.

No lo era: la tabla no se llama `audit_log` sino `audit_auditlog`, y los tres
errores eran «relation does not exist». Lo que lo delató fue el **control**: un
INSERT que sí debía funcionar y funcionó, lo que dejaba claro que el modelo
existía y que mi consulta no lo estaba tocando.

**Regla**: cuando una prueba de ataque salga «bien rechazada», comprueba que el
rechazo es el que esperabas y no un error de escritura. Un control que **debe
pasar**, junto al que debe fallar, cuesta dos líneas y es lo único que distingue
«está protegido» de «me he equivocado de nombre». Es la lección 143 en su forma
más barata de pasar por alto: aquí el falso negativo venía disfrazado del
resultado que quería ver.

## 203. Una `UniqueConstraint` con condición no está en `pg_constraint`

Al cotejar las veinte constraints que declaran los modelos contra las que hay en
la base, seis salieron «faltan»: los dos festivos, las tres de `users_user` y la
de los tipos de permiso. Parecía que se habían perdido.

No se habían perdido: Django implementa una `UniqueConstraint` **con
`condition=`** como un **índice único parcial**, no como una constraint. Viven en
`pg_index`, no en `pg_constraint`, y hay que mirar los dos sitios ---y en el
segundo, `indisvalid`, porque un `CREATE INDEX CONCURRENTLY` a medias deja un
índice que existe y no impone nada---.

**Regla**: para saber si las salvaguardas declaradas siguen en la base, la
consulta tiene que unir `pg_constraint` y `pg_index`. Y como con los triggers de
la vuelta anterior, mirar el campo de estado y no solo el nombre: `convalidated`
para las constraints ---una `NOT VALID` no se comprobó sobre lo que ya había--- e
`indisvalid` para los índices.

**Y el método**: seis «faltan» de golpe es demasiado ordenado para ser cierto.
Cuando una comprobación acuse a muchas cosas a la vez, sospecha de la
comprobación antes que del código --- que es la misma regla que ya vale para las
pruebas.

## 204. Un sello tiene que sellar el hecho, no cómo se escribió el hecho

`compute_hash` metía en la huella `timestamp.isoformat()`. Esa cadena no depende
solo del instante: depende del huso en que esté el objeto que lo lleva.

    2026-07-02T06:58:00+02:00   <- construido en la hora de la empresa
    2026-07-02T04:58:00+00:00   <- releído de la base, que devuelve UTC

Es el mismo momento y son dos huellas distintas. Todo lo que se escribiera con
hora local ---una importación, la semilla, cualquier integración que arme el
instante en el huso del centro--- se sellaba con una cadena y se verificaba con
la otra. **577 de 1.185 fichajes de la base de desarrollo daban el sello por
roto, y los 577 cuadraban en hora local.** Cero quedaban sin explicar.

Lo caro no era el número: el informe del art. 34.9 los sacaba con la observación
«un fichaje ya no cuadra con su sello de integridad: se alteró fuera de la
aplicación». Un producto cuya razón de ser es dar fe acusaba de manipulación a
registros que nadie había tocado, en el documento que se entrega a la Inspección.

**Regla**: lo que entra en una huella va **normalizado**. Un instante, en UTC;
un decimal, con su escala fija; un texto, con su forma Unicode decidida. Si dos
escrituras del mismo dato dan huellas distintas, lo que se está sellando es la
escritura.

**Y el corolario, que es lo que hace esto peligroso**: este fallo se manifiesta
como *acusación*, no como error. Nada peta, ningún registro falla, ninguna
prueba se pone roja; solo aparece una frase en un documento diciendo que alguien
manipuló algo. Un fallo que se disfraza de hallazgo es de los que más tardan en
mirarse, porque la primera reacción ante «el sello no cuadra» es creérselo.

## 205. Arreglar una comprobación no puede aflojarla

Para que los 577 volvieran a verificar había dos caminos: reescribir los sellos
guardados ---que es exactamente la manipulación que el sello existe para hacer
visible, y el propio módulo lo prohíbe por escrito--- o aceptar que las versiones
antiguas sellaron una *representación* y probar las escrituras válidas del mismo
instante.

Se hizo lo segundo, y por eso la mitad de la prueba nueva son alteraciones de
verdad: mover el fichaje **dos horas justas** ---el desfase de Madrid en verano,
que es el caso que más de cerca pasa---, cambiar el tipo, el origen, el intervalo
o la naturaleza de las horas. Todas siguen rompiendo el sello. Comprobado además
en caliente, adelantando un fichaje por SQL directo contra la base de desarrollo.

**Regla**: cuando arregles un falso positivo de una comprobación de integridad,
la prueba que lo acompaña tiene que incluir el **verdadero positivo más
parecido** al caso que acabas de perdonar. Si no, lo que has escrito no es un
arreglo: es un permiso.

## 206. Dos documentos legales distintos no pueden salir del mismo generador sin decir cuál son

`/reports/payroll-summary/` devolvía tres cosas según el formato. En JSON, el
resumen del art. 6.1: totales del periodo, régimen, jornada pactada. En PDF y
CSV, **el registro diario completo del art. 34.9**, titulado «Registro de
jornada», dentro de un fichero llamado `resumen_…`.

Se entiende cómo pasa: el resumen necesita los mismos datos, así que reutiliza
`build_report`, y de ahí a pasarle el resultado al generador del otro documento
hay un paso. Nadie escribió nada falso; simplemente no se dijo qué documento era.

Lo que lo hace un fallo y no una minucia es a quién va: el del art. 6.1 se
entrega **con el recibo de salarios**, y quien lo recibe compara sus horas con
lo que cobra. Un papel que se titula como el documento de la Inspección y que se
calla el régimen y la jornada pactada ---las dos cifras contra las que se miden
esas horas--- no le sirve para eso, aunque contenga más datos.

**Regla**: cuando dos salidas comparten generador, el parámetro que las
distingue no es un detalle de presentación: es qué documento es. Y la prueba
tiene que llevar **el contraste** ---que el otro documento no se haya convertido
en este--- porque un `para_nomina=True` cableado por error pasaría igual todas
las comprobaciones del resumen.

**Y el olfato que lo encontró**: el JSON traía campos que el fichero no. Cuando
una API devuelve más de lo que el documento equivalente enseña, o sobra en la
API o falta en el documento; en ninguno de los dos casos está bien.

## 207. Una regla aplicada a mano en dos sitios es una regla que falta en el tercero

Pedir un periodo que acaba antes de empezar se rechazaba en el informe del art.
34.9 y en el cuadrante, cada uno por su cuenta y con el mismo mensaje traducido.
En los listados de fichajes y del rastro devolvía **200 con cero filas**.

Es el mismo patrón que los cinco catálogos de la vuelta 102 y que los trabajos
periódicos de la 104: la decisión estaba tomada, escrita y traducida, y no había
llegado al sitio donde vive el mecanismo compartido ---aquí
`LocalDayRangeFilter`, que ya rechazaba los **nombres** equivocados del periodo
con este razonamiento: contestar 200 con un periodo que nadie pidió es
exactamente lo que el art. 34.9 no admite---. El orden es el mismo argumento.

Y el cero es peor que el error. En un informe queda un documento con su periodo
escrito dentro; en un listado queda una tabla vacía que se lee como «no hubo
actividad», que en un rastro de auditoría es la conclusión contraria a la
verdadera.

**Regla**: cuando encuentres una validación escrita a mano, `grep` del mensaje
antes de seguir. Si aparece dos veces, la pregunta no es si está bien puesta,
sino **dónde falta la tercera** --- y el sitio donde tiene que vivir suele ser
uno que ya rechaza algo parecido por el mismo motivo.

## 208. Lo que el documento dice de un caso simple tiene que seguir diciéndolo cuando el caso se complica

Un día de vacaciones sin fichajes salía en el registro con «Vacaciones» en su
columna. Un día de vacaciones **en el que además se trabajó** salía idéntico a un
día ordinario: las horas, y observaciones en blanco. El dato estaba
---`build_report` rellena `row.absence`--- y los dos renderizadores lo pintaban
solo en la rama en que no había fichajes.

Es fácil de escribir sin darse cuenta, porque el código lo dice literalmente:

    if row.absence and not row.entries:      # aquí sí
        ...
    for entry, exit_ in row.entries:         # y aquí se olvidó

Y el caso que se pierde es justo el interesante. Un día de vacaciones sin
trabajar no le hace falta a nadie explicarlo; uno en el que a alguien lo llamaron
y vino, sí --- a la persona, para reclamar si le descuentan el día, y a quien lee
el registro, para preguntar por qué se trabajó un día dado por libre.

**Regla**: cuando un renderizador tenga una rama para «solo A» y otra para «solo
B», mira qué pasa con **A y B a la vez**. Suele caer en la segunda rama, que fue
escrita pensando solo en B, y el resultado es un documento que se calla lo que ya
sabía decir en el caso fácil.

**Y el olfato**: si un dato viaja a la huella de verificación pero no aparece en
el papel, algo está mal en el papel. La ausencia ya entraba en el `fingerprint`,
o sea que el producto la consideraba parte del registro; solo faltaba enseñarla.

## 209. `str()` de una lista enseña el `repr` de lo que lleva dentro

El manejador de errores de la API metía el mensaje con `str(detail)`. Cuando
`detail` era una lista ---lo que produce `ValidationError([...])`, y lo que sale
cuando la regla no cuelga de un campo concreto--- el cliente recibía esto:

    [ErrorDetail(string='“pepe” no es un UUID válido.', code='invalid')]

La frase buena estaba dentro, envuelta en el nombre de una clase de DRF. Y no se
notaba porque **el caso frecuente iba bien**: un error por campo llega como
diccionario y se serializa limpio, y un `NotFound` trae un `detail` de texto. Solo
la rama de la lista, que es la menos transitada, salía así.

La trampa concreta: `ErrorDetail` hereda de `str`, así que `str(uno)` da la frase
y `str([uno])` da el `repr`. Un elemento suelto se ve bien y la lista no.

**Regla**: nunca metas una colección en un campo de texto con `str()`. Recorre y
convierte uno a uno. Y al auditar una API, prueba los errores igual que las
respuestas buenas: pásale a cada endpoint un identificador que no sea un
identificador y **lee la frase que devuelve**, no solo el código de estado.

## 210. Una sonda mal escrita puede acusar al producto y de paso encontrar otra cosa

La sonda de esta vuelta mandaba `?employee=<mi id>` para comprobar que pedir el
informe de uno mismo por identificador explícito funciona. Daba **400 en las
cuatro sesiones**, lo que parecía un fallo redondo: pedirse a uno mismo se
rechaza y pedir a otro no.

No era eso. `/auth/me/` no devuelve el identificador en el campo que yo leía, así
que la sonda mandaba literalmente `?employee=undefined`. Lo delató el propio
mensaje ---«“undefined” no es un UUID válido»--- que decía exactamente qué se
había enviado.

Dos cosas de aquí. La primera, la de siempre: **imprime lo que crees que estás
mandando** antes de acusar a nadie; una línea con el valor habría ahorrado el
rodeo. La segunda, que el rodeo valió la pena: el mensaje que desmontó mi
hipótesis era el que estaba mal formado, y ese sí era un fallo. Un experimento
que sale al revés de lo previsto no es tiempo perdido si se lee con atención lo
que devolvió.

## 211. Una lista blanca se prueba por los dos lados, y el lado caro es el bueno

Rechazar los parámetros que no se leen arregla un fallo real: `?employe=<id>`
---una letra menos--- devolvía **200 con el registro de quien preguntaba**, no el
pedido.

Pero una lista blanca a la que le falte un nombre rompe el producto de una forma
mucho más cara que el fallo que viene a arreglar: en vez de un documento
equivocado de vez en cuando, un 400 permanente en algo que funcionaba. Por eso la
mitad de la prueba son los parámetros que **sí** existen ---`format`, `scope`,
`department`, el periodo, y ninguno---, cada uno comprobando que sigue dando 200.

**Regla**: al escribir una lista de lo permitido, escribe primero la prueba de lo
permitido. Y sácala del código que lee esos parámetros ---aquí, los
`query_params.get(...)` y los `OpenApiParameter` ya declarados---, no de la
memoria: lo que se olvida al hacer la lista es exactamente lo que se olvida al
imaginar la prueba.

**Y dónde aplicarla**: solo donde el coste de ignorar sea alto. En un listado
corriente, rechazar lo desconocido rompe a quien añade un parámetro inocuo para
saltarse una caché; en un documento probatorio, un 400 es mejor respuesta que el
registro de otra persona.

## 212. `is_staff` no es un rol de negocio

Tres pruebas de esta vuelta fallaron y las tres eran mías: había creado a la
persona que manda con `is_staff=True`, creyendo que eso la hacía administración.
No: `can_manage` mira `role in {MANAGER, ADMIN}`, y `is_staff` es de Django ---el
acceso a su panel---, que aquí no decide nada.

El fallo se disfraza bien porque el nombre suena a lo que uno quiere y porque
falla **tarde**: la prueba se monta, la petición sale, y el 400 que vuelve dice
«solo puedes pedir tu propio registro», que se lee como un fallo del producto y
no como un fixture mal armado.

**Regla**: en las pruebas, el permiso se da con el campo que el producto lee de
verdad. Antes de dar por bueno un rechazo de permisos en una prueba nueva,
comprueba qué campo consulta el código que rechaza --- son tres segundos de `grep`
y evitan reportar como fallo lo que es un fixture.

## 213. Dos sistemas de permisos correctos por separado, y nadie mira el cruce

El producto tiene dos formas de entrar. Las personas, con su sesión y
`IsAuthenticatedInTenant` debajo de todo. Las aplicaciones, con su credencial y
`HasApplicationScope`, que dice de sí mismo: «una vista sin permiso declarado
deniega en vez de permitir; olvidar declararlo no debe abrir una puerta».

Los dos están bien. El cruce no lo miraba nadie. `ApplicationUser` contesta
`is_authenticated` y trae `tenant_id` ---porque el código compartido no debería
tener que preguntar con quién habla--- y eso es exactamente lo que
`IsAuthenticatedInTenant` comprueba. Medido con una credencial **sin ningún
permiso**:

    /departments/, /workplaces/, /working-time-rules/   -> 200
    /audit/, /punches/, /absences/, los dos informes    -> AttributeError (un 500)

O sea: leía la estructura de la empresa y sus reglas de jornada, y donde no
llegaba a leer reventaba en vez de contestar 403.

**Regla**: cuando existan dos identidades que autentican por caminos distintos,
prueba **cada una contra la puerta de la otra**. El fallo no está en ninguno de
los dos permisos ---leídos por separado los dos son correctos--- sino en que uno
de ellos nunca se preguntó si el llamante era del otro tipo.

**Y la pista que lo delata**: un `AttributeError` pidiendo `id`, `pk` o `tzinfo`
sobre un objeto que hace de usuario. Ahí el código ya estaba diciendo que quien
llama no es lo que él cree.

## 214. Cerrar una puerta se prueba por los dos lados

Rechazar a las aplicaciones en el permiso de personas es una línea. Y una línea
mal puesta deja fuera a **toda** integración, que es un daño mucho mayor que el
que arregla.

Por eso dos tercios de la prueba son lo que no puede romperse: que una aplicación
con sus permisos siga entrando por `/api/app/…`, y que una persona siga entrando
por la suya. Comprobado además en caliente antes de escribir la prueba.

**Regla**: toda restricción nueva se acompaña de las pruebas de lo que sigue
permitido, y esas se escriben **primero**. Es la misma disciplina que la lista
blanca de la vuelta anterior: al cerrar, lo caro no es que se cuele algo, es que
deje de pasar lo que debía.

## 215. Cuando el cruce se prueba en un sentido, el fallo está en el otro

La vuelta anterior encontró que una credencial de aplicación entraba por la
puerta de las personas. Al buscar en esta si hacía falta escribir la prueba,
apareció esta, que ya existía:

    test_a_person_token_does_not_open_the_application_doors

O sea: **alguien había pensado en el cruce y lo había probado en un sentido**
---persona contra la puerta de aplicaciones--- y no en el otro. Y el que faltaba
era el que estaba roto.

No es casualidad. Se prueba el sentido que se imagina primero, que suele ser el
que preocupa al escribir la puerta nueva («que no entre cualquiera aquí»); el
inverso ---«que esta credencial no entre en lo de siempre»--- exige acordarse de
un código que ya funcionaba y que nadie está tocando.

**Regla**: una prueba de cruce en un sentido es la señal de que falta la del
otro. Cuando encuentres una, escribe la simétrica en el momento, aunque parezca
redundante: es literalmente la mitad que no se ha mirado.

## 216. `on_commit` hace que un rastro parezca ausente

La sonda decía que dar de alta a una persona **no dejaba ni un apunte** en el
rastro de auditoría, ni hecho por una aplicación ni por administración. Sonaba a
hallazgo grave: el registro de quién cambia qué es media razón de ser del
producto.

Era mío. El rastro se escribe en `transaction.on_commit`, y en una prueba con
`django_db` la transacción no se confirma nunca, así que la llamada queda
encolada y jamás corre. Con `django_capture_on_commit_callbacks(execute=True)`
aparecieron los apuntes, y bien puestos: `PERSON_CREATED` con
`actor=«aplicación · Conector»` cuando lo hace un conector, y con el nombre de la
persona cuando lo hace una persona.

Lo que lo desmontó fue el **contraste**: medir lo mismo hecho por un humano. Si
la aplicación no dejaba rastro pero la persona sí, era un fallo del producto; al
salir cero las dos, el sospechoso pasaba a ser la sonda.

**Regla**: en este proyecto, cualquier medición del rastro, de los correos o del
borrado de ficheros va dentro de `django_capture_on_commit_callbacks`. Y cuando
una comprobación dé cero, mide **el caso que sí debería dar distinto de cero**
antes de escribir la palabra «hallazgo».

## 217. Una validación asimétrica delata que mira la forma y no el valor

Las horas pactadas se rechazaban así:

    20      -> 201        0020.0  -> 201
    20.0    -> 201        20.00   -> 400
    20.5    -> 201        20.50   -> 400

Los ceros de la izquierda daban igual y los de la derecha no. Esa asimetría es la
pista: si el valor fuera lo que se juzga, las dos columnas se comportarían igual.
`DecimalField` cuenta los decimales del `Decimal` **tal como llega**
---`Decimal("20.00").as_tuple().exponent` es -2--- y no los significativos.

Y el mensaje no ayudaba a verlo, porque era cierto: «asegúrese de que no haya más
de 1 decimales». Tiene dos. Ninguno cuenta.

Duele en integraciones: dos decimales es como formatea cualquiera que venga del
mundo de las nóminas, así que un cliente correcto se comía un 400 por escribir el
mismo número de otra forma.

**Regla**: cuando una validación acepte una escritura y rechace otra del **mismo
valor**, el fallo está en que se juzga la representación. Normaliza antes de
validar. Es la misma lección que el sello de la vuelta 109, en otro tipo de dato:
allí un instante en dos husos, aquí un número con dos colas de ceros.

**Y el límite de la normalización**: `20.55` no es `20.5`. Se quitan los ceros
que no dicen nada y se conserva lo que sí; la precisión que no cabe se sigue
rechazando, y eso es la mitad de la prueba.

## 218. Probar los formatos de un número, no solo un número

El fallo no apareció al probar valores límite ---cero, negativos, enormes, con
demasiados decimales--- que es lo que uno prueba primero y que aquí estaba todo
bien. Apareció por accidente: la sonda mandaba `"20.00"` porque a mí me salió
escribirlo así, y contestó 400 donde esperaba 201.

**Regla**: para un campo numérico, la tabla de casos incluye **el mismo número
escrito de varias formas** ---entero, con un decimal, con dos, con ceros a la
izquierda, en notación exponencial, como texto y como número--- además de los
valores límite. Son dos ejes distintos: uno prueba qué valores se aceptan y el
otro qué escrituras. El segundo casi nunca se prueba, y es donde viven los fallos
que solo ve quien integra.

## 219. Si dos cosas se buscan como iguales, no se pueden crear como distintas

El número de empleado se buscaba con `iexact` en los dos sitios que resuelven una
referencia ---la puerta de integración y el fichaje delegado--- y se comprobaba
**exacto** al dar de alta. Así que se podían crear `EMP-9` y `emp-9`, y luego:

    _resolve(«EMP-9»)          -> una de las dos, la primera, sin decir que hay otra
    resolve_employee(«EMP-9»)  -> «la referencia coincide con más de una persona»

Una puerta elegía al azar y la otra se plantaba, para todo el mundo. El conflicto
lo había creado un tercer sitio que no sabía de las otras dos.

Y otra vez la asimetría como pista: el espacio **sí** se normalizaba ---« EMP-9 »
chocaba--- y la caja no.

**Regla**: la unicidad y la búsqueda tienen que estar de acuerdo en qué es «el
mismo». Cuando encuentres un `iexact` al leer, mira con qué se compara al
escribir; y al revés. Si no coinciden, el sistema puede llegar a un estado que él
mismo considera ambiguo.

**Y el orden de la comprobación**: esto no se ve leyendo el serializador, que
está bien escrito para lo suyo. Se ve poniendo juntas la consulta de lectura y la
de escritura, que viven en ficheros distintos y las escribió gente distinta con
razón cada una.

## 220. Tres comprobaciones seguidas, y la tercera con otra vara

En la función que impide pisar la ficha de otro, la puerta de integración tenía
esto:

    if otros.filter(email__iexact=person.email)...
    if otros.filter(employee_id__iexact=person.employee_id)...
    if otros.filter(oidc_sub=person.oidc_sub)...          # <- exacto

Tres líneas seguidas, dos con `iexact` y la última sin él. No es un descuido
raro: se escriben en momentos distintos, y al añadir la tercera se copia la forma
pero se pierde un detalle de una palabra.

Y era la peor de las tres para perderlo. `oidc_sub` es «the immutable anchor» del
acceso federado: medido, empujar «sub-1» y «Sub-1» junto a «SUB-1» dejaba **tres
personas con la misma identidad**, con `_resolve` devolviendo la primera. Es lo
mismo que `users/backends.py` ya advierte del correo duplicado --- «son la misma
persona duplicada, y el acceso entraría en cualquiera» --- pero por la puerta que
usan las integraciones.

**Regla**: cuando veas comprobaciones hermanas en fila, léelas **en columna**, no
de arriba abajo. Poner una debajo de otra hace saltar a la vista la que usa otra
vara. Es la misma técnica que encontró la asimetría de los ceros y la del número
de empleado: comparar formas, no leer significados.

## 221. Una validación sobre un campo que el serializador no expone es decoración

Al arreglar lo de arriba escribí también un `validate_oidc_sub` en el serializador
de personas, que no tenía ninguna comprobación. Se veía razonable y no corría
nunca: DRF solo llama a `validate_<campo>` para los campos declarados, y ese
serializador no expone `oidc_sub`. La API de personas ignora el campo por
completo --- se manda y la persona queda sin identidad.

O sea, había escrito exactamente lo que esta auditoría lleva veinte vueltas
encontrando: código que parece proteger y no se ejecuta. Retirado, junto con su
cadena de traducción.

**Regla**: antes de escribir un `validate_x`, comprueba que `x` está en los
`fields`. Y en general, después de escribir una protección, **haz que falle una
vez**: si no consigues verla saltar, no está puesta.

## 222. Un mapa vacío no se lee como una decisión, pero se comporta como una

`finding_citations={}` en el marco de la directiva. Doce caracteres, sin
comentario, en un fichero donde **cada** hueco deliberado lleva su explicación
---el marco español tiene tres y los tres dicen por qué---. Y con él vacío, un
país no reconocido recibía los diecinueve avisos del cuadrante **sin ninguna base
legal**, cuando ese marco existe precisamente para «degradar a algo defendible».

Los artículos estaban escritos diez líneas más arriba, en las citas de las
cifras: art. 3 el descanso diario, art. 5 el semanal, art. 4 la pausa, art. 6.b
las cuarenta y ocho horas. El aviso y la cifra que lo produce salían del mismo
sitio y solo una de las dos citaba.

**Regla**: un contenedor vacío ---`{}`, `[]`, `None`, una lista de exenciones sin
entradas--- necesita comentario igual que uno lleno. Vacío por decisión y vacío
por olvido se escriben idénticos, y solo el comentario los distingue. Al auditar,
un vacío sin comentario rodeado de vacíos comentados es de las señales más
baratas que hay.

## 223. Una prueba que exige decidir vale más que una que comprueba una lista

Lo fácil era comprobar que los siete avisos que cité tienen su artículo. Eso
protege esos siete y no impide que el aviso número veinte salga mudo.

La prueba lee **los `code=` del propio fichero del cuadrante** y exige que de
cada uno haya una decisión: o cita un artículo, o está declarado en una tabla de
exentos **con el motivo escrito**. Añadir un aviso nuevo obliga a pasar por ahí.

Y la mitad que menos se piensa: la prueba contraria, que los declarados sin cita
**siguen sin ella**. Rellenar por rellenar es peor que no citar, porque apuntar a
un artículo que no dice lo que el aviso dice es lo que un inspector desmonta en
la primera pregunta. Citar la Directiva 2003/88 para un aviso sobre menores
---que regula la 94/33--- habría sido exactamente eso.

**Regla**: cuando el fallo sea «faltaba una entrada en una tabla», la prueba no
va sobre las entradas: va sobre **la fuente que las genera**, y obliga a que cada
elemento nuevo tenga decisión. Lo demás es arreglar el caso de hoy.

## 224. Un detector con demasiados resultados no es un hallazgo: es un detector mal hecho

El primer barrido de contenedores vacíos sin comentario dio **39**. Treinta y
nueve sitios sospechosos en un producto que llevo veinte vueltas auditando era
demasiado bueno para ser cierto, y no lo era: casi todos eran **parámetros con
`None` por defecto** en firmas de varias líneas, que no necesitan comentario
ninguno, y el resto tenían la explicación en el docstring de la clase, seis
líneas más arriba de donde yo miraba.

Con el detector rehecho ---leyendo el árbol sintáctico en vez de líneas, solo
asignaciones de módulo y de clase, y buscando el comentario también en el
docstring del bloque--- quedó **uno**. Y era correcto: el login vacía
`authentication_classes` porque si no, un token caducado en la cabecera daría 401
antes de poder entrar.

**Regla**: la regla de «muchos fallos a la vez no son muchos fallos» vale también
para las herramientas de auditoría, no solo para las pruebas. Antes de leer una
lista de treinta sospechosos, coge tres al azar y compruébalos a mano: si los
tres son falsos positivos, arregla el detector antes de seguir leyendo.

**Y el criterio para afinarlo**: un detector de texto sobre código casi siempre
sobra ruido. Si lo que buscas es estructura ---qué es una asignación de clase, qué
es un parámetro--- usa `ast`, que cuesta veinte líneas más y quita el noventa y
siete por ciento de los falsos positivos.

## 225. Antes de decir que algo no está explicado, mira donde se define

Vi `qualifying_annual_share=0` en el marco de la directiva y ningún consumidor en
todo el código: un campo que se rellena con el dato legal correcto ---un tercio de
la jornada anual, art. 36.1--- y que nadie lee. Con veinte vueltas de «la pieza
está hecha y desconectada» a la espalda, parecía el siguiente.

La razón estaba escrita en dos sitios distintos, y yo había leído solo uno. En
`holds_night_worker_status`: «el tercio anual no es algo que un mes de calendario
pueda ver, y por eso la empresa puede declararlo». Y en la **declaración del
campo**, que es donde se me ocurrió mirar al final: «se conserva como cifra aunque
el cuadrante no pueda ver un año entero».

**Regla**: cuando un campo parezca huérfano, lee su declaración antes de contar
sus usos. Un dato que existe solo para que conste la cifra es una decisión
legítima ---el marco legal es también documentación--- y en este proyecto suele
venir con el porqué al lado. Contar `grep` de usos dice si se ejecuta, no si debe.

## 226. Una limpieza en `on_commit` no limpia nada en una prueba

El almacén de desarrollo tenía **4.936 ficheros y 12 referenciados por una
ausencia**: 8,1 MiB de justificantes huérfanos. Y crecían de forma medible tanda a
tanda ---4.391 por la mañana, 4.625 unas horas después, 4.936 al medir hoy---, lo
que descartaba que fueran restos antiguos de algo.

El producto los borra bien: `descartar_justificante` lo hace en
`transaction.on_commit`, que es lo correcto ---no se tira un fichero hasta que la
fila que lo suelta está confirmada---. Pero una prueba con `django_db` **nunca
confirma su transacción**, así que ese `on_commit` no se ejecuta jamás. La
limpieza del producto es correcta y en pruebas no llega a correr.

Y como `pytest` corría con los ajustes de desarrollo, escribía en el almacén de
desarrollo. Dos cosas correctas por separado ---la limpieza diferida y reutilizar
los ajustes de dev--- que juntas hacen un almacén que solo crece.

**Regla**: si algo se borra en `on_commit`, en pruebas **no se borra**. Cuando eso
toque disco, el arreglo no es limpiar en cada prueba: es que las pruebas escriban
en otro sitio ---un `MEDIA_ROOT` temporal de sesión--- para que da igual que no se
limpie.

**Y la señal que lo delató**: el ratio. Cuatro mil novecientos huérfanos frente a
doce vivos no es un descuido acumulado, es un flujo que nadie cierra. Cuando la
proporción entre basura y datos buenos es de cientos a uno, lo que hay que buscar
es quién escribe, no quién olvidó borrar.

## 227. Para saber si algo está probado, rómpelo

Los tres avisos que el producto manda en `on_commit` ---al proponer una
corrección, al retirarla y al resolverla--- **no aparecían por su nombre en
ninguna prueba**. Con veintidós vueltas de «la pieza está hecha y desconectada»
detrás, eso olía a que el aviso del art. 4.b no lo verificaba nadie.

La medición correcta no es buscar el nombre: es **silenciar la línea y ver qué se
pone rojo**. Silenciando cada uno de los tres, cada vez falló exactamente una
prueba. Los tres estaban cubiertos, por pruebas que los ejercitan a través del
endpoint y miran el buzón, sin nombrar la función.

**Regla**: `grep` del nombre de una función en las pruebas mide **cómo están
escritas**, no qué cubren. Una prueba de extremo a extremo bien hecha no nombra
casi nada de lo que ejercita. Cuando quieras saber si algo está protegido,
quítalo y corre la suite; si no se rompe nada, ahí tienes la respuesta, y si se
rompe sabes además **cuál** es la prueba que lo vigila.

## 228. Una aserción negativa solo vale si el efecto podía ocurrir

Buscando pruebas que afirmen que **no** se manda un correo sin capturar los
callbacks ---que serían pruebas que pasan siempre, porque en una prueba
`on_commit` no corre--- salieron ocho candidatas.

Las ocho eran válidas: los correos de invitación, de contraseña y de
recordatorio se mandan **directamente** con `send_mail`, no en `on_commit`. Solo
los tres avisos de corrección son diferidos, y sus pruebas sí capturan.

**Regla**: antes de acusar a un `assert not X` de no comprobar nada, mira si `X`
podía llegar a ocurrir en ese contexto. La pregunta no es «¿captura los
callbacks?» sino «¿este efecto es diferido?». Ocho de quince candidatos se caen
con esa sola comprobación, y hacerla cuesta un `grep` por el sitio donde se
manda.

## 229. Al medir cobertura, acotar la suite da falsos huecos

Silenciando las trece comprobaciones del cuadrante una a una y corriendo
`apps/shifts`, `apps/reports` y `apps/legal` ---donde uno esperaría que vivan sus
pruebas--- dos salieron sin cobertura: el turno en festivo y el turno fuera de las
fechas del contrato. Dos avisos legales sin nadie mirándolos habría sido un
hallazgo gordo.

Con la **suite completa**, las dos rompen pruebas: dos y una. Las cubren ficheros
de otras apps, que es lo normal en pruebas de extremo a extremo --- una prueba de
ausencias ejercita el cuadrante sin vivir en `apps/shifts`.

**Regla**: la mutación mide cobertura solo si corre **todo**. Acotar la suite por
app acelera el barrido y a cambio convierte «no lo cubre esta app» en «no lo cubre
nadie», que es una conclusión distinta y falsa. Sirve para triar --- once de trece
quedaron resueltas en veinte segundos cada una --- pero **cada candidato que salga
limpio se repite con la suite entera antes de escribirlo en ningún sitio**.

Es el reverso de la lección 224: allí el detector tenía demasiado ruido, aquí
tenía poco alcance. Las dos veces el error fue creerme el primer número.

## 230. Un borrado masivo se hace en tres pasos, y ninguno es un `rm`

Cuatro mil novecientos diecisiete ficheros aprobados para borrar, con el encargo
explícito de tener cuidado con las comillas y las rutas. Lo que se hizo:

1. **Copia primero.** Ocho megas comprimidos a 111 KB, y **leída** después para
   comprobar que tenía dentro lo que decía. Una copia que no se ha abierto no es
   una copia.
2. **Simulacro que no escribe.** Cuenta, y sobre todo comprueba las dos cosas que
   convierten un borrado en un desastre: **cuántos candidatos caen fuera de la
   raíz** y **cuántos son enlaces simbólicos**. Las dos tienen que dar cero, y si
   no dan cero no se sigue.
3. **La purga en Python, nunca en shell.** No por gusto: un `find … -delete` con
   una ruta mal entrecomillada o una variable vacía borra otra cosa, y no hay
   forma de expresar «solo si además no está referenciado» sin salirse del shell
   igualmente.

Y los cinturones se repiten **dentro** del script que borra, no solo en el
simulacro: entre una cosa y otra pueden pasar minutos, y lo que se comprobó
entonces no es lo que hay ahora.

**Regla**: para borrar en masa, la ruta se resuelve a absoluta y se comprueba que
cuelga de donde debe (`RAIZ in p.resolve().parents`), cada elemento pasa las tres
condiciones ---dentro, sin referencia, no enlace--- y al terminar se cuenta lo que
queda **y lo que tenía que sobrevivir**. Contar solo lo borrado no dice si se
llevó por delante algo más.

## 231. La regla de contraste de MUI no es la de manual, y la diferencia cambia el veredicto

Al escribir la prueba que cuenta el contraste de la paleta, decidí el color del
texto con la regla clásica: claro si el fondo es oscuro, oscuro si es claro,
partiendo por luminancia 0,179.

MUI no hace eso. `getContrastText` pone **blanco siempre que el blanco llegue a 3**
sobre ese fondo, y solo recurre al casi negro cuando no llega. Con el rojo de
error la diferencia era: mi regla decía «texto oscuro, 4,18» ---casi bien--- y la
de verdad dice «texto blanco, 3,68» ---claramente mal---.

O sea que la aproximación de manual **daba por bueno un color que no se lee**, y
además por un camino que parecía más exigente.

**Regla**: al medir contraste de una paleta, el color del texto lo decide la
librería, no la teoría. Copia su regla ---son tres líneas--- o pregúntale al tema
ya construido. Y esto vale para cualquier comprobación sobre una librería: lo que
importa es lo que **hace**, no lo que uno haría en su lugar.

## 232. Un barrido de pantallas solo ve los estados que hoy están en pantalla

Ya había una prueba que recorre pantallas midiendo contraste. No cazó que el
ámbar de aviso estuviera a 3,11 durante meses, porque el estado que lo lleva
---una corrección «esperando a la empresa»--- no aparecía en ninguna de las
pantallas que recorre. Saltó el día que la demo tuvo una por casualidad.

El propio tema ya lo decía de un color anterior: «no lo vio el barrido ---su
estado no aparecía en ninguna de las pantallas recorridas--- sino la cuenta».
Estaba escrito y se repitió igual.

**Regla**: una comprobación que recorre lo que se ve depende de que ese día se
vea. Cuando exista una **fuente** de la que sale lo que se ve ---una paleta, un
catálogo de estados, una tabla de mensajes--- la comprobación va sobre la fuente,
y el recorrido de pantallas se queda para lo que solo existe al montarlo. Las dos,
no una.

Y se nota en lo que encuentran: la del recorrido cazó **un** color; la de la
paleta, al escribirla, cazó **tres**.

## 233. Un residuo no solo estorba: puede cambiar una regla de negocio de toda la empresa

La prueba de las cuatro manos ---quien registra una ausencia no puede
aprobarla--- fallaba a ratos con **200 donde espera 409**. Parecía la separación
de funciones rota, que sería gravísimo.

No lo era, y la cadena merece contarse entera:

1. Otra prueba fallaba por una espera por reloj y dejaba **un departamento con
   responsable**.
2. Que exista un departamento con responsable activa el **alcance por
   departamentos** en toda la empresa.
3. Con el alcance activo, el único responsable de la demo pasa a ver solo su
   departamento, y deja de alcanzar a la administradora.
4. Sin nadie más que pueda decidir sobre ella, el producto **la deja aprobar** ---y
   hace bien: lo contrario deja un asiento del registro mal con ninguna forma de
   arreglarlo, que es lo que documenta `someone_else_could_decide` con un caso
   real---.
5. La prueba se para ahí y deja **la ausencia aprobada**. Una aprobada no se
   puede cancelar, así que la limpieza del principio, que solo cancela
   pendientes, no la recoge nunca. **A partir de ahí no vuelve a pasar jamás**:
   las siguientes corridas chocan por solapamiento antes de llegar a lo que
   querían probar. Medido: 43 ausencias apiladas en las mismas dos fechas, 42
   canceladas y una aprobada bloqueando al resto.

**Regla**: cuando una prueba falle con un veredicto de negocio inesperado, antes
de acusar al producto pregunta **qué hay en la base que cambie la regla**. Aquí un
departamento de usar y tirar movía el alcance de toda la empresa, y el producto
contestaba correctamente a un estado que nadie había querido montar.

**Y la lección de diseño**: una prueba que usa fechas fijas y limpia solo un
estado se rompe **de forma permanente** en cuanto falla una vez. La de al lado, en
el mismo fichero, ya usaba días propios de cada corrida y explicaba por qué. La
regla estaba escrita a diez líneas de distancia.

## 234. Una regla que solo vive en el serializador no está puesta

La comprobación de que el número de empleado no se repita ignorando mayúsculas
llevaba ocho vueltas escrita ---en `validate_employee_id`--- y estaba **abierta por
todos los demás lados**: shell, importación, `update` masivo, `loaddata`. El
serializador es una puerta, no una regla; la regla vive en la base.

**Cómo se ve**: si un invariante importa, pregúntate quién lo rompe **sin pasar
por la vista**. Si la respuesta es «cualquiera con acceso al ORM», falta el
`UniqueConstraint`, el `CheckConstraint` o el trigger. La prueba que lo demuestra
tampoco puede usar el serializador: tiene que crear el objeto a pelo y esperar
`IntegrityError`.

## 235. Al endurecer un índice, mira antes y niégate con nombres

Un `AddConstraint` que se vuelve único puede reventar a mitad de la migración, y
lo que Postgres imprime ---la clave duplicada--- no dice de **quién** es. La
operación que mira va **primera**, antes del `RemoveConstraint`, y si encuentra
choques lanza `RuntimeError` con empresa, valor y correos, dejando la base como
estaba.

**Y no arregles tú el choque.** La tentación es renombrar el duplicado a
`X-bis` y seguir. Aquí ese número sale en la nómina y en el convenio de una
persona: elegir por la empresa es cambiarle un dato que firma un tercero. La
migración se planta y dice qué hay que decidir.

**Comprobado en caliente, no sobre el papel**: en esta base no hay ni un choque,
así que la defensa nunca habría saltado sola. Se retrocedió una migración, se
creó el choque a propósito por shell, se vio el mensaje, y se confirmó con
`showmigrations` que **la migración quedó sin aplicar**. Sigue valiendo la 227: si
quieres saber si una defensa está puesta, rómpela.

## 236. Una espera por reloj no falla por el reloj: falla por el `count()` que hay detrás

El rojo intermitente de «Fichajes › filtra por persona y por fechas» era una
`waitForTimeout(900)` seguida de `expect(await filas().count()).toBeLessThan(...)`.
Lo que rompe no es que 900 ms sea poco: es que **`count()` no espera**. Todo lo
que hay alrededor ---`toBeVisible`, `toHaveCount`, `toHaveText`--- reintenta hasta
el timeout; en el momento en que se saca el valor a una variable con `await`, se
pierde ese reintento y queda una foto de un instante arbitrario.

**Cómo se ve venir**: `await ...count()`, `await ...textContent()`, `await
...innerText()` metidos dentro de un `expect(...)`. Y peor si delante hay un
`waitForTimeout`, que es la confesión de que alguien ya sabía que había carrera.

**El arreglo es `expect.poll`**, que devuelve el reintento a un valor calculado.

**Y la razón de que la carrera exista importa**: aquí la pantalla retiene a
propósito las filas anteriores mientras carga (`placeholderData: previous`), para
no parpadear en blanco. Es una buena decisión de producto que convierte «todavía
no ha llegado» en algo **indistinguible** de «llegó y no cambió nada». Cuando una
lista mantiene los datos viejos durante la carga, ninguna aserción sobre su
contenido vale sin espera por condición.

**Corolario para leer los fallos**: el mensaje decía «filtrar no quitó nada», o
sea acusaba al filtro del producto. La prueba estaba describiendo su propia prisa.
Antes de creer a un fallo que acusa al producto, mira si la prueba pudo haber
mirado demasiado pronto.

## 237. Antes de borrar, mira qué apunta a lo que vas a borrar --- y míralo en todos los ficheros

`PunchCorrection.target` es `on_delete=PROTECT`. Un borrado en bloque de fichajes
corregidos lanza `ProtectedError` y se planta **a mitad de la pasada**, que es el
peor momento: con parte del trabajo hecho y sin saber cuál.

El primer barrido dijo «nadie apunta a `Punch` desde otras apps» y era mentira,
porque busqué en `apps/*/models.py` y en esta app los modelos viven en seis
ficheros distintos: `corrections.py`, `delegated.py`, `overtime.py`,
`reminders.py`, `workday.py`. Un modelo de Django no tiene por qué estar en
`models.py`; solo tiene que estar importado.

**Cómo hacerlo bien**: buscar `ForeignKey`/`OneToOneField` hacia el modelo en
**todos** los `.py`, con su `on_delete` al lado, y no olvidar la autorreferencia
---`"self"`--- que un grep por el nombre de la clase nunca encuentra.

**Y clasificar por `on_delete`, que decide el trabajo**: `PROTECT` hay que
resolverlo antes o el borrado no ocurre; `CASCADE` se lleva cosas que puede que no
quieras perder; `SET_NULL` deja filas apuntando a nada, y eso puede leerse como
un estado distinto ---una corrección con `result` vacío parece no aplicada---.

## 238. Un recuento escrito a mano se desincroniza de las filas que cuenta

El inventario de cobertura legal declaraba «91 situaciones, 49 sin cubrir» y tenía
**90 filas con 48**. Nadie mintió: se añadió una fila y no se tocó la cabecera, o
al revés. Y la cabecera es lo único que lee quien no baja a las tablas.

**La regla**: si un documento lleva un total, **genéralo contando**, no lo
escribas. Cuando eso no se pueda ---un documento a mano---, cuenta las filas antes
de tocar la cifra, aunque vengas solo a añadir un apartado.

Aquí el generador cuenta las píldoras de estado y con eso rellena el total, la
barra, la leyenda y el `aria-label`. Los porcentajes se reparten y el sobrante del
redondeo se le da al mayor, para que la barra sume 100 exacto.

## 239. Un documento derivado se queda atrás en silencio, y no lo dice

El artefacto de cobertura legal decía ser un reflejo de `docs/cobertura-legal.md`
---lo pone en su pie--- y estaba en el corte del 12/08. Entre medias se habían
cubierto **áreas enteras**: permisos retribuidos, las quince suspensiones del art.
45, los festivos, las ausencias de parte del día, el tope de horas extra. El
artefacto seguía diciendo «no existen en el sistema» de cosas que llevaban dos
semanas funcionando.

Nada avisa de eso. El documento no falla, no da error, y se lee perfectamente
coherente: es la peor clase de dato viejo.

**La regla**: al ir a actualizar un documento derivado, **lee primero la fuente
entera y compara**, en vez de añadir el apartado que traías. Lo que venía a ser un
apartado nuevo resultó ser la mitad del inventario mal.

**Y comprobar contra el código lo que la fuente no detalla.** El `.md` decía «las
quince del art. 45 están en el catálogo» pero no decía nada de la baja por
contingencia, que el artefacto daba por «A medias» y «Falta». En el código están
las dos, separadas y con su nota. Sin mirarlo habría publicado un «falta» sobre
algo que existe.

## 240. Un derecho que no se extingue no es lo mismo que un acceso que se conserva

Al mirar si quien deja la empresa puede seguir viendo su registro, la pregunta
parecía ser «sí o no». No lo era. El derecho del art. 15 RGPD **no se extingue**
con la relación laboral, y el art. 34.9 obliga a conservar el registro cuatro
años. Pero el art. 15 se ejerce **por solicitud y se satisface con una entrega**:
ninguno de los dos obliga a mantener a nadie dentro de la aplicación.

Y la lectura amplia ---dejarle la cuenta abierta--- **sería peor para todos**,
incluida esa persona: vería el cuadrante, a sus antiguos compañeros y lo que la
empresa haya cambiado desde que se fue.

**La regla de diseño**: cuando una obligación legal se traduce a producto,
pregúntate si lo que la ley pide es un **derecho a obtener** o un **derecho a
acceder**. Casi siempre es el primero, y construir el segundo da un producto con
más superficie y peor cumplimiento.

**Y no citar sentencias sin haberlas leído.** El razonamiento de arriba sale del
texto de los dos artículos, y así queda dicho en el cuaderno: lo que no se ha
comprobado se marca como sin comprobar, aunque suene más flojo.

## 241. Al copiar un mecanismo, comprueba cuál de sus propiedades venía del uso

El enlace de entrega hereda de `PasswordResetTokenGenerator`, así que escribí que
era «de un solo uso», que es lo que es el del restablecimiento. **Falso**: aquel se
invalida al usarse porque poner una contraseña cambia el hash que entra en el valor
firmado. Descargar un informe no cambia nada, así que el mío vale hasta que caduque.

Lo que se hereda es la **firma y el plazo**; el consumo al usarse era un efecto del
uso concreto, no del mecanismo.

**Y el arreglo fue el texto, no el código**: usarlo dos veces es el caso normal ---el
PDF y el CSV son dos descargas de la misma solicitud---, así que forzar un solo uso
habría sido construir un defecto para cumplir una frase que escribí yo.

**Cómo se ve venir**: al documentar una pieza copiada, por cada propiedad que le
atribuyas, señala **la línea** que la produce. Si no la encuentras, la propiedad no
está.

## 242. Un detector más estrecho que el guard que tiene que satisfacer

Retiré los flags `fuzzy` de los catálogos con `^#, fuzzy\n`, y dos mensajes
siguieron marcados: los que llevan `%(company)s` tienen la línea
`#, fuzzy, python-format`, con el flag acompañado.

El guard que vigila los fuzzy ya usaba el patrón correcto ---`^#,.*\bfuzzy\b`--- y
estaba escrito desde antes. Mi detector era **más estrecho que la comprobación que
iba a tener que pasar**, y lo supe porque la comprobación existía.

**La regla**: cuando arreglas algo que un guard vigila, **lee el patrón del guard y
usa ese**, no uno que escribes de nuevo. Si el tuyo es más estrecho tendrás un
verde falso hasta que el guard corra; si es más ancho, tocarás cosas que nadie te
pidió tocar.

## 243. «No lo mires porque son demasiados» es circular

El guard de residuos no revisaba las personas de baja, con una razón escrita y
sensata: el producto no borra personas porque sus fichajes viven cuatro años. Pero
había **946 personas de prueba de baja sin un solo fichaje**, de 969 en la empresa:
el 98 % de la pantalla era basura.

El comentario decía además que traerlas todas partiría la lista en páginas. Ahí
está el círculo: **no se miraban porque eran demasiadas, y eran demasiadas porque
nadie las miraba**.

**Cómo romperlo**: cuando una comprobación se salta un conjunto por su tamaño, ese
tamaño es el dato que hay que vigilar. Un tope con un mensaje que diga «subir el
tope no es el arreglo» cuesta diez líneas y convierte un punto ciego en una alarma.

**Y separa el «no se puede» del «no se hace»**: aquí no se podía borrar a quien
tiene fichajes ---cierto--- y de ahí se había concluido que no se podía borrar a
nadie, que es falso y era el 98 % del problema.

## 244. Un recuento no es una lista de defectos: clasifica antes de arreglar

La tarea decía «sustituir las 41 esperas por reloj por esperas por condición», y
ese 41 salía de contar `waitForTimeout` en la suite. Clasificadas por lo que llevan
detrás, **solo tres eran defectos**:

- **Carrera** (3): un valor del DOM sacado a una variable, que no reintenta. Son
  los rojos intermitentes.
- **Aserción negativa** (4): se comprueba que *nada* pasó ---la consola no se
  quejó, la sesión no cambió, ningún texto quedó bajo el contraste mínimo---. Hay
  que dar margen a que el efecto indeseado ocurra, y **no hay condición que
  esperar**: quitar el reloj no la hace más rápida, la hace ciega.
- **Estado intermedio** (1): se mira a propósito antes de que llegue la respuesta.
  Tampoco es expresable como condición.
- **«A que se asiente»** (25): no sacan ningún valor, la aserción que sigue ya
  reintenta. Lentas, no frágiles: 32 s de una tanda de 11,2 min.

**La regla**: cuando una tarea llega como un número ---«hay 41 X, cámbialos---»,
el primer trabajo es **partir ese número en clases y medir cada una**. Aquí ahorró
tocar 38 sitios que no estaban mal, y en dos de ellos habría quitado cobertura.

**Y decirlo al cerrar**: la tarea no se cumple «al 7 %», se cumple, y el enunciado
era el que contaba mal.

## 245. Una prueba puede estar rota por dos motivos que se tapan entre sí

«Filtra por tipo y por estado» comprobaba `filas().count() <= todas`. Dos defectos
a la vez:

1. La **aserción era hueca**: con el filtro desconectado el conteo no cambia, y «no
   cambia» cumple `<=`. Su propio comentario decía «lo que no vale es que no cambie
   nada nunca», que es justo lo que permitía.
2. El **locator no encontraba nada**: `getByRole('row')` sobre una rejilla de
   `Box` con `display: grid` y ningún `role`. Así que `todas` valía **cero** y la
   aserción era «0 <= 0».

Cada uno tapaba al otro. Arreglar solo la aserción habría dado un rojo confuso
---«esperaba 8, recibí 0»---, y arreglar solo el locator habría dejado la
comparación inútil pasando con números de verdad.

**Cómo se detecta**: una aserción sobre un conteo que nunca has visto valer. Antes
de confiar en `expect(n).toBeLessThan(m)`, imprime `n` y `m` una vez. Si uno es
cero, la prueba no está comprobando lo que dice.

**Y el defecto de producto que había debajo**: la rejilla sin roles no la podía
recorrer un lector de pantalla. Lo encontró una prueba que fallaba por otra cosa.

## 246. Localizar por rol también obliga a que el producto tenga roles

La regla «localiza por rol» se cumple mal cuando el producto no da roles: el
locator no falla, **devuelve cero**, y una aserción negativa o un `<=` pasan en
verde para siempre.

En una rejilla hecha con `div`s hay que ponerlos a mano: `role="table"` en el
contenedor, `role="row"` en cada fila, `columnheader` en las cabeceras de columna y
`rowheader` en la primera celda de cada fila. Con eso, `getByRole('row').filter({
has: page.getByRole('rowheader') })` distingue las filas de datos de la de
cabecera ---que era el otro error: `hasNotText: 'lun'` no excluía una cabecera hecha
de números---.

**Corolario**: cuando escribas una prueba que localiza por rol sobre una pantalla
que no es una tabla de HTML, comprueba primero que el conteo sin filtros es el que
esperas. Si es cero, el trabajo no es la prueba: es el producto.

## 247. Cuanto mejor documentado está un antipatrón, más falsos positivos da buscarlo por texto

Un grep de `date.today()` dio **36 resultados, cinco en código de producción**, y
esos cinco eran **comentarios avisando de que no se use**. El módulo que resuelve
el problema ---`apps/common/clock.py`--- lo explica en su primera línea, y cada
sitio que lo evitó dejó dicho por qué. Todo ese cuidado es exactamente lo que
ensucia la búsqueda.

Con `ast`: 25 llamadas reales, ninguna en producción. Una hora perdida.

**La regla**: para buscar una llamada, usa `ast`; para buscar una cadena, grep. Y
si el patrón que buscas es un antipatrón conocido del proyecto, **da por hecho que
sus menciones superan a sus usos**.

**Y en el guard, pruébalo**: una prueba que confirme que el detector no cuenta
comentarios vale más que la que confirma que encuentra el caso obvio. Esta segunda
la escribe cualquiera; la primera es la que se rompe.

## 248. Sustituir «hoy» no es mecánico: hay que decidir de quién es el día

`local_today(X)` responde con la zona de quien pregunta: una persona con la de su
centro de trabajo, cayendo a la de su empresa. Así que cambiar `date.today()` por
él **obliga a elegir un sujeto**, y ahí está el trabajo:

- La mayoría lo tienen en un parámetro de la función: se puede automatizar con
  `ast`, que sabe qué nombres hay a mano.
- Muchos lo tienen **dentro de un diccionario** ---`mundo["empresa"]`,
  `ours["worker"]`--- donde el script no llega.
- Un **helper compartido** no tiene ninguno: hay que pasárselo, y entonces cada
  llamada tiene que decir de quién es el día. Eso mejora la prueba, no solo la
  arregla.
- A **nivel de módulo** no existe todavía ninguna empresa. Ahí lo honesto es
  anclar la zona a mano y dejar dicho por qué.

**Y el atajo que no funciona**: `timezone.localdate()` parece la respuesta y con
`TIME_ZONE = "UTC"` devuelve exactamente lo mismo que `date.today()`. Comprobar el
ajuste antes de dar por bueno un reemplazo que solo suena mejor.

**Corolario para los dobles**: un stub que finge `.id` porque la prueba solo quiere
rutas tendrá que fingir también la zona. Que un doble crezca al arreglar esto es
señal de que el código pide un dato que antes no pedía --- correcto ---, no de que
el arreglo esté mal.

## 249. Una clasificación heredada también se audita, sobre todo si justifica no hacer trabajo

El proyecto tenía decidido «se traduce lo que llega a una persona y se deja la
etiqueta de un campo», con la regla operativa «si sale de un `models.py`, es
etiqueta». La decisión era buena. **La regla que la implementaba, no**: en este
proyecto los modelos viven en seis ficheros distintos, y con `ast` resultó que
**147 de las 300 supuestas etiquetas internas eran visibles** ---tipos de ausencia,
estados, las acciones que salen en el rastro---.

Lo que hace esto peligroso es que la clasificación **justificaba no trabajar**. Una
regla que dice «esto no hace falta» se revisa menos que una que dice «esto falta»,
porque nadie va a buscar trabajo. Y cuanto más razonada esté la decisión de fondo
---aquí lo estaba, y bien--- más se confía en la regla que la aplica.

**Cómo se audita**: coge el grupo «no hace falta» y clasifícalo otra vez con un
criterio distinto. Si los dos coinciden, la regla vale; si no, la diferencia es
trabajo escondido.

## 250. Un hueco que cae de pie no se ve, y por eso no se arregla

Los 207 mensajes visibles sin traducir en catalán y gallego llevaban meses ahí, y
nadie los había dejado a propósito: se añadían funciones y los catálogos no crecían
con ellas. **No se notaba porque cada uno caía al castellano** y la pantalla seguía
siendo perfectamente legible para todo el mundo.

Es el mismo patrón que un `fuzzy` (Django lo ignora y sale el original), que un
`role` que falta (el locator devuelve cero y la aserción pasa) y que un `skip` en
una prueba (verde sin comprobar nada). **Un mecanismo de degradación elegante
esconde su propia causa.**

**La regla**: cuando montes una caída elegante ---un idioma de reserva, un valor por
defecto, un reintento callado---, monta **al lado** la comprobación de cuántas veces
se está usando. La caída es para el usuario; el recuento es para ti.

## 251. `fuzzy` no es una marca de «revísame»

La forma obvia de decir «esta traducción está sin revisar» es `#, fuzzy`. Es
exactamente lo que no hay que hacer: **Django ignora los mensajes marcados fuzzy**,
así que marcarlos así equivale a no haberlos traducido, y la pantalla vuelve al
idioma de reserva sin que nadie lo note.

La marca correcta es un comentario del traductor, `# revisar: ...`, que gettext
conserva y no cambia nada en ejecución. **Y no `#.`**, que es el hueco de los
comentarios extraídos del código: `makemessages` lo regenera en cada pasada y se
lleva la marca por delante.

**Lo general**: antes de usar un campo de metadatos para lo que parece querer decir,
comprueba **qué hace el programa con él**. Aquí «dudoso» significaba «no lo uses»,
que es casi lo contrario de lo que se quería decir.

## 252. La captura del fallo se mira **primero**, no cuando se agotan las hipótesis

Falló el arranque de la sesión de admin con un tiempo agotado en `locator.fill`.
Perseguí tres hipótesis ---credenciales, el cupo de cinco intentos por IP, el estado
de los contenedores--- y comprobé el login por API, que funcionaba. Media hora.

La captura que Playwright ya había guardado tenía la respuesta a pantalla completa:
**un icono de MUI que no existe**, y el overlay de error de Vite tapando el
formulario. El campo no aparecía porque había un panel rojo encima.

**La regla**: cuando una prueba de navegador falla por «no encuentro el elemento»,
la primera acción es abrir `test-results/.../test-failed-1.png`. Playwright la deja
sin que se la pida nadie. Razonar sobre por qué no está un elemento sin mirar la
pantalla es adivinar con los ojos cerrados.

**Y la pista que casi lo delata**: fallaba **solo el admin** y las otras tres
sesiones pasaban en medio segundo. Eso no apuntaba al admin, apuntaba al
**formulario**: las otras tres no pasan por él porque su sesión guardada seguía
valiendo. Cuando un fallo es específico de un caso, pregunta qué hace ese caso que
los demás no hacen, no qué tiene de especial.

## 253. Un icono que no existe no es un icono que falta: es la pantalla entera caída

`import PauseIcon from '@mui/icons-material/PauseCircleOutline'` no da un hueco
donde iría el icono. Vite no resuelve el módulo, pone un **overlay a pantalla
completa** y con él se cae todo lo que hubiera detrás ---incluido el formulario de
otra ruta---. Un fallo de importación en una pantalla tumba la aplicación en
desarrollo.

**Antes de importar un símbolo de una biblioteca grande, comprueba que existe en la
versión instalada**: `ls node_modules/@mui/icons-material/ | grep -i pause` cuesta
dos segundos. En MUI 9 hay `PauseCircle` y `PauseCircleOutlined`; `PauseCircleOutline`
---sin la «d»--- es de una versión anterior y es el nombre que la memoria sugiere.

Va en la misma familia que la lección del HMR: **el símbolo nuevo y su import van
en el mismo cambio, y el import se verifica contra lo que hay instalado**, no contra
lo que uno recuerda.

## 254. Al documentar algo, comprueba también la mitad que no estabas mirando

`docs/traducciones.md` se escribió mirando los catálogos de Django, y empezaba
diciendo «el producto habla castellano, catalán y gallego». Cierto del servidor. El
catálogo del **frontend** tiene 23 claves y son las del menú: el resto de la
interfaz está en castellano fijo en el código.

Así que el documento describía correctamente lo que había mirado y **falsamente el
producto**. Una empresa catalana vería el menú y los correos en catalán y la
pantalla en castellano.

**La regla**: cuando escribas «el producto hace X», enumera por dónde puede pasar X
---servidor, pantalla, correos, informes, exportaciones--- y comprueba cada uno.
Documentar la parte que se acaba de tocar es lo natural, y es justo lo que produce
un documento que exagera sin mentir en ningún dato concreto.

## 255. El número de una versión se lee, no se recuerda

Declaré `cryptography==46.0.5` de memoria y la instalación entera falló con un
conflicto de resolución: `pywebpush 2.4.0` pide una más nueva, y la que estaba
puesta y funcionando era la **50.0.0**. Lo mismo con `pillow`: escribí 12.1.0 y era
la 12.3.0.

**Al declarar una dependencia que ya está instalada ---y en una auditoría son
todas--- la versión correcta es la que hay puesta.** `pip show` o `pip freeze`
cuestan un segundo. Inventarla no da un aviso: rompe la instalación completa, y con
ella el entorno de quien venga detrás a reconstruir la imagen.

Va con la 253, que es la misma con nombres de símbolos: **lo que existe se
comprueba contra lo instalado, no contra lo que uno recuerda**.

## 256. Un aviso de seguridad se lee hasta el vector, no hasta la severidad

Dos avisos «moderados» sobre `pypdf`: consumo de memoria sin techo con un PDF
preparado a mano. Con un producto que **acepta justificantes en PDF**, la lectura
rápida es «alguien sube un fichero y tumba el servidor».

No lo era, por dos cosas que solo se ven mirando el código:

- `pypdf` estaba en `requirements/dev.txt`: la usan **cuatro pruebas**, para leer
  los PDF que genera el propio proyecto.
- Lo que sube una persona **no se parsea**. La validación mira los bytes de la
  cabecera y el tamaño. Y el informe se **escribe** con `reportlab`, que no lee.

**La regla**: de un aviso, lo que importa no es la severidad sino **quién puede
llegar a ese código con datos suyos**. Grep de la biblioteca, mira si el camino
sale de una petición, y decide con eso. Se actualiza igual ---es gratis--- pero la
diferencia entre «hay que parar todo» y «entra en la siguiente tanda» es esa
comprobación.

## 257. Una exención sin forma de comprobarla acaba justificando lo que ya no se usa

Al exigir que todo lo declarado se use, dos paquetes no aparecían en ningún fichero
porque se usan **por su efecto**: `pytest-cov` (lo invoca el CI con `--cov`) e
`ipython` (`manage.py shell` lo usa si está instalado).

Los dos son legítimos, así que van exentos. Pero una lista de exentos es una lista
de cosas que la comprobación deja de mirar, y con el tiempo justifica dependencias
que ya nadie usa. Así que cada una lleva **el motivo escrito**, y la que se puede
comprobar **se comprueba**: si desaparece la configuración de cobertura, la
exención de `pytest-cov` falla y dice que la quites de los dos sitios.

**Y la que no se puede comprobar, dicho**: la de `ipython` se sostiene solo en su
propio texto. Eso hay que escribirlo, no dejarlo intuir: la próxima persona tiene
que saber cuál de las dos exenciones tiene apoyo y cuál es una promesa.

## 258. Un modal deja el resto de la página invisible para los locators por rol

`await expect(page.getByRole('row').filter({ hasText: correo })).toHaveCount(0)`
justo después de confirmar un borrado pasaba **sin que se hubiera borrado nada**:
MUI marca el resto del documento con `aria-hidden` mientras hay un diálogo
abierto, y `getByRole` no ve lo que está oculto para accesibilidad. Cero filas, y
la aserción contenta.

**La regla**: después de pulsar dentro de un modal, **espera a que el modal se
vaya** ---`await expect(page.getByRole('dialog')).toHaveCount(0)`--- antes de
comprobar cualquier cosa de la página de debajo. Y para lo que de verdad importa,
pregunta al servidor: la pantalla puede tardar en enterarse, el servidor no.

Es la familia de la 245 y la 246: **un conteo que da cero puede darlo por una
razón que no es la tuya**. Antes de confiar en un `toHaveCount(0)`, pregúntate qué
más lo haría cierto.

## 259. Una prueba que comprueba con la API se ensucia su propia consola

La prueba pedía `GET /employees/<id>/` esperando un 404 para confirmar el borrado,
y **el navegador apunta ese 404 como error de red**. La vigilancia de la consola,
que estaba al final, lo recogía y la prueba fallaba por su propia comprobación.

**La regla**: `vigilarConsola` mira lo que hace **la pantalla**, así que su
comprobación va **antes** de cualquier llamada que haga la prueba por su cuenta.
Si tienen que convivir, filtra por lo que tú provocas ---y entonces escribe por
qué, porque un filtro en la vigilancia de errores es justo donde se esconde el
siguiente.

## 260. La marca de «sin revisar» tiene que ser verdad en cada idioma

El aplicador de traducciones ponía `# revisar: traducido sin hablante nativo` en
los tres catálogos, castellano incluido. En castellano eso **es falso**: se escribe
con conocimiento, y marcarlo pedía una revisión que nadie necesita hacer ---y
diluía las 360 marcas de catalán y gallego, que sí la piden---.

**La regla**: una marca de calidad se pone donde la condición se cumple, no en todo
lo que pasa por la misma función. Cuando una herramienta trata igual a casos
distintos, el que sobra no es inofensivo: gasta la señal.

## 261. Antes de montar un mecanismo, comprueba si el proyecto ya lo tiene a medio usar

La tarea era «montar el multiidioma de la interfaz». Estaba montado: i18next,
`ConIdioma` resolviendo el idioma desde la sesión, la empresa y el navegador, y una
decisión de diseño mejor que la que yo habría tomado ---la clave es la cadena
castellana, así que lo que falta cae al castellano igual que en el backend---.

Lo que engañaba era la cifra: **23 claves** en el catálogo. Parecía «no hay nada» y
era «hay todo y se usa en dos pantallas de treinta y ocho».

**La regla**: cuando algo parece no existir, busca el mecanismo antes que el hueco.
`grep -rl useTranslation src/` costaba dos segundos y cambiaba la estimación de
«montar más traducir» a «solo traducir» ---y, más importante, evitó traer una
segunda librería de i18n al proyecto por no haber mirado.

**Y respeta la decisión que encuentres, o discútela explícitamente.** Aquí la clave
castellana tiene su razonamiento escrito en el módulo. Cambiarla a claves con punto
habría destruido esa propiedad sin que nada avisara.

## 262. Una prueba de traducción tiene que comprobar que el original ya NO está

Con la cadena castellana como clave, `t('Ver también las bajas')` devuelve
exactamente eso cuando no hay traducción. Así que una prueba que solo compruebe
«en catalán se ve *Veure també les baixes*» falla si falta la traducción... pero una
que compruebe el título de la pantalla, o cualquier cosa que también esté en el
menú ya traducido, **pasa con el catálogo vacío**.

Lo que la hace valer es la comprobación negativa: **en catalán, el texto castellano
no puede seguir en pantalla**. Verificado vaciando el catálogo y viendo la prueba
ponerse roja.

Es la misma familia que la 250: cuando hay una caída elegante ---aquí, la clave que
es su propia traducción de reserva--- hay que comprobar explícitamente que no se
está usando.

## 263. `set(` acaba en `t(`

Mi extractor de claves contaba `set('email')` como una llamada a `t('email')`, y
salieron diecisiete claves inventadas ---`first_name`, `role`, `contract_end`---
que no existen en el código. El patrón era `t\(\s*'...'` sin límite por la
izquierda.

`(?<![A-Za-z_$.])t\(` lo arregla. Y la comprobación que lo delató en un segundo:
**mirar si las claves raras existen en el fichero**. Diecisiete nombres en inglés
minúsculas entre sesenta y seis frases en castellano cantaban solos.

Va con la 224 y la 247: **un detector con resultados que no encajan con el resto es
un detector mal hecho**, y el patrón corto es el que más se equivoca.

## 264. Antes de escribir una prueba, busca la que ya comprueba eso

Escribí `53-la-pantalla-en-tres-idiomas` sin mirar si existía algo parecido.
Existía: `36-interfaz-traducida`, desde antes, comprobando la misma cadena por otro
camino. Y me enteré porque **la rompí**: usaba como muestra de «algo sin traducir»
justo el texto que yo acababa de traducir.

`ls e2e/ | grep -i traduc` costaba dos segundos. Es la gemela de la 261 ---busca el
mecanismo antes que el hueco--- aplicada a las pruebas.

Las dos se han quedado porque de verdad no se solapan, y **eso hay que escribirlo
en las dos**: si no, la siguiente persona borrará una creyendo que sobra.

## 265. Una prueba que necesita que algo siga roto lleva fecha de caducidad: pónsela por escrito

«Lo que todavía no está traducido sale en castellano» necesita, por definición,
**algo sin traducir**. Es una comprobación legítima ---es la condición que hace
utilizable un catálogo a medias--- pero su caso desaparece según avanza el trabajo.

Dejarla apuntando a una muestra concreta sin decir nada la convierte en una mina:
rompe sin motivo aparente, y quien la encuentre puede «arreglarla» debilitándola.

**Lo que hay que dejar escrito, en la propia prueba**: que va a romperse, que ese
rojo significa avance, de dónde traer la siguiente muestra, el historial de las
anteriores, y **qué hacer el día que no quede ninguna** ---aquí, borrarla, porque el
guard del catálogo completo la sustituye---. Una prueba que se queda sin caso y
sigue en verde es peor que no tenerla.

## 266. Una prueba que opera sobre «su» fila tiene que buscarla, no confiar en verla

La prueba del borrado creaba una persona y buscaba su fila con
`getByRole('row').filter({ hasText: correo })`. Pasaba sola y fallaba en la tanda
completa: con decenas de filas ---las que dejan las demás pruebas--- la recién
creada no estaba en la parte visible ni en la primera página.

**La regla**: si la pantalla tiene buscador o filtro, **úsalo**. Es lo que haría
una persona, y hace la prueba independiente de cuántas filas haya. Fiarse de que
«acabo de crearla, estará arriba» funciona en una base vacía y falla en cuanto el
proyecto crece, que es justo cuando la prueba hace falta.

## 267. Cuando construyas la función que faltaba, ve a buscar quién la estaba echando de menos

Al terminar el borrado de altas equivocadas, lo que quedaba pendiente no era
código: era **usarlo donde el problema aparecía**. `darDeBajaLasDePrueba` solo
podía dar de baja, y por eso el sedimento crecía tres personas por tanda y el guard
saltaba cada pocas vueltas.

Añadir una línea allí resolvió de raíz lo que el guard venía avisando desde la
vuelta 128 ---y el aviso ya lo decía: «o una prueba está creando personas que no
necesita, o hace falta poder borrar de verdad»---.

**La regla**: una función nueva no está terminada cuando pasa sus pruebas. Está
terminada cuando **los sitios que la necesitaban la usan**. Busca en el cuaderno y
en los mensajes de los guards quién pedía exactamente esto: normalmente está
escrito, con nombre y fecha.

## 268. Una muestra que no cambia entre idiomas no comprueba una traducción

Elegí «Mes anterior» como texto de control para comprobar la pantalla en catalán.
Se escribe igual en los tres idiomas, así que la aserción que da valor a esa prueba
---que el texto castellano **ya no está**--- no podía cumplirse nunca.

Y el rojo era desconcertante: fallaba en catalán y gallego, pasaba en castellano, y
apuntaba a una línea que parecía correcta.

**La regla**: al elegir texto para comprobar una traducción, **comprueba primero
que el texto cambia**. Es una aserción de dos líneas sobre la propia tabla de datos
de la prueba, y convierte un fallo confuso en uno que dice exactamente qué pasa.

Es la familia de la 245 y la 258: **una aserción puede fallar (o pasar) por una
razón que no es la que crees**, y el sitio barato para descubrirlo es validar los
datos de entrada de la propia prueba.

## 269. Los roles de MUI no son los que se suponen

Dos en la misma vuelta:

- `<TextField type="number">` expone rol **`spinbutton`**, no `textbox`.
- `<Switch>` expone **`switch`**, no `checkbox`.

Y ya salió antes que una rejilla de `Box` con `display: grid` **no expone nada**.

**La regla**: antes de escribir `getByRole('x')` sobre un componente de una
biblioteca, compruébalo ---la propia página en modo depuración lo dice, o un
`page.getByRole('...').count()` en una prueba de usar y tirar---. Suponer el rol
da un locator que devuelve cero, y cero es exactamente lo que muchas aserciones
aceptan sin protestar.

## 270. Los números van dentro de la frase, no cosidos alrededor

«Se muestran {mostradas} de {total}. Usa los filtros…» se puede escribir en JSX
partiendo el texto en tres trozos con los números en medio. Traducirlo así es
imposible: los trozos por separado no significan nada, y **en otro idioma no van
necesariamente en ese orden**.

Con la clave entera y la interpolación de i18next ---`{{mostradas}}`,
`{{total}}`--- quien traduce ve la frase completa y coloca los huecos donde su
idioma los pida.

**La regla**: una cadena traducible es **una frase entera**. Si tienes que
concatenar para meter un dato, el dato va como parámetro con nombre, no como
trozo de la concatenación. Y el nombre importa: `{{cuantas}}` se traduce mejor que
`{{n}}`.

## 271. Una salvaguarda vale más cuando cambia lo que eliges que cuando salta

En la vuelta anterior puse una comprobación que exige que el texto de muestra de la
prueba de idiomas **cambie entre idiomas**, después de perder un rato con «Mes
anterior», que se escribe igual en los tres.

En esta vuelta iba a elegir «Por decidir» ---idéntico en castellano y gallego--- y
me detuve antes de escribirlo, porque sabía que saltaría. La salvaguarda no llegó a
ejecutarse y ya había hecho su trabajo.

**Vale la pena escribirlo así**: el valor de una comprobación no se mide solo por
las veces que se pone roja, sino por las decisiones que cambia mientras está en
verde. Eso también es una razón para que su mensaje explique **por qué** falla y no
solo que falla.

## 272. Una medida que no ve la mitad es peor que no medir

Llevaba tres vueltas diciendo «quedan 160 cadenas en 23 ficheros». Eran **719 en
41**. La diferencia no era un margen de error: mi extractor de traducciones estaba
hecho con expresiones regulares y se dejaba dos familias enteras.

- Los **párrafos partidos** por un `<strong>` o un `<code>`: el patrón no cruzaba
  el salto de línea, así que una frase de tres líneas con la cifra en negrita en
  medio, sencillamente, no existía.
- Los **rótulos dentro de un objeto** ---`{label: 'Pendiente'}`---, que es donde
  viven todos los estados de `common.jsx`, o sea los que salen en todas las
  pantallas a la vez.

Lo caro no fue el número. Fue que **di por terminadas tres pantallas que no lo
estaban**, y las cerré con su commit y su entrada en el cuaderno. Un hueco que
nadie ha medido sigue estando a la vista de quien abra esa pantalla; un hueco que
una medida declara inexistente ya no lo va a mirar nadie.

**La regla**: antes de dejar que una medida gobierne el trabajo, comprobar contra
un caso conocido **que la medida encuentra lo que ya sabes que está ahí**. Aquí el
aviso llegó solo y por casualidad ---tres cadenas que había traducido «de más»
resultaron estar en el fichero y no en mi lista---. Esa discrepancia era el
contraste que no había hecho. Cuando aparezca una así, no es ruido: es la medida
diciendo que está mal.

Y el corolario de herramienta: para leer código, el árbol de sintaxis. `grep` sirve
para encontrar dónde mirar, no para contar cuánto falta.

## 273. Un mapa de constantes no se traduce donde se escribe

`const KIND_LABELS = { ADD: 'Añadir un fichaje que falta' }` se evalúa **una vez, al
cargar el módulo**, cuando todavía no se sabe en qué idioma va a mirarlo nadie.
Poner `t()` ahí lo congela en el idioma del arranque, y encima con un `t` que a esa
altura no existe.

La solución no es dejarlo sin marcar: eso lo vuelve invisible para la comprobación
de catálogos, que busca la cadena literal en el código. Es marcarlo con una función
identidad ---`alCatalogo()` aquí, `gettext_noop` en gettext--- y traducir en el
punto de uso.

Y el detalle que casi se me escapa: ese mismo mapa alimentaba el **buscador**. Si
solo se traduce donde se lee, el filtro sigue comparando contra el castellano y
escribir «Canviar l'hora» en catalán no encuentra nada. **Un rótulo traducido tiene
que estar traducido en los dos sitios: donde se pinta y donde se busca.**

## 274. Un mecanismo nuevo entra con la prueba que lo mira

`<Trans>` se estrenó en esta vuelta para las frases que llevan la cifra en negrita
en medio. Las cinco pruebas de idioma que ya existían habrían seguido en verde con
`<Trans>` completamente roto: ninguna miraba esas frases, y en pantalla se leería
`<destacado>3 días</destacado>` tal cual sin que nada lo dijera.

Lo barato fue no montar una prueba nueva: `05-ausencias` **ya fabricaba** el exceso
de tope para comprobar el aviso, así que el dato estaba sembrado y solo había que
mirar dos cosas más. Buscar la prueba que ya tiene el escenario montado sale más a
cuenta que escribir una desde cero ---y la deja cubriendo algo más, en vez de
sumar otro fichero a la tanda---.

## 275. Lo que no cambia de idioma se ve más que lo que falta

Seis pantallas traducidas enteras al catalán seguían diciendo «Agosto de 2026» en
la cabecera, porque nueve sitios formateaban con `'es-ES'` escrito a mano.

La diferencia con una cadena sin traducir es de lectura, no de cantidad. Lo que
falta cae al castellano y se lee como «esto todavía no está»; una fecha en
castellano dentro de una pantalla en catalán se lee como **un descuido**, porque
todo lo de alrededor sí cambió. La segunda hace más daño con menos motivo.

Y tenía dos causas encadenadas, las dos invisibles desde el catálogo:

1. El locale escrito a mano, que es la que se ve buscando `'es-ES'`.
2. **El idioma se fijaba en un `useEffect`**, o sea después del primer pintado.
   `useTranslation` repinta a quien lo usa; un módulo de utilidades no es un
   componente y no puede usarlo, así que lo que él escribe se queda con el idioma
   de arranque para siempre.

**La regla**: al revisar si algo está traducido, mirar también lo que **no** pasa
por el catálogo ---fechas, horas, números, monedas, órdenes de clasificación---.
El catálogo al 100 % no significa que la pantalla hable un solo idioma.

## 276. La singularización mecánica no sobrevive al cambio de idioma

`noun.replace(/s$/, '')` para sacar «persona» de «personas». En castellano cuela
casi siempre; en catalán, «persones» da «persone», que no es una palabra, y
«correccions» da «correccion», sin el acento que la hace serlo.

Lo llamativo es que el proyecto **ya tenía** un `plural(n, una, muchas)` escrito en
agosto justo por esto, con su prueba, y aun así dos componentes seguían quitando la
«s». El helper existía y no se había aplicado donde hacía falta: **una herramienta
escrita no es una herramienta usada**, y al arreglar un defecto conviene buscar
todos sus hermanos antes de darlo por cerrado.

Al cambiar la firma ---`noun={{ singular, plural }}`--- salió otra: nombrar las
claves con género (`una`/`varias`) se lee bien en el punto de llamada y **no
generaliza**, porque el mismo componente cuenta cosas de los dos géneros. El
nombre neutro es peor de leer una vez y correcto siempre.

## 277. El espacio de separación no es parte de la clave

`t(' · sin sueldo')`, con el espacio dentro. Seis veces, y una me la había hecho yo
la vuelta anterior.

El espacio ahí es maquetación: separa este trozo del anterior. Pero viaja dentro de
la clave, y en cuanto la clave pasa por cualquier sitio que recorte ---mi lista de
pendientes, un editor de catálogos, una hoja de cálculo--- la traducción se guarda
sin él. Entonces el código pide « · sin sueldo» y el catálogo tiene «· sin sueldo»:
i18next no encuentra nada y devuelve la clave, **que se lee perfectamente en
castellano**. Un hueco que no parece un hueco.

Lo que lo hizo durar fue el punto ciego de la comprobación: `comprobar-catalogos`
busca cada clave en el código con `includes`, y la versión recortada **sí** es una
subcadena de la entera. Verde con el agujero dentro.

**La regla**: el espacio va fuera. `` `${t('· sin sueldo')} ` `` y no `t(' · sin
sueldo')`. Y cuando una comprobación use `includes` o `in`, preguntarse qué pareja
de valores distintos pasaría por igual --- ahí es donde se esconden estos.

## 278. La prueba no puede pedirle al producto que le dé de qué hablar

La tabla de la prueba de idiomas exigía, por pantalla, un texto y un **control** que
cambiaran de idioma. Al llegar a Aplicaciones no había ninguno: su único botón
siempre visible es «Autorizar», que se escribe igual en castellano y en gallego.

La tentación fue retocar la traducción gallega para que difiriera. Habría sido
escribir peor gallego para que una prueba tuviera qué mirar --- y el gallego lo lee
gente y la prueba no.

Se hizo al revés: `control` pasó a ser opcional, con el motivo escrito al lado. Una
prueba que no puede comprobar algo debe decirlo y seguir comprobando el resto, no
empujar al producto a encajar en ella.

## 279. Cuando un guard salta, la primera pregunta es qué está midiendo

El guard del sedimento saltó, y no por lo que vigila. Vigila que no se acumulen
personas de prueba por encima de sesenta; lo que dijo fue que **la lista ya no cabía
en una página** y se negaba a dar por limpio lo que no había visto.

Si hubiera leído «sedimento» y subido el tope, habría tapado las dos cosas a la vez:
la que avisaba y la que ni siquiera había mirado. Y la comprobación que se niega a
mirar media lista es la parte buena del guard, no la que estorba.

**La regla**: leer el mensaje, no el nombre de la prueba. Y cuando un guard tiene una
salvaguarda propia ---«esto no es todo lo que hay»--- esa salvaguarda salta antes que
lo que vigila, y dice algo distinto.

El diagnóstico después cambió el plan entero: ninguna de las sesenta era de hoy, o
sea que el arreglo de hace seis vueltas funciona y esto era sedimento viejo. Sin
mirar las fechas habría ido a buscar una regresión que no existía.

## 280. Una regla correcta puede dejar una tarea recurrente, y eso no la invalida

Veintidós de las personas de prueba no se pueden borrar porque cada una tiene una
ausencia aprobada, y la regla dice que quien tiene una ausencia aprobada no es un
alta equivocada. La regla es correcta. La prueba que las crea también tiene razón:
aprueba lo que pide, y una aprobada no se cancela.

Las dos partes bien y el resultado es basura que se acumula. La tentación era mover
una de las dos ---relajar la regla, o hacer que la prueba no apruebe--- y las dos
habrían empeorado algo real para arreglar algo de laboratorio.

Lo que faltaba era una tercera pieza que no existía: **la escoba**. Un comando de
mantenimiento del entorno, fuera del producto, que se niega en producción y aplica la
misma regla que la API. Cuando dos decisiones correctas producen residuo, el residuo
es una tarea de mantenimiento, no una prueba de que una de las dos esté mal.

## 281. Antes de traducir una lista, preguntar si tiene que traducirse

Dos de las de esta vuelta no.

**Los nombres de los idiomas** no se traducen: van en su propio idioma. Quien abre
ese desplegable puede no entender el idioma en el que está la pantalla ---es
exactamente por eso por lo que lo abre--- y «Inglés» no le dice nada a quien busca
«English». Estaba a medias, con dos en castellano y dos en el suyo, y la salida no
era pasarlos por `t()` sino terminar el criterio que ya había empezado.

**Los doce meses** tampoco: los da el navegador con el locale, igual que las fechas.
Estaban escritos a mano, y traducirlos habría sido mantener tres listas de doce
palabras que `Intl` ya sabe.

**La regla**: cuando una lista de rótulos aparece en la cuenta de lo pendiente,
mirar antes si el idioma le aplica siquiera ---nombres propios, endónimos, unidades,
símbolos--- y si el sistema ya la sabe. Traducirla es lo más caro de las tres
salidas y a veces es la peor.

## 282. Una prueba que depende de lo que falta por hacer lleva su caducidad escrita

Para abrir el formulario de ausencias hay que pulsar un botón de la pantalla que lo
contiene, y esa pantalla todavía no está traducida. Escrito a lo fácil, el selector
habría sido «Solicitar» y se pondría rojo el día que a esa pantalla le toque su
tanda --- un rojo por trabajo bien hecho, que es el peor de todos porque enseña a
desconfiar de la suite.

Acepta los dos rótulos, `/^(Solicitar|Demanar)$/`, con el motivo al lado.

Es la misma forma de la lección 265 y de la muestra «sin traducir» de la prueba 36:
cuando algo depende de un estado transitorio del proyecto, o se escribe para que
sobreviva al cambio, o se deja escrito **cuándo** va a romperse y qué hacer entonces.
Lo que no vale es dejarlo mudo.
