# Idiomas: qué está traducido y qué pide revisión

El producto habla **castellano** entero. Del catalán y del gallego hay **el
servidor traducido y la pantalla a medias**, y las traducciones que hay se
hicieron **sin hablante nativo**. Las dos cosas hay que saberlas antes de
enseñárselo a un cliente.

| Qué | Catalán y gallego |
|---|---|
| Lo que responde el servidor: correos, errores, avisos legales, tipos y estados | **Traducido** ---558 de 711 mensajes; el resto son etiquetas de campo que se dejan a propósito--- |
| La pantalla: botones, rótulos, textos de cada página | **En curso** ---764 de 921 cadenas al 28/08/2026. Diecinueve pantallas enteras ---la de fichar incluida---, el formulario de pedir una ausencia y todo lo compartido (menú, paginadores, filtros, estados, fechas)--- |

Así que una empresa catalana ve hoy el menú, los correos y los errores en
catalán, seis pantallas en catalán y el resto en castellano. **Hasta que esté
entera no se puede anunciar como «disponible en catalán»**, y así lo dice el
dossier.

## Cómo se cuenta lo que falta

```bash
cd frontend
npm run i18n:falta     # cuántas cadenas visibles no pasan por t(), por fichero
npm run i18n:check     # y que ninguna traducción se haya quedado huérfana
```

El espacio de separación **va fuera de la clave**: `` `${t('· sin sueldo')} ` ``
y nunca `t(' · sin sueldo')`. Dentro se pierde en cuanto la clave pasa por algo
que recorte, y entonces el código pide una cosa y el catálogo guarda otra: se lee
en castellano y nada avisa. Lo comprueba `i18n:check`.

Los dos scripts miran direcciones contrarias y hacen falta los dos.
`comprobar-catalogos.mjs` comprueba que **toda traducción le corresponde a una
cadena del código**; `lo-que-se-ve.mjs`, que **toda cadena visible del código
pasa por el catálogo**.

El segundo lee el **árbol de sintaxis**, no expresiones regulares, y no por
gusto: la medida hecha con grep decía 160 cadenas cuando eran 719. Se dejaba los
párrafos partidos por un `<strong>` ---el patrón no cruzaba el salto de línea---
y los rótulos que viven dentro de un objeto, que es donde están los estados
compartidos de `common.jsx`. Con esa cuenta se dieron por terminadas tres
pantallas que no lo estaban.

## Cómo se traduce una pantalla

La clave **es la cadena en castellano**, no un identificador: `t('Ver también
las bajas')`. El razonamiento entero está en `src/i18n/index.js` y se resume en
que lo no traducido cae al castellano solo, igual que en el backend, y en que
estas pantallas se revisan leyéndolas.

Tres formas, según dónde esté la cadena:

| Dónde | Cómo |
|---|---|
| Un texto o un rótulo | `t('Rechazar la solicitud')` |
| Una frase con un dato o una etiqueta en medio | `<Trans i18nKey="… <destacado>{{exceso}}</destacado> …" values={…} components={{ destacado: <strong /> }} />` |
| Un mapa de constantes, fuera de todo componente | `alCatalogo('Anular un fichaje')` al declararlo, y `t(MAPA[clave])` al pintarlo |

`<Trans>` es para lo que no se puede partir. Envolver los trozos de «Las fechas
se pusieron con **3 días** de antelación» por separado obligaría a traducir «de
antelación, y el» suelto, que no es una frase en ningún idioma y en catalán ni
siquiera va ahí.

`alCatalogo()` es `gettext_noop` con otro nombre: el mapa se evalúa al cargar el
módulo, cuando todavía no se sabe en qué idioma va a mirarlo nadie, así que la
cadena se marca ahí y se traduce en el punto de uso. Y ojo con los mapas que
además **alimentan un buscador**: si solo se traduce donde se pinta, el filtro
sigue comparando contra el castellano y escribir en catalán no encuentra nada.

## Lo que no pasa por el catálogo

Un catálogo al 100 % no significa que la pantalla hable un solo idioma.

**Lo que no se traduce y no es un hueco.** Los nombres de los idiomas van cada
uno en el suyo ---«English», no «Inglés»---: quien abre ese desplegable puede no
entender el idioma en el que está la pantalla. Y los meses los da `Intl` con el
locale, así que no hay tres listas de doce palabras que mantener.

**Las fechas y las horas** salen de `toLocaleDateString`, no de `t()`. Iban con
`'es-ES'` escrito a mano en nueve sitios, así que seis pantallas traducidas
enteras decían «Agosto de 2026» encima. El locale sale ahora de
`localeDeFechas()`, en `src/i18n/index.js`. **Ningún `'es-ES'` nuevo**: lo mira
la prueba `las fechas también hablan el idioma`.

**Los sustantivos contables** llevan las dos formas. `Pager` y `SelectionBar`
reciben `noun={{ singular: 'persona', plural: 'personas' }}` y eligen con
`plural()`. Sacar el singular quitándole la «s» al plural da «persone» en
catalán, que no es una palabra.

**Y el idioma se fija antes de pintar**, no en un efecto: `useTranslation` solo
repinta a quien lo usa, y `format.js` no es un componente. Cambiar de idioma en
caliente remonta la aplicación con una `key`, que cuesta el estado de la
pantalla y pasa una vez.

## Qué se traduce y qué no

**Se traduce lo que llega a una persona**: los correos, los errores y avisos de la
API, los tipos de ausencia, los estados, las acciones que salen en el rastro, los
textos legales del cuadrante.

**No se traduce la etiqueta de un campo** ---el `verbose_name` o el `help_text` de
un `models.CharField`---. Son ciento cincuenta y tres, y se dejan a propósito: solo
salen en el panel de Django y en el esquema de la API, que los usa el equipo.

Eso funciona porque **lo que falta cae al castellano, no al inglés**:
`LANGUAGE_CODE` es `es` y Django encadena por ahí. Si cayera al inglés ---que es el
idioma en que se escriben los originales--- una empresa catalana vería su producto
en dos idiomas extranjeros a la vez. Está comprobado en
`test_lo_que_no_esta_traducido_cae_al_castellano_y_no_al_ingles`, porque de ese
comportamiento depende toda la decisión.

Y lo vigila `test_los_dos_idiomas_van_al_dia`, que clasifica cada cadena con `ast`
---mirando **qué la envuelve**, no en qué fichero está--- y exige que lo visible
esté en los dos idiomas. Sin ese guard el criterio no se sostiene: el 27/08/2026
había **207 mensajes visibles sin traducir** que nadie había dejado así a
propósito. Se fueron añadiendo funciones y los catálogos no crecieron con ellas, y
no se notaba porque cada uno caía al castellano.

## Lo que pide revisión

Las traducciones al catalán y al gallego las hizo Claude desde el **27/08/2026**,
sin hablante nativo. Francisco lo aprobó así: «no vamos a disponer de nativos que lo
supervisen; haz lo que puedas. Si en un futuro tenemos que corregir traducciones,
se hace».

Cada una lleva su marca en el catálogo:

```
# revisar: traducido sin hablante nativo el 2026-08-27
msgid "Sick leave"
msgstr "Baixa mèdica"
```

En el frontend no hay dónde poner esa marca ---el catálogo es un JSON, sin
comentarios---, así que vale para todo el fichero: **`ca.json` y `gl.json` están
sin revisar enteros**.

Para verlas todas, o contarlas:

```bash
grep -c '^# revisar:' backend/locale/ca/LC_MESSAGES/django.po
grep -A3 '^# revisar:' backend/locale/gl/LC_MESSAGES/django.po | less
```

**La marca es un comentario del traductor** (`# `) y no un `#.`, que es el hueco de
los comentarios extraídos del código y `makemessages` regenera en cada pasada. Y
**no** se usa `#, fuzzy` para esto, que sería lo aparentemente correcto: Django
**ignora** los mensajes marcados fuzzy, así que marcarlos así equivaldría a no
haberlos traducido, y la pantalla volvería al castellano sin que nadie lo notara.

Cuando alguien las revise, lo que hay que hacer es corregir lo que esté mal y
**quitar la marca** de lo que quede aprobado. Lo que siga marcado es lo que sigue
sin revisar.

## Al añadir un mensaje nuevo

```bash
cd backend
python manage.py makemessages -l es -l ca -l gl --no-obsolete
# traducir en los tres catálogos
python manage.py compilemessages
```

Dos cosas que la construcción comprueba y conviene saber antes:

- **Cero mensajes marcados `fuzzy`** en los tres idiomas. Cuando `makemessages`
  encuentra un texto parecido al que cambió, arrastra la traducción vieja y la
  marca así. Django la ignora, así que un `fuzzy` es un hueco disfrazado ---y a
  veces peor: en agosto uno arrastraba «Consultó el registro de otra persona»
  como traducción de «entregó a alguien su propio registro»---.
- **El castellano completo**, y el catalán y el gallego completos en lo visible.

## Euskera

Estuvo montado y **se retiró a propósito**: medio idioma en un producto que
explica obligaciones legales confunde más de lo que ayuda. Si vuelve, vuelve
entero.
