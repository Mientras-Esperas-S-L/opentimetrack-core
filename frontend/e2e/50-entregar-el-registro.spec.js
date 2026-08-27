/** Mandarle su propio registro a quien ya no trabaja aquí.
 *
 *  El art. 34.9 obliga a conservar su registro cuatro años y el art. 15 del RGPD
 *  le da derecho a pedirlo, y las dos cosas siguen valiendo después del último
 *  día. Lo que se acaba es la relación laboral, no el derecho sobre los datos.
 *
 *  Lo que no se sigue de ahí es que deba conservar la cuenta: reactivársela para
 *  que vea su registro le daría acceso al cuadrante, a sus antiguos compañeros y
 *  a lo que la empresa haya cambiado desde que se fue. Así que se entrega.
 *
 *  Esta prueba mira **solo** lo que el backend no puede mirar: que la opción
 *  existe en la pantalla. La API llevaba la acción y sin el botón sería una pieza
 *  escrita y desconectada, que es el patrón que más veces ha aparecido en esta
 *  auditoría.
 *
 *  Lo demás ---que el enlace no abre sesión, que el de una persona no sirve para
 *  otra, que caduca, que reactivar la cuenta lo mata--- está en
 *  `apps/reports/tests/test_entrega_del_registro.py`, que es donde se puede
 *  comprobar de verdad. Aquí había una segunda prueba que lo intentaba y **se
 *  saltaba sola** cuando no encontraba a nadie de baja: una prueba que se salta
 *  no comprueba nada y se lee como si lo hiciera.
 */

import { expect, test } from '@playwright/test'

import { irA, vigilarConsola } from './apoyo.js'

test.describe('Entregar el registro', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('se le puede enviar su registro a alguien, de alta o de baja', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/personas', 'Personas')

    // La primera fila que tenga menú. No se busca a nadie concreto: la opción
    // tiene que estar para cualquiera, y fijar un nombre haría que la prueba
    // dependiera de los datos de demostración.
    const menus = page.getByRole('button', { name: /Más acciones para/ })
    await expect(menus.first()).toBeVisible()
    await menus.first().click()

    const opcion = page.getByRole('menuitem', { name: 'Enviarle su registro' })
    await expect(opcion).toBeVisible()
    await opcion.click()

    // El aviso dice a qué dirección fue, que es lo que necesita ver quien lo
    // manda: si la dirección está mal, el enlace no llega y nadie se entera.
    await expect(page.getByText(/@/).first()).toBeVisible()

    expect(ruido()).toEqual([])
  })
})
