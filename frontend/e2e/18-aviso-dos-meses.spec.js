/** El aviso de los dos meses del art. 38.3, de punta a punta.
 *
 *  «El trabajador conocerá las fechas que le correspondan dos meses antes, al
 *  menos, del comienzo del disfrute.» El plazo existe para que a nadie le fijen
 *  las vacaciones encima: es lo que permite reservar un vuelo o apuntar a un
 *  crío a un campamento.
 *
 *  Aquí se comprueba lo que hace que un aviso sirva para algo, que no es que
 *  aparezca: es que **no aparezca cuando no toca**. Si saltara también con las
 *  vacaciones que uno pide para sí mismo, saldría en la mitad de las
 *  solicitudes normales y en dos semanas nadie lo miraría.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

const MARCA = 'Prueba plazo 38.3'

/** Dentro de tres semanas: por debajo de los dos meses, sin discusión. */
function dentroDe(dias) {
  const cuando = new Date()
  cuando.setDate(cuando.getDate() + dias)
  return cuando.toISOString().slice(0, 10)
}

async function limpiar(page) {
  const pendientes = await api(page, '/absences/?status=PENDING')
  for (const fila of pendientes.body?.results ?? pendientes.body ?? []) {
    if ((fila.reason ?? '').startsWith(MARCA)) {
      await api(page, `/absences/${fila.id}/cancel/`, { method: 'POST' })
    }
  }
}

test.describe('Vacaciones puestas por la empresa', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('avisa del plazo al registrarlas y al ir a decidirlas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/calendario', 'Calendario del equipo')
    await limpiar(page)

    // Se registran por API para llegar al aviso sin repetir el recorrido del
    // formulario, que ya tiene su prueba en 09. Lo que se comprueba aquí es
    // otra cosa: qué se enseña de la respuesta.
    const tipos = await api(page, '/leave-types/')
    const vacaciones = (tipos.body?.results ?? tipos.body ?? []).find((t) =>
      /vacacion/i.test(t.name ?? ''),
    )
    expect(vacaciones, 'hacía falta el permiso de vacaciones').toBeTruthy()

    const gente = await api(page, '/employees/?is_active=true')
    const yo = await api(page, '/auth/me/')
    const otra = (gente.body?.results ?? gente.body ?? []).find((p) => p.id !== yo.body.user.id)
    expect(otra, 'hacía falta otra persona en la plantilla').toBeTruthy()

    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: otra.id,
        leave_type: vacaciones.id,
        start_date: dentroDe(21),
        end_date: dentroDe(27),
        reason: `${MARCA} puestas`,
      },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)
    expect(alta.body.short_notice, 'el servidor no avisó del plazo').toBeTruthy()
    expect(alta.body.short_notice.citation).toBe('Art. 38.3 ET')

    // Y quien decide lo ve en su cola, que es donde se decide. Si el aviso solo
    // llegara a quien las puso, bastaría con no leerlo.
    await irA(page, '/panel/decisiones', 'Por decidir')
    await expect(page.getByText(/pide dos meses/i).first()).toBeVisible()

    await limpiar(page)
    expect(ruido()).toEqual([])
  })

  test('pedirlas uno mismo no dispara el aviso', async ({ page }) => {
    // El contraste, y la mitad que hace que el aviso valga: quien pide sus
    // vacaciones conoce las fechas por definición. No hay plazo que incumplir.
    await irA(page, '/panel/calendario', 'Calendario del equipo')
    await limpiar(page)

    const tipos = await api(page, '/leave-types/')
    const vacaciones = (tipos.body?.results ?? tipos.body ?? []).find((t) =>
      /vacacion/i.test(t.name ?? ''),
    )

    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        leave_type: vacaciones.id,
        start_date: dentroDe(21),
        end_date: dentroDe(27),
        reason: `${MARCA} pedidas por mí`,
      },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)
    expect(alta.body.short_notice).toBeNull()

    await limpiar(page)
  })
})
