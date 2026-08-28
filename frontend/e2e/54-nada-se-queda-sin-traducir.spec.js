/** El guard del catálogo completo, dentro de la tanda.
 *
 *  Los dos scripts de `scripts/` se pueden llamar a mano, y a mano no los llama
 *  nadie. Aquí corren con el resto, sin navegador ---no hacen falta--- y en
 *  medio segundo.
 *
 *  Lo que vigilan, y por qué hace falta ahora y no antes: mientras la interfaz
 *  iba a medias, lo no traducido caía al castellano y eso era **correcto**,
 *  porque la clave es la cadena castellana. Terminada la conversión, esa misma
 *  propiedad se vuelve el agujero: una pantalla nueva escrita sin `t()` se lee
 *  perfectamente en castellano y no lo delata nada hasta que alguien mira la
 *  aplicación en catalán.
 *
 *  Esta prueba **sustituye** a `36-interfaz-traducida`, que comprobaba que lo
 *  no traducido cayera al castellano y no al inglés. Aquella tenía una muestra
 *  de pantalla sin traducir que se movió dos veces ---Personas, Informes--- y
 *  al terminar Turnos se quedó sin caso. Lo dejaba dicho en su propio texto:
 *  «cuando no quede ninguna sin traducir, esta prueba se borra».
 */

import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'

const correr = (script) => {
  try {
    return { salida: 0, texto: execFileSync('node', [script], { encoding: 'utf8' }) }
  } catch (fallo) {
    return { salida: fallo.status, texto: `${fallo.stdout ?? ''}${fallo.stderr ?? ''}` }
  }
}

test.describe('Nada se queda sin traducir', () => {
  test('ninguna cadena visible se ha quedado fuera del catálogo', () => {
    const { salida, texto } = correr('scripts/comprobar-lo-visible.mjs')
    expect(salida, texto).toBe(0)
    // Y que de verdad ha mirado el proyecto: sin esto, un lector roto daría
    // cero pendientes y se leería como «está todo bien».
    expect(texto).toMatch(/\d{3,} cadenas traducidas/)
  })

  test('ninguna traducción se ha quedado huérfana', () => {
    const { salida, texto } = correr('scripts/comprobar-catalogos.mjs')
    expect(salida, texto).toBe(0)
  })
})
