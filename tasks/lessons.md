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
