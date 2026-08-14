/** La interfaz en el idioma de la empresa, no solo los correos.
 *
 *  Hasta ahora los catálogos del backend llegaban a los correos y a los errores
 *  de la API, y las pantallas seguían en castellano pasara lo que pasara. Una
 *  empresa catalana veía su producto a medias traducido, que es peor que verlo
 *  entero en un idioma.
 *
 *  Esta prueba recorre la cadena completa ---la empresa declara su idioma, la
 *  sesión lo trae, i18next lo activa, el DOM lo enseña--- porque cada eslabón se
 *  ha roto por su cuenta alguna vez y ninguno se ve desde el de al lado. El
 *  último que se rompió: el middleware del backend no se ejecutaba nunca en la
 *  API y nadie lo notó porque el navegador mandaba la cabecera por su cuenta.
 *
 *  Se comprueba con el menú porque es lo que se ve sin hacer nada y porque está
 *  traducido de verdad. **Lo demás de la aplicación sigue en castellano**: la
 *  conversión de las ~460 cadenas está a medias y esto solo cubre el armazón.
 */
import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.describe('El idioma de la interfaz', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  /** Deja la empresa como estaba pase lo que pase: la base es compartida y una
   *  empresa que se queda en catalán rompe todas las pruebas siguientes. */
  const conIdioma = async (page, idioma, hacer) => {
    const antes = (await api(page, '/company/')).body.language
    try {
      await api(page, '/company/', { method: 'PATCH', body: { language: idioma } })
      await hacer()
    } finally {
      await api(page, '/company/', { method: 'PATCH', body: { language: antes || 'es' } })
    }
  }

  test('en castellano el menú está en castellano', async ({ page }) => {
    // El contraste primero. Sin él, la prueba de abajo pasaría igual si el menú
    // estuviera en catalán para todo el mundo.
    await irA(page, '/panel', 'Resumen')
    await expect(page.getByRole('link', { name: 'Fichar', exact: true })).toBeVisible()
  })

  test('una empresa catalana ve el menú en catalán', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    await conIdioma(page, 'ca', async () => {
      await page.reload()
      await expect(page.getByRole('link', { name: 'Fitxar', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Quadrant', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Fichar', exact: true })).toHaveCount(0)

      // El atributo del documento, que no se ve pero lo lee todo: sin él un
      // lector de pantalla castellano pronuncia el catalán con las reglas del
      // castellano, y la partición de palabras se hace mal.
      await expect(page.locator('html')).toHaveAttribute('lang', 'ca')
    })
  })

  test('y lo que todavía no está traducido sale en castellano, no en inglés', async ({ page }) => {
    /** La condición que hace utilizable un catálogo a medias.
     *
     *  Es la misma que ya se comprueba en el backend, y por el mismo motivo: si
     *  lo que falta cayera al inglés, una empresa catalana vería su producto en
     *  dos idiomas extranjeros a la vez. Aquí cae al castellano solo, sin
     *  configurar nada, porque la clave **es** la cadena castellana.
     */
    await irA(page, '/panel/personas', 'Personas')

    await conIdioma(page, 'ca', async () => {
      await page.reload()
      await expect(page.getByRole('link', { name: 'Persones', exact: true })).toBeVisible()

      // Sin traducir todavía, y por eso vale como muestra.
      await expect(page.getByText('Ver también las bajas')).toBeVisible()
    })
  })
})
