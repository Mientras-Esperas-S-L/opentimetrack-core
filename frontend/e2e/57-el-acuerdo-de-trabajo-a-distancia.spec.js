/** El acuerdo de trabajo a distancia (Ley 10/2021), desde la pantalla.
 *
 *  La ley se aplica desde el 30 % de la jornada a distancia en tres meses, y a
 *  partir de ahí exige acuerdo por escrito y **previo** al inicio (art. 5.1). El
 *  cálculo del umbral y los avisos llegaron el 28/08; esto es lo que faltaba
 *  para poder registrar el acuerdo sin abrir un shell de Django.
 *
 *  Dos decisiones de esta pantalla que el servidor no puede tomar, y por eso se
 *  comprueban desde fuera:
 *
 *  1. **Se ofrece a todo el mundo**, no solo a quien ya teletrabaja. Un acuerdo
 *     se firma antes de empezar, así que exigir que ya conste trabajo a
 *     distancia obligaría a incumplir el artículo para poder cumplirlo.
 *  2. **Firmar tarde se avisa y se guarda.** Es un incumplimiento que ya ha
 *     ocurrido: negarse a registrarlo no lo deshace, deja el registro sin rastro
 *     de un acuerdo que existe, y empuja a escribir una fecha falsa para que el
 *     formulario pase.
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
      last_name: `Distancia ${sufijo}`,
      email: `distancia-${sufijo}@demo.local`,
      role: 'EMPLOYEE',
    },
  })
  expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
  return alta.body
}

async function abrirSuAcuerdo(page, sufijo) {
  await page.getByPlaceholder('Buscar por nombre, correo o número').fill(sufijo)
  await expect(page.getByText(`distancia-${sufijo}@demo.local`)).toBeVisible()
  await page.getByRole('button', { name: `Más acciones para Prueba Distancia ${sufijo}` }).click()
  await page.getByRole('menuitem', { name: 'Trabajo a distancia' }).click()
  return page.getByRole('dialog')
}

test.describe('El acuerdo de trabajo a distancia', () => {
  test('se registra uno y queda con sus fechas', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    const persona = await daDeAlta(page, sufijo)

    await page.reload()
    const dialogo = await abrirSuAcuerdo(page, sufijo)
    await expect(
      dialogo.getByText('No consta ningún acuerdo de trabajo a distancia.'),
    ).toBeVisible()

    await dialogo.getByLabel('Firmado').fill('2027-01-15')
    await dialogo.getByLabel('Empieza').fill('2027-02-01')
    await dialogo.getByLabel('% pactado').fill('40')
    await dialogo.getByRole('button', { name: 'Añadir' }).click()

    await expect(dialogo.getByText(/Desde el 01 feb 2027, sin fecha de fin/)).toBeVisible()
    await expect(dialogo.getByText(/40 % pactado/)).toBeVisible()

    // Y el servidor lo tiene, que es lo que apaga el aviso del cuadrante.
    const guardados = await api(page, `/remote-work-agreements/?employee=${persona.id}`)
    expect(guardados.body?.results ?? []).toHaveLength(1)
    expect(guardados.body.results[0].signed_late).toBe(false)

    await page.keyboard.press('Escape')
  })

  test('firmarlo tarde avisa antes de guardar, y se guarda igual', async ({ page }) => {
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    const persona = await daDeAlta(page, sufijo)

    await page.reload()
    const dialogo = await abrirSuAcuerdo(page, sufijo)

    // El aviso sale **mientras se escribe**: decirlo cuando ya está guardado es
    // tarde para quien todavía puede mirar la fecha del papel.
    await dialogo.getByLabel('Firmado').fill('2027-03-10')
    await dialogo.getByLabel('Empieza').fill('2027-02-01')
    await expect(dialogo.getByText(/La firma es posterior al inicio/)).toBeVisible()

    await dialogo.getByRole('button', { name: 'Añadir' }).click()

    // Se guarda, y queda señalado.
    await expect(dialogo.getByText(/después de haber empezado/)).toBeVisible()
    const guardados = await api(page, `/remote-work-agreements/?employee=${persona.id}`)
    expect(guardados.body.results[0].signed_late).toBe(true)

    await page.keyboard.press('Escape')
  })

  test('se ofrece a todo el mundo, no solo a quien ya teletrabaja', async ({ page }) => {
    /* El contraste de la decisión de pantalla. Las temporadas del fijo
       discontinuo se ofrecen **solo** a quien lo es, y el atajo evidente aquí
       habría sido copiar ese criterio y pedir que ya conste trabajo a
       distancia. Sería justo al revés de lo que dice el art. 5.1. */
    const sufijo = marca()
    pendienteDeRetirar = sufijo
    await irA(page, '/panel/personas', 'Personas')
    await daDeAlta(page, sufijo)

    await page.reload()
    await page.getByPlaceholder('Buscar por nombre, correo o número').fill(sufijo)
    await expect(page.getByText(`distancia-${sufijo}@demo.local`)).toBeVisible()
    await page.getByRole('button', { name: `Más acciones para Prueba Distancia ${sufijo}` }).click()

    // Recién dada de alta, sin un solo fichaje ni presencial ni a distancia.
    await expect(page.getByRole('menuitem', { name: 'Trabajo a distancia' })).toBeVisible()
    // Y las temporadas no, que es la que sí depende del contrato: si esta
    // aserción cayera, la de arriba dejaría de significar nada.
    await expect(page.getByRole('menuitem', { name: 'Temporadas' })).toHaveCount(0)

    await page.keyboard.press('Escape')
  })
})
