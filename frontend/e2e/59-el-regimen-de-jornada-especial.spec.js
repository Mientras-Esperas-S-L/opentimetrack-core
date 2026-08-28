/** Declarar el régimen del RD 1561/1995, y que los avisos lo digan.
 *
 *  El producto avisa cuando una cifra se sale del suelo o del techo que fija un
 *  artículo. Poner el descanso entre jornadas en diez horas se contesta con «por
 *  debajo del mínimo de 12 que fija el Art. 34.3 ET», que para una empresa de
 *  transporte se lee como una acusación: el RD 1561/1995 **aparta esa cifra en
 *  su sector**, y diez horas ahí pueden ser lo que toca.
 *
 *  Esta prueba está en la suite de navegador y no solo en la de servidor por una
 *  razón concreta: **el campo existía en la API desde el 28/08 y no había dónde
 *  rellenarlo**. El aviso que nombra el sector no lo habría visto nadie nunca,
 *  porque el sector no se podía decir sin escribir una llamada a la API. Lo que
 *  hay que impedir que vuelva es eso, y eso solo se ve desde la pantalla.
 *
 *  Las opciones las manda el servidor, ya traducidas. Si algún día alguien las
 *  escribe aquí en vez de pedirlas, habrá dos listas que mantener y esta prueba
 *  seguirá pasando: por eso comprueba que están **todas**, contra lo que dice la
 *  API, y no contra una lista escrita a mano.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Lo que había antes, para dejarlo como estaba. */
let previo = null

test.beforeEach(async ({ page }) => {
  await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
  const { body: reglas } = await api(page, '/working-time-rules/')
  previo = {
    special_regime: reglas.special_regime ?? '',
    daily_rest_hours: reglas.daily_rest_hours,
  }
})

test.afterEach(async ({ page }) => {
  if (!previo) return
  const volver = previo
  previo = null
  await api(page, '/working-time-rules/', { method: 'PATCH', body: volver })
})

test.describe('El régimen de jornada especial', () => {
  test('se declara desde la pantalla, sin abrir un shell', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const campo = page.getByRole('combobox', { name: 'Régimen de jornada especial' })
    await expect(campo).toBeVisible()

    // La etiqueta se pide a la API en vez de escribirla aquí. Viene traducida al
    // idioma de la sesión, y una prueba que buscara «Transporte por carretera»
    // se pondría roja el día que alguien mire esta pantalla en catalán.
    const {
      body: { regimes },
    } = await api(page, '/working-time-rules/')
    const suyo = regimes.find((r) => r.value === 'ROAD_TRANSPORT')

    await campo.click()
    await page.getByRole('option', { name: suyo.label }).click()
    await expect(campo).toHaveText(suyo.label)
  })

  test('el selector ofrece todas las opciones que manda el servidor', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    const {
      body: { regimes },
    } = await api(page, '/working-time-rules/')
    expect(regimes.length).toBeGreaterThan(10)

    await page.getByRole('combobox', { name: 'Régimen de jornada especial' }).click()
    const opciones = page.getByRole('option')
    await expect(opciones).toHaveCount(regimes.length)

    for (const r of regimes) {
      await expect(opciones.filter({ hasText: r.label }).first()).toBeVisible()
    }
    await page.keyboard.press('Escape')
  })

  test('con el régimen puesto, el aviso de una cifra apartada lo nombra', async ({ page }) => {
    await api(page, '/working-time-rules/', {
      method: 'PATCH',
      body: { special_regime: 'ROAD_TRANSPORT' },
    })
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const descanso = page.getByLabel('Descanso entre jornadas (h)')
    await descanso.fill('10')
    await descanso.blur()

    // El límite sigue citado ---es de dónde sale la comparación--- y ahora
    // también el porqué.
    const {
      body: { regimes },
    } = await api(page, '/working-time-rules/')
    const suyo = regimes.find((r) => r.value === 'ROAD_TRANSPORT')

    const aviso = page.locator('p.MuiFormHelperText-root').filter({ hasText: /Art\. 34\.3/ })
    await expect(aviso).toBeVisible()
    await expect(aviso).toContainText('1561/1995')
    await expect(aviso).toContainText(suyo.label)
  })

  test('sin régimen declarado el aviso sale igual, pero sin hablar del sector', async ({
    page,
  }) => {
    await api(page, '/working-time-rules/', {
      method: 'PATCH',
      body: { special_regime: '' },
    })
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const descanso = page.getByLabel('Descanso entre jornadas (h)')
    await descanso.fill('10')
    await descanso.blur()

    // **El contraste, y las dos mitades importan.** Que el aviso siga saliendo:
    // el real decreto no quita el límite, lo aparta en sectores concretos, y
    // callarlo sería decir que ahí no hay nada que comprobar. Y que no nombre
    // ningún sector: a una oficina no se le puede insinuar que la ampara un
    // real decreto de sectores que no es el suyo.
    const aviso = page.locator('p.MuiFormHelperText-root').filter({ hasText: /Art\. 34\.3/ })
    await expect(aviso).toBeVisible()
    await expect(aviso).not.toContainText('1561/1995')
  })
})
