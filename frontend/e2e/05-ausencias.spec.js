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
    // Antes esta prueba pedía los avisos y comprobaba
    // `expect(await avisos.count()).toBeGreaterThanOrEqual(0)`, que es cierto
    // siempre: un `count()` no puede ser negativo. Su propio comentario decía
    // «no siempre hay una que se pase», y en vez de fabricar una que se pasara
    // no comprobaba nada. Llevaba en verde sin mirar la pantalla.
    await irA(page, '/panel/decisiones', 'Por decidir')

    const permisos = await api(page, '/leave-types/')
    const conTope = (permisos.body?.results ?? permisos.body ?? []).find(
      (t) => t.amount && Number(t.amount) > 0 && t.unit?.startsWith('DAYS') && t.is_active !== false,
    )
    expect(conTope, 'hace falta un permiso con tope en el catálogo').toBeTruthy()

    const gente = await api(page, '/employees/')
    const yo = await api(page, '/auth/me/')
    const otra = (gente.body?.results ?? []).find((p) => p.id !== yo.body.user.id)
    expect(otra, 'no se puede resolver lo propio: hace falta otra persona').toBeTruthy()

    // Se pide el doble de lo que da, para que el exceso no dependa de festivos
    // ni de fines de semana.
    const dias = Number(conTope.amount) * 2
    const desde = new Date()
    desde.setDate(desde.getDate() + 300)
    const hasta = new Date(desde)
    hasta.setDate(hasta.getDate() + dias)

    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: otra.id,
        leave_type: conTope.id,
        start_date: desde.toISOString().slice(0, 10),
        end_date: hasta.toISOString().slice(0, 10),
        reason: 'Prueba de interfaz: pasarse del tope a propósito.',
      },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)

    try {
      // Primero el servidor: si él no lo marca, la pantalla no tiene qué pintar
      // y el fallo estaría en otro sitio.
      expect(alta.body.over_the_limit, 'el servidor no marcó el exceso').toBeTruthy()

      await page.reload()
      await expect(page.getByText(/se pasaría del tope|y el permiso da/).first()).toBeVisible()
    } finally {
      const fuera = await api(page, `/absences/${alta.body.id}/cancel/`, { method: 'POST' })
      expect([200, 204], 'la limpieza no retiró la solicitud').toContain(fuera.status)
    }
  })

  test('rechazar exige que quede constancia y la solicitud se conserva', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')

    // Se crea la solicitud en vez de esperar a que la semilla traiga una. Antes
    // era `test.skip(!pendientes.body?.length, ...)` y llevaba sin ejecutarse:
    // la cola de la base de desarrollo se vacía en cuanto alguien la usa, y el
    // salto lo tapaba en silencio.
    //
    // Queda rechazada y eso está bien: una rechazada es historial ---es
    // justamente lo que esta prueba comprueba--- y no ensucia la cola.
    const gente = await api(page, '/employees/')
    const yo = await api(page, '/auth/me/')
    const otra = (gente.body?.results ?? []).find((p) => p.id !== yo.body.user.id)
    expect(otra, 'hace falta otra persona: no se puede resolver lo propio').toBeTruthy()

    const dentro = (dias) => {
      const d = new Date()
      d.setDate(d.getDate() + dias)
      return d.toISOString().slice(0, 10)
    }
    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: otra.id,
        absence_type: 'VACATION',
        start_date: dentro(200),
        end_date: dentro(201),
        reason: 'Prueba de interfaz: solicitud para rechazar.',
      },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)

    const una = alta.body
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
