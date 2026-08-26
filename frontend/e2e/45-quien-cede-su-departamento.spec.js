/** El aviso de Ajustes sobre responsables que no llevan ningún departamento.
 *
 *  Decía siempre «así que ve a toda la empresa». Era verdad el primer día de una
 *  empresa y mentira a partir del momento en que alguien lleva un departamento:
 *  desde entonces quien no lleva ninguno ve **solo su propio registro**, que es
 *  lo que le pasa a quien acaba de ceder el suyo a un compañero.
 *
 *  Hasta la vuelta 84 le pasaba lo contrario ---se llevaba la plantilla entera---
 *  y eso se prueba en el backend, que es donde está la regla
 *  (`test_reasignar_un_departamento_no_amplia_a_nadie`). Aquí se prueba la frase,
 *  porque un aviso que dice lo contrario de lo que ocurre es peor que no tenerlo
 *  y ninguna prueba se pone roja cuando un texto miente.
 *
 *  Se ejercita el helper y no la pantalla montada: para verla haría falta dejar a
 *  una responsable de la semilla sin departamento, y una prueba que reorganiza la
 *  empresa de demostración le cambia los datos a las demás.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

test.describe('Quien cede su departamento', () => {
  test('el aviso dice lo que de verdad le pasa', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes')

    const dicho = await page.evaluate(async () => {
      const { avisoDeAlcance } = await import('/src/pages/admin/avisoDeAlcance.js')
      const ana = [{ name: 'Ana Ruiz' }]
      const dos = [{ name: 'Ana Ruiz' }, { name: 'Berta Gil' }]
      return {
        sinNadieAlMando: avisoDeAlcance(ana, false),
        yaHayAlguienAlMando: avisoDeAlcance(ana, true),
        dosSueltas: avisoDeAlcance(dos, true),
        ninguna: avisoDeAlcance([], true),
        sinDato: avisoDeAlcance(undefined, true),
      }
    })

    // El día uno: nadie lleva nada, así que la responsable lee a todo el mundo.
    // Es un riesgo de privacidad y va en amarillo.
    expect(dicho.sinNadieAlMando.severity).toBe('warning')
    expect(dicho.sinNadieAlMando.text).toBe(
      'Ana Ruiz no lleva ningún departamento, así que ve a toda la empresa.',
    )

    // Ya se usan los departamentos: quien no lleva ninguno no ve a nadie. Es un
    // estorbo, no un riesgo, y va en azul.
    expect(dicho.yaHayAlguienAlMando.severity).toBe('info')
    expect(dicho.yaHayAlguienAlMando.text).toBe(
      'Ana Ruiz no lleva ningún departamento, así que solo ve su propio registro.',
    )

    // En plural concuerdan el verbo y el posesivo, no solo el sustantivo.
    expect(dicho.dosSueltas.text).toBe(
      '2 responsables no llevan ningún departamento, así que solo ven su propio registro: Ana Ruiz, Berta Gil.',
    )

    // Y sin nadie suelto no hay aviso, ni tampoco cuando la API aún no ha llegado.
    expect(dicho.ninguna).toBeNull()
    expect(dicho.sinDato).toBeNull()
  })
})
