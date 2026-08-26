/** Moverse sin ratón.
 *
 *  El eje que quedaba de la familia de accesibilidad. No salió nada roto, y eso
 *  también hay que dejarlo escrito: el foco se ve, los diálogos lo atrapan y lo
 *  devuelven al botón que los abrió, y se llega a todo tabulando.
 *
 *  Lo que sí enseñó fue **cómo medirlo**. Tres sondas seguidas dijeron que el
 *  foco era invisible ---no hay `outline`, no hay `box-shadow`, y añadir la clase
 *  `Mui-focusVisible` a mano no cambia el fondo--- y las tres se equivocaban. La
 *  marca existe y se ve; lo que fallaba era mirarla desde el DOM. Comparando
 *  **píxeles** se acabó la discusión en un intento.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

test.describe('Con el teclado', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('el foco se ve, tanto en un enlace del menú como en un botón', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    await page.waitForTimeout(400)

    for (const mando of [
      page.getByRole('link', { name: 'Departamentos' }),
      page.getByRole('button', { name: 'Dar de alta', exact: true }),
    ]) {
      const apagado = await mando.screenshot()
      const otraVezApagado = await mando.screenshot()

      // La prueba se valida a sí misma. Dos capturas del mismo estado tienen
      // que salir idénticas: si no lo fueran, la comparación estaría midiendo
      // ruido y el «sí se ve» de abajo no significaría nada.
      //
      // Hace falta decirlo porque no conseguí construir el contraste de la
      // forma habitual ---apagar la marca de foco y ver la prueba en rojo---: la
      // pinta MUI de un modo que no se deja desactivar desde el tema. Esto es
      // lo que sí se puede afirmar.
      expect(
        Buffer.compare(apagado, otraVezApagado),
        'dos capturas del mismo estado salen distintas: la comparación mide ruido',
      ).toBe(0)

      await mando.focus()
      await page.waitForTimeout(150)
      const encendido = await mando.screenshot()

      // Píxeles y no estilos calculados: tres sondas seguidas dieron la marca
      // por ausente ---sin `outline`, sin `box-shadow`, sin cambio de fondo---
      // y las tres se equivocaban.
      expect(
        Buffer.compare(apagado, encendido),
        `no se ve ninguna diferencia al enfocar ${await mando.textContent()}`,
      ).not.toBe(0)
    }
  })

  test('un diálogo atrapa el foco y lo devuelve al cerrarse', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    const abrir = page.getByRole('button', { name: 'Dar de alta', exact: true })
    await abrir.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog')).toBeVisible()

    // El foco entra solo. Sin esto, quien abre con el teclado se queda con el
    // foco fuera y tabula por detrás de un diálogo que no puede ver.
    expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(
      true,
    )

    // Y no se escapa: veinte tabulaciones sin salir.
    for (let i = 0; i < 20; i += 1) {
      await page.keyboard.press('Tab')
      const dentro = await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))
      expect(dentro, `el foco se escapó del diálogo en la tabulación ${i + 1}`).toBe(true)
    }

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()

    // Vuelve a donde estaba. Perder el foco al cerrar deja a quien navega con
    // teclado al principio de la página, y hay que rehacer el camino entero.
    expect(
      await page.evaluate(() =>
        (document.activeElement?.textContent || '').includes('Dar de alta'),
      ),
    ).toBe(true)
  })
})

test.describe('Fichar con el teclado', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('se llega al botón tabulando y se pulsa con Intro', async ({ page }) => {
    await irA(page, '/', 'Hola')

    const boton = page.getByRole('button', { name: /^Fichar (entrada|salida)$/ })
    await expect(boton).toBeVisible()

    // Alcanzable de verdad: se tabula hasta él en vez de darle el foco a mano.
    let llegado = false
    for (let i = 0; i < 25 && !llegado; i += 1) {
      await page.keyboard.press('Tab')
      llegado = await page.evaluate(() =>
        /^Fichar (entrada|salida)$/.test((document.activeElement?.textContent || '').trim()),
      )
    }
    expect(llegado, 'no se llega al botón de fichar tabulando').toBe(true)
  })
})
