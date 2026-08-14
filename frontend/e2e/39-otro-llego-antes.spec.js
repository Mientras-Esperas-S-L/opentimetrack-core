/** Cuando otra persona resuelve lo mismo un segundo antes.
 *
 *  El servidor lo rechaza desde hoy con `already_resolved` ---antes las dos
 *  escribían y la solicitud acababa contradiciéndose--- y la pantalla enseñaba
 *  el mensaje **dejando la fila en la lista**. Quien lo leía volvía a pulsar,
 *  recibía lo mismo, y la cola le seguía mintiendo hasta recargar a mano.
 *
 *  Las treinta y cuatro mutaciones del producto hacían `onError: setError` y
 *  ninguna refrescaba. La mayoría hace bien: casi todos los rechazos son sobre
 *  lo que acabas de escribir, y ahí la lista sigue siendo verdad. Estos cuatro
 *  códigos no, porque dicen que otra persona llegó antes.
 *
 *  ## Por qué se finge la respuesta y no se monta el caso de verdad
 *
 *  Lo que cambió es comportamiento del navegador, así que el servidor puede ser
 *  de mentira y la prueba gana en precisión: se provoca el 409 exacto sin
 *  depender de que haya algo pendiente en la base.
 *
 *  Y sobre todo, no deja residuo. Montarlo de verdad exige aprobar una ausencia,
 *  y una ausencia aprobada **no se puede borrar** ---el ViewSet no expone
 *  `destroy`, a propósito---. Cada ejecución dejaría una, que es la forma de
 *  envenenar la base compartida que ya ha roto pruebas dos veces hoy.
 */
import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Crea una solicitud pendiente y la retira al terminar.
 *
 *  Se puede retirar precisamente porque la aprobación va interceptada: el
 *  servidor nunca la ve, así que la solicitud sigue pendiente y `cancel`
 *  ---que solo funciona sobre las abiertas--- la limpia sin dejar rastro.
 */
const conUnaPendiente = async (page, hacer) => {
  // Para otra persona, no para quien prueba: la regla de cuatro ojos no deja
  // resolver lo propio, así que una solicitud mía no traería botón de aprobar.
  const gente = await api(page, '/employees/')
  const yo = await api(page, '/auth/me/')
  const otra = (gente.body?.results ?? []).find((p) => p.id !== yo.body.user.id)
  expect(otra, 'hace falta al menos otra persona en la empresa').toBeTruthy()
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
      start_date: dentro(120),
      end_date: dentro(121),
      reason: 'Prueba de carrera',
    },
  })
  expect(alta.status, JSON.stringify(alta.body)).toBe(201)

  try {
    await hacer()
  } finally {
    const fuera = await api(page, `/absences/${alta.body.id}/cancel/`, { method: 'POST' })
    expect([200, 204], 'la limpieza no retiró la solicitud').toContain(fuera.status)
  }
}

const YA_RESUELTA = {
  error: {
    code: 'already_resolved',
    message: 'Esta solicitud ya está resuelta.',
    details: {},
  },
}

test.describe('Otro llegó antes', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('al recibir «ya está resuelta», la cola se vuelve a pedir', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')
    await conUnaPendiente(page, async () => {
      await page.reload()

      // Cualquier resolución contesta 409, como si otra persona hubiera llegado.
      await page.route(/\/api\/absences\/[^/]+\/(approve|reject)\//, (route) =>
        route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify(YA_RESUELTA),
        }),
      )

      // Se cuentan las peticiones a la cola: lo que se comprueba es que **vuelve
      // a pedirla**, no cómo quede el DOM, que depende de lo que haya en la base.
      let recargas = 0
      await page.route(/\/api\/absences\/(pending|\?|$)/, async (route) => {
        recargas += 1
        await route.continue()
      })

      const aprobar = page.getByRole('button', { name: 'Aprobar' }).first()
      // Sin `skip`: la prueba crea su propia solicitud, así que si el botón no
      // aparece es un fallo y no una base sin datos. Con `skip` se ponía verde
      // sin haber comprobado nada, que es la peor forma de pasar.
      await expect(aprobar).toBeVisible()

      const antes = recargas
      await aprobar.click()

      await expect(page.getByRole('alert').filter({ hasText: /ya está resuelta/i })).toBeVisible()
      await expect
        .poll(() => recargas, {
          message: 'la cola no se volvió a pedir: la fila resuelta se queda',
        })
        .toBeGreaterThan(antes)
    })
  })

  test('pero un rechazo corriente no recarga la lista', async ({ page }) => {
    /** El contraste, y es la mitad que justifica la lista corta de códigos.
     *
     *  Refrescar en cualquier error sería más simple y traería la lista entera
     *  cada vez que a alguien le falta un campo, que es la mayoría de las veces.
     */
    await irA(page, '/panel/decisiones', 'Por decidir')
    await conUnaPendiente(page, async () => {
      await page.reload()

      await page.route(/\/api\/absences\/[^/]+\/(approve|reject)\//, (route) =>
        route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            error: { code: 'reason_required', message: 'Hace falta un motivo.', details: {} },
          }),
        }),
      )

      let recargas = 0
      await page.route(/\/api\/absences\/(pending|\?|$)/, async (route) => {
        recargas += 1
        await route.continue()
      })

      const aprobar = page.getByRole('button', { name: 'Aprobar' }).first()
      // Sin `skip`: la prueba crea su propia solicitud, así que si el botón no
      // aparece es un fallo y no una base sin datos. Con `skip` se ponía verde
      // sin haber comprobado nada, que es la peor forma de pasar.
      await expect(aprobar).toBeVisible()

      const antes = recargas
      await aprobar.click()
      await expect(page.getByRole('alert').filter({ hasText: /motivo/i })).toBeVisible()
      await page.waitForTimeout(600)

      expect(recargas, 'recarga con cualquier error, no solo con los que caducan la vista').toBe(
        antes,
      )
    })
  })
})
