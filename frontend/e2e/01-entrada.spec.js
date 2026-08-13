/** La entrada: el único formulario que ve alguien que todavía no es nadie. */

import { expect, test } from '@playwright/test'

import { EMPRESA, api, entrar, errorVisible, salir } from './apoyo.js'

// Cada prueba de aquí gasta al menos un intento contra `/api/auth/token/`, que
// está limitado a cinco por minuto --- y ese límite es lo que impide probar
// contraseñas a lo bruto, así que no se toca: se espacian las pruebas.
//
// Veinte segundos y no trece: la de «el mismo mensaje» envía el formulario dos
// veces, así que con trece la quinta prueba caía dentro de la misma ventana y
// se llevaba un 429 que parecía un fallo de la aplicación.
//
// El resto de la suite no paga este peaje: usa las sesiones guardadas por
// `00-sesiones.setup.js`. Aquí se paga porque lo que se prueba es la puerta.
test.describe.configure({ mode: 'serial' })
test.beforeEach(async ({ page }) => {
  await page.waitForTimeout(20_000)
})

test.describe('Entrada', () => {
  test('con credenciales buenas, entra y ve su nombre', async ({ page }) => {
    await entrar(page, EMPRESA.propia.operario)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Hola')
  })

  test('con la contraseña mal, lo dice y no entra', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('Correo electrónico').fill(EMPRESA.propia.operario)
    await page.getByLabel('Contraseña').fill('no-es-esta')
    await page.getByRole('button', { name: 'Entrar' }).click()

    await expect(errorVisible(page)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  })

  test('un correo que no existe contesta lo mismo que uno que sí', async ({ page }) => {
    // Si contestara distinto, probar direcciones diría quién trabaja aquí.
    await page.goto('/')
    await page.getByLabel('Correo electrónico').fill('nadie@demo.local')
    await page.getByLabel('Contraseña').fill('no-es-esta')
    await page.getByRole('button', { name: 'Entrar' }).click()
    const conInexistente = await errorVisible(page).textContent()

    await page.reload()
    await page.getByLabel('Correo electrónico').fill(EMPRESA.propia.operario)
    await page.getByLabel('Contraseña').fill('no-es-esta')
    await page.getByRole('button', { name: 'Entrar' }).click()
    const conExistente = await errorVisible(page).textContent()

    expect(conInexistente).toBe(conExistente)
  })

  test('los campos son obligatorios y el navegador no deja enviar vacío', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('Correo electrónico').fill('')
    await page.getByRole('button', { name: 'Entrar' }).click()
    // Sigue en la entrada: el formulario no se ha enviado.
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  })

  test('cerrar sesión invalida el refresco en el servidor', async ({ page }) => {
    // Con su propia entrada por formulario y no con una sesión guardada: al
    // cerrarla se invalida el token en el servidor, y si fuera el compartido
    // dejaría sin sesión al resto de la suite.
    await entrar(page, EMPRESA.propia.operario)
    const refresco = await page.evaluate(() => localStorage.getItem('ott.refresh'))
    await salir(page)

    const respuesta = await api(page, '/auth/refresh/', {
      method: 'POST',
      body: { refresh: refresco },
    })
    expect(respuesta.status).toBeGreaterThanOrEqual(400)
  })
})
