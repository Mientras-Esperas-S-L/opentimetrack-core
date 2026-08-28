/** Las vacaciones que quedan por liquidar cuando el contrato termina.
 *
 *  Las vacaciones no se pagan (art. 38.1 ET), salvo aquí: si el contrato se
 *  extingue ya no hay cuándo disfrutarlas, y los días devengados y no
 *  disfrutados van al finiquito. Hasta ahora había que contarlos a mano mirando
 *  el calendario.
 *
 *  **Lo que esta prueba fija de verdad es el momento.** La cifra se necesita
 *  *mientras* se escribe la fecha de baja, no después de guardarla: quien la
 *  está poniendo quiere saber qué debe antes de darle a guardar. La primera
 *  versión solo sabía contestar por la fecha ya guardada, así que el número
 *  aparecía tras guardar, cerrar la ficha y volver a abrirla ---o sea, cuando
 *  ya no servía para decidir---. Por eso la consulta lleva la fecha del
 *  formulario y no solo la persona.
 */

import { expect, test } from '@playwright/test'

import { api, darDeBajaLasDePrueba, irA, marca } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Lo que esta tanda ha dado de alta, para recogerlo pase lo que pase. */
let pendienteDeRetirar = null

test.afterEach(async ({ page }) => {
  if (!pendienteDeRetirar) return
  const sufijo = pendienteDeRetirar
  pendienteDeRetirar = null
  await darDeBajaLasDePrueba(page, sufijo)
})

async function daDeAlta(page, sufijo) {
  const alta = await api(page, '/employees/', {
    method: 'POST',
    body: {
      first_name: 'Prueba',
      last_name: `Liquidacion ${sufijo}`,
      email: `liquidacion-${sufijo}@demo.local`,
      role: 'EMPLOYEE',
      contract_start: '2026-01-01',
    },
  })
  expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
  return alta.body
}

async function abrirSuFicha(page, sufijo) {
  await page.getByPlaceholder('Buscar por nombre, correo o número').fill(sufijo)
  await expect(page.getByText(`liquidacion-${sufijo}@demo.local`)).toBeVisible()
  await page
    .getByRole('row')
    .filter({ hasText: `Liquidacion ${sufijo}` })
    .getByRole('button', { name: 'Editar' })
    .click()
  return page.getByRole('dialog')
}

const elAviso = (dialogo) => dialogo.getByRole('alert').filter({ hasText: /liquid|finiquito/i })

test.describe('La liquidación de vacaciones', () => {
  test('sin fecha de fin no se dice nada', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo)
    await page.reload()

    const dialogo = await abrirSuFicha(page, sufijo)
    await expect(dialogo.getByLabel('Fin del contrato')).toHaveValue('')

    // **El contraste.** Mientras el contrato siga no hay nada que liquidar, y
    // decirle «te quedan 11 por liquidar» a quien está en plantilla es decirle
    // que se va.
    await expect(elAviso(dialogo)).toHaveCount(0)
  })

  test('al escribir la fecha aparece el número, sin guardar', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo)
    await page.reload()

    const dialogo = await abrirSuFicha(page, sufijo)
    await dialogo.getByLabel('Fin del contrato').fill('2026-06-30')

    // Sin tocar «Guardar»: es el momento en que la cifra sirve para decidir.
    await expect(elAviso(dialogo)).toBeVisible()
    await expect(elAviso(dialogo)).toContainText('38.1')
  })

  test('cambiar la fecha cambia el número', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo)
    await page.reload()

    const dialogo = await abrirSuFicha(page, sufijo)
    const campo = dialogo.getByLabel('Fin del contrato')

    await campo.fill('2026-06-30')
    await expect(elAviso(dialogo)).toBeVisible()
    const medioAno = await elAviso(dialogo).innerText()

    await campo.fill('2026-12-31')
    // El año entero devenga más que medio, así que el texto tiene que cambiar.
    // Si la consulta ignorara la fecha y solo mirase a la persona, este aviso
    // se quedaría clavado en el primer número y nadie lo notaría.
    await expect(elAviso(dialogo)).not.toHaveText(medioAno)
  })
})
