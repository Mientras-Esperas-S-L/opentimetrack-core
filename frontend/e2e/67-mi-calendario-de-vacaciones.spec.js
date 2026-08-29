/** El calendario de vacaciones, en la pantalla de quien las disfruta (art. 38.3).
 *
 *  «El calendario de vacaciones se fijará en cada empresa. El trabajador
 *  conocerá las fechas que le correspondan dos meses antes, al menos, del
 *  comienzo del disfrute.»
 *
 *  Va en la suite de navegador porque el artículo es una pantalla, no un
 *  cálculo: **el sujeto es quien trabaja**, y era el único que no lo veía. El
 *  calendario del equipo está tras el permiso de gestión, y el aviso de los dos
 *  meses llegaba a quien metió las fechas y a quien las decide. A quien tiene
 *  que reservar un vuelo, no.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** El panel, como región y no como «el div que contiene ese texto».
 *
 *  Un `hasText` sobre `div` engancha el contenedor del propio título ---y
 *  entonces la prueba comprueba que el título contiene el título---. El panel es
 *  una región con nombre porque `Panel` se pinta como `<section aria-labelledby>`,
 *  que además es lo que permite saltar de sección con un lector de pantalla.
 */
const elCalendario = (page) => page.getByRole('region', { name: 'Mi calendario de vacaciones' })

test.describe('Mi calendario de vacaciones', () => {
  test.describe('quien las disfruta', () => {
    test.use({ storageState: 'e2e/.sesiones/operario.json' })

    test('ve sus fechas y quién se las fijó', async ({ page }) => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')

      await expect(page.getByText('Mi calendario de vacaciones')).toBeVisible()
      // Quién, con nombre: «te las fijó <UUID>» no le dice nada a nadie.
      await expect(elCalendario(page)).toContainText(/te las fijó \w/i)
    })

    test('y el aviso de los dos meses le llega a ella, con el artículo', async ({ page }) => {
      // **Lo que faltaba.** El aviso existía desde hace tiempo y lo veían todos
      // menos la persona a la que le habían fijado las fechas.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      await expect(elCalendario(page)).toContainText('38.3')
      await expect(elCalendario(page)).toContainText(/Lo supiste con \d+ días/)
    })

    test('el cumplimiento también se ve, no solo el incumplimiento', async ({ page }) => {
      // Un plazo que solo se nota cuando falla no se puede comprobar: solo se
      // puede padecer. La demostración lleva los dos casos a propósito.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      await expect(elCalendario(page)).toContainText(/de antelación/)
    })

    test('la API trae los dos datos que la frase necesita', async ({ page }) => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const { body: saldo } = await api(page, '/absences/balance/')
      const { body: tramos } = await api(
        page,
        `/absences/calendar/?from=${saldo.period_start}&to=${saldo.period_end}`,
      )
      const vacaciones = tramos.filter((a) => a.absence_type === 'VACATION')

      expect(vacaciones.length, 'la semilla ya no fija vacaciones').toBeGreaterThan(0)
      for (const tramo of vacaciones) {
        expect(tramo, 'sin la antelación').toHaveProperty('notice_days')
        expect(tramo, 'sin quién las fijó').toHaveProperty('requested_by_name')
      }
      // Los dos casos, el que incumple y el que cumple.
      const dias = vacaciones.map((v) => v.notice_days).filter((d) => d !== null)
      expect(Math.min(...dias), 'ningún caso por debajo de los 60').toBeLessThan(60)
      expect(Math.max(...dias), 'ningún caso por encima de los 60').toBeGreaterThanOrEqual(60)
    })
  })

  test.describe('quien además lleva gente', () => {
    test.use({ storageState: 'e2e/.sesiones/admin.json' })

    test('en «Mis ausencias» ve las suyas y no las de su gente', async ({ page }) => {
      // **El defecto que se vio abriendo la pantalla**, y que ya estaba antes de
      // este panel: `?employee=` no se pasaba, así que quien tiene permiso de
      // gestión veía aquí el historial de toda su gente ---las filas no dicen de
      // quién son--- mientras el saldo de arriba sí era el suyo.
      //
      // Se cuenta **lo que se dibuja**, no lo que contesta la API. La primera
      // versión de esta prueba pedía la ventana con `?employee=` y comprobaba la
      // respuesta: eso demuestra que el servidor sabe acotar, no que la pantalla
      // se lo pida. Quitando el filtro de la pantalla seguía en verde.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const {
        body: { user: yo },
      } = await api(page, '/auth/me/')
      const { body: saldo } = await api(page, '/absences/balance/')
      const { body: todas } = await api(
        page,
        `/absences/calendar/?from=${saldo.period_start}&to=${saldo.period_end}`,
      )

      const mias = todas.filter(
        (a) => a.absence_type === 'VACATION' && String(a.employee) === String(yo.id),
      )
      const ajenas = todas.filter(
        (a) => a.absence_type === 'VACATION' && String(a.employee) !== String(yo.id),
      )
      expect(ajenas.length, 'la demostración ya no tiene vacaciones de otra gente').toBeGreaterThan(
        0,
      )

      // Un tramo pintado es una fecha en el panel. Si se colaran las ajenas,
      // saldrían más de las suyas ---y sin decir de quién son, que es lo peor
      // del defecto: no es que sobren, es que parecen tuyas---.
      const pintados = await elCalendario(page)
        .getByText(/^\d{2} \w+ → /)
        .count()
      expect(pintados, 'el panel pinta tramos que no son suyos').toBe(mias.length)
    })
  })

  test.describe('quien no tiene ninguna fijada', () => {
    test.use({ storageState: 'e2e/.sesiones/vecina.json' })

    test('lee un estado vacío que dice por dónde llegan', async ({ page }) => {
      // Un estado vacío que solo dice «no hay nada» deja a quien lo lee sin
      // saber si es que no le tocan o es que el sistema no las tiene.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      await expect(elCalendario(page)).toContainText(/Todavía no tienes vacaciones fijadas/)
      await expect(elCalendario(page)).toContainText(/las pidas tú o te las fije la empresa/)
    })
  })
})
