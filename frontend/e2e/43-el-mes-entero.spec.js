/** El registro de una persona no cabe en una página, y la ley no admite recorte.
 *
 *  «Tu registro completo», dice la pantalla. El servidor sirve las listas de
 *  cincuenta en cincuenta y esta pedía una sola tanda, así que un mes con más de
 *  cincuenta fichajes se enseñaba a medias --- los más recientes, porque el
 *  orden es descendente. Los primeros días del mes salían en blanco, como si no
 *  se hubiera trabajado, y nada en la pantalla decía que faltara nada.
 *
 *  Un mes laborable con entrada, pausa, vuelta y salida son ochenta y ocho
 *  fichajes: no es un caso extremo, es un mes normal de alguien que hace pausas.
 *
 *  Es el art. 34.9 del Estatuto: la persona tiene derecho a consultar su
 *  registro. Enseñarle un trozo y llamarlo completo no es consultarlo.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

/** El mes con más fichajes de esta persona, y cuántos tiene. */
async function elMesMasCargado(page) {
  const cuenta = new Map()
  for (let pagina = 1; pagina <= 20; pagina += 1) {
    const { status, body } = await api(page, `/punches/?page=${pagina}&ordering=-timestamp`)
    expect(status).toBe(200)
    for (const fichaje of body.results ?? []) {
      const mes = fichaje.timestamp.slice(0, 7)
      cuenta.set(mes, (cuenta.get(mes) ?? 0) + 1)
    }
    if (!body.next) break
  }
  const [mes, total] = [...cuenta.entries()].sort((a, b) => b[1] - a[1])[0] ?? []
  return { mes, total }
}

test.describe('Mi jornada · el mes entero', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('un mes con más fichajes de los que caben en una página se ve entero', async ({ page }) => {
    const ruido = vigilarConsola(page)
    // Primero la pantalla: las llamadas a pelo sacan el testigo del
    // `localStorage`, y eso solo existe cuando la página está en el origen.
    await irA(page, '/mi-jornada', 'Mi jornada')

    const { mes, total } = await elMesMasCargado(page)
    // Si ningún mes pasa de una página, esta prueba no puede demostrar nada y
    // decirlo es mejor que dar un verde que no significa nada.
    expect(
      total,
      `ningún mes de esta persona pasa de 50 fichajes (${mes}: ${total})`,
    ).toBeGreaterThan(50)

    // Lo que el servidor dice que hay en ese mes, que es la vara de medir.
    const { body: delMes } = await api(
      page,
      `/punches/?date_from=${mes}-01&date_to=${mes}-31&ordering=timestamp`,
    )
    const primerDia = delMes.results[0].timestamp.slice(0, 10)
    expect(delMes.count).toBe(total)

    // La pantalla se mueve con flechas, no con un campo de fecha: se retrocede
    // desde el mes en curso hasta el que interesa.
    const [anio, numero] = mes.split('-').map(Number)
    const hoy = new Date()
    const atras = (hoy.getFullYear() - anio) * 12 + (hoy.getMonth() + 1 - numero)
    for (let paso = 0; paso < atras; paso += 1) {
      await page.getByRole('button', { name: 'Mes anterior' }).click()
    }

    // El día más antiguo del mes es justo el que se perdía: con cincuenta filas
    // descendentes la pantalla llegaba más o menos a la mitad del mes.
    const dia = Number(primerDia.slice(8, 10))
    await expect(
      page.getByText(new RegExp(`\\b0?${dia}\\b`)).first(),
      `el ${primerDia} no aparece: el mes se está enseñando a medias`,
    ).toBeVisible()

    // Y la pantalla no puede prometer entero lo que no lo esté.
    await expect(page.getByText('más fichajes de los que caben aquí')).toHaveCount(0)

    expect(ruido()).toEqual([])
  })
})
