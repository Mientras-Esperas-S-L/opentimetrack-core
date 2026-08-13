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
