/** El producto en un teléfono, que es donde se ficha.
 *
 *  Toda la suite corría a ancho de escritorio. Fichar se hace con el móvil en
 *  la mano, en una obra o en un portal, y esa anchura no la ejercitaba nadie ---
 *  la misma forma que el favicon que solo se veía con ventana.
 *
 *  Barriéndolo salió una sola cosa, y era mía: el buscador de Personas había
 *  pasado el día antes al componente compartido, que fijaba el ancho en vez de
 *  ponerle un tope. En una pantalla de 390 px, un campo de 380 más su borde se
 *  sale. Seis píxeles, y la barra de desplazamiento horizontal de una pantalla
 *  que se usa a diario.
 *
 *  El resto aguantó, y conviene dejarlo escrito: ninguna otra pantalla se sale,
 *  los diálogos caben con sus botones dentro, y el botón de fichar mide 255×64
 *  en mitad de la pantalla.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

const TELEFONO = { width: 390, height: 844 }

// Las diecisiete, no una selección. Faltaban seis ---y entre ellas las dos que
// más ancho piden, Calendario y Turnos--- así que «ninguna otra pantalla se
// sale» era una afirmación sobre las que se miraron.
const PANTALLAS = [
  ['/', 'Hola'],
  ['/mi-jornada', 'Mi jornada'],
  ['/mis-ausencias', 'Mis ausencias'],
  ['/actividad', 'Registro de actividad'],
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/departamentos', 'Departamentos'],
  ['/panel/centros', 'Centros de trabajo'],
  ['/panel/calendario', 'Calendario del equipo'],
  ['/panel/cuadrante', 'Cuadrante'],
  ['/panel/turnos', 'Turnos'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/informes', 'Informes'],
  ['/panel/aplicaciones', 'Aplicaciones'],
  ['/panel/ajustes', 'Ajustes de la empresa'],
]

/** Cuánto se sale la página a lo ancho, y quién tiene la culpa. */
const desborde = (page) =>
  page.evaluate(() => {
    const doc = document.documentElement
    const cuanto = doc.scrollWidth - doc.clientWidth
    if (cuanto <= 2) return { cuanto: 0, culpables: [] }
    const culpables = []
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect()
      if (r.width > 0 && r.right > doc.clientWidth + 2) {
        culpables.push(`${el.tagName.toLowerCase()} hasta ${Math.round(r.right)}px`)
        if (culpables.length > 3) break
      }
    }
    return { cuanto, culpables }
  })

test.describe('En un teléfono', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json', viewport: TELEFONO })

  for (const [ruta, titulo] of PANTALLAS) {
    test(`${ruta} no se sale de la pantalla`, async ({ page }) => {
      await irA(page, ruta, titulo)
      await page.waitForLoadState('networkidle').catch(() => {})
      await page.waitForTimeout(400)

      const { cuanto, culpables } = await desborde(page)
      expect(cuanto, `${ruta} se sale ${cuanto}px: ${culpables.join(', ')}`).toBe(0)
    })
  }

  test('los diálogos caben, con su botón de confirmar dentro', async ({ page }) => {
    // Un diálogo es donde el móvil se rompe: varios campos, fechas y dos
    // botones al fondo. Si el de confirmar se sale, la acción no se puede
    // terminar --- y no hay forma de saberlo sin mirar a esta anchura.
    for (const [ruta, titulo, boton] of [
      ['/mis-ausencias', 'Mis ausencias', 'Solicitar'],
      ['/mi-jornada', 'Mi jornada', 'Pedir una corrección'],
      ['/panel/personas', 'Personas', 'Dar de alta'],
    ]) {
      await irA(page, ruta, titulo)
      await page.getByRole('button', { name: boton, exact: true }).first().click()
      const dialogo = page.getByRole('dialog')
      await expect(dialogo).toBeVisible()

      const cabe = await dialogo.evaluate((d) => {
        const doc = document.documentElement
        const r = d.getBoundingClientRect()
        return r.right <= doc.clientWidth + 2 && r.left >= -2
      })
      expect(cabe, `el diálogo de ${ruta} se sale`).toBe(true)
      expect((await desborde(page)).cuanto, `${ruta} con el diálogo abierto`).toBe(0)

      await page.keyboard.press('Escape')
    }
  })
})

test.describe('Fichar, en la mano', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json', viewport: TELEFONO })

  test('el botón es grande y está donde llega el pulgar', async ({ page }) => {
    // Es la acción del producto entero, y se hace de pie, deprisa y a veces con
    // guantes. Un botón de tamaño normal aquí sería el fallo más caro posible.
    await irA(page, '/', 'Hola')

    const boton = page.getByRole('button', { name: /^Fichar (entrada|salida)$/ })
    await expect(boton).toBeVisible()

    const caja = await boton.boundingBox()
    expect(caja.height, 'el botón de fichar es más bajo que un dedo').toBeGreaterThanOrEqual(48)
    expect(caja.width).toBeGreaterThanOrEqual(180)
    // En la mitad de abajo, que es hasta donde llega el pulgar con una mano.
    expect(caja.y).toBeGreaterThan(TELEFONO.height * 0.35)
  })
})

test.describe('Los meses y los días, escritos como en castellano', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json', viewport: { width: 1280, height: 900 } })

  /** `text-transform: capitalize` sube cada palabra. `toLocaleDateString`
   *  devuelve «agosto de 2026» y en pantalla salía «Agosto De 2026», con la
   *  preposición en mayúscula. Estaba en tres pantallas. */
  for (const [ruta, titulo] of [
    ['/panel/calendario', 'Calendario del equipo'],
    ['/panel/cuadrante', 'Cuadrante'],
  ]) {
    test(`${ruta} no dice «De»`, async ({ page }) => {
      await irA(page, ruta, titulo)
      const mes = page.getByText(/^[A-ZÁÉÍÓÚ][a-záéíóú]+ (de|De) \d{4}$/).first()
      await expect(mes).toBeVisible()
      await expect(mes).toHaveText(/ de \d{4}$/)
    })
  }

  test('/mi-jornada tampoco, en el día de cada tarjeta', async ({ browser }) => {
    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const suPagina = await suyo.newPage()
    await irA(suPagina, '/mi-jornada', 'Mi jornada')
    // «Lunes, 25 Ago» era lo que salía; la primera en mayúscula y el resto no.
    const dias = suPagina.getByText(/^[A-ZÁÉÍÓÚ][a-záéíóú]+, \d{1,2} [a-zA-Z]{3}/)
    if (await dias.count()) {
      await expect(dias.first()).not.toHaveText(/ [A-ZÁÉÍÓÚ][a-z]{2}$/)
    }
    await suyo.close()
  })
})
