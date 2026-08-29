/** Pedir más descanso compensatorio del que consta que se debe.
 *
 *  El producto calculaba el saldo ---«te quedan 24 h»---, lo enseñaba en la
 *  pantalla de quien lo disfruta, y **no lo usaba en el único sitio donde
 *  alguien decide algo**. Medido: con veinticuatro horas debidas se podían pedir
 *  diez días seguidos y ni quien los pedía ni quien los aprobaba veía nada.
 *
 *  Va en la suite de navegador porque el hallazgo es de pantalla: la cifra
 *  existía en la API desde el primer día. Lo que faltaba era decirla donde se
 *  decide, y decirla **antes** de pedir, que es cuando todavía sirve para algo.
 *
 *  Avisa, no impide: el saldo es incompleto por diseño ---los descansos por
 *  ampliación sectorial están fuera a propósito y el convenio puede dar más---.
 */

import { expect, test } from '@playwright/test'

import { api, irA, marca } from './apoyo.js'

/** La ausencia de prueba, para retirarla al terminar. */
let creada = null

test.afterEach(async ({ page }) => {
  if (!creada) return
  const cual = creada
  creada = null
  await irA(page, '/mis-ausencias', 'Mis ausencias')
  await api(page, `/absences/${cual}/cancel/`, { method: 'POST' }).catch(() => {})
})

test.describe('Pedir más descanso del que se debe', () => {
  test.describe('quien lo pide', () => {
    test.use({ storageState: 'e2e/.sesiones/operario.json' })

    test('ve lo que se le debe antes de pedirlo', async ({ page }) => {
      // **Justo antes de pedir es donde sirve.** Enterarse de que se piden
      // ochenta horas cuando constan veinticuatro tiene que pasar al escribirlo,
      // no al recibir el rechazo.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const {
        body: { rest_debt: deuda },
      } = await api(page, '/absences/balance/')
      expect(deuda, 'la demostración ya no genera deuda de descanso').toBeTruthy()

      await page
        .getByRole('button', { name: /Solicitar/ })
        .first()
        .click()
      const dialogo = page.getByRole('dialog')
      await dialogo.getByRole('combobox').first().fill('Descanso')
      await page.getByRole('option', { name: /^Descanso compensatorio/ }).click()

      await expect(dialogo).toContainText(
        new RegExp(`Te constan ${deuda.remaining_hours} h de descanso`),
      )
      // Y con el matiz, que es lo que impide leerlo como un tope legal.
      await expect(dialogo).toContainText(/no cuenta los descansos que fije el convenio/i)
      await page.getByRole('button', { name: 'Cancelar' }).click()
    })

    test('la API avisa al pedir más de lo que consta', async ({ page }) => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const { body: tipos } = await api(page, '/leave-types/?page_size=200')
      const descanso = (tipos.results ?? tipos).find((t) => t.code === 'es.compensatory_rest')

      // Diez días seguidos, empezando pasado mañana.
      const dia = (offset) => {
        const d = new Date()
        d.setDate(d.getDate() + offset)
        return d.toISOString().slice(0, 10)
      }
      const { status, body } = await api(page, '/absences/', {
        method: 'POST',
        body: {
          absence_type: 'PAID_LEAVE',
          leave_type: descanso.id,
          start_date: dia(2),
          end_date: dia(11),
          reason: `Saldo ${marca()}`,
        },
      })
      expect(status).toBe(201)
      creada = body.id

      expect(body.over_the_limit, 'no avisa de pedir más de lo debido').toBeTruthy()
      expect(body.over_the_limit.kind).toBe('rest_debt')
      expect(body.over_the_limit.owed_hours).toBeGreaterThanOrEqual(0)
    })
  })
})
