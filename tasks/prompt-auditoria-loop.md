# Prompt de auditoría en bucle

La versión de `tasks/prompt-auditoria-completa.md` pensada para `/loop`: pasadas
cortas, que se acuerdan de la anterior y paran solas cuando dejan de encontrar
nada.

## Cómo lanzarlo

```
/loop 45m <pega aquí el prompt de abajo>
```

Cuarenta y cinco minutos es un intervalo razonable: una pasada acotada da
tiempo a explorar un área, arreglar lo que salga y dejar las suites en verde. Si
lo pones más corto, las pasadas se cortan a medias y la siguiente empieza sin
saber dónde se quedó ---por eso el cuaderno de abajo no es opcional---.

Con `/loop` sin intervalo, el propio bucle decide cuándo volver.

---

## El prompt

> Auditoría continua de OpenTimeTrack. Cada pasada hace **un trozo acotado**,
> lo deja terminado y verde, y anota qué falta. No intentes abarcarlo todo en
> una vuelta: el bucle se encarga de que haya más.
>
> ### Lo primero de cada pasada: el cuaderno
>
> Lee `tasks/auditoria-continua.md`. Si no existe, créalo con este esqueleto y
> con el inventario completo de pantallas, endpoints y áreas legales por
> revisar, todas en estado «sin tocar»:
>
> ```markdown
> # Auditoría continua — cuaderno
>
> Vueltas dadas: 0 · Vueltas seguidas sin hallazgos: 0
>
> ## Áreas
> | Área | Estado | Última pasada | Hallazgos |
> |---|---|---|---|
> | Personas | sin tocar | — | — |
> | ... | | | |
>
> ## Hallazgos abiertos
> (ninguno todavía)
>
> ## Cerrado
> (nada todavía)
>
> ## Descartado a propósito
> (con el motivo, para no volver a proponerlo)
> ```
>
> El cuaderno manda. **No vuelvas a un área en estado «limpia»** mientras queden
> áreas «sin tocar»: repetir lo fácil es la forma más habitual de que un bucle
> parezca productivo sin serlo.
>
> ### Qué hacer en la pasada
>
> Elige **un área** ---la primera «sin tocar», o la más antigua si ya no
> quedan--- y hazle todo esto:
>
> 1. **Inventario real del DOM o de la API.** Los rótulos que crees que hay casi
>    nunca son los que hay.
> 2. **Ejercítala entera**: cada campo, botón, desplegable, pestaña, filtro,
>    acción de fila y diálogo. Guardar con todo, guardar sin lo obligatorio,
>    valores en el límite y fuera, rangos al revés, reabrir el formulario para
>    ver que no arrastra estado. Listas: vacía, con una fila, con varias
>    páginas. Descargas: **ábrelas**.
> 3. **Escucha la consola.** Un `console.error` es un fallo.
> 4. **Seguridad, por API y con la sesión del atacante.** Otra empresa, un
>    operario, parámetros manipulados. Un botón que no se pinta no demuestra
>    nada sobre lo que el servidor acepta.
> 5. **Ley**, si el área toca alguna: comprueba en el código que se ejecuta, no
>    en el marco ni en los comentarios. «Solo citado» es lo más peligroso,
>    porque parece cubierto.
> 6. **Los cuatro perfiles**, si el área tiene pantalla: operario con el móvil y
>    con prisa, responsable un lunes con veinte personas, administración en el
>    cierre de mes, e Inspección pidiendo un periodo. Haz su tarea entera y anota
>    dónde te atascas.
>
> ### Cómo buscar (esto es lo que rinde)
>
> - **Comprueba los bytes, no la extensión.** Un zip empieza por `PK`.
> - **Valida toda comprobación limpia contra un caso conocido.** Si un filtro
>   «no devuelve nada raro», pruébalo con un valor que sí deba devolver algo.
> - **Pregunta al producto, no al rótulo.** Los contadores llegan tarde.
> - **Limpia antes de crear, no solo después.**
> - **Localiza por rol, no por texto literal.**
> - **Si el frontend no ve algo que el servidor manda, mira CORS primero.**
> - **Muchos fallos a la vez no son muchos fallos**: sospecha de la prueba.
> - **Antes de escribir un mecanismo transversal, busca si ya existe** en
>   `components/`, `hooks/` y `services/`.
>
> ### Las líneas que no se cruzan
>
> - **El registro de jornada no se toca en masa.** Un asiento se corrige de uno
>   en uno (art. 4.b). Un «seleccionar todo» ahí es un fallo, no una mejora.
> - **Resolver en bloque solo si cada decisión guarda su rastro** con nombre y
>   apellidos, y sin saltarse la separación de las cuatro manos.
> - **Donde la ley admite excepción, avisa citando el artículo; no impidas.** Y
>   la cifra va en el marco legal del país, nunca escrita en la pantalla.
>
> ### Antes de cerrar la pasada
>
> Obligatorio, y en este orden:
>
> 1. Arregla lo que hayas encontrado, con **una prueba que impida que vuelva**.
>    Playwright para el frontend, pytest para el backend.
> 2. Deja **las dos suites enteras en verde**, los linters limpios, las
>    traducciones completas y sin migraciones pendientes. Nunca termines una
>    pasada con el repositorio roto: la siguiente empezaría a ciegas.
> 3. **No lances dos suites a la vez.** Comparten servidor y base de datos, y el
>    resultado son decenas de fallos que no existen. Si ves muchos rojos de
>    golpe, comprueba eso antes que nada.
> 4. Actualiza el cuaderno: el estado del área, los hallazgos abiertos, lo
>    cerrado, y lo descartado **con su motivo**.
> 5. Si has aprendido algo que evite repetir un error, añádelo a
>    `tasks/lessons.md` como regla.
>
> ### Cuándo parar
>
> Al final de cada pasada, actualiza el contador del cuaderno:
>
> - Si has encontrado algo, «vueltas seguidas sin hallazgos» vuelve a 0.
> - Si no has encontrado nada **y no quedan áreas sin tocar**, súmale uno.
>
> **Para el bucle cuando llegue a 3**, y no antes. Tres vueltas completas sin un
> solo hallazgo es convergencia; una sola es haber mirado poco. Al parar, deja
> en el cuaderno un resumen de lo cerrado y de lo descartado.
>
> Si en algún momento el repositorio queda roto y no puedes arreglarlo en la
> pasada, **para el bucle y dilo**: seguir dando vueltas sobre algo roto no
> converge, acumula.
>
> ### Cada pasada, en dos líneas
>
> Termina diciendo qué área tocaste, qué encontraste y en qué quedó el contador.
> Sin prólogos.

---

## Por qué está partido así

Tres decisiones que no son de estilo:

**El cuaderno.** Sin un fichero que sobreviva entre vueltas, cada pasada empieza
de cero y acaba revisando lo mismo ---lo que se encuentra rápido--- mientras lo
difícil no se toca nunca. El estado por área es lo que obliga a avanzar.

**Un área por vuelta.** Una pasada que intenta todo se queda a medias, y una
pasada a medias deja el repositorio en un estado que la siguiente no entiende.

**Tres vueltas en blanco, no una.** Una vuelta sin hallazgos puede ser
casualidad, un área pequeña o una pasada floja. Tres seguidas, con todas las
áreas ya visitadas, es otra cosa.
