/** La lactancia se puede pedir reduciendo la jornada, no solo como ausencia.
 *
 *  El art. 37.4 da **dos formas y las elige quien trabaja**: una hora de
 *  ausencia, divisible en dos fracciones, o media hora de reducción de jornada.
 *  El catálogo solo traía la primera y la pantalla decidía si ofrecer el campo
 *  de la fracción adivinándolo ---«suspensión que registra la empresa»--- en vez
 *  de mirar el campo que existe justo para eso.
 *
 *  Ese heurístico se equivocaba en ocho de los treinta y cuatro tipos, **en las
 *  dos direcciones**: no ofrecía reducir en la lactancia ni en la reducción por
 *  guarda legal, que son derechos de quien trabaja y se ejercen precisamente
 *  reduciendo; y sí lo ofrecía en la huelga, el cierre patronal y la prisión
 *  provisional, que no reducen la jornada sino que la paran.
 *
 *  Va en la suite de navegador porque el campo estaba en el modelo desde el
 *  principio: lo que faltaba era servirlo y mirarlo, y eso solo se ve abriendo
 *  la pantalla.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/operario.json' })

// Ancladas al principio: cada opción lleva detrás su cuantía y su artículo
// ---«Lactancia · 1 hora · al día · Art. 37.4 ET»---, así que un nombre exacto no
// casa y uno suelto cazaría también «Riesgo durante la lactancia natural».
const LACTANCIA = /^Lactancia/
const GUARDA_LEGAL = /^Reducción de jornada por guarda legal/
//: El contraste tiene que ser algo que **esta persona pueda pedir**: la huelga
//: la registra la empresa y no sale en esta lista, así que no serviría para
//: comprobar que la pantalla distingue.
const SIN_REDUCCION = /^Matrimonio/

async function abrirSolicitud(page, nombre) {
  await irA(page, '/mis-ausencias', 'Mis ausencias')
  await page
    .getByRole('button', { name: /Pedir|Solicitar/i })
    .first()
    .click()
  const dialogo = page.getByRole('dialog')
  await dialogo.getByRole('combobox').first().click()
  await page.getByRole('option', { name: nombre }).first().click()
  return dialogo
}

const laFraccion = (dialogo) => dialogo.getByLabel('Reducción de jornada (%)')

test.describe('La lactancia', () => {
  test('se puede pedir reduciendo la jornada', async ({ page }) => {
    const dialogo = await abrirSolicitud(page, LACTANCIA)
    await expect(laFraccion(dialogo)).toBeVisible()
  })

  test('y el texto de ayuda no habla de suspender el contrato', async ({ page }) => {
    // Decía «vacío o 100 suspende el contrato entero» para cualquier permiso
    // que ofreciera la fracción. En la lactancia es falso: dejarla vacía es
    // pedirla como la hora de ausencia del art. 37.4, no suspender nada.
    const dialogo = await abrirSolicitud(page, LACTANCIA)
    await expect(dialogo.getByText(/suspende el contrato entero/i)).toHaveCount(0)
    await expect(dialogo.getByText(/se pide como ausencia/i)).toBeVisible()
  })

  test('la cifra concuerda con su unidad', async ({ page }) => {
    // Es una hora al día, así que el fallo de plural salía en el primer permiso
    // que alguien abre: «1 horas · al día».
    const dialogo = await abrirSolicitud(page, LACTANCIA)
    await expect(dialogo.getByText('1 horas')).toHaveCount(0)
    await expect(dialogo.getByText(/1 hora\b/).first()).toBeVisible()
  })
})

test.describe('El campo de la fracción sale de lo que dice el permiso', () => {
  test('la guarda legal también lo ofrece, y la pide quien trabaja', async ({ page }) => {
    // La otra mitad del mismo fallo: es una SUSPENSION que inicia la PERSONA,
    // así que el heurístico la dejaba fuera. El derecho del art. 37.6 se ejerce
    // **reduciendo**, de modo que sin este campo no se podía ejercer entero.
    const dialogo = await abrirSolicitud(page, GUARDA_LEGAL)
    await expect(laFraccion(dialogo)).toBeVisible()
  })

  test('un permiso que no reduce no lo ofrece', async ({ page }) => {
    // **El contraste**, y no es simétrico con lo de arriba: sin esto, «lo dice
    // el permiso» y «se lo ofrezco a todo el mundo» se verían igual. Los quince
    // días por matrimonio se cogen enteros; un campo para pedirlos a media
    // jornada es una invitación a anotar algo que no existe.
    const dialogo = await abrirSolicitud(page, SIN_REDUCCION)
    await expect(laFraccion(dialogo)).toHaveCount(0)
  })
})

test('el permiso dice si puede reducir, y la API lo sirve', async ({ page }) => {
  await irA(page, '/mis-ausencias', 'Mis ausencias')
  const { body: tipos } = await api(page, '/leave-types/?page_size=100')
  const lista = tipos.results ?? tipos
  const de = (code) => lista.find((x) => x.code === code)

  // Sin este campo en la respuesta, la pantalla no tiene con qué decidir y
  // vuelve a adivinar.
  expect(de('es.breastfeeding').can_reduce_the_day).toBe(true)
  expect(de('es.childcare_reduced_hours').can_reduce_the_day).toBe(true)
  expect(de('es.strike').can_reduce_the_day).toBe(false)
})
