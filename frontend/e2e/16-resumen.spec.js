/** El Resumen, y que sus números sean ciertos.
 *
 *  Es la portada del panel: cuatro cifras y tres listas. Nadie la lee con
 *  atención --- se mira de reojo para decidir dónde entrar --- y por eso un
 *  número equivocado a la baja hace más daño aquí que en ninguna otra pantalla:
 *  una cola que la portada da por vacía es una cola que nadie abre.
 *
 *  Pasó con «esperando decisión». Contaba dos de las cinco colas de «Por
 *  decidir» y se dejaba fuera la más grande: decía **2** habiendo **57**. Entre
 *  lo que no contaba estaban las horas extra, que tienen cuatro meses de plazo
 *  para compensarse con descanso (art. 35.1), así que el número no era un
 *  adorno: era la diferencia entre resolverlas y no enterarse.
 *
 *  Estas pruebas comparan la pantalla con lo que dice el servidor, no con una
 *  cifra escrita a mano. Una prueba que espera «57» se pondría roja el día que
 *  alguien resuelva una, y a la tercera vez la desactivaría cualquiera.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, vigilarConsola } from './apoyo.js'

/** Lo que la portada suma, según el servidor. */
async function loQueEspera(page) {
  const cuerpo = (await api(page, '/overview/')).body?.awaiting_decision ?? {}
  return {
    total:
      (cuerpo.absences ?? 0) +
      (cuerpo.corrections ?? 0) +
      (cuerpo.awaiting_employee ?? 0) +
      (cuerpo.recoveries ?? 0) +
      // Las horas extra entran desde que contarlas dejó de costar medio
      // segundo. Quedarse fuera era el fallo de la vuelta 2 en pequeño: la
      // portada decía un número y «Por decidir» tenía más cosas que ese número.
      (cuerpo.overtime ?? 0),
    hayHorasExtra: (cuerpo.overtime ?? 0) > 0 || cuerpo.overtime_pending === true,
    detalle: cuerpo,
  }
}

test.describe('Resumen', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la cifra de «esperando decisión» cuenta todas las colas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel', 'Resumen')

    const { total, detalle } = await loQueEspera(page)

    // Las cinco colas están todas en la respuesta.
    // Si alguna desapareciera, la portada volvería a mentir en silencio.
    for (const cola of ['absences', 'corrections', 'awaiting_employee', 'recoveries', 'overtime']) {
      expect(detalle, `falta la cola ${cola}`).toHaveProperty(cola)
    }

    // Contra el texto de la página y no con `getByText` de la frase entera: la
    // tarjeta pinta el número y el rótulo en dos elementos, así que la frase
    // completa no es ningún nodo.
    await expect(page.locator('body')).toContainText(`${total}`)
    await expect(page.locator('body')).toContainText('esperando decisión')
    await expect(page.getByRole('link', { name: new RegExp(`^${total}\\b`) })).toBeVisible()

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })

  test('la portada y «Por decidir» dicen lo mismo', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // El contraste que hace falta: dos pantallas que cuentan lo mismo tienen
    // que decir lo mismo. Discrepaban en cinco, y era la pestaña la que
    // truncaba --- contaba las filas recibidas, no el total, y llegan de
    // cincuenta en cincuenta.
    await irA(page, '/panel/decisiones', 'Por decidir')
    const numeroDe = async (cola) => {
      const pestaña = page.getByRole('tab', { name: new RegExp(`^${cola}`) })
      await expect(pestaña).toContainText(/\d/)
      // `\+?` porque el Badge trunca por encima de su tope. Si lo hace, el
      // número leído es el truncado y **no** coincidirá con el de la portada,
      // que es exactamente el fallo que esta prueba busca: dos pantallas
      // contando lo mismo y diciendo cosas distintas.
      return Number((await pestaña.innerText()).match(/(\d+)\+?\s*$/)?.[1] ?? -1)
    }

    // Se vuelven a leer las dos cifras juntas hasta que coincidan, en vez de
    // comparar una foto de la API tomada hace un momento contra la pantalla de
    // ahora. Esta base la comparten todas las pruebas y alguna resuelve colas
    // en bloque: entre las dos lecturas el número **puede** haber cambiado, y
    // eso no es el fallo que esta prueba busca --- el que busca es un truncado,
    // que no se arregla solo por mirar otra vez.
    await expect
      .poll(async () => {
        const { detalle: ahora } = await loQueEspera(page)
        return (
          [
            await numeroDe('Ausencias'),
            await numeroDe('Fichajes'),
            await numeroDe('Sin acuerdo'),
          ].join('/') === [ahora.absences, ahora.corrections, ahora.awaiting_employee].join('/')
        )
      })
      .toBe(true)
  })

  test('una lista recortada lo dice', async ({ page }) => {
    await irA(page, '/panel/decisiones', 'Por decidir')
    await page.getByRole('tab', { name: /^Sin acuerdo/ }).click()
    await page.waitForTimeout(900)

    const total = (await api(page, '/corrections/?status=AWAITING_EMPLOYEE')).body?.count ?? 0
    const filas = await page.getByRole('button', { name: 'Aplicar sin acuerdo' }).count()

    // El aviso de «se muestran 50 de 55» era el arreglo de la vuelta 2, cuando
    // la cola llegaba recortada y no lo decía. En la 22 se sustituyó por un
    // paginador, que además deja llegar a las que faltan --- el aviso mandaba a
    // usar los filtros, y los filtros son en cliente sobre lo ya cargado.
    //
    // Esta prueba se quedó vieja sin que nadie lo notara, porque con menos de
    // cincuenta propuestas tomaba la rama del «no debe aparecer» y pasaba.
    if (total > filas) {
      await expect(page.getByText(`1–${filas} de ${total} propuestas`)).toBeVisible()
    } else {
      await expect(page.getByText(`${total} propuestas`)).toBeVisible()
    }
  })

  test('lo que enseña coincide con quien está fichado', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // «Trabajando ahora» sale del registro, no de un campo de estado. Se
    // comprueba contra el propio registro para que siga siendo verdad.
    const overview = (await api(page, '/overview/')).body
    for (const persona of overview.working_now ?? []) {
      await expect(page.getByText(persona.name).first()).toBeVisible()
    }
    await expect(page.locator('body')).toContainText(`${overview.headcount}`)
    await expect(page.locator('body')).toContainText('personas de alta')
  })
})

test.describe('Resumen · un operario', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('no ve el panel ni por API le cuentan la empresa', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    // La portada de gestión no está en su menú, y por debajo el servidor le
    // responde con lo suyo: su día, y ni un dato de nadie más.
    const suyo = await api(page, '/overview/')
    expect(suyo.status).toBe(200)
    expect(suyo.body.scope).toBe('self')
    expect(suyo.body).not.toHaveProperty('working_now')
    expect(suyo.body).not.toHaveProperty('headcount')
    expect(suyo.body).not.toHaveProperty('off_today')
  })
})
