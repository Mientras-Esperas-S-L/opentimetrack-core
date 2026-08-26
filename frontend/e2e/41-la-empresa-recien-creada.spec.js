/** Una empresa el día que se da de alta: sin nadie, sin turnos, sin nada.
 *
 *  Es la primera pantalla que ve un cliente y la que nadie mira, porque la
 *  semilla siempre trae datos. Recorriéndola aparecieron dos cosas: los vacíos
 *  están cuidados ---cada pantalla dice qué falta y dónde crearlo--- y **la
 *  concordancia con uno no**. «1 personas de alta» solo sale cuando hay
 *  exactamente una, o sea justo aquí.
 *
 *  La prueba no crea la empresa: comprueba el helper que decide la palabra, que
 *  es donde estaba el fallo y donde puede volver. Montar un inquilino nuevo
 *  desde la suite exigiría un endpoint de alta que el producto no tiene ---solo
 *  se dan de alta por API con credencial de plataforma--- y la deuda de dejarlo
 *  ahí para siempre.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

test.describe('Cuando hay uno de algo', () => {
  test('la palabra concuerda', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    const dicho = await page.evaluate(async () => {
      const { plural } = await import('/src/components/format.js')
      return {
        una: `1 ${plural(1, 'persona de alta', 'personas de alta')}`,
        varias: `4 ${plural(4, 'persona de alta', 'personas de alta')}`,
        ninguna: `0 ${plural(0, 'día', 'días')}`,
        texto: `2 ${plural('2', 'día', 'días')}`,
      }
    })

    expect(dicho.una).toBe('1 persona de alta')
    expect(dicho.varias).toBe('4 personas de alta')
    // Cero va en plural en castellano, y un número que llega como texto también
    // tiene que contar: los recuentos vienen de la API y no siempre son number.
    expect(dicho.ninguna).toBe('0 días')
    expect(dicho.texto).toBe('2 días')
  })

  test('y ninguna pantalla dice «1 personas»', async ({ page }) => {
    for (const [ruta, titulo] of [
      ['/panel', 'Resumen'],
      ['/panel/personas', 'Personas'],
      ['/panel/departamentos', 'Departamentos'],
      ['/panel/centros', 'Centros de trabajo'],
      ['/panel/decisiones', 'Por decidir'],
      ['/panel/ajustes', 'Ajustes de la empresa'],
    ]) {
      await irA(page, ruta, titulo)
      const texto = await page.locator('main').innerText()
      expect(
        texto.replace(/\s+/g, ' '),
        `${ruta} dice «1» con un sustantivo en plural`,
      ).not.toMatch(/\b1 (personas|días|horas|turnos|permisos|centros|departamentos|solicitudes)\b/)
    }
  })
})
