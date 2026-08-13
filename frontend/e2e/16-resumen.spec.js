/** El Resumen, y que sus números sean ciertos.
 *
 *  Es la portada del panel: cuatro cifras y tres listas. Nadie la lee con
 *  atención --- se mira de reojo para decidir dónde entrar --- y por eso un
 *  número equivocado a la baja hace más daño aquí que en ninguna otra pantalla:
 *  una cola que la portada da por vacía es una cola que nadie abre.
 *
 *  Pasó con «esperando decisión». Contaba dos de las cinco colas de «Por
 *  decidir» y se dejaba fuera la más grande: decía **2** habiendo **57**. Entre
 *  lo que no contaba estaban las horas extra, que tienen cuatro meses de plazo
 *  para compensarse con descanso (art. 35.1), así que el número no era un
 *  adorno: era la diferencia entre resolverlas y no enterarse.
 *
 *  Estas pruebas comparan la pantalla con lo que dice el servidor, no con una
 *  cifra escrita a mano. Una prueba que espera «57» se pondría roja el día que
 *  alguien resuelva una, y a la tercera vez la desactivaría cualquiera.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, vigilarConsola } from './apoyo.js'

/** Lo que la portada suma, según el servidor. */
async function loQueEspera(page) {
  const cuerpo = (await api(page, '/overview/')).body?.awaiting_decision ?? {}
  return {
    total:
      (cuerpo.absences ?? 0) +
      (cuerpo.corrections ?? 0) +
      (cuerpo.awaiting_employee ?? 0) +
      (cuerpo.recoveries ?? 0),
    hayHorasExtra: cuerpo.overtime_pending === true,
    detalle: cuerpo,
  }
}

test.describe('Resumen', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la cifra de «esperando decisión» cuenta todas las colas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel', 'Resumen')

    const { total, detalle } = await loQueEspera(page)

    // Las cuatro colas que se pueden contar barato están todas en la respuesta.
    // Si alguna desapareciera, la portada volvería a mentir en silencio.
    for (const cola of ['absences', 'corrections', 'awaiting_employee', 'recoveries']) {
      expect(detalle, `falta la cola ${cola}`).toHaveProperty(cola)
    }

    // Contra el texto de la página y no con `getByText` de la frase entera: la
    // tarjeta pinta el número y el rótulo en dos elementos, así que la frase
    // completa no es ningún nodo.
    await expect(page.locator('body')).toContainText(`${total}`)
    await expect(page.locator('body')).toContainText('esperando decisión')
    await expect(page.getByRole('link', { name: new RegExp(`^${total}\\b`) })).toBeVisible()

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })

  test('la portada y «Por decidir» dicen lo mismo', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')
    const { detalle } = await loQueEspera(page)

    // El contraste que hace falta: dos pantallas que cuentan lo mismo tienen
    // que decir lo mismo. Discrepaban en cinco, y era la pestaña la que
    // truncaba --- contaba las filas recibidas, no el total, y llegan de
    // cincuenta en cincuenta.
    await irA(page, '/panel/decisiones', 'Por decidir')
    const numeroDe = async (cola) => {
      const pestaña = page.getByRole('tab', { name: new RegExp(`^${cola}`) })
      await expect(pestaña).toContainText(/\d/)
      return Number((await pestaña.innerText()).match(/(\d+)\s*$/)?.[1] ?? -1)
    }

    expect(await numeroDe('Ausencias')).toBe(detalle.absences)
    expect(await numeroDe('Fichajes')).toBe(detalle.corrections)
    expect(await numeroDe('Sin acuerdo')).toBe(detalle.awaiting_employee)
  })

  test('una lista recortada lo dice', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /^Sin acuerdo/ }).click()
    await page.waitForTimeout(900)

    const total = (await api(page, '/corrections/?status=AWAITING_EMPLOYEE')).body?.count ?? 0
    const filas = await page.getByRole('button', { name: 'Aplicar sin acuerdo' }).count()

    if (total > filas) {
      // Cincuenta y cinco pendientes vistas como cincuenta, sin nada que dijera
      // que faltaban cinco. Un recorte callado se lee como «ya está todo».
      await expect(page.getByText(`Se muestran ${filas} de ${total}`)).toBeVisible()
    } else {
      await expect(page.getByText(/Se muestran \d+ de \d+/)).toHaveCount(0)
    }
  })

  test('lo que enseña coincide con quien está fichado', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // «Trabajando ahora» sale del registro, no de un campo de estado. Se
    // comprueba contra el propio registro para que siga siendo verdad.
    const overview = (await api(page, '/overview/')).body
    for (const persona of overview.working_now ?? []) {
      await expect(page.getByText(persona.name).first()).toBeVisible()
    }
    await expect(page.locator('body')).toContainText(`${overview.headcount}`)
    await expect(page.locator('body')).toContainText('personas de alta')
  })
})

test.describe('Resumen · un operario', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('no ve el panel ni por API le cuentan la empresa', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    // La portada de gestión no está en su menú, y por debajo el servidor le
    // responde con lo suyo: su día, y ni un dato de nadie más.
    const suyo = await api(page, '/overview/')
    expect(suyo.status).toBe(200)
    expect(suyo.body.scope).toBe('self')
    expect(suyo.body).not.toHaveProperty('working_now')
    expect(suyo.body).not.toHaveProperty('headcount')
    expect(suyo.body).not.toHaveProperty('off_today')
  })
})
