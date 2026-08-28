/** Cuándo se llama a trabajar a quien tiene contrato fijo discontinuo (art. 16).
 *
 *  El campo «fijo discontinuo» existía desde antes y no servía para nada: el
 *  sistema sabía que alguien lo era, pero no **cuándo** lo estaba. Esta pantalla
 *  es lo que faltaba para poder decirlo.
 *
 *  Se comprueba desde fuera y no solo por API porque la mitad de la decisión es
 *  de la pantalla: la acción **solo se ofrece a quien es fijo discontinuo**, y
 *  eso no lo puede fijar el servidor --- él se limita a rechazar lo que llegue.
 */

import { expect, test } from '@playwright/test'

import { api, darDeBajaLasDePrueba, irA, marca } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Lo que esta tanda ha dado de alta, para recogerlo pase lo que pase. */
let pendienteDeRetirar = null

test.afterEach(async ({ page }) => {
  if (!pendienteDeRetirar) return
  const sufijo = pendienteDeRetirar
  pendienteDeRetirar = null
  await darDeBajaLasDePrueba(page, sufijo)
})

/** Da de alta a alguien por la API, con o sin la marca de fijo discontinuo. */
async function daDeAlta(page, sufijo, { seasonal }) {
  const alta = await api(page, '/employees/', {
    method: 'POST',
    body: {
      first_name: 'Prueba',
      last_name: `Temporada ${sufijo}`,
      email: `temporada-${sufijo}@demo.local`,
      role: 'EMPLOYEE',
      seasonal,
    },
  })
  expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
  return alta.body
}

async function abrirSusAcciones(page, sufijo) {
  await page.getByPlaceholder('Buscar por nombre, correo o número').fill(sufijo)
  await expect(page.getByText(`temporada-${sufijo}@demo.local`)).toBeVisible()
  // Por su nombre y no `.first()`: el buscador puede haber dejado más de una
  // fila, y abrir el menú de otra persona daba un fallo que apuntaba al menú
  // ---«no existe Temporadas»--- en vez de a la fila equivocada.
  await page.getByRole('button', { name: `Más acciones para Prueba Temporada ${sufijo}` }).click()
}

test.describe('Las temporadas del fijo discontinuo', () => {
  test('se declara una, y queda con su fecha de llamamiento', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    const persona = await daDeAlta(page, sufijo, { seasonal: true })

    await page.reload()
    await abrirSusAcciones(page, sufijo)
    await page.getByRole('menuitem', { name: 'Temporadas' }).click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo.getByText('Todavía no hay ninguna temporada declarada.')).toBeVisible()

    await dialogo.getByLabel('Empieza').fill('2027-06-01')
    await dialogo.getByLabel('Acaba').fill('2027-09-30')
    await dialogo.getByLabel('Llamamiento').fill('2027-05-15')
    await dialogo.getByRole('button', { name: 'Añadir' }).click()

    await expect(dialogo.getByText(/01 jun 2027.*30 sept 2027/)).toBeVisible()
    await expect(dialogo.getByText(/Llamamiento del/)).toBeVisible()

    // Y el servidor lo tiene, que es lo que decide si se espera jornada.
    const guardadas = await api(page, `/activity-periods/?employee=${persona.id}`)
    expect(guardadas.body?.results ?? []).toHaveLength(1)
    expect(guardadas.body.results[0].called_on).toBe('2027-05-15')

    await page.keyboard.press('Escape')
  })

  test('a quien no es fijo discontinuo no se le ofrece', async ({ page }) => {
    /** El contraste de la de arriba: si la acción saliera para cualquiera,
     *  aquella pasaría igual y esto sería una pantalla que invita a escribir un
     *  dato que el servidor va a rechazar. */
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo, { seasonal: false })

    await page.reload()
    await abrirSusAcciones(page, sufijo)

    await expect(page.getByRole('menuitem', { name: 'Temporadas' })).toHaveCount(0)
    // Y el menú sí está abierto: sin esto, un menú que no abre daría el mismo
    // verde que una acción bien escondida.
    await expect(page.getByRole('menuitem', { name: 'Enviarle su registro' })).toBeVisible()

    await page.keyboard.press('Escape')
  })

  test('el llamamiento posterior a la temporada se rechaza, y dice por qué', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo, { seasonal: true })

    await page.reload()
    await abrirSusAcciones(page, sufijo)
    await page.getByRole('menuitem', { name: 'Temporadas' }).click()

    const dialogo = page.getByRole('dialog')
    await dialogo.getByLabel('Empieza').fill('2027-06-01')
    await dialogo.getByLabel('Llamamiento').fill('2027-06-20')
    await dialogo.getByRole('button', { name: 'Añadir' }).click()

    await expect(dialogo.getByRole('alert').filter({ hasText: /antes/ })).toBeVisible()

    await page.keyboard.press('Escape')
  })
})
