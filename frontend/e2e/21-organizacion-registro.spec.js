/** Cómo se organizó el registro de jornada. Art. 34.9, párrafo segundo.
 *
 *  «Mediante negociación colectiva o acuerdo de empresa o, en su defecto,
 *  decisión del empresario previa consulta con los representantes legales de
 *  los trabajadores en la empresa, se organizará y documentará este registro de
 *  jornada.»
 *
 *  El artículo pide dos cosas y el producto solo hacía una: registraba la
 *  jornada y no había dónde escribir con qué amparo se organizó ese registro.
 *  Es lo primero que una inspección pide después de los propios registros.
 *
 *  Lo que se comprueba aquí es la diferencia que decide si faltaba algo: la
 *  consulta previa solo la exige el tercer camino. Pedirla en los otros dos
 *  sería inventarse un trámite; no pedirla en el tercero es el hueco.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

/** Deja la declaración como estaba: otras pruebas leen esta pantalla. */
async function limpiar(page) {
  await api(page, '/company/record-arrangement/', {
    method: 'PATCH',
    body: { basis: '', reference: '', in_force_since: null, consulted_on: null },
  })
}

test.describe('Ajustes · cómo se organizó el registro', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('declarar un convenio y verlo al volver', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    await limpiar(page)
    await page.reload()

    await page.getByRole('combobox', { name: 'Con qué amparo' }).click()
    await page.getByRole('option', { name: 'Convenio colectivo' }).click()
    await page.getByLabel('Cuál').fill('Convenio del metal de Sevilla, art. 22')
    await page.getByLabel('En vigor desde').fill('2023-05-01')
    await page.getByRole('button', { name: /^Guardar \d+ cambio/ }).click()

    const guardado = await api(page, '/company/record-arrangement/')
    expect(guardado.body.basis).toBe('COLLECTIVE')
    expect(guardado.body.reference).toContain('metal de Sevilla')

    await limpiar(page)
    expect(ruido()).toEqual([])
  })

  test('la decisión de la empresa sin consulta se señala en pantalla', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    await api(page, '/company/record-arrangement/', {
      method: 'PATCH',
      body: { basis: 'EMPLOYER', reference: 'Decisión de dirección de 12/01/2024' },
    })
    await page.reload()

    await expect(page.getByText(/no consta su fecha/i)).toBeVisible()

    // Y al poner la fecha, el aviso se va: un aviso que no se puede apagar
    // haciendo lo correcto es un aviso que se aprende a ignorar.
    await page.getByLabel('Consulta a la representación').fill('2024-01-10')
    await page.getByRole('button', { name: /^Guardar \d+ cambio/ }).click()
    await expect(page.getByText(/no consta su fecha/i)).toHaveCount(0)

    await limpiar(page)
  })

  test('un convenio no pide fecha de consulta', async ({ page }) => {
    // El campo ni se ofrece: un acuerdo **es** la negociación, y preguntar por
    // una consulta previa ahí sugiere un trámite que no existe.
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    await api(page, '/company/record-arrangement/', {
      method: 'PATCH',
      body: { basis: 'COLLECTIVE', reference: 'El que sea' },
    })
    await page.reload()

    await expect(page.getByLabel('Consulta a la representación')).toHaveCount(0)

    await limpiar(page)
  })
})

test.describe('Un operario', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('puede leer con qué amparo se organizó, pero no cambiarlo', async ({ page }) => {
    // No es generosidad: el mismo párrafo pone el registro a disposición de las
    // personas trabajadoras y de sus representantes.
    await irA(page, '/', 'Hola')

    const lectura = await api(page, '/company/record-arrangement/')
    expect(lectura.status).toBe(200)

    const escritura = await api(page, '/company/record-arrangement/', {
      method: 'PATCH',
      body: { basis: 'COLLECTIVE', reference: 'Lo que sea' },
    })
    expect(escritura.status).toBe(403)
  })
})
