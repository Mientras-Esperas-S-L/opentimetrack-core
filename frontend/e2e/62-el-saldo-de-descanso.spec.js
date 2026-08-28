/** Lo que se debe en descanso por horas extra, en la pantalla de quien lo debe.
 *
 *  «Deberán ser compensadas mediante descanso dentro de los cuatro meses
 *  siguientes a su realización» (art. 35.1 ET). El producto sabía desde el
 *  primer día **cómo** se salda cada hora extra ---con dinero o con descanso---
 *  y no sabía **si** se había saldado.
 *
 *  Va en la suite de navegador porque la cifra sin la pantalla no sirve: «te
 *  quedan 4 h» lo tiene que ver quien las tiene que disfrutar, y quien las debe
 *  devolver. Y porque la mitad del valor está en la **fecha**: pasado el plazo,
 *  el artículo está incumplido y ya no se arregla.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/operario.json' })

const elAviso = (page) => page.getByRole('alert').filter({ hasText: /descanso/i })

test.describe('El saldo de descanso', () => {
  test('se ve en Mis ausencias, con la fecha límite', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const {
      body: { rest_debt: deuda },
    } = await api(page, '/absences/balance/')

    // La demostración genera alguna hora extra a compensar con descanso, así
    // que esto tiene que existir. Si deja de generarlas, esta prueba avisa
    // antes de que la función desaparezca de las demostraciones.
    expect(deuda, 'la semilla ya no genera horas extra a compensar').not.toBeNull()

    await expect(elAviso(page)).toBeVisible()
    await expect(elAviso(page)).toContainText('35.1')
  })

  test('dice cómo se devuelve, no solo cuánto se debe', async ({ page }) => {
    // Un aviso que dice lo que debes y no el siguiente paso obliga a adivinar
    // por qué puerta se devuelve.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await expect(elAviso(page)).toContainText(/Descanso compensatorio/i)
  })

  test('y ese permiso existe en la lista de solicitar', async ({ page }) => {
    // El contraste del anterior: decirle a alguien que pida algo que no está en
    // la lista es peor que no decirle nada.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await page
      .getByRole('button', { name: /Pedir|Solicitar/i })
      .first()
      .click()
    await page.getByRole('dialog').getByRole('combobox').first().click()
    await expect(page.getByRole('option', { name: /^Descanso compensatorio/ })).toBeVisible()
  })

  test('la API sirve el saldo con lo que hace falta para leerlo', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const {
      body: { rest_debt: deuda },
    } = await api(page, '/absences/balance/')

    // Sin la fecha, «te quedan 4 h» no sirve para no llegar tarde. Y sin los
    // días sin convertir, un saldo podría parecer devuelto sin estarlo.
    for (const campo of ['owed_hours', 'remaining_hours', 'overdue_hours', 'due_on', 'days']) {
      expect(deuda, `falta ${campo}`).toHaveProperty(campo)
    }
    expect(deuda.citation).toBe('Art. 35.1 ET')
  })
})
