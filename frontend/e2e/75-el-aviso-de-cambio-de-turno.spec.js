/** A quien le cambian el turno le llega un aviso, y la empresa ve que lo leyó.
 *
 *  El cuadrante se cambiaba sin que a la persona le llegara nada. El RD 723/2026
 *  pide avisar de los cambios de turno y, por un canal electrónico, poder probar
 *  cuándo llegó el aviso y cuándo se leyó (art. 6).
 *
 *  Los avisos no se borran ---son prueba---, así que la prueba no puede dejar la
 *  base como estaba. Deja el turno como lo encontró y marca como leídos los
 *  avisos que genera, que es lo que los saca de la pantalla del operario.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const iso = (fecha) => fecha.toLocaleDateString('sv-SE')
const TARDE = [{ start: '15:00', end: '22:00' }]
const NOCHE = [{ start: '22:00', end: '06:00' }]

test.describe('El aviso de cambio de turno', () => {
  test('el operario lo ve, dice que lo ha visto y la empresa lo sabe', async ({ browser }) => {
    const admin = await browser.newPage({ storageState: 'e2e/.sesiones/admin.json' })
    const operario = await browser.newPage({ storageState: 'e2e/.sesiones/operario.json' })
    await irA(admin, '/panel/cuadrante', 'Cuadrante')
    await operario.goto('/')

    const yo = (await api(operario, '/auth/me/')).body
    const quien = yo.id ?? yo.user?.id
    const dentro = new Date()
    dentro.setDate(dentro.getDate() + 12)
    const dia = iso(dentro)

    // Lo que había, para dejarlo igual al terminar.
    const antes = (await api(admin, `/shifts/roster/?from=${dia}&to=${dia}`)).body.find(
      (s) => s.employee === quien,
    )

    const leerTodos = async () => {
      const pendientes = (await api(operario, '/shift-notices/?mine=true&unread=true')).body
      for (const aviso of pendientes.results) {
        await api(operario, `/shift-notices/${aviso.id}/read/`, { method: 'POST' })
      }
    }

    // Distinto de lo que hubiera: pintar lo mismo no es un cambio y no avisa.
    const nuevo = antes?.segments?.[0]?.start === TARDE[0].start ? NOCHE : TARDE

    try {
      await leerTodos()
      const pintado = await api(admin, '/shifts/paint/', {
        method: 'POST',
        body: { cells: [{ employee: quien, day: dia, segments: nuevo }] },
      })
      expect(pintado.status).toBe(200)
      expect(pintado.body.notified).toBe(1)

      await operario.reload()
      const aviso = operario.getByRole('alert').filter({ hasText: 'Te han cambiado el turno' })
      await expect(aviso).toBeVisible()
      await expect(aviso).toContainText(`${nuevo[0].start}–${nuevo[0].end}`)
      await aviso.getByRole('button', { name: 'Entendido' }).click()
      await expect(aviso).toBeHidden()

      await admin.reload()
      const panel = admin.getByRole('region', { name: 'Avisos de cambios de turno' })
      await expect(panel.getByText(/^Leído /).first()).toBeVisible()
      await expect(panel.getByText(/^Llegó .* · OpenTimeTrack$/).first()).toBeVisible()
    } finally {
      await api(admin, '/shifts/paint/', {
        method: 'POST',
        body: {
          cells: [
            antes
              ? { employee: quien, day: dia, segments: antes.segments, pattern: antes.pattern }
              : { employee: quien, day: dia },
          ],
        },
      })
      await leerTodos()
      await admin.close()
      await operario.close()
    }
  })
})
