/** Que no quede texto de pantalla sin pasar por el catálogo.
 *
 *  La otra mitad de `comprobar-catalogos.mjs`. Aquel vigila que ninguna
 *  traducción se haya quedado huérfana; este, que ninguna cadena visible se
 *  haya quedado fuera --- que es lo que iba a medias por diseño hasta que dejó
 *  de ir a medias.
 *
 *  ## Por qué hace falta ahora y no antes
 *
 *  Mientras la conversión estaba a medias, lo no traducido caía al castellano
 *  y eso era **correcto**: la clave es la cadena castellana. Terminada la
 *  conversión, esa misma propiedad se vuelve el problema: una pantalla nueva
 *  escrita sin `t()` se lee perfectamente en castellano y nadie la ve hasta
 *  que alguien mira la aplicación en catalán. Sin esta comprobación, el
 *  producto vuelve a las andadas una pantalla cada vez.
 *
 *  ## Lo que no se traduce, y por qué
 *
 *  El último 5 % de una migración así no es trabajo pendiente: es trabajo de
 *  clasificación. Hay texto que aparece en el código, se ve o casi, y **no
 *  debe** traducirse --- nombres propios, teclas, cabeceras HTTP---. Un guard
 *  que exija cero sin decir cuáles son esas es un guard que obliga a traducir
 *  «Chrome», y a los dos meses alguien lo apaga.
 *
 *  Así que van aquí, una a una, con su motivo. Añadir una es declarar por
 *  escrito que esa cadena no se lee o no se traduce, y eso es una decisión que
 *  se revisa, no un silencio.
 *
 *      node scripts/comprobar-lo-visible.mjs
 */

import { ficherosDeLaAplicacion, loQueSeVe, RAIZ } from './lo-que-se-ve.mjs'
import { readFileSync } from 'node:fs'
import { join, relative } from 'node:path'

/** `fichero: {cadena: por qué no se traduce}`. */
const NO_SE_TRADUCE = {
  'src/services/push.js': {
    Android: 'nombre del sistema',
    Windows: 'nombre del sistema',
    Linux: 'nombre del sistema',
    Chrome: 'nombre del navegador',
    Edge: 'nombre del navegador',
    Firefox: 'nombre del navegador',
    Safari: 'nombre del navegador',
    Notification: 'la API del navegador, que se comprueba por su nombre',
  },
  'src/services/api.js': {
    'Bearer {{}}': 'la cabecera HTTP se escribe así o no autentica',
    '[catálogo] {{}} tiene {{}} elementos y se han traído {{}}:':
      'aviso de consola para quien desarrolla, no para quien usa',
    'lo que falta no se podrá elegir': 'la segunda mitad de ese mismo aviso',
  },
  'src/components/format.js': {
    '{{}} h {{}} min': 'símbolos de duración, iguales en los tres idiomas',
    '{{}} min': 'símbolos de duración, iguales en los tres idiomas',
  },
  'src/pages/SignIn.jsx': {
    OpenTimeTrack: 'el nombre del producto',
  },
  'src/pages/admin/Roster.jsx': {
    Escape: 'el valor de `event.key`, no un texto',
  },
  'src/pages/admin/TeamCalendar.jsx': {
    Enter: 'el valor de `event.key`, no un texto',
  },
  'src/hooks/useAuth.js': {
    'useAuth must be used inside AuthProvider': 'error de programación, para quien programa',
  },
  'src/hooks/useColorScheme.js': {
    'useColorScheme must be used inside Providers': 'error de programación, para quien programa',
  },
  'src/theme.js': {
    // El paquete de español de MUI traduce «open» por lo que el desplegable
    // **está**, no por lo que el botón **hace**. La corrección ya va por
    // idioma, en el propio fichero.
    Abrir: 'corrección del paquete de MUI, ya declarada por idioma',
  },
}

let fuera = 0
let dentro = 0
let exentas = 0
const sobran = []
/** Todo lo que pasa por `t()`, para cotejarlo luego con los catálogos. */
const enElCodigo = new Set()

for (const ruta of ficherosDeLaAplicacion()) {
  const relativa = relative(RAIZ, ruta)
  const permitidas = NO_SE_TRADUCE[relativa] ?? {}
  const { dentro: hechas, fuera: pendientes } = loQueSeVe(ruta)
  dentro += hechas.length
  for (const cadena of hechas) enElCodigo.add(cadena)

  const sinJustificar = pendientes.filter(([cadena]) => !(cadena in permitidas))
  if (sinJustificar.length) {
    fuera += sinJustificar.length
    console.error(`\n${relativa}: ${sinJustificar.length} sin pasar por el catálogo`)
    for (const [cadena, linea] of sinJustificar) console.error(`  ${linea}  ${cadena}`)
  }

  // Y al revés: una exención que ya no le corresponde a nada es una decisión
  // vieja que sigue tapando. Si la cadena se tradujo o desapareció, la
  // exención sobra y hay que quitarla.
  const vistas = new Set(pendientes.map(([cadena]) => cadena))
  for (const cadena of Object.keys(permitidas)) {
    if (vistas.has(cadena)) exentas += 1
    else sobran.push(`${relativa}: ${JSON.stringify(cadena)}`)
  }
}

if (sobran.length) {
  console.error(`\n${sobran.length} exención(es) que ya no le corresponden a nada:`)
  for (const linea of sobran) console.error(`  · ${linea}`)
  console.error('  Quitar la línea de NO_SE_TRADUCE: esa cadena ya no está o ya se traduce.')
}

// El contraste, y aquí importa más que en ningún otro sitio: si el lector
// dejara de encontrar cadenas, cero pendientes se leería como «está todo
// traducido» en vez de «no se ha mirado nada».
if (dentro < 500) {
  console.error(`\nSolo se han visto ${dentro} cadenas traducidas: eso no es esta aplicación.`)
  process.exit(2)
}

// Y que lo que pasa por `t()` esté **traducido**, que es la mitad que faltaba.
//
// `comprobar-catalogos.mjs` mira que no sobren traducciones; esto mira que no
// falten. Su docstring decía que lo contrario no se comprobaba «a propósito,
// porque la conversión va a medias por diseño», y eso dejó de ser cierto el
// 28/08/2026, cuando la interfaz quedó entera en los tres idiomas. Nadie rehízo
// el criterio, así que durante trece vueltas se podía añadir una pantalla nueva
// sin traducir y `i18n:check` daba verde: la cadena cae al castellano y en
// pantalla no se distingue de una traducción correcta.
const IDIOMAS = ['ca', 'gl']
const sinTraducir = []
for (const idioma of IDIOMAS) {
  const catalogo = JSON.parse(readFileSync(join(RAIZ, `src/i18n/locales/${idioma}.json`), 'utf8'))
  const faltan = [...enElCodigo].filter((cadena) => !(cadena in catalogo))
  if (faltan.length) sinTraducir.push([idioma, faltan])
}

if (sinTraducir.length) {
  for (const [idioma, faltan] of sinTraducir) {
    console.error(`\n${faltan.length} cadena(s) sin traducir en ${idioma}:`)
    for (const cadena of faltan.slice(0, 20)) console.error(`  · ${JSON.stringify(cadena)}`)
    if (faltan.length > 20) console.error(`  ... y ${faltan.length - 20} más`)
  }
  console.error(
    '\nSe traducen en el mismo paso que se escriben. Si no hay quien lo revise,\n' +
      'tradúcelo lo mejor que puedas: media pantalla en castellano dentro del\n' +
      'catalán no se ve como un hueco, se ve como una traducción mala.',
  )
}

// El consejo va con el problema que se ha encontrado. Aconsejar «envuélvelo en
// `t()`» a quien lo tiene envuelto y sin traducir manda a mirar donde no es.
if (fuera || sobran.length) {
  console.error(
    '\nLa clave **es** la cadena castellana, así que lo que no pasa por `t()` se lee\n' +
      'perfectamente en castellano y no lo delata nada hasta que alguien mira la\n' +
      'aplicación en catalán. Envuélvelo, o declara aquí por qué no se traduce.',
  )
}

if (fuera || sobran.length || sinTraducir.length) process.exit(1)

console.log(
  `Nada visible fuera del catálogo: ${dentro} cadenas traducidas y ${exentas} exentas con motivo.`,
)
