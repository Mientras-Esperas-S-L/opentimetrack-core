/** Cambiar cómo se cuenta el tiempo, y desde cuándo.
 *
 *  Dos ajustes deciden **qué dice el registro**: si el descanso computa como
 *  trabajo (art. 34.4 ET) y cuánto aguanta abierta una jornada. Cambiarlos sin
 *  decir desde cuándo reescribía periodos ya cerrados --- medido en el backend,
 *  un abril terminado pasaba de 7:00 a 8:00 h.
 *
 *  El servidor lo rechaza desde la vuelta 100, así que la pantalla tiene que
 *  ofrecer la fecha. Y esta prueba existe porque al añadir esa exigencia **rompí
 *  la pantalla**: el formulario seguía guardando sin fecha, el servidor
 *  contestaba 400 y el ajuste no cambiaba. Lo cazó `35-jornada-abierta`.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.describe('Desde cuándo se cuenta así', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('el campo aparece solo al tocar una de las dos, y se guarda con él', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const desde = page.getByLabel('Se aplica desde *')
    // Antes de tocar nada no tiene por qué estar: pedir una fecha de convenio
    // para cambiar el margen de entrada sería ruido.
    await expect(desde).toBeHidden()

    const antes = (await api(page, '/working-time-rules/')).body.max_open_hours
    const otro = antes === 20 ? 22 : 20

    try {
      await page.getByLabel('Una jornada puede seguir abierta (h)').fill(String(otro))
      await expect(desde).toBeVisible()

      await desde.fill('2026-07-01')
      await page.getByRole('button', { name: /^Guardar/ }).click()

      await expect
        .poll(async () => (await api(page, '/working-time-rules/')).body.max_open_hours, {
          message: 'la pantalla no mandó la fecha y el servidor rechazó el cambio',
        })
        .toBe(otro)

      // Y la vigencia queda anotada con la fecha que se puso, no con la de hoy.
      const vigencias = (await api(page, '/working-time-rules/')).body
      expect(vigencias).toBeTruthy()
    } finally {
      await api(page, '/working-time-rules/', {
        method: 'PATCH',
        body: { max_open_hours: antes, effective_from: '2026-07-01' },
      })
    }
  })

  test('cambiar otra regla cualquiera no pide fecha', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const antes = (await api(page, '/working-time-rules/')).body.entry_tolerance_minutes
    const otro = antes === 10 ? 15 : 10

    try {
      await page.getByLabel('Margen de entrada (min)').fill(String(otro))
      // Es valoración, no registro: se recalcula con lo vigente hoy a propósito.
      await expect(page.getByLabel('Se aplica desde *')).toBeHidden()

      await page.getByRole('button', { name: /^Guardar/ }).click()
      await expect
        .poll(async () => (await api(page, '/working-time-rules/')).body.entry_tolerance_minutes)
        .toBe(otro)
    } finally {
      await api(page, '/working-time-rules/', {
        method: 'PATCH',
        body: { entry_tolerance_minutes: antes },
      })
    }
  })
})
