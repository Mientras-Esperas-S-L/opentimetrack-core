/** La sesión, ya abierta: renovación y perfiles.
 *
 *  Aparte de `01-entrada.spec.js` porque estas no necesitan pasar por el
 *  formulario, y pasar por él gastaba un intento del límite de cinco por
 *  minuto que protege la puerta.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

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

  test('un 429 no es un cierre de sesión', async ({ page }) => {
    // El fallo salió escribiendo las pruebas del cuadrante: la propia suite
    // agotó las peticiones por hora de la cuenta y la aplicación se convirtió
    // en el formulario de entrada, sin decir por qué. La causa era una línea
    // ---`catch { tokens.clear() }`--- que trataba **cualquier** fallo de
    // `/auth/me/` como un token inválido: un 429, un 502 del balanceador
    // mientras se despliega, o el wifi parpadeando.
    //
    // Solo un 401 o un 403 son «esta sesión ya no vale». Lo demás se reintenta
    // y, si no hay manera, el testigo se queda donde está: recargar puede
    // funcionar, y borrarlo garantiza que no.
    let veces = 0
    await page.route('**/api/auth/me/', async (ruta) => {
      veces += 1
      // Los dos primeros intentos se estrellan; el tercero pasa.
      if (veces <= 2) {
        return ruta.fulfill({
          status: 429,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Request was throttled.' }),
        })
      }
      return ruta.continue()
    })

    await page.goto('/panel')

    await expect(page.getByRole('heading', { name: 'Resumen', level: 1 })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Entrar' })).toHaveCount(0)
    expect(veces, 'debería haber reintentado').toBeGreaterThan(1)
    expect(await page.evaluate(() => localStorage.getItem('ott.access'))).toBeTruthy()
  })

  test('un 429 que no cede deja el testigo puesto', async ({ page }) => {
    // El caso peor: no cede nunca. Aun así el testigo sigue guardado, porque
    // borrarlo convierte un problema pasajero en tener que volver a entrar.
    await page.goto('/panel')
    const antes = await page.evaluate(() => localStorage.getItem('ott.access'))

    await page.route('**/api/auth/me/', (ruta) =>
      ruta.fulfill({ status: 429, contentType: 'application/json', body: '{}' }),
    )
    await page.goto('/panel/personas')
    await page.waitForTimeout(2500)

    expect(await page.evaluate(() => localStorage.getItem('ott.access'))).toBe(antes)
  })

  test('si la sesión muere estando dentro, lleva a entrar', async ({ page }) => {
    // El caso que ninguna prueba cubría, y salió en la consola de un uso real:
    // las que había **navegaban**, y al navegar se vuelve a comprobar la sesión
    // y todo funciona. Lo roto era quedarse quieto dentro.
    //
    // `tokens.clear()` vaciaba el almacén y React no se enteraba: la pantalla
    // seguía puesta y su consulta seguía pidiendo cada minuto, con un 401 cada
    // vez. Un 401 por minuto para siempre, delante de una pantalla que ni se
    // arregla sola ni te lleva a ninguna parte.
    await irA(page, '/panel', 'Resumen')

    // Se rompen los dos sin recargar: es lo que pasa cuando el acceso caduca y
    // el refresco ya no vale.
    await page.evaluate(() => {
      localStorage.setItem('ott.access', 'caducado')
      localStorage.setItem('ott.refresh', 'tampoco-vale')
    })

    // Y se provoca una petición sin navegar, como haría el refresco periódico.
    await page.getByRole('link', { name: 'Personas' }).click()

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
