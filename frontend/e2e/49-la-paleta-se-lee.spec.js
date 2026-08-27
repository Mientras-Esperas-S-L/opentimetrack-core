/** Los colores del tema, contados en vez de mirados.
 *
 *  Ya hay un barrido de contraste ---`30-contraste`--- que recorre pantallas y
 *  mide lo que encuentra. Es imprescindible y tiene un hueco por construcción:
 *  **solo ve los estados que estén en pantalla ese día**. El terracota se
 *  arregló en su momento «no por el barrido sino por la cuenta, al mirar por qué
 *  fallaba el otro», y el ámbar de aviso ---3,11 con el texto blanco que MUI le
 *  pone encima--- estuvo ahí hasta que una corrección quedó en «esperando a la
 *  empresa» y la pantalla lo enseñó por casualidad.
 *
 *  Esto no depende del azar: coge la paleta y hace la cuenta. Un color nuevo mal
 *  elegido se caza el día que se escribe, no el día que a alguien le toca verlo.
 *
 *  El umbral es 4,5 ---AA para texto normal--- y no 3, porque estos colores
 *  llevan encima el texto de un chip o de un botón, no un titular.
 */

import { expect, test } from '@playwright/test'

import { buildTheme } from '../src/theme.js'

const MINIMO = 4.5

/** Luminancia relativa, tal como la define WCAG 2.1. */
function luminancia(hex) {
  const canal = (v) => {
    const x = v / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)
}

function contraste(a, b) {
  const [x, y] = [luminancia(a), luminancia(b)]
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

/** El texto que MUI pone sobre un color relleno.
 *
 *  Su regla ---`getContrastText`--- no es «claro u oscuro por luminancia», que es
 *  la aproximación de manual: pone **blanco siempre que el blanco llegue a 3**
 *  sobre ese fondo, y solo si no llega recurre al casi negro. La diferencia no es
 *  académica: con la regla de manual, el rojo de error salía a 4,18 contra texto
 *  oscuro, y con la de verdad sale a 3,68 contra el blanco que le pone MUI. Una
 *  daba por bueno un color que no se lee. */
const encima = (fondo) => (contraste(fondo, '#ffffff') >= 3 ? '#ffffff' : '#212121')

const ROLES = ['primary', 'secondary', 'success', 'warning', 'error', 'info']

for (const modo of ['light', 'dark']) {
  test(`la paleta en tema ${modo === 'light' ? 'claro' : 'oscuro'} se lee`, async () => {
    const { palette } = buildTheme(modo, 'es')

    const flojos = []
    for (const rol of ROLES) {
      const fondo = palette[rol]?.main
      if (!fondo || !fondo.startsWith('#')) continue
      const texto = encima(fondo)
      const ratio = contraste(fondo, texto)
      if (ratio < MINIMO) {
        flojos.push(`${rol} ${fondo} con ${texto}: ${ratio.toFixed(2)}`)
      }
    }

    expect(
      flojos,
      `estos colores no llegan a ${MINIMO} con el texto que llevan encima, así que ` +
        'un chip o un botón con ese color no se lee. Si el color viene de MUI y no ' +
        'del tema, hay que declararlo en el tema con un tono propio',
    ).toEqual([])
  })
}

test('y los dos estados que piden algo no se parecen entre sí', async () => {
  // «Esperando a la empresa» y «esperando tu respuesta» van en ámbar; una
  // corrección aplicada sin acuerdo, en terracota. Si los dos tonos se
  // acercaran, el estado dejaría de leerse de un vistazo, que es justo para lo
  // que está el color.
  const { palette } = buildTheme('light', 'es')
  const separacion = [1, 3, 5]
    .map((i) =>
      Math.abs(
        parseInt(palette.warning.main.slice(i, i + 2), 16) -
          parseInt(palette.secondary.main.slice(i, i + 2), 16),
      ),
    )
    .reduce((a, b) => a + b, 0)

  expect(separacion, `el aviso y el terracota están demasiado cerca`).toBeGreaterThan(60)
})
