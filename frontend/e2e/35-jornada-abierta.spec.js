/** El tope de horas que una jornada puede seguir abierta.
 *
 *  Es la frontera entre «cerró tarde» y «se olvidó de fichar la salida», y no
 *  la fija ningún artículo: la pone cada empresa. Con guardias de veinticuatro
 *  horas ---bomberos, residencias, vigilancia--- el defecto de dieciséis parte
 *  la guardia por la mitad y el registro de esa noche sale mal.
 *
 *  La prueba existe porque el campo nació igual que otros cuatro que ya me han
 *  salido en esta auditoría: modelo, API y regla aplicándose, y ningún sitio
 *  donde tocarlo. Un ajuste que solo se puede cambiar por API es un ajuste que
 *  la empresa no tiene. Así que se comprueba de punta a punta ---la pantalla lo
 *  escribe, el backend lo devuelve--- y no solo que el campo se pinte.
 */
import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.describe('Cuánto aguanta abierta una jornada', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('se cambia desde Ajustes y el backend se entera', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const campo = page.getByLabel('Una jornada puede seguir abierta (h)')
    const antes = (await api(page, '/working-time-rules/')).body.max_open_hours
    expect(antes, 'la API no sirve el campo').toBeDefined()
    await expect(campo).toHaveValue(String(antes))

    // 26: lo que necesita una guardia de veinticuatro con margen para fichar
    // la salida con calma.
    await campo.fill('26')
    await expect(page.getByRole('alert').filter({ hasText: 'Sin guardar' })).toContainText(
      'Jornada abierta como mucho',
    )
    await page.getByRole('button', { name: /^Guardar/ }).click()

    await expect
      .poll(async () => (await api(page, '/working-time-rules/')).body.max_open_hours, {
        message: 'la pantalla decía que guardaba y el backend seguía con lo de antes',
      })
      .toBe(26)

    // Se deja como estaba: la base de desarrollo es compartida y una prueba que
    // cambia una regla de la empresa y no la devuelve rompe a las siguientes.
    await campo.fill(String(antes))
    await page.getByRole('button', { name: /^Guardar/ }).click()
    await expect
      .poll(async () => (await api(page, '/working-time-rules/')).body.max_open_hours)
      .toBe(antes)
  })
})
