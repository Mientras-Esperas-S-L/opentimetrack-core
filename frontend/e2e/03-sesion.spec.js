/** La sesión, ya abierta: renovación y perfiles.
 *
 *  Aparte de `01-entrada.spec.js` porque estas no necesitan pasar por el
 *  formulario, y pasar por él gastaba un intento del límite de cinco por
 *  minuto que protege la puerta.
 */

import { expect, test } from '@playwright/test'

test.describe('Sesión abierta', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('se renueva sola cuando caduca el acceso', async ({ page }) => {
    // El fallo del 13/08: no había endpoint de refresco, el navegador guardaba
    // un token de siete días que no se podía canjear, y la sesión moría a los
    // quince minutos echando a la gente a media pantalla.
    await page.goto('/panel')
    await page.evaluate(() => localStorage.setItem('ott.access', 'ya-no-vale'))

    await page.goto('/panel/personas')
    await expect(page.getByRole('heading', { name: 'Personas', level: 1 })).toBeVisible()

    const renovado = await page.evaluate(() => localStorage.getItem('ott.access'))
    expect(renovado).not.toBe('ya-no-vale')
  })

  test('sin refresco válido sí devuelve a la entrada', async ({ page }) => {
    await page.goto('/panel')
    await page.evaluate(() => {
      localStorage.setItem('ott.access', 'roto')
      localStorage.setItem('ott.refresh', 'roto-tambien')
    })

    await page.goto('/panel/personas')
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  })

  test('administración ve las pantallas de gestión', async ({ page }) => {
    await page.goto('/panel')
    await expect(page.getByRole('link', { name: 'Personas' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Aplicaciones' })).toBeVisible()
  })
})

test.describe('Sesión de un operario', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('solo ve lo suyo en el menú', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Fichar' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Personas' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Aplicaciones' })).toHaveCount(0)
  })
})

test.describe('Un responsable', () => {
  test.use({ storageState: 'e2e/.sesiones/responsable.json' })

  test('ve gestión pero no las aplicaciones', async ({ page }) => {
    // Autorizar una aplicación es repartir una llave a los registros de la
    // empresa: la API se lo niega con un 403, así que el menú no se lo ofrece.
    await page.goto('/panel')
    await expect(page.getByRole('link', { name: 'Personas' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Aplicaciones' })).toHaveCount(0)
  })
})
