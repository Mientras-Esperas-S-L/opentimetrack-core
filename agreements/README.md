# Fichas de convenio

Un formato abierto para escribir los parámetros de tiempo de trabajo de un
convenio colectivo, de manera que un programa pueda aplicarlos y una persona
pueda comprobarlos.

Esto no es un catálogo. Es el **formato** del catálogo, más las fichas que hemos
podido verificar contra el texto oficial. Tres fichas que alguien puede
contrastar valen más que doscientas volcadas a ciegas, y una ficha equivocada es
peor que ninguna: la empresa que confía en ella incumple creyendo que cumple.

## Qué es y qué no es

**Es** un conjunto de parámetros con su procedencia: de qué artículo sale cada
cifra, de qué boletín, de qué fecha, quién lo transcribió y cuándo se comprobó
por última vez.

**No es** el convenio. Lo aplicable es el texto publicado. Esto ayuda a
configurar un sistema y **puede estar desactualizado o mal transcrito**. Por eso
cada valor lleva el artículo del que sale: para que se pueda ir al original y
discutirlo.

**No decide qué convenio aplica.** Qué convenio rige una relación laboral
depende de la actividad, del ámbito territorial y a veces de más cosas. El
sistema propone; lo confirma la empresa.

## El formato

Una ficha es un fichero YAML. El esquema está en `schema.json` y se valida con:

```
python manage.py check_agreements
```

Las tres partes de una ficha:

```yaml
agreement:      # qué convenio es, y cómo comprobarlo
  regcon: "99002995011981"
  source:
    publication: "BOE-A-2026-2227"
    url: https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-2227

working_time:   # los parámetros, cada uno con su artículo
  weekly_hours:
    value: 38.6
    basis: "Art. 16"
    note: "1700 h anuales; el semanal es una derivada, no una cifra del texto"

provenance:     # quién responde de la transcripción
  transcribed_by: ...
  verified_on: 2026-08-12
```

### Por qué cada valor lleva `basis` y `note`

Porque las cifras de un convenio casi nunca son directamente las que un programa
necesita. El convenio de jardinería fija **1700 horas al año**; nuestro sistema
compara semanas. Convertir una en otra es una operación con supuestos, y quien
lea la ficha tiene derecho a saber cuál se hizo y a decir que está mal.

Un valor sin `basis` no se acepta: el esquema lo rechaza.

## Verificado y sin verificar

`provenance.verified_on` es la fecha en que alguien abrió el boletín y comparó.
No es la fecha en que se escribió el fichero.

Una ficha con `verified_on` antigua sigue siendo válida —los convenios duran
años— pero el sistema lo muestra, porque un dato que lleva dos años sin mirar y
uno comprobado ayer no merecen la misma confianza.

**Si no se ha podido verificar, la ficha no entra.** Hay convenios del sector que
no están aquí por eso, y es preferible a que estén mal. La ausencia es
información: significa «configúralo tú», no «no hay convenio».

## Añadir una ficha

1. Copia `_template.yaml`.
2. Abre el texto oficial. No una web que lo resuma: el boletín.
3. Rellena cada valor con el artículo del que sale.
4. Lo que no encuentres, déjalo fuera. Un valor omitido usa el mínimo legal; un
   valor inventado se aplica como si fuera cierto.
5. `python manage.py check_agreements`
6. En el mensaje del commit, di qué comprobaste y contra qué.

## Licencia

Las fichas se publican bajo **CC BY 4.0**, aparte de la AGPL del código. La idea
es que se puedan usar, corregir y redistribuir sin arrastrar la licencia del
programa: un formato que solo sirve dentro de un producto no llega a ser un
formato.
