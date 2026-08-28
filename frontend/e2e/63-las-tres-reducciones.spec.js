/** Las tres reducciones que faltaban, en la pantalla de quien las pide.
 *
 *  El inventario las agrupaba como una sola cosa ---«van sobre la misma
 *  maquinaria»--- y es cierto. Lo que no es común es lo que las distingue, y es
 *  justo lo que hay que ver en pantalla: en el párrafo tercero del art. 37.6 la
 *  mitad es el **mínimo**, mientras que en la guarda legal del mismo artículo es
 *  el máximo.
 *
 *  Va aquí y no solo en la suite de servidor porque estos tres derechos los
 *  ejerce quien trabaja: un permiso que existe en el catálogo y no sale en la
 *  lista de «Solicitar» no se puede ejercer.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/operario.json' })

const PREMATURO_HORA = /^Hijo prematuro u hospitalizado: la hora de ausencia/
const PREMATURO_REDUCCION = /^Hijo prematuro u hospitalizado: la reducción/
const ENFERMEDAD_GRAVE = /^Cuidado de menor con cáncer o enfermedad grave/
const VIOLENCIA = /^Violencia de género o sexual: reducción o reordenación/

async function elegir(page, nombre) {
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

test.describe('Las tres reducciones', () => {
  test('las tres se pueden pedir, y con su fracción', async ({ page }) => {
    for (const nombre of [PREMATURO_REDUCCION, ENFERMEDAD_GRAVE, VIOLENCIA]) {
      const dialogo = await elegir(page, nombre)
      await expect(laFraccion(dialogo)).toBeVisible()
      await page.keyboard.press('Escape')
    }
  })

  test('la hora del prematuro no reduce, que es el otro derecho del mismo artículo', async ({
    page,
  }) => {
    // **El contraste.** El art. 37.5 concede dos cosas: una hora de ausencia
    // retribuida y una reducción de hasta dos horas sin sueldo. Si la hora
    // ofreciera también la fracción, las dos entradas sobrarían y la distinción
    // entre lo que se cobra y lo que no se perdería.
    const dialogo = await elegir(page, PREMATURO_HORA)
    await expect(laFraccion(dialogo)).toHaveCount(0)
  })

  test('la nota se lee con su énfasis, no con los asteriscos', async ({ page }) => {
    // Lo que va destacado es lo que se confunde: «al menos la mitad» frente al
    // «como máximo la mitad» del otro párrafo del mismo artículo. Con los
    // asteriscos puestos, el texto parece a medio escribir.
    const dialogo = await elegir(page, ENFERMEDAD_GRAVE)
    const nota = dialogo.getByText(/al menos la mitad/)
    await expect(nota).toBeVisible()
    await expect(nota).not.toContainText('**')
  })

  test('y la cuantía no dice «el tiempo indispensable»', async ({ page }) => {
    // Un permiso que **recorta** la jornada no dura «el tiempo que haga falta».
    // Esa frase es la de los que la paran ---una consulta, un examen--- y en una
    // reducción es engañosa.
    const dialogo = await elegir(page, ENFERMEDAD_GRAVE)
    await expect(dialogo.getByText(/la parte de jornada que se acuerde/)).toBeVisible()
  })
})

test('la reducción por violencia no pide justificante', async ({ page }) => {
  // La acreditación se hace ante quien corresponde, no colgando un documento en
  // una herramienta de fichaje. Pedirlo convertiría el ejercicio del derecho en
  // una declaración de algo íntimo delante de quien aprueba las ausencias.
  await irA(page, '/mis-ausencias', 'Mis ausencias')
  const { body: tipos } = await api(page, '/leave-types/?page_size=100')
  const lista = tipos.results ?? tipos
  const de = (code) => lista.find((x) => x.code === code)

  expect(de('es.gender_violence_reduction').needs_justification).toBe(false)
  // Y el contraste, en el mismo artículo de al lado: la de enfermedad grave sí
  // lo pide, así que «no pide justificante» no es el valor por defecto de todo.
  expect(de('es.serious_illness_care').needs_justification).toBe(true)
})
