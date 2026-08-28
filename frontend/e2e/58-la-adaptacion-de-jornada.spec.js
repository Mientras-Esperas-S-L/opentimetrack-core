/** Pedir una adaptación de jornada y contestarla (art. 34.8 ET).
 *
 *  El expediente llegó en la parte A; esto es lo que faltaba para que se pueda
 *  usar sin abrir un shell. Son **dos pantallas y dos personas distintas**, y
 *  eso es justo lo que no puede comprobar una prueba de servidor:
 *
 *  - Quien trabaja la pide desde «Mi jornada» ---no desde «Mis ausencias»:
 *    pedir entrar media hora más tarde no es faltar un día---.
 *  - Quien administra la contesta desde «Por decidir», y **si la respuesta no
 *    es un sí, la pantalla pide el motivo antes de mandarlo**. El servidor lo
 *    rechaza igual, pero enterarse de la obligación por un error es enterarse
 *    tarde y mal.
 */

import { expect, test } from '@playwright/test'

import { api, irA, marca } from './apoyo.js'

//: Quien contesta. La que pide abre su propio contexto: son dos personas, y esa
//: es justamente la mitad que una prueba de servidor no puede comprobar.
test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Lo que esta tanda ha creado, para recogerlo pase lo que pase. */
let pendienteDeRetirar = null

test.afterEach(async ({ browser }) => {
  if (!pendienteDeRetirar) return
  const id = pendienteDeRetirar
  pendienteDeRetirar = null
  const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
  const pagina = await contexto.newPage()
  await pagina.goto('/panel')
  await api(pagina, `/schedule-adaptations/${id}/`, { method: 'DELETE' })
  await contexto.close()
})

test.describe('La adaptación de jornada', () => {
  test('quien trabaja la pide desde Mi jornada', async ({ browser }) => {
    // Su propio contexto, con **su** sesión. `storageState({path})` sobre el
    // contexto de la prueba **guarda** el estado en vez de cargarlo, así que
    // esto habría corrido con la sesión de administración creyendo que era la
    // suya --- y la prueba habría pasado sin comprobar lo que dice.
    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const page = await suyo.newPage()
    const loQuePido = `Entrar a las 9:30 · ${marca()}`

    await irA(page, '/mi-jornada', 'Mi jornada')
    await expect(page.getByRole('heading', { name: 'Adaptación de jornada' })).toBeVisible()

    await page.getByRole('button', { name: 'Pedir una adaptación' }).click()
    await page.getByLabel('Qué pides').fill(loQuePido)
    await page.getByRole('button', { name: 'Pedirla' }).click()

    await expect(page.getByText(loQuePido)).toBeVisible()
    await expect(page.getByText('En negociación').first()).toBeVisible()

    // Y el servidor la tiene a su nombre, que es lo único a cuyo nombre se
    // puede pedir.
    const mías = await api(page, '/schedule-adaptations/')
    const recién = (mías.body.results ?? []).find((f) => f.asked_for === loQuePido)
    expect(recién, JSON.stringify(mías.body)).toBeTruthy()
    pendienteDeRetirar = recién.id
    expect(recién.status).toBe('PENDING')

    await suyo.close()
  })

  test('denegar pide el motivo antes de mandarlo', async ({ page, browser }) => {
    /* La decisión de pantalla que el servidor no puede tomar. El art. 34.8
       obliga a motivar la negativa; el servidor lo rechaza, pero descubrirlo
       con un error después de haber pulsado es descubrirlo tarde. */
    const loQuePido = `Jornada continua los viernes · ${marca()}`

    // La pide el operario, por API: lo que se comprueba aquí es la respuesta.
    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const suPagina = await suyo.newPage()
    await suPagina.goto('/mi-jornada')
    const creada = await api(suPagina, '/schedule-adaptations/', {
      method: 'POST',
      body: { requested_on: '2026-08-03', asked_for: loQuePido },
    })
    expect([200, 201], JSON.stringify(creada.body)).toContain(creada.status)
    pendienteDeRetirar = creada.body.id
    await suyo.close()

    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /Adaptaciones de jornada/ }).click()
    await expect(page.getByText(loQuePido)).toBeVisible()

    const tarjeta = page.locator('div').filter({ hasText: loQuePido }).last()
    await tarjeta.getByRole('button', { name: 'Denegar' }).click()

    // El botón de mandar está apagado hasta que haya motivo escrito.
    const mandar = page.getByRole('button', { name: 'Contestar' })
    await expect(mandar).toBeDisabled()

    await page.getByLabel('Por qué').fill('El turno de mañana no se puede cubrir de otra forma.')
    await expect(mandar).toBeEnabled()
    await mandar.click()

    // Y queda con su motivo y con quién contestó.
    await expect(page.getByText(loQuePido)).toHaveCount(0)
    const guardada = await api(page, `/schedule-adaptations/${creada.body.id}/`)
    expect(guardada.body.status).toBe('REFUSED')
    expect(guardada.body.answer).toContain('turno de mañana')
    expect(guardada.body.answered_by).toBeTruthy()
  })

  test('aceptar no pide motivo', async ({ page, browser }) => {
    /* El contraste de la prueba anterior. Si la pantalla exigiera el motivo
       siempre, esto se quedaría con el botón apagado para siempre --- y estaría
       inventándose una obligación que el artículo solo pone a las otras dos
       respuestas. */
    const loQuePido = `Salir a las 16:00 · ${marca()}`

    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const suPagina = await suyo.newPage()
    await suPagina.goto('/mi-jornada')
    const creada = await api(suPagina, '/schedule-adaptations/', {
      method: 'POST',
      body: { requested_on: '2026-08-03', asked_for: loQuePido },
    })
    pendienteDeRetirar = creada.body.id
    await suyo.close()

    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /Adaptaciones de jornada/ }).click()
    await expect(page.getByText(loQuePido)).toBeVisible()

    const tarjeta = page.locator('div').filter({ hasText: loQuePido }).last()
    await tarjeta.getByRole('button', { name: 'Aceptar' }).click()

    // Sin escribir nada, se puede mandar.
    await expect(page.getByRole('button', { name: 'Contestar' })).toBeEnabled()
    await expect(page.getByLabel('Por qué')).toHaveCount(0)
  })
})
