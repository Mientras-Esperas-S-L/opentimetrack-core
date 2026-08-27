/** Retirar un alta equivocada, desde la pantalla.
 *
 *  Dar de baja no es borrar, y hace bien en no serlo: los fichajes de quien
 *  trabajó aquí viven cuatro años. Pero eso dejaba sin salida el correo mal
 *  escrito y la persona duplicada, que solo se podían desactivar y se quedaban
 *  en la lista para siempre ---en esta misma base de demostración llegaron a ser
 *  946 de 969 personas---.
 *
 *  Lo que se comprueba aquí es lo que el backend no puede: **que la opción esté
 *  donde tiene que estar y solo ahí**. Que se niegue cuando hay algo que
 *  explicar ---incluidas las decisiones que esa persona tomó sobre otras, que es
 *  la parte que no se ve--- está en `apps/users/tests/test_borrar_un_alta_equivocada.py`.
 *
 *  La prueba crea su propia persona y la retira ella misma, así que no deja
 *  sedimento: es, de hecho, la primera que puede limpiar del todo lo que crea.
 */

import { expect, test } from '@playwright/test'

import { api, irA, marca, vigilarConsola } from './apoyo.js'

test.describe('Borrar un alta equivocada', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('se ofrece solo con la cuenta de baja, y retira a quien no dejó rastro', async ({
    page,
  }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/personas', 'Personas')

    const correo = `equivocada-${marca()}@demo.local`
    const alta = await api(page, '/employees/', {
      method: 'POST',
      body: { email: correo, first_name: 'Equi', last_name: 'Vocada', role: 'EMPLOYEE' },
    })
    expect(alta.status, 'no se pudo crear la persona de la prueba').toBe(201)
    const id = alta.body.id

    try {
      // De alta no se ofrece: lo que toca con alguien que trabaja aquí es darle
      // de baja, no borrarle el rastro.
      await page.reload()
      const suya = page.getByRole('row').filter({ hasText: correo })
      await expect(suya).toHaveCount(1)
      await suya.getByRole('button', { name: /Más acciones/ }).click()
      await expect(page.getByRole('menuitem', { name: 'Borrar definitivamente' })).toHaveCount(0)
      await page.keyboard.press('Escape')

      // Se da de baja, que es como se llega a darse cuenta del error.
      const baja = await api(page, `/employees/${id}/`, { method: 'DELETE' })
      expect(baja.status).toBe(200)
      await page.reload()

      // Y hay que pedir ver las bajas: la lista enseña solo a quien está de
      // alta, que es lo correcto ---y es también donde vive esta opción---.
      // Es un `Switch` de MUI, así que su rol es `switch` y no `checkbox`.
      await page.getByRole('switch', { name: /Ver también las bajas/ }).check()

      // Y ahora sí.
      await suya.getByRole('button', { name: /Más acciones/ }).click()
      await page.getByRole('menuitem', { name: 'Borrar definitivamente' }).click()

      // El diálogo dice que no se puede deshacer y cuándo no va a funcionar.
      await expect(page.getByText(/no se puede deshacer/i)).toBeVisible()
      await page.getByRole('button', { name: 'Borrar', exact: true }).click()

      // Primero que el diálogo se haya ido: MUI marca el resto de la página con
      // `aria-hidden` mientras hay uno abierto, así que contar filas antes daba
      // **cero por el diálogo** y la comprobación pasaba sin haber borrado nada.
      await expect(page.getByRole('dialog')).toHaveCount(0)

      await expect(page.getByRole('row').filter({ hasText: correo })).toHaveCount(0)

      // Aquí, y no al final: lo que se vigila es la consola **mientras se usa la
      // pantalla**. Lo que viene después es una comprobación mía que pide un 404
      // a propósito, y el navegador lo apunta como error de red: dejarla dentro
      // hacía que la prueba se sabotease a sí misma.
      expect(ruido()).toEqual([])

      // Y la verdad la tiene el servidor. Con reintento, porque la lista se
      // recarga cuando la petición vuelve.
      await expect
        .poll(async () => (await api(page, `/employees/${id}/`)).status, {
          message: 'la persona sigue existiendo',
        })
        .toBe(404)
    } finally {
      // Por si algo falló a mitad: sin fichajes se puede retirar, y si ya no
      // está el 404 no molesta a nadie.
      await api(page, `/employees/${id}/erase/`, { method: 'POST' }).catch(() => {})
    }
  })
})
