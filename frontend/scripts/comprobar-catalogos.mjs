/** Que los catálogos y el código sigan hablando del mismo texto.
 *
 *  Las claves de traducción **son** las cadenas en castellano. Eso es lo que
 *  hace que un catálogo a medias caiga al castellano solo, sin configurar nada,
 *  igual que el backend cae a `LANGUAGE_CODE`. Y trae un precio: retocar una
 *  coma del castellano deja su traducción huérfana **en silencio**, porque la
 *  clave nueva no existe en el catálogo y i18next devuelve la clave, que se lee
 *  perfectamente en castellano. Nadie se entera hasta que alguien mira la
 *  aplicación en catalán.
 *
 *  Es el mismo agujero que gettext tapa con `#, fuzzy` en el backend, y aquí no
 *  hay quien lo tape solo. Esto lo tapa: cada clave de cada catálogo tiene que
 *  aparecer literalmente en el código.
 *
 *  No comprueba lo contrario ---que todo lo del código esté traducido--- a
 *  propósito: la conversión va a medias por diseño y lo no traducido cae al
 *  castellano, que es correcto. Lo que no puede haber es una traducción que ya
 *  no le corresponde a nada.
 *
 *      node scripts/comprobar-catalogos.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const RAIZ = new URL('..', import.meta.url).pathname
const CATALOGOS = join(RAIZ, 'src/i18n/locales')

const ficherosDe = (dir) =>
  readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) return ficherosDe(ruta)
    return /\.jsx?$/.test(nombre) ? [ruta] : []
  })

const codigo = ficherosDe(join(RAIZ, 'src'))
  .map((f) => readFileSync(f, 'utf8'))
  .join('\n')

let problemas = 0

/** Una clave con un espacio en el borde ---`t(' · sin sueldo')`--- es un hueco
 *  esperando: el espacio es separación, no texto, y quien traduce lo pierde sin
 *  darse cuenta. Entonces el código pide « · sin sueldo» y el catálogo guarda
 *  «· sin sueldo», i18next no encuentra nada y devuelve la clave, que se lee
 *  perfectamente en castellano.
 *
 *  Y lo peor: la comprobación de abajo **no lo ve**, porque busca la clave con
 *  `includes` y la versión sin espacio sí es una subcadena del código. Pasó con
 *  «(+3 días si hay desplazamiento)», que estuvo un día entero sin traducir en
 *  catalán con todo en verde.
 */
const CLAVES_EN_EL_CODIGO = /(?<![A-Za-z_$.])t\(\s*'((?:[^'\\]|\\.)*)'/g
const conBorde = [...codigo.matchAll(CLAVES_EN_EL_CODIGO)]
  .map((m) => m[1])
  .filter((clave) => clave !== clave.trim() && clave.trim().length > 0)

if (conBorde.length) {
  problemas += conBorde.length
  console.error(`\n${conBorde.length} clave(s) con un espacio en el borde:`)
  for (const clave of new Set(conBorde)) console.error(`  · ${JSON.stringify(clave)}`)
  console.error("  El espacio va fuera de la clave: `${t('…')} ` en vez de `t(' …')`.")
}

for (const fichero of readdirSync(CATALOGOS).filter((f) => f.endsWith('.json'))) {
  const idioma = fichero.replace('.json', '')
  const catalogo = JSON.parse(readFileSync(join(CATALOGOS, fichero), 'utf8'))
  const claves = Object.keys(catalogo)

  const huerfanas = claves.filter((clave) => !codigo.includes(clave))
  if (huerfanas.length) {
    problemas += huerfanas.length
    console.error(`\n[${idioma}] ${huerfanas.length} clave(s) que ya no están en el código:`)
    for (const clave of huerfanas) console.error(`  · ${JSON.stringify(clave)}`)
  }

  const vacias = claves.filter((clave) => !String(catalogo[clave]).trim())
  if (vacias.length) {
    problemas += vacias.length
    // Una traducción vacía no cae a la clave: gana, y deja el hueco en blanco.
    // Pasó en el backend con una forma plural sin rellenar y se leyó como «».
    console.error(`\n[${idioma}] ${vacias.length} traducción(es) en blanco:`)
    for (const clave of vacias) console.error(`  · ${JSON.stringify(clave)}`)
  }
}

// El contraste, porque cero problemas no prueba nada por sí solo: si la lectura
// del código fallara y `codigo` viniera vacío, TODAS las claves saldrían
// huérfanas y esto sería ruidoso, no silencioso. El riesgo real es el otro
// ---leer de más y que todo parezca presente--- así que se comprueba que el
// corpus es el que se cree.
if (codigo.length < 100_000) {
  console.error(`\nSolo se han leído ${codigo.length} caracteres de código: eso no es el proyecto.`)
  process.exit(2)
}

// Y el contraste de la comprobación del borde, por lo mismo: si el patrón
// dejara de encajar con nada, cero claves con espacio parecería un producto
// limpio en vez de una comprobación rota.
if ([...codigo.matchAll(CLAVES_EN_EL_CODIGO)].length < 200) {
  console.error('\nApenas se han reconocido llamadas a t(): el patrón ya no encaja con el código.')
  process.exit(2)
}

if (problemas) {
  console.error(`\n${problemas} problema(s). Los catálogos están en src/i18n/locales/.`)
  process.exit(1)
}

console.log(`Catálogos al día. ${codigo.length} caracteres de código revisados.`)
