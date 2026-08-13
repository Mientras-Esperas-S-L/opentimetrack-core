/** El alta de personas, que es el formulario más largo del producto.
 *
 *  Y el que más consecuencias tiene: cada campo de ahí cambia cómo se mide la
 *  jornada de alguien. Un centro decide su zona horaria y sus festivos; la
 *  fecha de nacimiento decide si se le aplican las protecciones de menores;
 *  las fechas de contrato deciden cuántas vacaciones le tocan.
 */

import { expect, test } from '@playwright/test'

import { api, darDeBajaLasDePrueba, irA, marca } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Rellena lo mínimo obligatorio y devuelve el correo usado. */
async function rellenarMinimo(page, sufijo) {
  const correo = `prueba.${sufijo}@demo.local`
  await page.getByLabel(/^Nombre/).fill('Prueba')
  await page.getByLabel(/^Apellidos/).fill(`De Playwright ${sufijo}`)
  await page
    .getByLabel(/^Correo/)
    .first()
    .fill(correo)
  return correo
}

test.describe('Alta de personas', () => {
  test('el formulario abre con lo obligatorio marcado y nada relleno', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    await page.getByRole('button', { name: 'Dar de alta' }).click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo.getByRole('heading', { name: 'Dar de alta' })).toBeVisible()
    await expect(dialogo.getByLabel(/^Nombre/)).toHaveValue('')
    // El perfil arranca en lo menos peligroso, no en administración.
    await expect(dialogo.getByLabel(/^Perfil/)).toContainText('Persona trabajadora')
  })

  test('da de alta y aparece en la lista', async ({ page }) => {
    const sufijo = marca()
    // Lo que la prueba crea, la prueba lo recoge.
    test.info().annotations.push({ type: 'limpia', description: sufijo })
    await irA(page, '/panel/personas', 'Personas')
    await page.getByRole('button', { name: 'Dar de alta' }).click()
    const correo = await rellenarMinimo(page, sufijo)
    await page.getByRole('button', { name: 'Guardar' }).click()

    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByPlaceholder('Buscar por nombre, correo o número').fill(sufijo)
    await expect(page.getByText(correo)).toBeVisible()

    await darDeBajaLasDePrueba(page, sufijo)
  })

  test('el mismo correo dos veces lo rechaza, y dice por qué', async ({ page }) => {
    const sufijo = marca()
    await irA(page, '/panel/personas', 'Personas')

    for (const vuelta of [1, 2]) {
      await page.getByRole('button', { name: 'Dar de alta' }).click()
      await rellenarMinimo(page, sufijo)
      await page.getByRole('button', { name: 'Guardar' }).click()

      if (vuelta === 1) {
        await expect(page.getByRole('dialog')).toHaveCount(0)
      } else {
        // Sigue abierto, con el motivo concreto y no un «datos no válidos».
        const dialogo = page.getByRole('dialog')
        await expect(dialogo).toBeVisible()
        await expect(dialogo.getByRole('alert')).toBeVisible()
        await page.getByRole('button', { name: 'Cancelar' }).click()
      }
    }

    await darDeBajaLasDePrueba(page, sufijo)
  })

  test('el diálogo no arrastra lo del anterior al reabrirlo', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    await page.getByRole('button', { name: 'Dar de alta' }).click()
    await page.getByLabel(/^Nombre/).fill('Se queda por ahí')
    await page.getByRole('button', { name: 'Cancelar' }).click()

    await page.getByRole('button', { name: 'Dar de alta' }).click()
    await expect(page.getByRole('dialog').getByLabel(/^Nombre/)).toHaveValue('')
  })

  test('dar de baja no borra: la persona sigue con sus registros', async ({ page }) => {
    const sufijo = marca()
    await irA(page, '/panel/personas', 'Personas')
    await page.getByRole('button', { name: 'Dar de alta' }).click()
    const correo = await rellenarMinimo(page, sufijo)
    await page.getByRole('button', { name: 'Guardar' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)

    // Se da de baja por la API: el menú de la fila es un detalle de la
    // interfaz y lo que aquí importa es qué le pasa al dato.
    const gente = await api(page, `/employees/?search=${sufijo}`)
    const persona = gente.body.results[0]
    const baja = await api(page, `/employees/${persona.id}/`, { method: 'DELETE' })
    expect(baja.status).toBeLessThan(300)

    const activos = await api(page, `/employees/?search=${sufijo}&is_active=true`)
    expect(activos.body.count).toBe(0)
    const todos = await api(page, `/employees/?search=${sufijo}`)
    expect(todos.body.count).toBe(1)
    expect(todos.body.results[0].email).toBe(correo)
  })

  test('«ver también las bajas» las trae de vuelta a la lista', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    const antes = await page.getByRole('row').count()
    await page.getByLabel('Ver también las bajas').click()
    await expect.poll(() => page.getByRole('row').count()).toBeGreaterThan(antes)
  })
})

test.describe('Reglas de negocio del alta', () => {
  test('un responsable no puede dar de alta a nadie', async ({ browser }) => {
    const contexto = await browser.newContext({
      storageState: 'e2e/.sesiones/responsable.json',
    })
    const page = await contexto.newPage()
    await page.goto('/panel/personas')

    const intento = await api(page, '/employees/', {
      method: 'POST',
      body: { email: `colado.${marca()}@demo.local`, first_name: 'Colado', last_name: 'Por Ahí' },
    })
    expect(intento.status).toBe(403)
    await contexto.close()
  })

  test('el número de empleado no se puede repetir', async ({ page }) => {
    await page.goto('/panel/personas')
    const gente = await api(page, '/employees/')
    const yaUsado = gente.body.results.find((p) => p.employee_id)?.employee_id
    test.skip(!yaUsado, 'la semilla no trae números de empleado')

    const intento = await api(page, '/employees/', {
      method: 'POST',
      body: {
        email: `repe.${marca()}@demo.local`,
        first_name: 'Repe',
        last_name: 'Tido',
        employee_id: yaUsado,
      },
    })
    expect(intento.status).toBe(400)
  })
})
