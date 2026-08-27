/** La pausa (art. 3.d) y el modo de trabajo (art. 3.e), al fichar.
 *
 *  El backend los aceptaba desde antes: `register_punch` recibe `interval` y
 *  `work_mode`, la vista los lee y `build_day_status` devuelve `ON_BREAK` y
 *  cuenta los segundos de pausa aparte. Lo que faltaba era **ofrecerlos**: la
 *  web mandaba solo el identificador del dispositivo, así que ninguna persona
 *  podía abrir una pausa ni decir desde dónde trabaja. La pieza estaba hecha y
 *  desconectada, que es el patrón que más veces ha salido en esta auditoría.
 *
 *  **Aquí se simula el servidor**, y a propósito. Lo que hay que comprobar es el
 *  contrato entre la pantalla y la API ---qué ofrece en cada estado y qué manda
 *  al pulsar---, y eso pide poder poner el estado a voluntad. Que el registro
 *  quede bien guardado ya lo comprueban las pruebas de `apps/punches`, que es
 *  donde se puede comprobar de verdad.
 *
 *  Y hay una razón práctica: **un fichaje no se puede borrar**. Se anula con una
 *  corrección, que exige motivo y avisa a la persona. Una prueba que fichara de
 *  verdad dejaría cuatro fichajes en el día del operario en cada corrida, sin
 *  forma de retirarlos.
 */

import { expect, test } from '@playwright/test'

import { irA, vigilarConsola } from './apoyo.js'

const ZONA = 'Europe/Madrid'

/** El estado del día que devolvería el servidor. */
const dia = (state, extra = {}) => ({
  employee: '00000000-0000-0000-0000-000000000001',
  time_zone: ZONA,
  state,
  segments: [],
  worked_seconds: 0,
  break_seconds: 0,
  standby_seconds: 0,
  ...extra,
})

/** Pone el estado del día y recoge lo que la pantalla manda al fichar. */
async function conElServidorEn(page, estado) {
  const enviados = []
  await page.route('**/api/punches/today/', (ruta) =>
    ruta.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(estado) }),
  )
  await page.route('**/api/punches/', async (ruta) => {
    if (ruta.request().method() !== 'POST') return ruta.continue()
    enviados.push(ruta.request().postDataJSON())
    await ruta.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'x', day_status: estado }),
    })
  })
  return enviados
}

test.describe('Pausa y modo de trabajo', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('sin empezar: se puede decir desde dónde, y se puede no decirlo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const enviados = await conElServidorEn(page, dia('NOT_STARTED'))
    await irA(page, '/', 'Hola')

    // Ninguno de los dos preseleccionado: vacío es «no consta», y suponer
    // «presencial» llenaría el registro de un dato que nadie ha afirmado.
    const presencial = page.getByRole('button', { name: 'Presencial' })
    const distancia = page.getByRole('button', { name: 'A distancia' })
    await expect(presencial).toBeVisible()
    await expect(distancia).toBeVisible()

    // Sin tocar nada, se ficha como siempre y no se manda modo.
    await page.getByRole('button', { name: 'Fichar entrada' }).click()
    await expect.poll(() => enviados.length).toBe(1)
    expect(enviados[0].work_mode, 'mandó un modo que nadie eligió').toBeUndefined()
    expect(
      enviados[0].interval,
      'la entrada de jornada no lleva intervalo explícito',
    ).toBeUndefined()

    expect(ruido()).toEqual([])
  })

  test('elegir «a distancia» lo manda, y se recuerda dentro del día', async ({ page }) => {
    const enviados = await conElServidorEn(page, dia('NOT_STARTED'))
    await irA(page, '/', 'Hola')

    await page.getByRole('button', { name: 'A distancia' }).click()
    await page.getByRole('button', { name: 'Fichar entrada' }).click()

    await expect.poll(() => enviados.length).toBe(1)
    expect(enviados[0].work_mode).toBe('REMOTE')

    // Y sigue elegido al volver a la pantalla: el art. 3.e habla del día «o
    // parte de él», así que se recuerda por día y no para siempre.
    await irA(page, '/mi-jornada', 'Mi jornada')
    await irA(page, '/', 'Hola')
    await expect(page.getByRole('button', { name: 'A distancia' })).toHaveAttribute(
      'class',
      /MuiChip-filled/,
    )
  })

  test('trabajando: se ofrece empezar una pausa, y manda BREAK', async ({ page }) => {
    const enviados = await conElServidorEn(page, dia('WORKING', { worked_seconds: 3600 }))
    await irA(page, '/', 'Hola')

    await expect(page.getByText('Trabajando')).toBeVisible()
    // El modo ya no se ofrece: lo describe el fichaje que abre el tramo, y este
    // tramo ya está abierto.
    await expect(page.getByRole('button', { name: 'A distancia' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Empezar una pausa' }).click()
    await expect.poll(() => enviados.length).toBe(1)
    expect(enviados[0].interval).toBe('BREAK')
  })

  test('en pausa: lo dice, y solo ofrece volver', async ({ page }) => {
    const enviados = await conElServidorEn(page, dia('ON_BREAK', { worked_seconds: 3600 }))
    await irA(page, '/', 'Hola')

    // Antes decía «Sin empezar» a quien tenía una pausa abierta: el estado
    // llegaba del servidor y la pantalla no lo conocía.
    await expect(page.getByText('En pausa')).toBeVisible()
    await expect(page.getByText('Sin empezar')).toHaveCount(0)

    // Y no se ofrece fichar la salida: cerraría la jornada con la pausa abierta,
    // que es un día diciendo que alguien se fue a comer y no volvió nunca.
    await expect(page.getByRole('button', { name: 'Fichar salida' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Empezar una pausa' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Volver de la pausa' }).click()
    await expect.poll(() => enviados.length).toBe(1)
    expect(enviados[0].interval).toBe('BREAK')
  })

  test('el desglose dice qué fue cada tramo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await conElServidorEn(
      page,
      dia('OFF', {
        worked_seconds: 25200,
        break_seconds: 3600,
        segments: [
          {
            in: '2026-08-27T06:00:00+00:00',
            out: '2026-08-27T12:00:00+00:00',
            seconds: 21600,
            interval: 'WORK',
            work_mode: 'REMOTE',
            hours_nature: 'ORDINARY',
          },
          {
            in: '2026-08-27T12:00:00+00:00',
            out: '2026-08-27T13:00:00+00:00',
            seconds: 3600,
            interval: 'BREAK',
            work_mode: '',
            hours_nature: 'ORDINARY',
          },
        ],
      }),
    )
    await irA(page, '/', 'Hola')

    // Un rato de pausa se leía igual que un rato trabajado.
    await expect(page.getByText('Pausa', { exact: true })).toBeVisible()
    await expect(page.getByText('A distancia').first()).toBeVisible()
    // `hhmm` da «01:00», no «1h 00m».
    await expect(page.getByText(/01:00 de pausa/)).toBeVisible()

    expect(ruido()).toEqual([])
  })
})
