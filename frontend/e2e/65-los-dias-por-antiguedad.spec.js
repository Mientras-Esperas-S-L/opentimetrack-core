/** Los días de vacaciones que el convenio suma por antigüedad.
 *
 *  **No salen del Estatuto:** el art. 38.1 fija treinta días naturales y no dice
 *  nada de la antigüedad. Los da el convenio, así que la escala la declara la
 *  empresa y sin declararla no cambia nada.
 *
 *  Va en la suite de navegador por la frase, no por la cifra. «24» no se puede
 *  comprobar; «22 más uno por antigüedad, con doce años de servicio» sí, y es la
 *  diferencia entre un saldo que alguien acepta y uno que acaba en una
 *  conversación con la gestoría.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/operario.json' })

test.describe('Los días por antigüedad', () => {
  test('el saldo los suma y explica de dónde salen', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const { body: saldo } = await api(page, '/absences/balance/')

    expect(
      saldo.seniority_days,
      'la demostración ya no tiene escala de antigüedad',
    ).toBeGreaterThan(0)
    await expect(page.getByText(/por antigüedad/i).first()).toBeVisible()
    await expect(page.getByText(/años de servicio/i).first()).toBeVisible()
  })

  test('la API dice los años con los que ha contado', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const { body: saldo } = await api(page, '/absences/balance/')

    // Sin los años, la frase no se puede comprobar: quien la lea no sabe si el
    // producto ha contado desde la fecha buena.
    expect(saldo.seniority_years).toBeGreaterThan(0)
    expect(saldo).toHaveProperty('seniority_unknown')
  })

  test('la cifra grande y la explicación hablan del mismo saldo', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const { body: saldo } = await api(page, '/absences/balance/')

    // Que los días por antigüedad estén **dentro** del total lo prueba la suite
    // de servidor, que tiene la cifra base para compararla. Desde aquí no se
    // puede: sin saber cuántos días daba el convenio antes de sumarlos, un total
    // con extra y uno sin ellos se ven igual. La primera versión de esta prueba
    // decía comprobarlo y pasaba con la suma quitada.
    //
    // Lo que sí se comprueba aquí, y es lo que ve quien la abre: que los números
    // de la pantalla son los del saldo servido, y no otros.
    const conteo = await page
      .getByText(/días laborables de/i)
      .first()
      .innerText()
    // El total al que se compara: «días laborables de 24». Lo que queda va en
    // el número grande, que es otro elemento.
    expect(conteo).toContain(String(saldo.entitled))
  })
})
