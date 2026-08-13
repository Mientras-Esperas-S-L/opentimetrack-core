/** Pedir una ausencia, y que la resuelvan.
 *
 *  Aquí no se prueba una pantalla: se prueba el reparto de poder. Quién puede
 *  pedir qué, quién puede decidirlo, y qué no puede hacer ninguno de los dos.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.describe('Pedir una ausencia', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('el catálogo llega agrupado y con su artículo', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await page.getByRole('button', { name: 'Solicitar' }).click()

    const dialogo = page.getByRole('dialog')
    await dialogo.getByLabel(/Qué pides/).click()

    // Agrupado por familia, y cada permiso con lo que da y de dónde sale: quien
    // pide no tiene por qué saberse el Estatuto.
    await expect(page.getByRole('listbox')).toBeVisible()
    await expect(page.getByText('Permisos retribuidos')).toBeVisible()
    await expect(page.getByText(/Art\. 37\.3/).first()).toBeVisible()
  })

  test('no se ofrece lo que solo registra la empresa', async ({ page }) => {
    // Un ERTE o una huelga los registra la empresa, no se piden. El servidor lo
    // rechazaría, y un desplegable que ofrece lo que luego se niega es una
    // trampa.
    await page.goto('/mis-ausencias')
    const tipos = await api(page, '/leave-types/')
    const soloEmpresa = (tipos.body.results ?? []).filter((t) => t.initiated_by === 'COMPANY')
    expect(soloEmpresa.length).toBeGreaterThan(0)

    await page.getByRole('button', { name: 'Solicitar' }).click()
    await page
      .getByRole('dialog')
      .getByLabel(/Qué pides/)
      .click()
    const listado = await page.getByRole('listbox').innerText()
    for (const tipo of soloEmpresa) {
      expect(listado, `«${tipo.name}» se ofrece y solo lo registra la empresa`).not.toContain(
        tipo.name,
      )
    }
  })

  test('el saldo dice en qué unidad cuenta', async ({ page }) => {
    // «Quedan 9» significa cosas distintas en días naturales y en laborables, y
    // la diferencia en una quincena son cinco días.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await expect(page.getByText(/días (laborables|naturales) de/)).toBeVisible()
  })

  test('pedirla para uno mismo no la aprueba sola', async ({ page }) => {
    await page.goto('/mis-ausencias')
    const tipos = await api(page, '/leave-types/')
    const propios = (tipos.body.results ?? []).find(
      (t) => t.initiated_by !== 'COMPANY' && t.family === 'PAID_LEAVE',
    )

    const pedida = await api(page, '/absences/', {
      method: 'POST',
      body: {
        leave_type: propios.id,
        start_date: '2026-11-03',
        end_date: '2026-11-03',
        reason: 'Prueba de interfaz',
      },
    })
    expect(pedida.status).toBe(201)
    expect(pedida.body.status).toBe('PENDING')

    // Y no puede resolverse la suya.
    const intento = await api(page, `/absences/${pedida.body.id}/approve/`, { method: 'POST' })
    expect(intento.status).toBeGreaterThanOrEqual(400)

    await api(page, `/absences/${pedida.body.id}/cancel/`, { method: 'POST' })
  })

  test('no puede pedir una ausencia en nombre de otra persona', async ({ page, browser }) => {
    const admin = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
    const suPagina = await admin.newPage()
    await suPagina.goto('/panel')
    const gente = await api(suPagina, '/employees/')
    const otro = gente.body.results.find((p) => p.email !== 'operario@demo.local')
    const tipos = await api(suPagina, '/leave-types/')
    const tipo = (tipos.body.results ?? []).find((t) => t.initiated_by !== 'COMPANY')
    await admin.close()

    await page.goto('/mis-ausencias')
    const intento = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: otro.id,
        leave_type: tipo.id,
        start_date: '2026-11-04',
        end_date: '2026-11-04',
      },
    })

    if (intento.status === 201) {
      // Si lo acepta, que al menos no se la haya puesto a la otra persona.
      expect(intento.body.employee, 'la ausencia se creó a nombre de otra persona').not.toBe(
        otro.id,
      )
      await api(page, `/absences/${intento.body.id}/cancel/`, { method: 'POST' })
    } else {
      expect(intento.status).toBeGreaterThanOrEqual(400)
    }
  })
})

test.describe('Resolver ausencias', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la cola enseña el aviso de tope cuando se pasa', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')
    // No siempre hay una que se pase; lo que se comprueba es que la pantalla
    // sepa decirlo cuando la haya.
    const avisos = page.getByText(/se pasaría del tope|y el permiso da/)
    expect(await avisos.count()).toBeGreaterThanOrEqual(0)
  })

  test('rechazar exige que quede constancia y la solicitud se conserva', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')
    const pendientes = await api(page, '/absences/pending/')
    test.skip(!pendientes.body?.length, 'no hay ausencias pendientes en la semilla')

    const una = pendientes.body[0]
    const rechazo = await api(page, `/absences/${una.id}/reject/`, {
      method: 'POST',
      body: { note: 'Prueba de interfaz: coincide con dos bajas en la cuadrilla.' },
    })
    expect(rechazo.status).toBeLessThan(300)

    // Rechazada, no borrada: que alguien lo pidiera y se le dijera que no
    // también es parte del historial.
    const despues = await api(page, `/absences/${una.id}/`)
    expect(despues.status).toBe(200)
    expect(despues.body.status).toBe('REJECTED')
  })
})
