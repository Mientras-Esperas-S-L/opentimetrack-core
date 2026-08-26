/** «Pedir una corrección», las dos mitades.
 *
 *  El fallo: la opción «La hora registrada no es la real» **fallaba siempre**.
 *  El servidor exige decir qué fichaje se corrige ---sin eso el consentimiento
 *  del art. 4.b no significa nada: se estaría autorizando un cambio sin saber
 *  cuál--- y la pantalla no ofrecía dónde indicarlo. Quien lo intentaba recibía
 *  «Indica qué fichaje se corrige» y ningún sitio donde hacerlo.
 *
 *  La otra opción, «Olvidé fichar», sí funcionaba, y por eso el hueco había
 *  pasado desapercibido: la mitad usada funcionaba.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

const MARCA = 'Prueba corrección 22'

/** Retira lo que esta prueba dejó pedido, y lo retira **otra persona**.
 *
 *  Esta prueba entra como administradora y pide una corrección de su propio
 *  fichaje, así que la limpieza no puede ir por su misma sesión: quien pide un
 *  cambio en el registro no lo resuelve, y eso vale también para archivarlo
 *  ---no cambiar nada también es decidir---. Con la sesión de la propia
 *  administradora el servidor contesta 409 `cannot_decide_your_own`, que es lo
 *  correcto y lo que hacía fallar esta prueba por la consola.
 */
async function limpiar(page, browser) {
  const mias = await api(page, '/corrections/?status=PENDING')
  const suyas = (mias.body?.results ?? mias.body ?? []).filter((fila) =>
    (fila.reason ?? '').startsWith(MARCA),
  )
  if (suyas.length === 0) return

  const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/responsable.json' })
  const otra = await contexto.newPage()
  // Cualquier pantalla suya vale: solo hace falta estar en el origen para que
  // `api` encuentre el testigo en el `localStorage`.
  await irA(otra, '/mi-jornada', 'Mi jornada')
  for (const fila of suyas) {
    await api(otra, `/corrections/${fila.id}/reject/`, {
      method: 'POST',
      body: { note: 'limpieza de la prueba' },
    })
  }
  await contexto.close()
}

test.describe('Mi jornada · pedir una corrección', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('cambiar la hora de un fichaje concreto llega al servidor', async ({ page, browser }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mi-jornada', 'Mi jornada')

    // Un fichaje propio si el mes está vacío: sin ninguno no hay nada que
    // corregir, y la prueba se saltaba sola --- que es no comprobar nada. Los
    // fichajes no se borran (son el registro), así que se abre y se cierra la
    // jornada para no dejarla colgando.
    // Se retrocede hasta un mes con fichajes propios en vez de crear ninguno.
    //
    // La primera versión los creaba con dos POST seguidos, y la protección del
    // doble toque rechazaba el segundo: la jornada quedaba **abierta**, Ana
    // aparecía fichada, y eso tumbó dieciséis pruebas de otros ficheros que
    // miran contadores en vivo. Una prueba no puede dejar la base de desarrollo
    // en un estado que otra no espera.
    const mes = page.getByRole('button', { name: 'Mes anterior' })
    for (let vueltas = 0; vueltas < 6; vueltas += 1) {
      if ((await page.getByRole('button', { name: /^Descargar / }).count()) === 0) break
      const filas = await page.getByRole('listitem').count()
      if (filas > 0) break
      await mes.click()
      await page.waitForTimeout(400)
    }

    await page.getByRole('button', { name: 'Pedir una corrección' }).click()
    const dialogo = page.getByRole('dialog')

    await dialogo.getByRole('combobox', { name: 'Qué pasó' }).click()
    await page.getByRole('option', { name: /no es la real/i }).click()

    // El desplegable que faltaba. Si no hay fichajes este mes, la pantalla lo
    // dice en vez de ofrecer una lista vacía.
    const cual = dialogo.getByRole('combobox', { name: 'Cuál' })
    await expect(cual).toBeVisible()
    await cual.click()
    await page.getByRole('option').first().click()

    await dialogo.getByLabel('Hora real').fill('2026-08-13T09:15')
    await dialogo.getByLabel('Motivo').fill(`${MARCA}: fiché con el reloj del móvil parado`)
    await dialogo.getByRole('button', { name: 'Enviar solicitud' }).click()

    await expect(dialogo).toBeHidden()

    const creadas = await api(page, '/corrections/?status=PENDING')
    const mia = (creadas.body?.results ?? []).find((c) => (c.reason ?? '').startsWith(MARCA))
    expect(mia, 'la corrección no llegó al servidor').toBeTruthy()
    expect(mia.kind).toBe('MODIFY')
    // Lo que hace que el consentimiento signifique algo: qué fichaje se toca.
    expect(mia.target).toBeTruthy()

    await limpiar(page, browser)
    expect(ruido()).toEqual([])
  })

  test('«olvidé fichar» sigue sin pedir cuál', async ({ page }) => {
    // El contraste: para un fichaje que falta no hay ninguno que señalar, y
    // pedirlo sería pedir un imposible.
    await irA(page, '/mi-jornada', 'Mi jornada')

    await page.getByRole('button', { name: 'Pedir una corrección' }).click()
    const dialogo = page.getByRole('dialog')

    await expect(dialogo.getByRole('combobox', { name: 'Qué falta' })).toBeVisible()
    await expect(dialogo.getByRole('combobox', { name: 'Cuál' })).toHaveCount(0)
  })
})
