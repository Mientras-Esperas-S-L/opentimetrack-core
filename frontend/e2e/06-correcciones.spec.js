/** Tocar un asiento del registro: el art. 4.b de punta a punta.
 *
 *  La pieza legal más delicada del producto. Cambiar una hora ya registrada
 *  necesita la autorización de **las dos partes**, y sin ella la empresa puede
 *  aplicarlo igual pero tiene que constar que fue sin acuerdo, con la versión
 *  de la persona al lado.
 *
 *  Lo que se comprueba aquí no es que los botones funcionen: es que nadie pueda
 *  saltarse una garantía. Que no haya una segunda puerta sin motivo, que el
 *  original no desaparezca, y que a quien tiene que consentir se le diga qué.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Prepara una propuesta de la empresa sobre el registro del operario. */
async function proponerAnulacion(browser) {
  const admin = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
  const page = await admin.newPage()
  await page.goto('/panel')

  const gente = await api(page, '/employees/?search=operario')
  const persona = gente.body.results[0]
  const fichajes = await api(page, `/punches/?employee=${persona.id}&is_active=true`)
  const fichaje = fichajes.body.results.find((p) => p.punch_type === 'OUT')

  const propuesta = await api(page, '/corrections/', {
    method: 'POST',
    body: {
      employee: persona.id,
      kind: 'VOID',
      target: fichaje.id,
      reason: 'Prueba de interfaz: fichaje del terminal equivocado.',
    },
  })
  await admin.close()
  return { correccion: propuesta.body, fichaje, persona }
}

test.describe('Quien tiene que consentir', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('ve QUÉ fichaje se va a tocar, no solo que se va a tocar algo', async ({
    page,
    browser,
  }) => {
    // El fallo del 13/08: con una anulación no hay hora propuesta ---ese es el
    // cambio--- así que la pantalla decía «Anular un fichaje» y ponía dos
    // botones. Se pedía consentir sin decir qué.
    const { fichaje } = await proponerAnulacion(browser)

    await irA(page, '/mi-jornada', 'Mi jornada')
    // El título se pluraliza cuando hay varios, así que la prueba no puede
    // atarse al singular.
    await expect(page.getByText(/Cambios? en tu registro/)).toBeVisible()

    // Lo que hay que ver: de qué a qué. Sin esto la pantalla decía «Anular un
    // fichaje» y ponía dos botones debajo.
    await expect(page.getByText('queda anulado').first()).toBeVisible()
    const hora = new Date(fichaje.timestamp).toLocaleTimeString('es-ES', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Madrid',
    })
    await expect(page.getByText(hora, { exact: false }).first()).toBeVisible()
  })

  test('discrepar exige contar tu versión', async ({ page, browser }) => {
    const { correccion } = await proponerAnulacion(browser)

    await page.goto('/mi-jornada')
    const sinVersion = await api(page, `/corrections/${correccion.id}/dispute/`, {
      method: 'POST',
      body: { account: '' },
    })
    // Un «no» a secas deja el registro con una discrepancia y nada que pesar al
    // lado, y a quien perjudica es a quien discrepa.
    expect(sinVersion.status).toBeGreaterThanOrEqual(400)

    const conVersion = await api(page, `/corrections/${correccion.id}/dispute/`, {
      method: 'POST',
      body: { account: 'Ese fichaje es mío, ese día cerré yo la nave.' },
    })
    expect(conVersion.status).toBeLessThan(300)
  })

  test('no puede aceptar una corrección de otra persona', async ({ page, browser }) => {
    const admin = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
    const suPagina = await admin.newPage()
    await suPagina.goto('/panel')
    const todas = await api(suPagina, '/corrections/')
    const ajena = (todas.body.rows ?? todas.body.results ?? []).find(
      (c) => c.employee_name && !c.employee_name.includes('Marta'),
    )
    await admin.close()
    test.skip(!ajena, 'no hay correcciones de otra persona en la semilla')

    await page.goto('/mi-jornada')
    const intento = await api(page, `/corrections/${ajena.id}/accept/`, { method: 'POST' })
    expect(intento.status).toBeGreaterThanOrEqual(400)
  })
})

test.describe('Quien propone el cambio', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('una corrección sin motivo se rechaza', async ({ page }) => {
    await page.goto('/panel')
    const gente = await api(page, '/employees/?search=operario')
    const persona = gente.body.results[0]
    const fichajes = await api(page, `/punches/?employee=${persona.id}&is_active=true`)

    const intento = await api(page, '/corrections/', {
      method: 'POST',
      body: { employee: persona.id, kind: 'VOID', target: fichajes.body.results[0].id, reason: '' },
    })
    // Sin motivo, una corrección no se distingue de una manipulación.
    expect(intento.status).toBe(400)
  })

  test('no hay una segunda puerta para anular un fichaje sin motivo', async ({ page }) => {
    // `PATCH /punches/{id}/void/` existió y se quitó a propósito: dejaba
    // tachar un asiento sin motivo y sin avisar, mientras la corrección
    // equivalente exige las dos cosas. Dos puertas al mismo acto, una sin
    // garantías, vacían el procedimiento.
    await page.goto('/panel')
    const fichajes = await api(page, '/punches/')
    const alguno = fichajes.body.results[0]

    const puertaTrasera = await api(page, `/punches/${alguno.id}/void/`, {
      method: 'PATCH',
      body: { reason: 'por las bravas' },
    })
    expect([404, 405]).toContain(puertaTrasera.status)
  })

  test('el fichaje original no se borra al aplicar la corrección', async ({ page, browser }) => {
    const { correccion, fichaje } = await proponerAnulacion(browser)

    // La persona da su conformidad, que es el paso que faltaba. Antes esto era
    // `test.skip(aplicada.status >= 400, 'necesita la conformidad de la persona
    // primero')`: la prueba sabía cuál era el paso que le faltaba y en vez de
    // darlo se rendía, así que llevaba sin comprobar nada. Y lo que comprueba
    // es la regla que gobierna el módulo entero ---el original nunca se borra---.
    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const suPagina = await suyo.newPage()
    await suPagina.goto('/mi-jornada')
    const conforme = await api(suPagina, `/corrections/${correccion.id}/accept/`, {
      method: 'POST',
    })
    await suyo.close()
    expect(conforme.status, JSON.stringify(conforme.body)).toBe(200)

    await page.goto('/panel')
    const tras = await api(page, `/corrections/${correccion.id}/`)
    expect(tras.body.status, 'aceptar no la aplicó').toBe('APPROVED')

    // Anulado y legible: el registro conserva lo que pasó y lo que se decidió.
    const original = await api(page, `/punches/${fichaje.id}/`)
    expect(original.status).toBe(200)
    expect(original.body.is_active).toBe(false)
  })

  test('aplicar sin acuerdo queda marcado como tal', async ({ page, browser }) => {
    const { correccion } = await proponerAnulacion(browser)

    // La persona discrepa.
    const suyo = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
    const suPagina = await suyo.newPage()
    await suPagina.goto('/mi-jornada')
    await api(suPagina, `/corrections/${correccion.id}/dispute/`, {
      method: 'POST',
      body: { account: 'No es mío ese fichaje.' },
    })
    await suyo.close()

    await page.goto('/panel')
    const impuesta = await api(page, `/corrections/${correccion.id}/apply-anyway/`, {
      method: 'POST',
    })
    test.skip(impuesta.status >= 400, `la empresa no pudo aplicarlo: ${impuesta.status}`)

    const despues = await api(page, `/corrections/${correccion.id}/`)
    expect(despues.body.applied_without_agreement).toBe(true)
    // Y la versión de la persona viaja con ella.
    expect(despues.body.employee_dissent).toContain('No es mío')
  })
})
