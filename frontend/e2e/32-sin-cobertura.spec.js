/** Fichar sin cobertura: qué ve quien está en un sótano.
 *
 *  Es el escenario de campo de este producto y no lo había mirado nadie. El
 *  service worker **no guarda cola a propósito** ---y el motivo está escrito en
 *  él: la hora de un fichaje no se decide en el navegador--- así que sin red no
 *  se ficha. Eso está bien decidido. Lo que estaba mal era lo que se decía.
 *
 *  El aviso era «The server could not be reached.», en inglés, en un producto
 *  en castellano. Y no decía lo único que hace falta saber: que **no ha quedado
 *  nada**. Sin esa frase, quien está en una obra ve un aviso, se encoge de
 *  hombros y se va convencido de haber fichado --- que es cómo se pierde un
 *  fichaje sin que nadie se entere.
 *
 *  Se aborta la petición en vez de usar el emulado de «sin red»: ese no siempre
 *  alcanza a `localhost`, y con él la sonda se quedaba colgada en «Registrando…»
 *  haciendo pensar en un fallo que no existía.
 */

import { expect, test } from '@playwright/test'

import { irA, vigilarConsola } from './apoyo.js'

test.describe('Fichar sin cobertura', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json', viewport: { width: 390, height: 844 } })

  test('lo dice en castellano y avisa de que no ha quedado nada', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/', 'Hola')

    await page.route('**/api/punches/', (ruta) =>
      ruta.request().method() === 'POST' ? ruta.abort('internetdisconnected') : ruta.continue(),
    )

    await page.getByRole('button', { name: /^Fichar (entrada|salida)$/ }).click()

    await expect(page.getByText('No hay conexión con el servidor.')).toBeVisible()
    await expect(page.getByText(/No se ha registrado nada/)).toBeVisible()
    // Nada de inglés en la pantalla.
    await expect(page.getByText(/could not be reached/i)).toHaveCount(0)

    // Y se puede volver a intentar: el botón vuelve, no se queda «Registrando…».
    await expect(page.getByRole('button', { name: /^Fichar (entrada|salida)$/ })).toBeEnabled()

    // Un fallo de red no es un error de programación: no debe ensuciar la
    // consola, porque entonces la prueba que la vigila deja de servir.
    expect(ruido().filter((r) => !/Failed to load resource/i.test(r))).toEqual([])
  })

  test('lo de «no ha quedado nada» solo sale cuando es la red', async ({ page }) => {
    // El contraste. Un 409 del propio producto ---«acabas de fichar»--- sí llegó
    // al servidor, y decirle a alguien que no quedó nada sería mentirle.
    await irA(page, '/', 'Hola')

    await page.route('**/api/punches/', (ruta) =>
      ruta.request().method() === 'POST'
        ? ruta.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              error: { code: 'punch_too_soon', message: 'Acabas de fichar.', details: {} },
            }),
          })
        : ruta.continue(),
    )

    await page.getByRole('button', { name: /^Fichar (entrada|salida)$/ }).click()

    await expect(page.getByText('Acabas de fichar.')).toBeVisible()
    await expect(page.getByText(/No se ha registrado nada/)).toHaveCount(0)
  })
})
