/** Un catálogo que no cabe en una página se sigue viendo entero.
 *
 *  Ninguna vista del backend desactiva la paginación ---`PAGE_SIZE` es 50--- y
 *  el cliente se quedaba con la primera página tirando `next` en silencio. Para
 *  una lista con `Pager` eso está bien: la pantalla dice «1-50 de 1.284». Para
 *  un catálogo no, porque alimenta un selector, y **lo que no se carga no se
 *  puede elegir**: no sale ningún error, la opción sencillamente no está.
 *
 *  Se prueba con los festivos porque son los que más fácil pasan de cincuenta
 *  ---dos locales por municipio, más los nacionales y autonómicos--- y porque de
 *  ellos depende qué días no se espera que nadie trabaje.
 */

import { expect, test } from '@playwright/test'

import { api, irA, marca, vigilarConsola } from './apoyo.js'

/** El año siguiente: el selector de la pantalla ofrece este año y sus vecinos,
 *  y el que viene está vacío en la demo. */
const AÑO = new Date().getFullYear() + 1

/** Cincuenta y cinco: cinco más de los que caben en una página. Van seguidos
 *  desde el 1 de enero porque la lista se ordena por día, así que los que se
 *  caen son los de fecha más tardía. */
const CUANTOS = 55

const diaNumero = (n) => {
  const fecha = new Date(Date.UTC(AÑO, 0, 1))
  fecha.setUTCDate(fecha.getUTCDate() + n - 1)
  return fecha.toISOString().slice(0, 10)
}

test.use({ storageState: 'e2e/.sesiones/admin.json' })

test.describe('Un catálogo más largo que una página', () => {
  test('se ve entero, no las cincuenta primeras', async ({ page }) => {
    await irA(page, '/panel/centros', 'Centros de trabajo')

    const mia = marca()
    const creados = []
    try {
      for (let n = 1; n <= CUANTOS; n += 1) {
        const alta = await api(page, '/holidays/', {
          method: 'POST',
          body: {
            day: diaNumero(n),
            name: `Puente ${mia} ${String(n).padStart(2, '0')}`,
            scope: 'COMPANY',
          },
        })
        expect(alta.status, JSON.stringify(alta.body)).toBe(201)
        creados.push(alta.body.id)
      }

      const ruido = vigilarConsola(page)
      await page.reload()
      await page
        .getByRole('combobox')
        .filter({ hasText: String(new Date().getFullYear()) })
        .click()
      await page.getByRole('option', { name: String(AÑO) }).click()

      // El que hace 55, que es el de fecha más tardía y el primero en caerse.
      await expect(
        page.getByText(`Puente ${mia} ${CUANTOS}`),
        'el último del catálogo no llegó a la pantalla: se quedó en la primera página',
      ).toBeVisible()

      // Y el contador tiene que contarlos todos, no cincuenta.
      await expect(page.getByText(`${CUANTOS} de los 14`)).toBeVisible()

      expect(ruido()).toEqual([])
    } finally {
      for (const id of creados) {
        await api(page, `/holidays/${id}/`, { method: 'DELETE' })
      }
    }
  })
})
