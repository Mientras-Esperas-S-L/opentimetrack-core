/** El paginador de «Por decidir».
 *
 *  Las colas de correcciones llegan de cincuenta en cincuenta. Antes había un
 *  aviso que decía «se muestran 50 de 137. Usa los filtros de arriba para llegar
 *  al resto» --- y **los filtros son en cliente sobre lo ya cargado**, así que
 *  seguir ese consejo no podía funcionar: a las 87 restantes no se llegaba desde
 *  ninguna parte.
 *
 *  Se prueba con la respuesta interceptada y no con datos de verdad: hacen falta
 *  más de cincuenta correcciones pendientes para verlo, y crearlas en la base de
 *  desarrollo estropea las cuentas de media docena de pruebas más. Lo que se
 *  comprueba aquí es la pantalla, y para eso el servidor de mentira vale.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

/** Una página de correcciones inventada, con `count` grande. */
function paginaDe(cuantas, total, desde = 0) {
  return {
    count: total,
    results: Array.from({ length: cuantas }, (_, i) => ({
      id: `00000000-0000-0000-0000-${String(desde + i).padStart(12, '0')}`,
      employee: '00000000-0000-0000-0000-000000000001',
      employee_name: `Persona ${desde + i}`,
      kind: 'ADD',
      kind_display: 'Añadir un fichaje que falta',
      status: 'PENDING',
      status_display: 'Pendiente',
      reason: `Motivo ${desde + i}`,
      proposed_timestamp: '2026-08-10T08:00:00Z',
      proposed_type: 'IN',
      created_at: '2026-08-10T09:00:00Z',
      target: null,
      target_detail: null,
      result_detail: null,
    })),
  }
}

test.describe('Por decidir · paginar', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('dice cuántas hay y deja pasar a la siguiente página', async ({ page }) => {
    const pedidas = []
    await page.route('**/api/corrections/**', async (ruta) => {
      const url = new URL(ruta.request().url())
      if (url.searchParams.get('status') !== 'PENDING') return ruta.continue()
      const pagina = Number(url.searchParams.get('page') ?? 1)
      pedidas.push(pagina)
      return ruta.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          pagina === 1 ? paginaDe(50, 137) : paginaDe(50, 137, 50),
        ),
      })
    })

    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /Fichajes/ }).click()

    await expect(page.getByText('1–50 de 137 correcciones')).toBeVisible()
    // Y la primera fila es de la primera página.
    await expect(page.getByText('Persona 0')).toBeVisible()

    // Por el texto dentro de la navegación, no por el nombre accesible: MUI le
    // pone un `aria-label` traducido ---«Ir a la página 2»--- que tapa el «2»
    // que se ve. Atar la prueba a ese rótulo sería atarla al idioma.
    await page.getByRole('navigation').getByText('2', { exact: true }).click()

    await expect(page.getByText('51–100 de 137 correcciones')).toBeVisible()
    await expect(page.getByText('Persona 50')).toBeVisible()
    expect(pedidas, 'no llegó a pedir la segunda página').toContain(2)
  })

  test('con una sola página no aparece el paginador', async ({ page }) => {
    // El contraste: un paginador sobre siete filas es ruido. Lo que se enseña
    // entonces es solo cuántas hay.
    await page.route('**/api/corrections/**', async (ruta) => {
      const url = new URL(ruta.request().url())
      if (url.searchParams.get('status') !== 'PENDING') return ruta.continue()
      return ruta.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(paginaDe(7, 7)),
      })
    })

    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /Fichajes/ }).click()

    await expect(page.getByText('7 correcciones')).toBeVisible()
    await expect(page.getByRole('navigation')).toHaveCount(0)
  })
})
