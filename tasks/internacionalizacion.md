# Qué hace falta para que sirva fuera de España

Escrito el 12/08/2026 tras medir dónde está lo español, no tras suponerlo. Las
cifras de abajo salen de contar sobre el código de hoy y son reproducibles con
los comandos que aparecen al final.

**Resumen en una línea:** el núcleo ya es neutro, lo español es una capa fina y
está mal separada, y el trabajo real no es traducir sino sacar la base legal a
un módulo por país.

---

## Por qué tiene sentido plantearlo

La sentencia del TJUE de 14 de mayo de 2019 (**C-55/18**, *CCOO contra Deutsche
Bank*) obliga a todos los estados miembros a exigir un sistema **objetivo,
fiable y accesible** de registro de la jornada diaria. La necesidad existe en
los 27, no solo aquí; España se limitó a legislarla antes y con más detalle.

Lo que cambia de un país a otro son las cifras, los procedimientos y qué
documento se entrega. La forma del registro —eventos con hora de servidor, sin
sobrescritura, con trazabilidad— es la misma en todos.

---

## Lo que ya es neutro

Esto no hay que tocarlo, y conviene tenerlo escrito para no rehacerlo por
inercia.

| | |
|---|---|
| Almacenamiento | Siempre UTC. Cada empresa lleva su zona, y un despliegue puede servir a la vez a una empresa en Madrid y a otra en Canarias |
| Identificador fiscal | Genérico ya: *«Company tax number (CIF/NIF, VAT, EIN…)»*. Sin validación de formato español |
| Idioma | Todo pasa por gettext, y el código fuente está en inglés. La cadena de resolución ya está hecha: primero la persona, luego su empresa, luego el navegador |
| Fichaje | La hora la pone el servidor, el tipo se infiere, no se edita ni se borra. Nada de eso es español |
| Aislamiento | Multiempresa por `ContextVar` y gestor por defecto, sin nada geográfico |

Y una pieza que **ya está puesta y nadie usa**: `Tenant.country`, con
`help_text` que dice literalmente *«ISO 3166-1 alpha-2 code. Selects the
applicable legal rules»*. Se escribe al registrar una empresa y **no lo lee
ningún sitio**. Ese campo es el gancho de todo lo que sigue.

---

## Lo que es español, medido

### 1. Diecinueve citas legales llegan a la pantalla

No son comentarios: están dentro de `help_text`, de `message=` o de `basis=`, y
por tanto acaban en la interfaz o en el informe.

| Fichero | Cuántas |
|---|---|
| `apps/shifts/services.py` | 8 |
| `apps/tenants/rules.py` | 3 |
| `apps/users/models.py` | 2 |
| `apps/users/serializers.py` | 2 |
| `apps/punches/models.py` | 2 |
| `apps/punches/corrections.py` | 1 |
| `apps/punches/services.py` | 1 |

Un cliente alemán vería «Art. 34.3 ET» en su pantalla de ajustes. Traducirlas no
arregla nada: traducidas dirían lo mismo en alemán, y seguiría siendo la ley
española.

Las de `shifts/services.py` son las de los avisos del cuadrante, y esas son las
que importan: cada aviso dice de qué artículo sale, que es lo que permite
discutirlo. Sin cita, el aviso pierde su razón de ser; con la cita equivocada,
miente.

### 2. Las protecciones de menores son constantes del módulo

Seis, en `apps/tenants/rules.py`:

```
MINOR_MAX_DAILY_HOURS = 8         MINOR_WEEKLY_REST_HOURS = 48
MINOR_BREAK_AFTER_HOURS = 4.5     MINOR_NIGHT_WORK_FORBIDDEN = True
MINOR_BREAK_MINUTES = 30          MINOR_OVERTIME_FORBIDDEN = True
```

Están así **a propósito**: son suelos que ningún convenio puede rebajar, y
hacerlas configurables sería ofrecer un ajuste cuyo único uso es incumplir. Ese
razonamiento sigue valiendo dentro de un país y deja de valer entre países,
porque los suelos cambian. Alemania (JArbSchG) y Francia (art. L3162 del Code
du travail) tienen los suyos.

Son constantes de España, no constantes del producto.

### 3. Siete de los ocho idiomas devuelven inglés

Declarados: `es`, `en`, `ca`, `gl`, `eu`, `fr`, `pt`, `de`.
Catálogos que existen: **uno**, el español, con 371 cadenas y una sin traducir.

Elegir «Catalán» o «Alemán» hoy da inglés, en silencio. No es un fallo —gettext
cae al original, que está en inglés y es legible— pero el desplegable promete
ocho idiomas y sirve dos.

### 4. Ocho formatos de fecha fijados al español en el frontend

Ocho usos de `toLocaleDateString('es-ES', …)` y similares. Un usuario alemán ve
la interfaz en su idioma y las fechas en formato español.

Distinto de los siete usos de `'sv-SE'`, que **son correctos y no hay que
tocar**: es el truco estándar para obtener `AAAA-MM-DD` de la fecha local sin
pasar por UTC.

### 5. Tres artefactos con forma española

- **El informe de jornada** tiene la forma del art. 34.9 y del art. 3 del
  proyecto de real decreto: qué columnas, qué totales, qué se marca.
- **El resumen de nómina** existe porque lo pide el art. 6.1, con el periodo
  atado al ciclo de pago.
- **El flujo de corrección** implementa el art. 4.b: autorización de las dos
  partes, discrepancia registrada, aviso a la representación legal.

El tercero es el más interesante. Ese procedimiento es *bueno* independientemente
de la ley que lo exija —hace que el registro sostenga dos relatos del mismo día—
así que probablemente se queda como comportamiento del producto y no como
requisito español.

### 6. Las fichas de convenio son un concepto español

Convenio colectivo estatal, provincial, REGCON, BOE. La idea de un acuerdo
sectorial que mejora el mínimo legal existe en otros sitios con otra forma
(*Tarifvertrag* en Alemania, *convention collective* en Francia), pero el
formato de `agreements/schema.json` está escrito con el vocabulario de aquí:
`regcon`, ámbito estatal/provincial, publicación en boletín.

---

## El plan

### Fase 0 · Decidir el alcance antes de tocar nada

No es programación y es lo que decide todo lo demás.

- ¿Vender fuera, o solo permitir que alguien autoaloje fuera? No es lo mismo:
  lo segundo pide un producto configurable, lo primero pide responder de que
  las cifras son correctas, y eso es lo que hace caro cada país.
- ¿Qué país primero? Y sobre todo: **quién conoce su normativa**. Sin eso, un
  módulo de país es un fichero de números inventados con la misma pinta que los
  buenos.

Vale aquí el mismo razonamiento que en el catálogo de convenios: publicar el
formato y que la asesoría de cada cliente ponga sus cifras traslada la
afirmación a quien tiene el criterio.

### Fase 1 · Sacar la ley a un módulo por país — **HECHA (12/08/2026)**

El trabajo de fondo. `Tenant.country` ya existe y ya dice que sirve para esto.

```
apps/legal/
├── __init__.py       # resuelve el módulo según tenant.country
├── base.py           # el contrato: qué tiene que ofrecer un país
├── es.py             # lo que hoy está repartido por seis ficheros
└── de.py, fr.py…     # después
```

Qué expone un módulo de país:

- **Valores por defecto** de `WorkingTimeRules` al crear una empresa.
- **Suelos de menores**, hoy constantes de módulo.
- **Citas**: qué artículo respalda cada regla, para que el aviso siga siendo
  discutible.
- **Comprobaciones propias**, si el país tiene alguna que España no.

Lo delicado: **las citas no se traducen, se sustituyen**. `basis="Art. 34.3 ET"`
tiene que venir del módulo del país, no del catálogo de idiomas. Un mismo texto
en alemán con la cita española sería peor que dejarlo en español, porque
parecería correcto.

Se estimaron dos o tres semanas y salió en una tarde, porque las reglas ya
estaban bien escritas: solo había que reunirlas. La medida se cumplió —las 448
pruebas anteriores siguen verdes sin tocar ninguna— y hay diez nuevas que
registran un país inventado con cifras distintas de las españolas y lo siguen
hasta el final.

Lo que quedó, además de lo previsto:

- Un país desconocido cae en la **Directiva 2003/88/CE**, no en España. Era la
  decisión importante: las cifras españolas bajo otra bandera parecerían
  configuradas y nadie las cuestionaría.
- **`/api/working-time-rules/` sirve las citas**, y la pantalla de ajustes pinta
  lo que le den. Eso resolvió de paso la duplicación: las seis citas escritas a
  mano en el frontend ya no existen.
- Las constantes `MINOR_*` siguen exportadas desde `tenants/rules.py` como capa
  de reenvío, para no romper las llamadas existentes. Código nuevo debe pedirle
  los suelos al marco.

Una prueba destapó algo en el momento: el cuadrante seguía leyendo esas
constantes de compatibilidad, que son las de España, así que los suelos de
menores no cambiaban de país. Para eso estaban.

### Fase 2 · Que la interfaz siga al idioma

Más pequeño y más visible.

- Los ocho `'es-ES'` del frontend pasan a la locale de la sesión. Los siete
  `'sv-SE'` se quedan.
- Catálogos de verdad para los idiomas que se declaren. **O quitar del
  desplegable los que no existan**: ofrecer ocho y servir dos es peor que
  ofrecer dos.
- Revisar los idiomas declarados: `ca`, `gl` y `eu` son de aquí y tienen sentido
  ya; `fr`, `pt` y `de` solo si se va a esos países.

Trabajo estimado: **tres a cinco días** el mecanismo, más lo que cueste cada
traducción.

### Fase 3 · El informe

El artefacto donde más se nota la forma española, y el que más cuesta hacer
genérico sin dejarlo peor para todos.

La salida razonable no es un informe universal, sino que el módulo de país
aporte su plantilla, sobre los mismos datos. Los datos ya son neutros: eventos,
tramos, totales, correcciones marcadas, huella. Lo que cambia es qué columnas
lleva, qué se declara y en qué orden.

Trabajo estimado: **una semana por país**, y hay que verlo con quien vaya a
entregarlo allí.

### Fase 4 · Convenios, si procede

El formato de ficha se generaliza o se deja como cosa española. No es urgente y
no bloquea nada: sin ficha, rigen los mínimos del módulo de país.

---

## Cuánto es

| | |
|---|---|
| ~~Fase 1, el refactor~~ | **hecha** |
| Fase 2, formatos e idiomas | 3–5 días |
| Fase 3, informe del primer país | ~1 semana |
| **Primer país nuevo, total** | **~2 semanas**, ya sin la fase 1 |
| Cada país siguiente | 1–2 semanas, más quien conozca su normativa |

La parte que no se puede acelerar programando es la última columna. Un módulo de
país lo escribe alguien que sabe qué dice esa ley, igual que las fichas de
convenio de aquí las escribió alguien leyendo el BOE.

---

## Lo que no hay que hacer

**No traducir las citas legales.** «Art. 34.3 ET» en alemán sigue siendo la ley
española y parecería correcto.

**No hacer configurables los suelos de menores.** El razonamiento por el que hoy
son constantes sigue valiendo: un ajuste cuyo único uso es incumplir. Lo que
cambia es de dónde salen, no que se puedan tocar.

**No anunciar multipaís antes de la Fase 1.** Hoy diría «Art. 34.3 ET» en la
pantalla de un cliente alemán, y eso no se arregla con una nota al pie.

---

## Reproducir las cifras

```bash
# Citas legales que llegan a pantalla, por fichero
cd backend && python3 - <<'PY'
import pathlib, re
for f in sorted(pathlib.Path("apps").rglob("*.py")):
    if "/tests/" in str(f) or "/migrations/" in str(f): continue
    n = sum(
        1 for m in re.finditer(r'(help_text=|message=|basis=|_\()[^\n]{0,400}', f.read_text())
        if re.search(r"Art\.\s?\d|RD \d|Estatuto|ET\b", m.group(0))
    )
    if n: print(f"{n:3}  {f}")
PY

# Catálogos que existen frente a idiomas declarados
ls locale/*/LC_MESSAGES/django.po
grep -A10 "^LANGUAGES = \[" config/settings/base.py

# Formatos fijados en el frontend
cd ../frontend
grep -rn "'es-ES'" src/ | wc -l    # a corregir
grep -rn "'sv-SE'" src/ | wc -l    # correctos, no tocar
```
