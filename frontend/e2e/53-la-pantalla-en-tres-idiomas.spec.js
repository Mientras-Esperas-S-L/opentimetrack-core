/** La interfaz en catalán y gallego, no solo el servidor.
 *
 *  El mecanismo estaba montado desde antes ---i18next, con **la cadena castellana
 *  como clave**, así que lo que falta cae al castellano igual que en el backend---
 *  y lo usaban dos pantallas de treinta y ocho: el catálogo tenía 23 claves y eran
 *  las del menú. Una empresa catalana veía el menú en catalán y las pantallas en
 *  castellano.
 *
 *  Esta prueba recorre lo traducido en cada idioma. Crece con el catálogo: al
 *  envolver una pantalla nueva se añade aquí su texto más característico, y con
 *  eso la traducción deja de poder desaparecer sin que nadie se entere.
 *
 *  Se elige texto **de la propia pantalla**, no del menú: el menú ya estaba
 *  traducido y comprobarlo daría verde sin haber traducido nada más.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Qué se espera ver en cada idioma, por pantalla. */
const PANTALLAS = [
  {
    ruta: '/panel/personas',
    titulo: { es: 'Personas', ca: 'Persones', gl: 'Persoas' },
    // Un texto largo de la propia pantalla, que no sale en ningún menú.
    propio: {
      es: 'Dar de baja no borra nada',
      ca: 'Donar de baixa no esborra res',
      gl: 'Dar de baixa non borra nada',
    },
    // Y un rótulo de control, que es la otra mitad de lo que se traduce.
    control: {
      es: 'Ver también las bajas',
      ca: 'Veure també les baixes',
      gl: 'Ver tamén as baixas',
    },
  },
]

test.describe('La pantalla, en los tres idiomas', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  for (const idioma of ['ca', 'gl', 'es']) {
    test(`en ${idioma}`, async ({ page }) => {
      // Se pide desde la sesión, que es de donde lo saca `ConIdioma`, y se
      // devuelve al final: dejar el idioma cambiado rompería las demás pruebas
      // en un sitio donde nadie miraría.
      // Hay que estar en la aplicación antes de usar `api`: lee el testigo de
      // `localStorage`, y en `about:blank` el navegador ni deja mirarlo.
      await page.goto('/')
      const antes = (await api(page, '/auth/me/')).body?.locale ?? ''
      try {
        const puesto = await api(page, '/auth/me/', {
          method: 'PATCH',
          body: { locale: idioma === 'es' ? '' : idioma },
        })
        expect(puesto.status, 'no se pudo cambiar el idioma').toBe(200)

        for (const { ruta, titulo, propio, control } of PANTALLAS) {
          await irA(page, ruta, titulo[idioma])
          await expect(page.getByText(new RegExp(propio[idioma], 'i'))).toBeVisible()
          await expect(page.getByRole('switch', { name: control[idioma] })).toBeVisible()

          // Y que de verdad ha cambiado: en catalán o gallego, el texto
          // castellano no puede seguir en pantalla. Sin esto la prueba pasaría
          // con el catálogo vacío, porque la clave **es** el castellano.
          if (idioma !== 'es') {
            await expect(page.getByText(propio.es, { exact: false })).toHaveCount(0)
          }
        }
      } finally {
        await api(page, '/auth/me/', { method: 'PATCH', body: { locale: antes } })
      }
    })
  }
})
