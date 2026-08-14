/** El zoom del navegador al 200 %.
 *
 *  La norma pide que el texto se pueda ampliar al 200 % sin perder contenido,
 *  y en una plantilla hay quien lo lleva puesto todos los días. Al 200 % en un
 *  portátil de 1280 la página cree que mide 640 de ancho: por debajo del móvil
 *  no, pero por encima del punto en que MUI pasa las filas a horizontal ---600---
 *  y ahí es donde aparece el hueco.
 *
 *  Lo que cazó: la fila de filtros de Personas no envolvía. Entre 600 y 1000 px
 *  se salía 60 px por la derecha y el interruptor de «ver también las bajas»
 *  quedaba fuera de la pantalla, sin barra horizontal que lo alcanzara porque el
 *  desbordamiento era del documento entero. En móvil no pasaba ---ahí la fila se
 *  apila--- y en el escritorio del que se desarrolla tampoco. Justo en medio.
 *
 *  La misma pantalla ya se había fabricado su propio buscador en vez de usar el
 *  común, y por eso se quedó sin nombre accesible. Esto es la segunda mitad de
 *  aquello: también se fabricaba la barra, y la común es la que lleva el
 *  `flexWrap`.
 */
import { expect, test } from '@playwright/test'
import { irA } from './apoyo.js'

const PANTALLAS = [
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/ajustes', 'Ajustes de la empresa'],
  ['/panel/cuadrante', 'Cuadrante'],
  ['/mi-jornada', 'Mi jornada'],
]

/** Cuánto se sale el documento por la derecha, y quién tiene la culpa. */
const MIRAR = () => {
  const doc = document.documentElement
  const cuanto = doc.scrollWidth - doc.clientWidth
  const culpables = []
  if (cuanto > 2) {
    for (const el of document.querySelectorAll('body *')) {
      const c = el.getBoundingClientRect()
      if (c.width > 0 && c.right > doc.clientWidth + 2) {
        culpables.push(`<${el.tagName.toLowerCase()}> hasta ${Math.round(c.right)}px`)
        if (culpables.length > 2) break
      }
    }
  }
  return { cuanto, culpables }
}

test.use({ storageState: 'e2e/.sesiones/admin.json', viewport: { width: 640, height: 480 } })

for (const [ruta, titulo] of PANTALLAS) {
  test(`al 200 % de zoom ${ruta} no se sale de la pantalla`, async ({ page }) => {
    await irA(page, ruta, titulo)
    await page.waitForLoadState('networkidle').catch(() => {})

    const { cuanto, culpables } = await page.evaluate(MIRAR)

    expect(
      cuanto,
      `${ruta} se sale ${cuanto}px por la derecha. ${culpables.join(', ')}`,
    ).toBeLessThanOrEqual(2)
  })
}

test('y la comprobación de arriba sabe ver un desbordamiento', async ({ page }) => {
  /** El contraste, porque ocho comprobaciones en verde no prueban nada por sí
   *  solas: `scrollWidth - clientWidth` puede dar cero por estar midiendo el
   *  elemento equivocado, o porque algo de arriba puso `overflow: hidden` y el
   *  documento ya no puede desbordarse aunque su contenido no quepa.
   *
   *  Así que se mete un elemento más ancho que la ventana y se comprueba que la
   *  sonda lo canta. Es exactamente la forma del fallo que la trajo: un hijo
   *  que llega más allá del borde derecho.
   */
  await irA(page, '/panel/personas', 'Personas')

  const limpio = await page.evaluate(MIRAR)
  expect(limpio.cuanto, 'ya venía desbordada: el contraste no diría nada').toBeLessThanOrEqual(2)

  const roto = await page.evaluate(() => {
    const d = document.createElement('div')
    d.style.cssText = 'width:1200px;height:10px'
    document.body.append(d)
    const doc = document.documentElement
    const r = doc.scrollWidth - doc.clientWidth
    d.remove()
    return r
  })

  expect(roto, 'la sonda no ve un hijo de 1200px en una ventana de 640').toBeGreaterThan(2)
})
