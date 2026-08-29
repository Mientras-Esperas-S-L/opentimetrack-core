/** «Te quedan 16 h» encima de tres líneas que suman 24.
 *
 *  Lo devuelto se resta una sola vez, del total, porque un descanso disfrutado no
 *  dice de qué fuente salda y repartirlo exigiría una regla de imputación que
 *  nadie ha acordado. La decisión es correcta y estaba razonada en el servidor;
 *  lo que faltaba era que la pantalla la dijera. Quien lee el aviso cuenta las
 *  líneas y no le sale.
 *
 *  **La prueba construye el caso.** La primera versión miraba el saldo que
 *  hubiera y se saltaba sola cuando no encajaba: con la demostración recién
 *  sembrada nadie ha disfrutado nada, así que la comprobación que importa no
 *  llegaba a correr nunca. Una prueba que se salta siempre no protege nada.
 */

import { expect, test } from '@playwright/test'

import { api, irA, marca } from './apoyo.js'

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

/** El saldo de esta persona, visto desde su propia sesión. */
async function saldoDe(browser, hacer) {
  const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/operario.json' })
  const suya = await contexto.newPage()
  try {
    await irA(suya, '/mis-ausencias', 'Mis ausencias')
    return await hacer(suya)
  } finally {
    await contexto.close()
  }
}

test.describe('El total del saldo y la suma de sus líneas', () => {
  // La administración crea y aprueba; quien trabaja mira. Dos sesiones, porque
  // una persona no puede aprobarse su propio descanso.
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  let creadas = []

  test.afterEach(async ({ page }) => {
    if (!creadas.length) return
    const cuales = creadas
    creadas = []
    await irA(page, '/panel/decisiones', 'Por decidir')
    for (const cual of cuales) {
      await api(page, `/absences/${cual}/cancel/`, { method: 'POST' }).catch(() => {})
    }
  })

  /** Un descanso de N horas, ya aprobado. **Por horas y no por días**: un día
   *  entero vale lo que ese día tocaba trabajar y sale del cuadrante, así que
   *  depender de él ataría la prueba a qué días tiene turno la persona en la
   *  demostración. Las horas se cuentan tal cual. */
  async function disfruta(page, quien, descanso, dia, horas) {
    const { status, body } = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: quien.id,
        absence_type: 'PAID_LEAVE',
        leave_type: descanso.id,
        start_date: dia,
        end_date: dia,
        start_time: '09:00',
        end_time: `${String(9 + horas).padStart(2, '0')}:00`,
        reason: `Desglose ${marca()}`,
      },
    })
    expect(status, `no se pudo registrar el descanso del ${dia}`).toBe(201)
    creadas.push(body.id)
    await api(page, `/absences/${body.id}/approve/`, { method: 'POST' })
  }

  const haceDias = (n) => {
    const d = new Date()
    d.setDate(d.getDate() - n)
    return d.toISOString().slice(0, 10)
  }

  test('un descanso disfrutado descuadra el total, y la pantalla lo explica', async ({
    page,
    browser,
  }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')

    // 1. Antes: el total es exactamente la suma de las líneas.
    const antes = await saldoDe(browser, async (suya) => {
      const {
        body: { rest_debt: deuda },
      } = await api(suya, '/absences/balance/')
      return { deuda, lineas: await lineasDelDesglose(suya) }
    })
    expect(antes.deuda, 'la demostración ya no genera deuda de descanso').toBeTruthy()
    expect(antes.deuda.settled_hours, 'la demostración ya trae descansos disfrutados').toBe(0)
    expect(antes.lineas.length, 'no hay desglose que comprobar').toBeGreaterThan(1)
    const suma = antes.lineas.reduce((a, b) => a + b, 0)
    expect(Math.round(suma * 10) / 10).toBe(antes.deuda.remaining_hours)

    // 2. Se disfruta un día de descanso, aprobado por la administración.
    const { body: gente } = await api(page, '/employees/?search=operario')
    const quien = (gente.results ?? gente).find((p) => p.email === 'operario@demo.local')
    const { body: tipos } = await api(page, '/leave-types/?page_size=200')
    const descanso = (tipos.results ?? tipos).find((t) => t.code === 'es.compensatory_rest')

    await disfruta(page, quien, descanso, haceDias(2), 8)

    // 3. Después: el total baja, las líneas no, y la frase dice por qué.
    const despues = await saldoDe(browser, async (suya) => {
      const {
        body: { rest_debt: deuda },
      } = await api(suya, '/absences/balance/')
      return { deuda, texto: await elSaldo(suya).innerText() }
    })

    expect(
      despues.deuda.settled_hours,
      'el descanso no se ha contado como devuelto',
    ).toBeGreaterThan(0)
    expect(despues.deuda.remaining_hours).toBeLessThan(antes.deuda.remaining_hours)
    // Las líneas siguen diciendo lo generado: eso es correcto y es el motivo de
    // que el total ya no sea su suma.
    expect(despues.texto).toContain('Ya has disfrutado')
    expect(despues.texto).toMatch(/se restan del total y no de una línea/)

    // 4. **El extremo.** Disfrutado todo, el desglose desaparece: sus líneas
    // llevan fechas ---«hasta el 12 dic 2026»--- y un plazo de algo saldado no
    // corre. «No queda descanso por recuperar» encima de esas líneas hacía creer
    // que quedaban ocho horas por caducar.
    let porDisfrutar = despues.deuda.remaining_hours
    let vuelta = 0
    while (porDisfrutar > 0 && vuelta < 6) {
      const cuantas = Math.min(8, Math.ceil(porDisfrutar))
      await disfruta(page, quien, descanso, haceDias(9 + vuelta * 7), cuantas)
      porDisfrutar -= cuantas
      vuelta += 1
    }

    const alFinal = await saldoDe(browser, async (suya) => {
      const {
        body: { rest_debt: deuda },
      } = await api(suya, '/absences/balance/')
      return {
        deuda,
        texto: await elSaldo(suya).innerText(),
        lineas: await lineasDelDesglose(suya),
      }
    })

    expect(alFinal.deuda.remaining_hours, 'no se ha llegado a saldar todo').toBe(0)
    expect(alFinal.texto).toMatch(/No queda descanso por recuperar/)
    expect(alFinal.lineas, 'el desglose sigue enseñando horas y plazos ya saldados').toEqual([])
  })
})
