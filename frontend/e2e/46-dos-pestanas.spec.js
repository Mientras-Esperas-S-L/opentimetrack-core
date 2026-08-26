/** Dos pestañas abiertas, que es como se trabaja de verdad.
 *
 *  El acceso dura quince minutos y el refresco rota: al usarlo, el viejo va a la
 *  lista negra. Dentro de una pestaña eso estaba resuelto ---cinco peticiones
 *  caducadas comparten una sola renovación--- pero cada pestaña tiene su propio
 *  módulo y su propio estado, y las dos leen el mismo refresco de
 *  `localStorage`.
 *
 *  Era una carrera con perdedor: la primera rota el refresco, y a la segunda el
 *  servidor le contesta 409 `session_expired` ---cuando lo que ha pasado es que
 *  su compañera acaba de renovarla. Como ese código estaba en la lista de
 *  rechazos definitivos, la echaba. Tener dos pestañas abiertas costaba una
 *  sesión cada cuarto de hora.
 *
 *  **Entra ella misma en vez de usar una sesión del arranque.** El refresco de
 *  las sesiones compartidas ya lo han rotado otras pruebas, y con uno que está en
 *  la lista negra esto no mide la carrera: mide un refresco caducado. Costó un
 *  rato de `token_not_valid` averiguarlo.
 */

import { expect, test } from '@playwright/test'

const CREDENCIALES = { email: 'operario@demo.local', password: 'demo-password-2026' }

test.describe('Dos pestañas', () => {
  test('la segunda no se va a la calle cuando la primera renueva', async ({ page, context }) => {
    // Sesión propia y sin usar. Se entra por la pantalla, no por la API, para
    // que los tokens queden guardados como los guarda el producto.
    await page.goto('/entrar')
    await page.getByLabel('Correo electrónico').fill(CREDENCIALES.email)
    await page.getByLabel('Contraseña').fill(CREDENCIALES.password)
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page.getByRole('heading', { name: 'Hola', level: 1 })).toBeVisible()

    // La segunda pestaña del mismo navegador: mismo origen, mismo
    // `localStorage`, mismo refresco.
    const otra = await context.newPage()
    await otra.goto('/mi-jornada')
    await expect(otra.getByRole('heading', { name: 'Mi jornada', level: 1 })).toBeVisible()

    const refrescoInicial = await page.evaluate(() => localStorage.getItem('ott.refresh'))
    expect(refrescoInicial).toBeTruthy()

    // Se invalida el acceso en las dos, que es el estado exacto a los quince
    // minutos. La siguiente petición de cada una da 401 y dispara la
    // renovación: el camino real, sin llamar a nada por dentro.
    for (const p of [page, otra]) {
      await p.evaluate(() => localStorage.setItem('ott.access', 'ya.no.vale'))
    }

    // **Y se fuerza el orden**, que es lo que costó. Las dos pestañas comparten
    // `localStorage` de verdad, así que si la segunda lee el refresco *después*
    // de que la primera lo haya guardado, coge el nuevo y no hay carrera
    // ninguna: la prueba pasaba igual con el arreglo quitado.
    //
    // Retrasando el refresco de la segunda, lee el viejo, se queda en vuelo
    // mientras la primera lo rota, y llega con uno que ya está en la lista
    // negra. Ese es el caso que se quiere probar.
    let retrasado = false
    await otra.route('**/auth/refresh/', async (ruta) => {
      if (!retrasado) {
        retrasado = true
        await new Promise((listo) => setTimeout(listo, 1500))
      }
      await ruta.continue()
    })

    const pedir = (p) =>
      p.evaluate(async () => {
        const { api } = await import('/src/services/api.js')
        try {
          const r = await api.get('/auth/me/')
          return { estado: r.status }
        } catch (e) {
          return {
            estado: e?.response?.status ?? 0,
            motivo: e?.code ?? e?.response?.data?.error?.code ?? String(e?.message ?? e),
          }
        }
      })

    const enVuelo = pedir(otra)
    // Un instante para que la segunda haya leído el refresco y esté esperando.
    await page.waitForTimeout(300)
    const uno = await pedir(page)
    const dos = await enVuelo

    expect(uno.estado, `la primera pestaña: ${uno.motivo ?? ''}`).toBe(200)
    expect(dos.estado, `la segunda pestaña: ${dos.motivo ?? ''}`).toBe(200)

    // Y ninguna se ha quedado sin sesión: la echada perdía el refresco entero.
    for (const p of [page, otra]) {
      const guardado = await p.evaluate(() => localStorage.getItem('ott.refresh'))
      expect(guardado, 'una pestaña se quedó sin refresco').toBeTruthy()
    }

    await otra.close()
  })
})
