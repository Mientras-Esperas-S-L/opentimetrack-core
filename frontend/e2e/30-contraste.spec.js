/** Que se lea, en los dos temas.
 *
 *  El producto tiene conmutador de claro y oscuro desde hace semanas y nadie
 *  había mirado el oscuro. Salió que el verde de «Aprobada» quedaba en 3.26 de
 *  contraste sobre el papel oscuro y el terracota de «Aplicada sin acuerdo» en
 *  3.24 --- por debajo del 4.5 que pide la norma para texto normal, y justo en
 *  los distintivos que dicen en qué estado está algo. `primary` sí se aclaraba
 *  en oscuro; `success` y `secondary` se habían quedado con el color del claro.
 *
 *  Se mide el contraste de verdad, sobre el fondo que realmente hay detrás:
 *  buscarlo en el código no vale, porque el color efectivo sale de la cascada.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

const PANTALLAS = [
  ['/', 'Hola'],
  ['/mi-jornada', 'Mi jornada'],
  ['/mis-ausencias', 'Mis ausencias'],
  ['/actividad', 'Registro de actividad'],
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/turnos', 'Turnos'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/permisos', 'Permisos'],
]

/** Los textos por debajo del mínimo de la norma, con su medida. */
const flojos = (page, fondoPorDefecto) =>
  page.evaluate((porDefecto) => {
    const aRgb = (s) => {
      const m = (s || '').match(/rgba?\(([^)]+)\)/)
      if (!m) return null
      const p = m[1].split(',').map((x) => parseFloat(x))
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }
    }
    const lum = (c) => {
      const f = (v) => {
        v /= 255
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
    }
    // El fondo real: se sube por los padres hasta encontrar uno opaco, porque
    // casi todo es transparente y el color de detrás no es el del elemento.
    const fondoDe = (el) => {
      let n = el
      while (n && n !== document.documentElement) {
        const c = aRgb(getComputedStyle(n).backgroundColor)
        if (c && c.a > 0.5) return c
        n = n.parentElement
      }
      return porDefecto
    }

    const malos = []
    for (const el of document.querySelectorAll('body *')) {
      const texto = [...el.childNodes]
        .filter((n) => n.nodeType === 3)
        .map((n) => n.textContent.trim())
        .join('')
      if (!texto) continue
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue
      const est = getComputedStyle(el)
      const frente = aRgb(est.color)
      // Lo casi transparente es decorativo o está desactivado a propósito.
      if (!frente || frente.a < 0.4) continue
      const fondo = fondoDe(el)
      const l1 = lum(frente)
      const l2 = lum(fondo)
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
      const tam = parseFloat(est.fontSize)
      const grande = tam >= 24 || (tam >= 18.66 && parseInt(est.fontWeight, 10) >= 700)
      if (ratio < (grande ? 3 : 4.5)) {
        malos.push(`${ratio.toFixed(2)} en «${texto.slice(0, 30)}» (${est.color})`)
      }
    }
    return [...new Set(malos)]
  }, fondoPorDefecto)

for (const [tema, fondo] of [
  ['dark', { r: 18, g: 22, b: 26, a: 1 }],
  ['light', { r: 246, g: 247, b: 245, a: 1 }],
]) {
  test.describe(`Tema ${tema === 'dark' ? 'oscuro' : 'claro'}`, () => {
    test.use({ storageState: 'e2e/.sesiones/admin.json', colorScheme: tema })

    for (const [ruta, titulo] of PANTALLAS) {
      test(`${ruta} se lee`, async ({ page }) => {
        await irA(page, ruta, titulo)
        await page.waitForLoadState('networkidle').catch(() => {})
        await page.waitForTimeout(400)

        expect(await flojos(page, fondo), `contraste corto en ${ruta} (${tema})`).toEqual([])
      })
    }
  })
}
