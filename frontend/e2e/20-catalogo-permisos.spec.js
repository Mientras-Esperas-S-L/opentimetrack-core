/** Que el catálogo de permisos exista y se vea.
 *
 *  El fallo: una empresa recién dada de alta se quedaba con **cero** permisos.
 *  El desplegable de «Qué pides» salía vacío y nadie podía pedir un matrimonio,
 *  un fallecimiento ni una hospitalización --- todo el art. 37.3 fuera del
 *  producto. Y no había forma de arreglarlo desde dentro: el endpoint que
 *  siembra el catálogo existía y no lo llamaba ninguna pantalla.
 *
 *  Aquí se comprueban las dos mitades: que Ajustes dice cuántos hay y ofrece
 *  traerlos, y que el desplegable **explica** el vacío en vez de quedarse mudo.
 *  Un desplegable sin opciones no dice nada, y lo que callaba era esto.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

test.describe('Ajustes · el catálogo de permisos', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('dice cuántos permisos hay y deja cargar los que falten', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const cuantos = (await api(page, '/leave-types/?is_active=true')).body
    const total = (cuantos.results ?? cuantos).length
    expect(total, 'la empresa de demostración debería tener catálogo').toBeGreaterThan(0)

    await expect(page.getByText(`${total} permisos configurados.`)).toBeVisible()

    // Cargarlo otra vez no toca nada: es idempotente, y lo dice.
    await page.getByRole('button', { name: 'Cargar el catálogo del país' }).click()
    await expect(page.getByText(/no faltaba ninguno/i)).toBeVisible()

    expect(ruido()).toEqual([])
  })

  test('el catálogo trae los permisos del art. 37.3 con su artículo', async ({ page }) => {
    // Las letras importan tanto como los números: el RDL 5/2023 partió la
    // antigua letra b en dos y sacó el fallecimiento a «b bis» sin correr las
    // demás. Citar mal manda a quien lo lea al artículo equivocado, y ahí leería
    // cinco días donde tiene dos.
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    const respuesta = await api(page, '/leave-types/?is_active=true')
    const filas = respuesta.body.results ?? respuesta.body

    const porBase = Object.fromEntries(filas.map((f) => [f.basis, f]))
    expect(Object.keys(porBase)).toEqual(expect.arrayContaining(['Art. 37.3.a ET', 'Art. 37.3.b ET']))
    expect(porBase['Art. 37.3.b bis ET'], 'falta el fallecimiento, o cita otra letra').toBeTruthy()
  })

  test('«Qué pides» ofrece los permisos, no una lista vacía', async ({ page }) => {
    await irA(page, '/panel/calendario', 'Calendario del equipo')
    await page.getByRole('button', { name: 'Registrar ausencia' }).click()

    const dialogo = page.getByRole('dialog')
    await dialogo.getByRole('combobox', { name: /Qué pides/ }).click()

    const opciones = page.getByRole('option')
    await expect(opciones.first()).toBeVisible()
    expect(await opciones.count()).toBeGreaterThan(5)

    // Y sin el aviso de vacío, que es lo que sale cuando no hay catálogo.
    await expect(page.getByText(/no tiene permisos configurados/i)).toHaveCount(0)
  })
})
