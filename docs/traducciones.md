# Idiomas: qué está traducido y qué pide revisión

El producto habla **castellano, catalán y gallego**. El castellano está completo;
los otros dos están **traducidos sin hablante nativo** y eso hay que saberlo antes
de enseñárselos a un cliente.

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

Las traducciones al catalán y al gallego las hizo Claude el **27/08/2026**, sin
hablante nativo. Francisco lo aprobó así: «no vamos a disponer de nativos que lo
supervisen; haz lo que puedas. Si en un futuro tenemos que corregir traducciones,
se hace».

Cada una lleva su marca en el catálogo:

```
# revisar: traducido sin hablante nativo el 2026-08-27
msgid "Sick leave"
msgstr "Baixa mèdica"
```

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
