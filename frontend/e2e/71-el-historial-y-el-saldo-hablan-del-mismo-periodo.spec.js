/** El saldo y el historial de «Mis ausencias», mirando la misma ventana.
 *
 *  Con el mes de inicio por defecto son la misma y no se notaba. Con cualquier
 *  otro ---que es lo que el producto ofrece configurar en Ajustes--- la pantalla
 *  se contradecía a dos centímetros:
 *
 *      Vacaciones · Periodo del 01 sept 2025 al 31 ago 2026
 *      24 días laborables de 24 · 0 disfrutados
 *      ...
 *      Historial · Año 2026
 *      Vacaciones 08 oct → 15 oct · 8 días · Aprobada
 *
 *  Las dos cosas eran ciertas. El saldo iba por el periodo de la empresa y el
 *  historial por el año natural, y nada lo decía.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const elFiltro = (page) => page.getByRole('combobox').first()

/** Mueve el mes en que empieza el periodo, y lo deja como estaba al terminar. */
async function conElPeriodoEn(page, mes, hacer) {
  const { body: antes } = await api(page, '/company/')
  const previo = antes.leave_year_start_month
  try {
    await api(page, '/company/', {
      method: 'PATCH',
      body: { leave_year_start_month: mes },
    })
    await hacer()
  } finally {
    await api(page, '/company/', {
      method: 'PATCH',
      body: { leave_year_start_month: previo },
    })
  }
}

test.describe('El saldo y el historial, en el mismo periodo', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('con el periodo natural, el filtro dice «Año»', async ({ page }) => {
    // El contraste que protege a la inmensa mayoría: con el mes por defecto
    // esta pantalla se queda exactamente como estaba.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const esteAño = String(new Date().getFullYear())

    await expect(page.getByText('Año', { exact: true }).first()).toBeVisible()
    await expect(elFiltro(page)).toContainText(esteAño)
  })

  test('con el periodo movido, el filtro dice el periodo y coincide con el saldo', async ({
    page,
  }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    await conElPeriodoEn(page, 9, async () => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const { body: saldo } = await api(page, '/absences/balance/')

      // El saldo abarca dos años naturales: es el caso que rompía la pantalla.
      const desde = saldo.period_start.slice(0, 4)
      const hasta = saldo.period_end.slice(0, 4)
      expect(desde, 'el periodo no llegó a cruzar el año').not.toBe(hasta)

      // Y el filtro nombra **ese** periodo, no el año natural en curso.
      await expect(page.getByText('Periodo', { exact: true }).first()).toBeVisible()
      await expect(elFiltro(page)).toContainText(`${desde}/${hasta.slice(2)}`)

      // Y la lista **empieza** por él. Comprobar solo lo seleccionado dejaba
      // pasar que las opciones se contaran desde el año natural: el desfase de
      // uno no se ve en el valor elegido ---que sigue estando en la lista--- y
      // sí en los extremos, ofreciendo un periodo futuro y comiéndose el más
      // antiguo. Lo destapó el contraste, no la lectura.
      await elFiltro(page).click()
      const opciones = await page.getByRole('option').allInnerTexts()
      await page.keyboard.press('Escape')
      const periodos = opciones.filter((o) => /^\d{4}\/\d{2}$/.test(o))
      expect(periodos[0], 'la lista no empieza por el periodo en curso').toBe(
        `${desde}/${hasta.slice(2)}`,
      )
    })
  })

  test('y la lista es la de ese periodo, no la del año natural', async ({ page }) => {
    // **El segundo fallo, y era mío.** La clave de la consulta llevaba el año
    // elegido ---nulo mientras no se elige--- y no el que la consulta usaba de
    // verdad, así que al llegar el saldo la clave no cambiaba y react-query
    // servía para siempre la respuesta pedida antes, con el año natural. La
    // pantalla enseñaba el rótulo del periodo correcto sobre la lista del
    // periodo equivocado: peor que el fallo que venía a arreglar.
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    await conElPeriodoEn(page, 9, async () => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const { body: saldo } = await api(page, '/absences/balance/')
      const { body: delPeriodo } = await api(
        page,
        `/absences/?employee=${(await api(page, '/auth/me/')).body.user.id}&year=${saldo.period_start.slice(0, 4)}`,
      )

      // Lo que la pantalla pinta y lo que la API devuelve para ese periodo
      // tienen que ser lo mismo. Si la clave no arrastrara el año, la lista
      // vendría del año natural y estos dos números no cuadrarían.
      const pintadas = await page
        .locator('main')
        .getByText(/·\s*\d+\s*(día|h)/)
        .count()
      expect(pintadas).toBe((delPeriodo.results ?? delPeriodo).length)
    })
  })
})
