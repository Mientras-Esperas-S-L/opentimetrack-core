/** Un día de trabajo no se corta a la mitad entre dos páginas.
 *
 *  El cuadro de fichajes servía cincuenta fichajes por página y luego los
 *  agrupaba por día. Cuando el corte caía dentro de un día ---y con una persona
 *  activa cae casi siempre--- ese día salía **dos veces**: una en cada página y
 *  con la mitad de sus horas cada vez. Medido en la demo: 34 fichajes de esa
 *  misma persona y ese mismo día se iban a la página siguiente.
 *
 *  Nada en la pantalla lo decía. Quien miraba el día 26 en la primera página
 *  creía que había visto el día 26.
 *
 *  Con una persona elegida el periodo se trae entero, porque ahí la unidad que
 *  se lee es la jornada. Sin persona esto es un volcado de toda la empresa: se
 *  pagina por fichaje, que es la unidad que se lista, y cada fila lleva su
 *  fecha.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

/** La persona con más fichajes en un solo día, y cuántos tiene ese día. */
async function elDiaMasCargado(page) {
  const cuenta = new Map()
  for (let pagina = 1; pagina <= 20; pagina += 1) {
    const { status, body } = await api(page, `/punches/?page=${pagina}&ordering=-timestamp`)
    expect(status).toBe(200)
    for (const fichaje of body.results ?? []) {
      const clave = `${fichaje.employee}|${fichaje.timestamp.slice(0, 10)}|${fichaje.employee_name}`
      cuenta.set(clave, (cuenta.get(clave) ?? 0) + 1)
    }
    if (!body.next) break
  }
  const [clave, total] = [...cuenta.entries()].sort((a, b) => b[1] - a[1])[0] ?? []
  const [id, dia, nombre] = (clave ?? '||').split('|')
  return { id, dia, nombre, total }
}

test.describe('Fichajes · el día entero', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la jornada de una persona no se parte entre páginas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/fichajes', 'Fichajes')

    const { dia, nombre, total } = await elDiaMasCargado(page)
    // Si ningún día pasa de una página, la prueba no puede demostrar nada, y
    // decirlo es mejor que dar un verde que no significa nada.
    expect(total, `ningún día llega a 50 fichajes (el mayor: ${dia}, ${total})`).toBeGreaterThan(50)

    await page.getByLabel('Desde').fill(dia)
    await page.getByLabel('Hasta').fill(dia)
    await page.getByLabel('Persona').click()
    await page.getByRole('option', { name: nombre }).first().click()

    // El encabezado de ese día, una sola vez. Con el corte salía dos.
    const encabezado = page.getByText(new RegExp(`\\b${Number(dia.slice(8, 10))}\\b.*\\d{4}`))
    await expect(encabezado).toHaveCount(1)

    // Y con todos sus fichajes, no con los cincuenta primeros.
    await expect
      .poll(async () => page.getByRole('row').count(), { timeout: 10_000 })
      .toBeGreaterThan(total)

    expect(ruido()).toEqual([])
  })

  test('el volcado de toda la empresa lleva la fecha en cada fila', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/fichajes', 'Fichajes')

    // Sin persona elegida se pagina por fichaje, así que agrupar por día
    // mentiría: la fecha va en la fila.
    await expect(page.getByRole('columnheader', { name: 'Fecha' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Persona' })).toBeVisible()

    expect(ruido()).toEqual([])
  })
})
