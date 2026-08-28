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

/** El mes más cargado de una persona: quién, qué mes, cuántos y su día mayor.
 *
 *  La primera versión buscaba a alguien con **más de cincuenta fichajes en un
 *  solo día**, porque la demostración de entonces los tenía: eran el poso de
 *  otras pruebas creando fichajes sobre la misma persona y el mismo día. Nadie
 *  ficha cincuenta veces en un día, así que aquella prueba solo podía correr
 *  sobre una base sucia, y en cuanto se resembró dijo «el mayor: 4».
 *
 *  El defecto que vigila no necesita ese disparate: basta con que el periodo
 *  pedido pase de una página, y un mes de alguien que hace pausas ---setenta y
 *  pico--- lo pasa de sobra. Es además el caso que se da de verdad.
 */
async function elMesMasCargado(page) {
  const cuenta = new Map()
  const porDia = new Map()
  for (let pagina = 1; pagina <= 30; pagina += 1) {
    const { status, body } = await api(page, `/punches/?page=${pagina}&ordering=-timestamp`)
    expect(status).toBe(200)
    for (const fichaje of body.results ?? []) {
      const mes = `${fichaje.employee}|${fichaje.timestamp.slice(0, 7)}|${fichaje.employee_name}`
      cuenta.set(mes, (cuenta.get(mes) ?? 0) + 1)
      const dia = `${mes}|${fichaje.timestamp.slice(0, 10)}`
      porDia.set(dia, (porDia.get(dia) ?? 0) + 1)
    }
    if (!body.next) break
  }
  const [clave, total] = [...cuenta.entries()].sort((a, b) => b[1] - a[1])[0] ?? []
  const [id, mes, nombre] = (clave ?? '||').split('|')
  // De ese mes, el día con más fichajes: es el encabezado que se comprueba que
  // sale una sola vez.
  const [suDia] =
    [...porDia.entries()]
      .filter(([k]) => k.startsWith(`${clave}|`))
      .sort((a, b) => b[1] - a[1])[0] ?? []
  return { id, mes, nombre, total, dia: (suDia ?? '|||').split('|')[3] }
}

test.describe('Fichajes · el día entero', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la jornada de una persona no se parte entre páginas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/fichajes', 'Fichajes')

    const { mes, dia, nombre, total } = await elMesMasCargado(page)
    // Si el periodo cabe en una página, la prueba no puede demostrar nada, y
    // decirlo es mejor que dar un verde que no significa nada.
    expect(
      total,
      `el mes más cargado de la empresa no pasa de 50 fichajes (${nombre}, ${mes}: ${total})`,
    ).toBeGreaterThan(50)

    await page.getByLabel('Desde').fill(`${mes}-01`)
    await page.getByLabel('Hasta').fill(`${mes}-31`)
    await page.getByLabel('Persona').click()
    await page.getByRole('option', { name: nombre }).first().click()

    // El encabezado del día más cargado, una sola vez. Con el corte salía dos:
    // media jornada en cada página y nada en pantalla que lo dijera.
    const encabezado = page.getByText(new RegExp(`\\b${Number(dia.slice(8, 10))}\\b.*\\d{4}`))
    await expect(encabezado).toHaveCount(1)

    // Y con todos sus fichajes del mes, no con los cincuenta primeros.
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
