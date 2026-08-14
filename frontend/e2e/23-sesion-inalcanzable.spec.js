/** Sesión buena, servidor que no contesta.
 *
 *  Con el testigo perfectamente vivo y `/auth/me/` devolviendo 429, la
 *  aplicación se rendía y pintaba el **formulario de entrada**: se le pedía la
 *  contraseña a quien tenía la sesión abierta, y volver a entrar daba el mismo
 *  429. En la vuelta 6 se arregló que el testigo dejara de borrarse; lo que veía
 *  la persona seguía siendo lo mismo.
 *
 *  Salió de verdad, no de imaginarlo: de tanto correr esta suite en un día se
 *  agotó el límite por persona y la pantalla de Ajustes se volvió el formulario
 *  de entrada. Con la sesión buena guardada al lado.
 */

import { expect, test } from '@playwright/test'

test.describe('Cuando no se puede comprobar la sesión', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('lo dice, y no pide la contraseña otra vez', async ({ page }) => {
    await page.route('**/api/auth/me/', (ruta) =>
      ruta.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          error: { code: 'throttled', message: 'Demasiados intentos. Vuelve a probar en 30 segundos.' },
        }),
      }),
    )

    await page.goto('/panel')

    await expect(page.getByText(/no hemos podido comprobar tu sesión/i)).toBeVisible()
    // Lo accionable del mensaje del servidor se conserva.
    await expect(page.getByText(/30 segundos/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible()

    // Y lo que no puede pasar: pedirle la contraseña a quien ya está dentro.
    await expect(page.getByRole('button', { name: 'Entrar' })).toHaveCount(0)
    expect(await page.evaluate(() => localStorage.getItem('ott.access'))).toBeTruthy()
  })

  test('una sesión rechazada de verdad sí lleva a entrar', async ({ page }) => {
    // El contraste. Un 401 es «esta sesión ya no vale», y ahí el formulario es
    // la respuesta correcta: sin él, quien de verdad tiene que volver a entrar
    // se quedaría mirando un aviso de reintentar para siempre.
    await page.goto('/panel')
    await page.evaluate(() => {
      localStorage.setItem('ott.access', 'roto')
      localStorage.setItem('ott.refresh', 'roto-tambien')
    })
    await page.goto('/panel/personas')

    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  })
})
