/** La asesoría laboral, que lee la gestión sin gestionar.
 *
 *  Su menú solo le ofrece Resumen, Personas, Calendario, Fichajes e Informes,
 *  pero la guarda del panel la dejaba entrar en todas las pantallas con la
 *  dirección escrita. En el Cuadrante y en «Por decidir» la pantalla se cargaba
 *  con peticiones que el servidor le contesta 403. Salió el 29/09, al recorrer
 *  el panel con cada perfil: era el único que ninguna prueba usaba.
 */

import { expect, test } from '@playwright/test'

import { huecosVisibles, vigilarConsola } from './apoyo.js'

const SUYAS = [
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/calendario', 'Calendario del equipo'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/informes', 'Informes'],
]

const AJENAS = [
  ['/panel/departamentos', 'Departamentos'],
  ['/panel/centros', 'Centros'],
  ['/panel/cuadrante', 'Cuadrante'],
  ['/panel/turnos', 'Turnos'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/ajustes', 'Ajustes'],
  ['/panel/aplicaciones', 'Aplicaciones'],
]

/** El nombre con el que la entrada sale en el menú. */
const EN_EL_MENU = {
  '/panel': 'Resumen',
  '/panel/personas': 'Personas',
  '/panel/calendario': 'Calendario',
  '/panel/fichajes': 'Fichajes',
  '/panel/informes': 'Informes',
}

test.describe('Asesoría laboral', () => {
  test.use({ storageState: 'e2e/.sesiones/asesoria.json' })

  test('entra por el resumen y su menú de gestión es el suyo', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/panel$/)

    for (const [ruta] of SUYAS) {
      await expect(page.getByRole('link', { name: EN_EL_MENU[ruta], exact: true })).toBeVisible()
    }
    for (const [, nombre] of AJENAS) {
      await expect(page.getByRole('link', { name: nombre, exact: true })).toHaveCount(0)
    }
    // Y no ficha: de «Mi trabajo» solo le queda la actividad.
    await expect(page.getByRole('link', { name: 'Fichar', exact: true })).toHaveCount(0)
  })

  for (const [ruta, titulo] of SUYAS) {
    test(`${ruta} carga limpia`, async ({ page }) => {
      const ruido = vigilarConsola(page)
      await page.goto(ruta)
      await expect(page.getByRole('heading', { level: 1 })).toContainText(titulo)
      await page.waitForLoadState('networkidle').catch(() => {})
      await page.waitForTimeout(600)

      expect(ruido(), `la consola se quejó en ${ruta}`).toEqual([])
      expect(await huecosVisibles(page)).toEqual([])
    })
  }

  test('las pantallas que no son suyas la devuelven al resumen', async ({ page }) => {
    const ruido = vigilarConsola(page)
    for (const [ruta] of AJENAS) {
      await page.goto(ruta)
      await expect(page, `${ruta} no debería abrirse`).toHaveURL(/\/panel$/)
    }
    expect(ruido()).toEqual([])
  })
})
