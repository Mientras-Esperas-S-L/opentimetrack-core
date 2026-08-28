/** Qué texto ve una persona en pantalla, y cuánto de él pasa por `t()`.
 *
 *  El compañero de `comprobar-catalogos.mjs`, que mira la otra dirección: aquel
 *  comprueba que ninguna traducción se ha quedado huérfana, y este que ninguna
 *  cadena visible se ha quedado fuera.
 *
 *  Con el árbol y no con expresiones regulares, y no por gusto. Medí con grep
 *  durante tres tandas y la cuenta salía en 160 cadenas; el árbol dice 719. Lo
 *  que el grep no veía eran dos familias enteras:
 *
 *    - los párrafos partidos por un `<strong>` o un `<code>`, porque el patrón
 *      no cruzaba el salto de línea;
 *    - los rótulos que viven dentro de un objeto ---`{label: 'Pendiente'}`---,
 *      que es donde están todos los estados de `common.jsx`, o sea los que
 *      salen en todas las pantallas a la vez.
 *
 *  Con esa medida di por terminadas pantallas que no lo estaban. Contar de
 *  menos es peor que no contar: no deja un hueco, deja un hueco *y* la
 *  impresión de que no lo hay.
 *
 *      node scripts/lo-que-se-ve.mjs                 # el resumen por fichero
 *      node scripts/lo-que-se-ve.mjs src/pages/…     # el detalle de unos pocos
 */

import { parse } from '@babel/parser'
import _traverse from '@babel/traverse'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const traverse = _traverse.default ?? _traverse

export const RAIZ = new URL('..', import.meta.url).pathname

/** Props y claves de objeto cuyo valor acaba en pantalla.
 *
 *  La lista es explícita a propósito: `variant`, `color` y `size` también
 *  llevan cadenas, y nadie las lee. */
const PROPS = new Set([
  'label',
  'title',
  'placeholder',
  'helperText',
  'subtitle',
  'aria-label',
  'hint',
  'noun',
  'secondary',
  'primary',
  'text',
  'alt',
  'summary',
  'i18nKey',
  'all',
])
const CLAVES = new Set([
  'label',
  'title',
  'body',
  'detail',
  'verb',
  'hint',
  'subtitle',
  'secondary',
  'text',
  'noun',
  'message',
  // Las dos formas de un sustantivo contable, que viajan juntas en un objeto:
  // `noun={{ singular: 'persona', plural: 'personas' }}`.
  'singular',
  'plural',
])

const ACENTO = /[áéíóúñüÁÉÍÓÚÑÜ¿¡]/
const LETRA = /[A-Za-zÁÉÍÓÚÑáéíóúñ]/

/** CSS, que también son cadenas y nadie lee. Un valor de `sx`, un selector, una
 *  consulta de medios, una pila de fuentes. Se descarta por la forma y no por
 *  una lista de nombres, que es lo que hace que sirva mañana. */
const ES_CSS = [
  /^&/, // un selector anidado de emotion
  /\.Mui[A-Z]/, // ...y el que apunta a una pieza de MUI
  /^\(\s*(prefers|min-width|max-width|hover|pointer)/, // una consulta de medios
  /\d+(px|rem|em|vh|vw|ch|fr|%)\b/, // cualquier medida
  /\b(repeat|calc|rgba?|hsla?|var|linear-gradient|repeating-linear-gradient|translate|scale)\(/,
  /\b(solid|dashed|dotted|inset|ease-in-out|sans-serif|system-ui)\b/,
]

/** Prosa, no identificador. Descarta `success`, `PENDING`, `es-ES`, `2xl`. */
function pareceTexto(s) {
  const limpia = s.trim()
  if (limpia.length < 3 || !LETRA.test(limpia)) return false
  if (ES_CSS.some((patron) => patron.test(limpia))) return false
  if (/^[a-z][a-zA-Z0-9]*$/.test(limpia)) return false // camelCase suelto
  if (/^[A-Z0-9_]+$/.test(limpia)) return false // CONSTANTE
  if (/^[\w.-]+\/[\w./-]*$/.test(limpia)) return false // rutas y tipos MIME
  return limpia.includes(' ') || ACENTO.test(limpia) || /^[A-ZÁÉÍÓÚÑ¿¡]/.test(limpia)
}

/** Una cadena suelta, fuera de toda posición declarada, aun así se lee si es
 *  prosa castellana: el `?? 'Continuar'` de un botón, el valor por defecto de
 *  un parámetro. */
function prosaCastellana(s) {
  const limpia = s.trim()
  if (!pareceTexto(limpia)) return false
  if (/\S\s+\S/.test(limpia) || ACENTO.test(limpia)) return true
  // Una palabra sola y sin acento: cuenta si lleva mayúscula inicial, que es
  // como se escribe un rótulo y no como se escribe un valor.
  return /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}$/.test(limpia)
}

const nombreDe = (n) =>
  n.type === 'JSXNamespacedName' ? `${n.namespace.name}-${n.name.name}` : (n.name ?? n.value)

/** `t()` traduce ahora; `alCatalogo()` marca la cadena para traducirla en el
 *  punto de uso. Las dos la dejan dentro del catálogo, que es lo que aquí se
 *  mide. */
const LLAMADAS = new Set(['t', 'alCatalogo'])

/** Y `i18next.t(...)`, que es como se traduce donde no hay componente al que
 *  enganchar el hook: `format.js`, `bulk.js`, `api.js`. */
const esLaLlamada = (nodo) =>
  (nodo.callee.type === 'Identifier' && LLAMADAS.has(nodo.callee.name)) ||
  (nodo.callee.type === 'MemberExpression' &&
    nodo.callee.object.type === 'Identifier' &&
    nodo.callee.object.name === 'i18next' &&
    nodo.callee.property.name === 't')

const bajoT = (camino) =>
  camino.findParent((p) => p.isCallExpression() && esLaLlamada(p.node)) != null

const bajoTrans = (camino) =>
  camino.findParent((p) => p.isJSXElement() && p.node.openingElement.name.name === 'Trans') != null

/** Lo visible de un fichero, separado en lo que ya pasa por `t()` y lo que no. */
export function loQueSeVe(ruta) {
  const arbol = parse(readFileSync(ruta, 'utf8'), { sourceType: 'module', plugins: ['jsx'] })
  const dentro = new Set()
  const fuera = new Map() // texto -> primera línea donde sale

  const anota = (texto, camino) => {
    const s = texto.replace(/\s+/g, ' ').trim()
    if (!pareceTexto(s)) return
    if (bajoT(camino) || bajoTrans(camino)) dentro.add(s)
    else if (!fuera.has(s)) fuera.set(s, camino.node.loc?.start.line ?? 0)
  }

  traverse(arbol, {
    JSXText(camino) {
      anota(camino.node.value, camino)
    },
    StringLiteral(camino) {
      const padre = camino.parent
      if (padre.type === 'JSXAttribute' && PROPS.has(nombreDe(padre.name)))
        anota(camino.node.value, camino)
      else if (
        padre.type === 'ObjectProperty' &&
        !padre.computed &&
        CLAVES.has(nombreDe(padre.key))
      )
        anota(camino.node.value, camino)
      else if (bajoT(camino)) anota(camino.node.value, camino)
      else if (prosaCastellana(camino.node.value)) anota(camino.node.value, camino)
    },
    TemplateLiteral(camino) {
      // Un `${…}` dentro no impide que el resto sea prosa. Se anota la
      // plantilla entera con los huecos marcados, que es como acaba escrita la
      // clave cuando se traduce.
      const partes = camino.node.quasis.map((q) => q.value.cooked)
      if (partes.join('').replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ]/g, '').length < 2) return
      anota(partes.join('{{}}'), camino)
    },
  })

  return { dentro: [...dentro].sort(), fuera: [...fuera.entries()].sort() }
}

/** Todo el código de la aplicación, menos el propio mecanismo de traducción. */
export function ficherosDeLaAplicacion() {
  const recorre = (dir) =>
    readdirSync(dir).flatMap((nombre) => {
      const ruta = join(dir, nombre)
      if (statSync(ruta).isDirectory()) return nombre === 'i18n' ? [] : recorre(ruta)
      return /\.jsx?$/.test(nombre) ? [ruta] : []
    })
  return recorre(join(RAIZ, 'src')).sort()
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const dados = process.argv.slice(2)
  const ficheros = dados.length ? dados : ficherosDeLaAplicacion()
  let sinTraducir = 0
  let traducidas = 0

  for (const ruta of ficheros) {
    const { dentro, fuera } = loQueSeVe(ruta)
    traducidas += dentro.length
    sinTraducir += fuera.length
    if (!fuera.length) continue
    console.log(
      `\n=== ${relative(RAIZ, ruta)}  (${fuera.length} de ${fuera.length + dentro.length})`,
    )
    if (dados.length)
      for (const [s, linea] of fuera) console.log(`  ${String(linea).padStart(4)}  ${s}`)
  }

  const total = traducidas + sinTraducir
  const hechas = total ? Math.round((traducidas / total) * 100) : 100
  console.log(`\n${traducidas} de ${total} cadenas visibles pasan por t() (${hechas} %).`)
  console.log(`Quedan ${sinTraducir}.`)
}
