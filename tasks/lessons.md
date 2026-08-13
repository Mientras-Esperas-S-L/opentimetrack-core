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
