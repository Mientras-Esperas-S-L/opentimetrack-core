/** Que cada mando de la pantalla se pueda nombrar.
 *
 *  Esta prueba nació de un fallo tonto y revelador: la prueba de la pantalla de
 *  permisos clicaba el conmutador de tema en vez del botón que buscaba, porque
 *  ambos se llamaban «Cambiar» y el localizador casa por subcadena. Lo que
 *  confunde a un localizador confunde igual a quien navega con lector de
 *  pantalla --- que oye una lista de botones y nada más.
 *
 *  Barriéndolo entero salieron cuatro pantallas con el mismo problema: 19
 *  «Editar» en Personas, 7 en Turnos, 6 en Departamentos y **47 «Corregir»** en
 *  Fichajes, más 7 «Eliminar» donde peor sienta equivocarse. Y el buscador
 *  compartido no tenía nombre: un `placeholder` no es una etiqueta ---desaparece
 *  al escribir--- y encima Personas se fabricaba el suyo aparte.
 *
 *  Se comprueban tres cosas y ninguna necesita una herramienta externa: que
 *  ningún mando visible esté mudo, que ningún campo visible se quede sin
 *  etiqueta, y que ningún rótulo se repita tantas veces que deje de distinguir.
 */

import { expect, test } from '@playwright/test'

import { irA } from './apoyo.js'

const PANTALLAS = [
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/departamentos', 'Departamentos'],
  ['/panel/centros', 'Centros de trabajo'],
  ['/panel/calendario', 'Calendario del equipo'],
  ['/panel/turnos', 'Turnos'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/informes', 'Informes'],
  ['/panel/ajustes', 'Ajustes de la empresa'],
  ['/mi-jornada', 'Mi jornada'],
  ['/mis-ausencias', 'Mis ausencias'],
  ['/actividad', 'Registro de actividad'],
]

/** Lo que el navegador anuncia de cada mando, mirado desde el DOM. */
async function revisar(page) {
  return page.evaluate(() => {
    const nombreDe = (el) =>
      (el.getAttribute('aria-label') || el.textContent || el.title || '').trim()
    // Lo que está oculto para la accesibilidad no cuenta: MUI deja `input`
    // internos con `aria-hidden` detrás de cada desplegable, y marcarlos sería
    // ladrar sin motivo.
    const cuenta = (el) =>
      (el.offsetParent !== null || el.getClientRects().length > 0) &&
      !el.closest('[aria-hidden="true"]') &&
      el.getAttribute('aria-hidden') !== 'true'

    const mudos = []
    for (const el of document.querySelectorAll('button, a[href]')) {
      if (cuenta(el) && !nombreDe(el)) mudos.push(el.outerHTML.slice(0, 120))
    }

    const sinEtiqueta = []
    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (!cuenta(el) || el.type === 'hidden') continue
      const tiene =
        el.labels?.length > 0 || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')
      if (!tiene) sinEtiqueta.push(el.outerHTML.slice(0, 120))
    }

    const veces = {}
    for (const el of document.querySelectorAll('button')) {
      if (!cuenta(el)) continue
      const nombre = nombreDe(el)
      if (nombre) veces[nombre] = (veces[nombre] ?? 0) + 1
    }
    // Dos iguales pueden ser legítimos ---«Cancelar» de dos diálogos---; a
    // partir de tres es una lista de filas y hay que decir de cuál es cada uno.
    const repetidos = Object.entries(veces).filter(([, n]) => n > 2)

    return { mudos, sinEtiqueta, repetidos }
  })
}

test.use({ storageState: 'e2e/.sesiones/admin.json' })

for (const [ruta, titulo] of PANTALLAS) {
  test(`${ruta} nombra todos sus mandos`, async ({ page }) => {
    await irA(page, ruta, titulo)
    await page.waitForLoadState('networkidle').catch(() => {})
    await page.waitForTimeout(500)

    const { mudos, sinEtiqueta, repetidos } = await revisar(page)

    expect(mudos, `mandos sin nombre en ${ruta}`).toEqual([])
    expect(sinEtiqueta, `campos sin etiqueta en ${ruta}`).toEqual([])
    expect(repetidos, `rótulos que no distinguen en ${ruta}`).toEqual([])
  })
}
