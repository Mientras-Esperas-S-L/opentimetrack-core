/** Lo que el saldo de descanso **no** cuenta, dicho en su pantalla (RD 1561/1995).
 *
 *  Los arts. 4 a 10 amplían la jornada en sectores concretos y cada uno fija sus
 *  propios descansos compensatorios. El producto **no los calcula, y es una
 *  decisión**: haría falta la cifra de cada sector ---quince números por cada uno
 *  de los trece regímenes--- y todos ellos tienen además convenio propio. Un
 *  número nuestro pisando el suyo se leería como la ley.
 *
 *  Lo que sí se puede hacer es decirlo. Sin esa línea, quien trabaja en
 *  hostelería ve las fuentes con sus artículos y da por hecho que están todas.
 *  Un saldo incompleto que no avisa de estarlo se cree.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const elSaldo = (page) => page.getByRole('alert').filter({ hasText: /descanso/i })

/** El régimen que había, para dejarlo como estaba. Lo cambia la administración y
 *  lo mira quien trabaja, así que hay que ponerlo y quitarlo alrededor. */
async function declara(page, regimen) {
  const { status } = await api(page, '/working-time-rules/', {
    method: 'PATCH',
    body: { special_regime: regimen },
  })
  expect(status, 'no se pudo declarar el régimen').toBe(200)
}

test.describe('Lo que el saldo no cuenta', () => {
  test.describe('quien lo configura', () => {
    test.use({ storageState: 'e2e/.sesiones/admin.json' })

    test('los regímenes salen en castellano, no en inglés', async ({ page }) => {
      // **El defecto que se vio abriendo la pantalla.** Los trece nombres
      // estaban traducidos al catalán y al gallego y no al castellano, así que
      // el desplegable enseñaba «Road transport» a cualquier empresa española.
      // El guard de traducciones no lo veía: comprobaba ca y gl, dando por hecho
      // que sin traducción se cae al castellano --- y el código está en inglés.
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      const { body: reglas } = await api(page, '/working-time-rules/')

      const nombres = reglas.regimes.map((r) => r.label)
      expect(nombres).toContain('Comercio y hostelería')
      expect(nombres).toContain('Transporte por carretera')
      for (const ingles of ['Road transport', 'Retail and hospitality', 'Farm work']) {
        expect(nombres, `«${ingles}» sigue sin traducir`).not.toContain(ingles)
      }
    })
  })

  test.describe('quien mira su saldo', () => {
    // La administración declara y quien trabaja lee: dos sesiones, y el régimen
    // vuelve a su sitio al terminar.
    test.use({ storageState: 'e2e/.sesiones/admin.json' })

    let previo = null

    test.beforeEach(async ({ page }) => {
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      const { body: reglas } = await api(page, '/working-time-rules/')
      previo = reglas.special_regime ?? ''
    })

    test.afterEach(async ({ page }) => {
      if (previo === null) return
      const volver = previo
      previo = null
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      await declara(page, volver)
    })

    test('en un sector de ampliación, dice que no está completo', async ({ page, browser }) => {
      await declara(page, 'RETAIL_HOSPITALITY')

      const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
      const suya = await contexto.newPage()
      try {
        await irA(suya, '/mis-ausencias', 'Mis ausencias')
        await expect(elSaldo(suya)).toContainText('RD 1561/1995')
        await expect(elSaldo(suya)).toContainText(/Comercio y hostelería/)
        await expect(elSaldo(suya)).toContainText(/mira tu convenio/i)
      } finally {
        await contexto.close()
      }
    })

    test('con la regla general no dice nada', async ({ page, browser }) => {
      // El contraste: la mayoría de las empresas van por la regla general, y una
      // advertencia sobre algo que no les pasa es ruido que enseña a no leer.
      await declara(page, '')

      const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
      const suya = await contexto.newPage()
      try {
        await irA(suya, '/mis-ausencias', 'Mis ausencias')
        await expect(elSaldo(suya)).toBeVisible()
        await expect(elSaldo(suya)).not.toContainText('RD 1561/1995')
      } finally {
        await contexto.close()
      }
    })

    test('y en una limitación tampoco', async ({ page, browser }) => {
      // El RD tiene dos clases de régimen y solo una amplía la jornada. Una
      // limitación la recorta: no trae descansos compensatorios que echar en
      // falta, y avisar de ellos inventaría una deuda que no existe.
      await declara(page, 'MINING')

      const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
      const suya = await contexto.newPage()
      try {
        await irA(suya, '/mis-ausencias', 'Mis ausencias')
        await expect(elSaldo(suya)).toBeVisible()
        await expect(elSaldo(suya)).not.toContainText('RD 1561/1995')
      } finally {
        await contexto.close()
      }
    })
  })
})
