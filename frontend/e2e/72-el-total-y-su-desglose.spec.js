/** «Te quedan 16 h» encima de tres líneas que suman 24.
 *
 *  Lo devuelto se resta una sola vez, del total, porque un descanso disfrutado no
 *  dice de qué fuente salda y repartirlo exigiría una regla de imputación que
 *  nadie ha acordado. La decisión es correcta y estaba razonada en el servidor;
 *  lo que faltaba era que la pantalla la dijera. Quien lee el aviso cuenta las
 *  líneas y no le sale.
 *
 *  **La prueba lee, no crea.** Dos versiones anteriores fallaron por lo mismo:
 *  la primera se saltaba sola con `skip` cuando la demostración no traía
 *  descansos disfrutados ---o sea siempre, recién sembrada---; la segunda los
 *  creaba y los aprobaba, y **no podía deshacerlos**, porque `cancel_absence`
 *  solo actúa mientras la ausencia está pendiente y eso es a propósito: una
 *  aprobada ya ha bloqueado días. Dejaba tres descansos en la base y la tanda
 *  siguiente empezaba con el saldo movido.
 *
 *  Ahora el caso vive en la semilla, que además es donde tiene que estar: una
 *  empresa con la deuda intacta es la de la primera semana, no la normal.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const elSaldo = (page) =>
  page
    .getByRole('alert')
    .filter({ hasText: /descanso/i })
    .first()

/** Las horas de cada línea del desglose, leídas de lo que se pinta. */
async function lineasDelDesglose(page) {
  const texto = await elSaldo(page).innerText()
  return texto
    .split('\n')
    .map((l) => l.match(/^([\d.,]+) h de /))
    .filter(Boolean)
    .map((m) => Number(m[1].replace(',', '.')))
}

test.describe('El total del saldo y la suma de sus líneas', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('el total es menor que la suma, y la pantalla dice por qué', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const {
      body: { rest_debt: deuda },
    } = await api(page, '/absences/balance/')

    expect(deuda, 'la demostración ya no genera deuda de descanso').toBeTruthy()
    expect(
      deuda.settled_hours,
      'la demostración ya no trae ningún descanso disfrutado: sin eso, esta prueba comprueba el caso fácil',
    ).toBeGreaterThan(0)

    const lineas = await lineasDelDesglose(page)
    expect(lineas.length, 'no hay desglose que comprobar').toBeGreaterThan(1)
    const generado = lineas.reduce((a, b) => a + b, 0)

    // El total es menor que la suma, y la diferencia **es** lo devuelto.
    expect(generado).toBeGreaterThan(deuda.remaining_hours)
    expect(Math.round((generado - deuda.remaining_hours) * 10) / 10).toBe(deuda.settled_hours)

    // Y la pantalla lo explica, en vez de dejar que quien lee cuente y no le
    // salga. Sin esta frase las dos cifras se contradicen a la vista.
    const texto = await elSaldo(page).innerText()
    expect(texto).toContain(`Ya has disfrutado ${deuda.settled_hours} h`)
    expect(texto).toMatch(/se restan del total y no de una línea/)
  })

  test('las líneas dicen lo generado, no lo que queda', async ({ page }) => {
    // El contraste de lo anterior. Si el servidor repartiera lo devuelto entre
    // las fuentes, la suma coincidiría con el total y la frase sobraría --- pero
    // haría falta una regla de imputación que nadie ha acordado, y cada línea
    // lleva su plazo, así que restar de la que no toca cambia cuándo vence.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const {
      body: { rest_debt: deuda },
    } = await api(page, '/absences/balance/')

    const suma = deuda.sources.reduce((a, f) => a + f.owed_hours, 0)
    expect(Math.round(suma * 10) / 10).toBe(deuda.owed_hours)
    expect(deuda.owed_hours).toBeGreaterThan(deuda.remaining_hours)
  })

  test('cada línea sigue llevando su artículo y su plazo', async ({ page }) => {
    // Lo que el desglose existe para decir: de dónde sale cada trozo y hasta
    // cuándo hay. Es también lo que lo hace peligroso cuando ya no queda nada,
    // y por eso la pantalla lo esconde en ese caso.
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    const texto = await elSaldo(page).innerText()

    for (const linea of texto.split('\n').filter((l) => /^[\d.,]+ h de /.test(l))) {
      expect(linea, `sin artículo: ${linea}`).toMatch(/Art\./)
      expect(linea, `sin estado de plazo: ${linea}`).toMatch(
        /hasta el|sin plazo|fuera de plazo|en los días siguientes/,
      )
    }
  })
})
