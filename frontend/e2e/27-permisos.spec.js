/** El catálogo de permisos: verlo y mejorarlo.
 *
 *  Existía entero ---el modelo, la siembra por país, el endpoint completo, y
 *  hasta `createLeaveType` y `updateLeaveType` exportados en el cliente--- y no
 *  había pantalla. O sea que la mejora que trae un convenio solo se podía
 *  aplicar por API, y la decisión de **copiar** el catálogo en vez de leerlo del
 *  marco legal ---tomada justo para permitir esa mejora--- no servía de nada.
 *
 *  Lo que se edita es cuánto da, no de qué artículo sale: el artículo es de la
 *  ley y cambiarlo mandaría a quien lo lea al sitio equivocado.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

test.describe('Permisos · administración', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('lista el catálogo con su artículo y lo que da', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/permisos', 'Permisos')

    await expect(page.getByText('Matrimonio', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('Art. 37.3.a ET').first()).toBeVisible()

    expect(ruido()).toEqual([])
  })

  test('el buscador filtra por artículo', async ({ page }) => {
    // Buscar por artículo es lo que hace quien viene del convenio en la mano.
    await irA(page, '/panel/permisos', 'Permisos')
    // A que haya lista antes de teclear: filtrar sobre una lista que todavía no
    // ha llegado deja la pantalla en «ningún permiso coincide», y el filtro se
    // aplica sobre lo que hay en memoria. Sin esta espera la prueba pasaba sola
    // y fallaba dentro de la tanda entera, que es cuando la pantalla tarda más.
    await expect(page.getByText('Art. 37.3.a ET').first()).toBeVisible()

    await page.getByPlaceholder('Buscar por nombre o artículo').fill('37.3.b bis')

    await expect(page.getByText('Art. 37.3.b bis ET').first()).toBeVisible()
    await expect(page.getByText('Art. 37.3.a ET')).toHaveCount(0)
  })

  test('subir los días de un permiso y dejarlo como estaba', async ({ page }) => {
    await irA(page, '/panel/permisos', 'Permisos')

    const antes = (await api(page, '/leave-types/?is_active=true')).body.results.find(
      (t) => t.code === 'es.marriage',
    )
    expect(antes, 'hacía falta el permiso de matrimonio').toBeTruthy()
    const original = Number(antes.amount)

    await page.getByPlaceholder('Buscar por nombre o artículo').fill('Matrimonio')
    // Por el nombre del permiso: `name` en Playwright casa por subcadena, así
    // que un «Cambiar» a secas también acertaba al «Cambiar entre claro y
    // oscuro» de la cabecera --- y el clic se iba al tema.
    await page.getByRole('button', { name: 'Cambiar Matrimonio', exact: false }).first().click()

    const dialogo = page.getByRole('dialog')
    // El artículo se enseña y no se edita: es de la ley.
    await expect(dialogo.getByText('Art. 37.3.a ET', { exact: false })).toBeVisible()
    await expect(dialogo.getByLabel('Artículo')).toHaveCount(0)

    await dialogo.getByLabel('Cuánto da').fill(String(original + 3))
    await dialogo.getByRole('button', { name: 'Guardar' }).click()
    await expect(dialogo).toBeHidden()

    const despues = (await api(page, '/leave-types/?is_active=true')).body.results.find(
      (t) => t.code === 'es.marriage',
    )
    expect(Number(despues.amount)).toBe(original + 3)

    // Se deja como estaba: esta base la comparten las demás pruebas, y un tope
    // de matrimonio distinto cambia lo que ve la de consumo de permisos.
    await api(page, `/leave-types/${antes.id}/`, {
      method: 'PATCH',
      body: { amount: original },
    })
  })
})

test.describe('Permisos · un responsable', () => {
  test.use({ storageState: 'e2e/.sesiones/responsable.json' })

  test('los ve pero no los cambia', async ({ page }) => {
    // Saber cuánto da un permiso es lo que hace falta para resolver una
    // solicitud, así que se leen. Cambiarlos es de administración, y la
    // pantalla no ofrece lo que la API va a negar con un 403.
    await irA(page, '/panel/permisos', 'Permisos')

    await expect(page.getByText('Art. 37.3.a ET').first()).toBeVisible()
    await expect(
      page.getByRole('button', { name: /^Cambiar (Matrimonio|Fallecimiento)/ }),
    ).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Cargar los que falten' })).toHaveCount(0)
  })
})
