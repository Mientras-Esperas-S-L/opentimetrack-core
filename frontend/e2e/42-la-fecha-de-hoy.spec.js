/** Los formularios proponen **hoy**, no ayer.
 *
 *  `new Date().toISOString().slice(0, 10)` da la fecha en UTC, y eso no es la
 *  fecha de nadie salvo en Greenwich. Al este ---España--- devuelve el día
 *  anterior durante toda la madrugada; al oeste, el siguiente durante la tarde.
 *
 *  `format.js` ya tenía el helper correcto **y un comentario avisando de esto**,
 *  y aun así quedaban tres sitios con el patrón malo: el diálogo de solicitar
 *  una ausencia y las dos fechas del periodo de los informes. Cazado a la 01:28
 *  de un miércoles: el diálogo proponía el martes.
 *
 *  Se prueba con el reloj movido a la madrugada, que es cuando se rompe. A
 *  media mañana las dos formas coinciden y la prueba pasaría con el fallo
 *  delante.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

// 00:30 en Madrid es todavía el día anterior en UTC.
const DE_MADRUGADA = new Date('2026-08-26T00:30:00+02:00')

test.use({
  storageState: 'e2e/.sesiones/operario.json',
  timezoneId: 'Europe/Madrid',
})

test.describe('De madrugada', () => {
  test.beforeEach(async ({ page }) => {
    await page.clock.setFixedTime(DE_MADRUGADA)
  })

  test('solicitar una ausencia propone hoy, no ayer', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await page.getByRole('button', { name: 'Solicitar' }).first().click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo).toBeVisible()
    await expect(dialogo.getByLabel('Desde *')).toHaveValue('2026-08-26')
    await expect(dialogo.getByLabel('Hasta *')).toHaveValue('2026-08-26')
  })
})

test.describe('Y el periodo de los informes', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('acaba hoy, no ayer', async ({ page }) => {
    await page.clock.setFixedTime(DE_MADRUGADA)
    await irA(page, '/panel/informes', 'Informes')

    // El «hasta» del registro de jornada. Es el documento que se entrega a la
    // Inspección: un periodo corrido un día no lo elige nadie.
    await expect(page.getByLabel('Hasta').first()).toHaveValue('2026-08-26')
  })
})
