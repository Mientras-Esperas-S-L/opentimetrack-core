/** «¿Cuánto he trabajado esta semana, este mes, entre estas fechas?»
 *
 *  «Mi jornada» enseñaba días sueltos, mes a mes, y nada más: las horas de una
 *  semana había que sumarlas a mano. Y las de cada día salían mal en cuanto
 *  había pausa: la pantalla emparejaba la entrada de la jornada con la de la
 *  pausa, así que un día de 6:57 a 14:57 con veinte minutos de pausa se leía
 *  00:20.
 *
 *  Las cifras van contra el servidor y no contra un número escrito a mano: lo
 *  que se enseña tiene que ser lo que dice el informe que se descarga.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

const hhmm = (segundos) =>
  `${String(Math.floor(segundos / 3600)).padStart(2, '0')}:${String(
    Math.floor((segundos % 3600) / 60),
  ).padStart(2, '0')}`

const iso = (fecha) => fecha.toLocaleDateString('sv-SE')

test.describe('Mi jornada · cuánto he trabajado', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('el total del mes pasado es el del informe', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mi-jornada', 'Mi jornada')

    const panel = page.getByRole('region', { name: 'Cuánto he trabajado' })
    await panel.getByRole('button', { name: 'El mes pasado' }).click()

    const hoy = new Date()
    const desde = iso(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1))
    const hasta = iso(new Date(hoy.getFullYear(), hoy.getMonth(), 0))
    const informe = await api(
      page,
      `/reports/working-time/?date_from=${desde}&date_to=${hasta}&format=json`,
    )
    expect(informe.status).toBe(200)
    expect(informe.body.total_seconds).toBeGreaterThan(0)

    await expect(panel.getByText(hhmm(informe.body.total_seconds), { exact: true })).toBeVisible()
    // Un mes se desglosa por semanas.
    await expect(panel.getByText(/^Semana /).first()).toBeVisible()

    expect(ruido()).toEqual([])
  })

  test('entre fechas, y con las fechas al revés lo dice', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    const panel = page.getByRole('region', { name: 'Cuánto he trabajado' })
    await panel.getByRole('button', { name: 'Entre fechas' }).click()
    await panel.getByLabel('Desde').fill('2026-10-10')
    await panel.getByLabel('Hasta').fill('2026-10-01')

    await expect(panel.getByText('La fecha final no puede ir antes que la inicial.')).toBeVisible()
  })

  test('un día con pausa suma lo trabajado, no la pausa', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    const hoy = new Date()
    const desde = iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1))
    const informe = await api(
      page,
      `/reports/working-time/?date_from=${desde}&date_to=${iso(hoy)}&format=json`,
    )
    expect(informe.status).toBe(200)

    // El total del mes junto a su nombre, y el mismo que el del informe.
    await expect(
      page.getByText(`Total ${hhmm(informe.body.total_seconds)}`, { exact: true }),
    ).toBeVisible()
    // Y alguna pausa a la vista, que es el caso que se contaba mal.
    await expect(page.getByText(/^pausa \d\d:\d\d – \d\d:\d\d$/).first()).toBeVisible()
  })
})
