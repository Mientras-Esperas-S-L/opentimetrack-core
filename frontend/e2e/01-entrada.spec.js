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
    // Una contraseña mal no es «falta la empresa»: pedir el CIF aquí mandaba a
    // buscar un dato que no era el problema.
    await expect(page.getByLabel('CIF o NIF de la empresa')).toHaveCount(0)
  })

  test('si el correo y la contraseña valen en dos empresas, pide el CIF y lo dice', async ({
    page,
  }) => {
    // La respuesta es la que da el servidor, capturada tal cual: la semilla no
    // tiene a nadie con el mismo correo en las dos empresas, y crearlo dejaría
    // una persona que no se puede borrar. Lo que el servidor contesta lo prueba
    // `test_el_correo_repetido_al_entrar.py`; aquí, lo que la pantalla hace con ello.
    const pedidas = []
    await page.route('**/api/auth/token/', async (route) => {
      const cuerpo = route.request().postDataJSON()
      pedidas.push(cuerpo)
      if (!cuerpo.tax_id) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: {
              code: 'company_required',
              message:
                'Ese correo y esa contraseña valen en más de una empresa. Añade el CIF o NIF de tu empresa.',
              details: {},
            },
          }),
        })
        return
      }
      await route.abort()
    })

    await page.goto('/')
    await expect(page.getByLabel('CIF o NIF de la empresa')).toHaveCount(0)
    await page.getByLabel('Correo electrónico').fill('doble@demo.local')
    await page.getByLabel('Contraseña').fill('la-de-las-dos')
    await page.getByRole('button', { name: 'Entrar' }).click()

    // El texto es el de la pantalla, no el del servidor: dice qué campo rellenar.
    await expect(errorVisible(page)).toContainText('Escribe el CIF o NIF de la tuya')
    await expect(errorVisible(page)).not.toContainText('Credenciales incorrectas')
    const cif = page.getByLabel('CIF o NIF de la empresa')
    await expect(cif).toBeVisible()

    // Y el CIF viaja en el siguiente intento.
    await cif.fill('B-00000002')
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect.poll(() => pedidas.length).toBe(2)
    expect(pedidas[1].tax_id).toBe('B-00000002')
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
