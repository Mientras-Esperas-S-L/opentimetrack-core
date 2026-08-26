/** Gestionar desde un teléfono.
 *
 *  La barra lateral solo existe de `md` para arriba y la de abajo lleva a las
 *  pantallas de la persona más una entrada a «Resumen». Sin un menú, diez de las
 *  doce pantallas de gestión no tenían por dónde llegarse: las rutas
 *  funcionaban si se tecleaban, y desde el Resumen solo se enlazan dos.
 *
 *  Quien lo sufre es el perfil que más usa el teléfono. Un responsable un lunes
 *  no podía abrir «Por decidir», ni el cuadrante, ni los informes.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

const MOVIL = { width: 390, height: 844 }

// El rótulo del menú y el título de la pantalla **no** son el mismo texto en
// tres de ellas, así que van por separado en vez de darlos por iguales.
const GESTION = [
  { ruta: '/panel', menu: 'Resumen', titulo: 'Resumen' },
  { ruta: '/panel/personas', menu: 'Personas', titulo: 'Personas' },
  { ruta: '/panel/departamentos', menu: 'Departamentos', titulo: 'Departamentos' },
  { ruta: '/panel/centros', menu: 'Centros', titulo: 'Centros de trabajo' },
  { ruta: '/panel/calendario', menu: 'Calendario', titulo: 'Calendario del equipo' },
  { ruta: '/panel/cuadrante', menu: 'Cuadrante', titulo: 'Cuadrante' },
  { ruta: '/panel/turnos', menu: 'Turnos', titulo: 'Turnos' },
  { ruta: '/panel/permisos', menu: 'Permisos', titulo: 'Permisos' },
  { ruta: '/panel/fichajes', menu: 'Fichajes', titulo: 'Fichajes' },
  { ruta: '/panel/decisiones', menu: 'Por decidir', titulo: 'Por decidir' },
  { ruta: '/panel/informes', menu: 'Informes', titulo: 'Informes' },
  { ruta: '/panel/aplicaciones', menu: 'Aplicaciones', titulo: 'Aplicaciones' },
  { ruta: '/panel/ajustes', menu: 'Ajustes', titulo: 'Ajustes de la empresa' },
]

test.use({ storageState: 'e2e/.sesiones/admin.json', viewport: MOVIL })

test.describe('Desde el móvil', () => {
  test('todas las pantallas de gestión se alcanzan por el menú', async ({ page }) => {
    await irA(page, '/panel/informes', 'Informes')

    const abrir = page.getByRole('button', { name: 'Abrir el menú' })
    await expect(abrir).toBeVisible()

    for (const { ruta, menu, titulo } of GESTION) {
      await abrir.click()
      const enlace = page.getByRole('link', { name: menu, exact: true })
      await expect(enlace, `falta ${menu} en el menú`).toBeVisible()
      await enlace.click()
      await expect(page.getByRole('heading', { name: titulo, level: 1 })).toBeVisible()
      expect(page.url(), `${menu} no llevó a su ruta`).toContain(ruta)
      // Elegir una pantalla cierra el cajón: es para lo que `NavSection`
      // aceptaba un `onNavigate` desde el principio.
      await expect(abrir).toBeVisible()
    }
  })

  test('el menú no se le ofrece a quien no gestiona', async ({ browser }) => {
    const suyo = await browser.newContext({
      storageState: 'e2e/.sesiones/operario.json',
      viewport: MOVIL,
    })
    const suPagina = await suyo.newPage()
    await suPagina.goto('/')
    await expect(suPagina.getByRole('heading', { level: 1 })).toBeVisible()

    await expect(suPagina.getByRole('button', { name: 'Abrir el menú' })).toHaveCount(0)
    await suyo.close()
  })
})

test.describe('La cabecera dice dónde estás', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('y no se queda en «Resumen» en todas las pantallas', async ({ page }) => {
    // `/panel` es prefijo de todas las demás, así que un `find` sin respetar
    // `end` devolvía siempre la primera que casa, que es «Resumen». La cabecera
    // decía «Resumen» estando en Informes, en el Cuadrante o en Ajustes.
    for (const { ruta, menu, titulo } of GESTION) {
      await irA(page, ruta, titulo)
      // La cabecera lleva el rótulo del menú, que es el nombre corto.
      await expect(
        page.getByRole('banner').getByText(menu, { exact: true }),
        `la cabecera no dice «${menu}» en ${ruta}`,
      ).toBeVisible()
    }
  })
})
