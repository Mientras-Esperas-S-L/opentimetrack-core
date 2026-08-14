/** Los nombres más largos que el modelo acepta no pueden romper la maquetación.
 *
 *  Cien caracteres en un departamento, ciento veinte en un centro, doscientos
 *  cincuenta y cinco en una empresa: son los máximos que la base admite, así que
 *  antes o después alguien los escribe. Y sin un solo espacio ---un código, dos
 *  nombres pegados, un pegado desde otro sistema--- no hay dónde partir la
 *  palabra.
 *
 *  Lo que encontró, con el tema sin arreglar: **tres pantallas**, no una.
 *  Departamentos se salía 434 px en escritorio y 719 en el móvil; Centros, 675;
 *  y Ajustes ---donde va el nombre de la empresa--- 1435. La página entera se
 *  desplazaba en horizontal.
 *
 *  El arreglo es una línea en el tema y no un parche por pantalla: son ocho las
 *  que pintan nombres libres en tarjetas y la novena que se añada mañana nacería
 *  con el mismo agujero.
 *
 *  Los datos se crean y se deshacen dentro de la prueba, con identidad fija y
 *  comprobando la limpieza. La versión anterior de otra prueba dejaba una
 *  persona de baja por tanda y a las nueve empezaron a fallar pruebas de otros
 *  ficheros.
 */
import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Cien y pico caracteres sin un solo espacio: el caso que no puede partirse. */
const LARGO = (n) => 'Wolfeschlegelsteinhausenbergerdorff'.repeat(20).slice(0, n)

const PANTALLAS = [
  ['/panel/personas', 'Personas'],
  ['/panel/departamentos', 'Departamentos'],
  ['/panel/centros', 'Centros'],
  ['/panel/ajustes', 'Ajustes de la empresa'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel', 'Resumen'],
]

//: Escritorio, la franja del 200 % de zoom, y el móvil.
const ANCHOS = [1280, 640, 390]

const CORREO = 'extremos.prueba@example.com'

const DESBORDE = () => {
  const doc = document.documentElement
  const cuanto = doc.scrollWidth - doc.clientWidth
  const culpables = []
  if (cuanto > 2) {
    for (const el of document.querySelectorAll('body *')) {
      const c = el.getBoundingClientRect()
      if (c.width > 0 && c.right > doc.clientWidth + 2) {
        culpables.push(`<${el.tagName.toLowerCase()}> hasta ${Math.round(c.right)}px`)
        if (culpables.length > 2) break
      }
    }
  }
  return { cuanto, culpables }
}

test.describe('Nombres en su longitud máxima', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('ninguna pantalla se desplaza en horizontal', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    const nombreEmpresa = (await api(page, '/company/')).body.name
    let persona = null
    let departamento = null
    let centro = null

    try {
      await api(page, '/company/', { method: 'PATCH', body: { name: LARGO(255) } })

      const previas = await api(page, `/employees/?search=${CORREO}&is_active=`)
      persona = (previas.body?.results ?? []).find((p) => p.email === CORREO)?.id
      if (persona) {
        await api(page, `/employees/${persona}/`, {
          method: 'PATCH',
          body: { is_active: true, first_name: LARGO(100), last_name: LARGO(80) },
        })
      } else {
        const alta = await api(page, '/employees/', {
          method: 'POST',
          body: { email: CORREO, first_name: LARGO(100), last_name: LARGO(80) },
        })
        expect(alta.status, JSON.stringify(alta.body)).toBe(201)
        persona = alta.body.id
      }

      departamento = (
        await api(page, '/departments/', { method: 'POST', body: { name: LARGO(100) } })
      ).body?.id
      centro = (
        await api(page, '/workplaces/', {
          method: 'POST',
          body: { name: LARGO(120), time_zone: 'Europe/Madrid' },
        })
      ).body?.id
      expect(departamento && centro, 'no se pudo montar el caso').toBeTruthy()

      const rotas = []
      for (const [ruta, titulo] of PANTALLAS) {
        for (const ancho of ANCHOS) {
          await page.setViewportSize({ width: ancho, height: 800 })
          await irA(page, ruta, titulo)
          await page.waitForLoadState('networkidle').catch(() => {})

          const { cuanto, culpables } = await page.evaluate(DESBORDE)
          if (cuanto > 2) rotas.push(`${ruta} @${ancho}px: ${cuanto}px · ${culpables.join(', ')}`)
        }
      }

      expect(rotas, 'un nombre largo saca la página de la pantalla').toEqual([])
    } finally {
      // Todo como estaba. La limpieza se comprueba: una que falla en silencio
      // deja la base envenenada y rompe pruebas de otros ficheros.
      if (departamento) await api(page, `/departments/${departamento}/`, { method: 'DELETE' })
      if (centro) await api(page, `/workplaces/${centro}/`, { method: 'DELETE' })
      const empresa = await api(page, '/company/', {
        method: 'PATCH',
        body: { name: nombreEmpresa },
      })
      expect(empresa.status, 'la empresa se quedó con el nombre largo').toBe(200)
      if (persona) {
        const vuelta = await api(page, `/employees/${persona}/`, {
          method: 'PATCH',
          body: { first_name: 'Extremos', last_name: 'Prueba', is_active: true },
        })
        expect(vuelta.status, 'la persona se quedó con el nombre largo').toBe(200)
      }
    }
  })

  test('y la sonda de arriba sabe ver un desbordamiento', async ({ page }) => {
    /** El contraste. Seis pantallas por tres anchos en verde también sale si
     *  `scrollWidth - clientWidth` está midiendo el elemento equivocado, o si
     *  algo de arriba puso `overflow: hidden` y el documento ya no puede
     *  desbordarse aunque su contenido no quepa. */
    await irA(page, '/panel/departamentos', 'Departamentos')

    const roto = await page.evaluate(() => {
      const d = document.createElement('div')
      d.style.cssText = 'width:3000px;height:10px'
      document.body.append(d)
      const doc = document.documentElement
      const r = doc.scrollWidth - doc.clientWidth
      d.remove()
      return r
    })

    expect(roto, 'la sonda no ve un hijo de 3000px').toBeGreaterThan(2)
  })
})
