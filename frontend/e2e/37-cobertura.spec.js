/** Un turno que se queda sin nadie, y las tres formas de enterarse.
 *
 *  Sale de una pregunta de Francisco: el cuadrante ya avisaba de que alguien se
 *  fue o está de baja, y ahí se acababa. Avisar no es cubrir. Alguien tiene que
 *  poner a otra persona en ese turno, y hasta ahora eso pedía salir de la
 *  revisión, abrir la rejilla y mirar ficha por ficha quién podía.
 *
 *  Las tres ventanas son al mismo motor y por eso van en la misma prueba: si el
 *  panel dice que hay un hueco y la rejilla no lo pinta, una de las dos miente,
 *  y esa contradicción es más fácil de introducir que cualquiera de los dos
 *  fallos por separado.
 *
 *  Se monta y se desmonta todo dentro de la prueba: la base de desarrollo es
 *  compartida y una persona dada de baja que se queda así rompe a las
 *  siguientes.
 */
import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const HOY = new Date()
const DENTRO_DE = (dias) => {
  const d = new Date(HOY)
  d.setDate(d.getDate() + dias)
  return d.toISOString().slice(0, 10)
}

test.describe('Cobertura de turnos', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  /** Crea a alguien con un turno futuro, lo da de baja, y lo limpia al salir. */
  const conUnHueco = async (page, hacer) => {
    const sufijo = Date.now().toString().slice(-6)
    const alta = await api(page, '/employees/', {
      method: 'POST',
      body: {
        email: `sevaa${sufijo}@example.com`,
        first_name: 'Cobertura',
        last_name: `Prueba ${sufijo}`,
      },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)
    const quien = alta.body.id
    const dia = DENTRO_DE(12)

    const turno = await api(page, '/shifts/', {
      method: 'POST',
      body: { employee: quien, day: dia, segments: [{ start: '08:00', end: '16:00' }] },
    })
    expect(turno.status, JSON.stringify(turno.body)).toBe(201)

    const baja = await api(page, `/employees/${quien}/`, { method: 'DELETE' })

    try {
      await hacer({ quien, dia, baja, turnoId: turno.body.id })
    } finally {
      await api(page, `/shifts/${turno.body.id}/`, { method: 'DELETE' })
    }
  }

  test('la baja dice cuántos turnos deja colgando', async ({ page }) => {
    // Ventana 3: enterarse en el momento, que es cuando se puede hacer algo.
    await irA(page, '/panel/personas', 'Personas')
    await conUnHueco(page, async ({ baja }) => {
      expect(baja.status).toBe(200)
      expect(baja.body.future_shifts, 'la baja no cuenta los turnos que deja').toBe(1)
    })
  })

  test('el panel del cuadrante lo lista con quién puede cubrirlo', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    await conUnHueco(page, async ({ dia, quien }) => {
      const cobertura = await api(page, `/shifts/coverage/?from=${dia}&to=${dia}`)
      expect(cobertura.status).toBe(200)

      const huecos = cobertura.body.uncovered
      expect(huecos.length, 'el hueco no aparece en cobertura').toBeGreaterThan(0)

      // Por persona y no solo por día: en los datos de demo ya hay alguien de
      // baja ese mismo día, y buscar por fecha cogía su hueco en vez del mío.
      // El propio fallo demuestra que el panel junta los dos motivos, que es lo
      // que tiene que hacer.
      const mio = huecos.find((h) => h.employee_id === quien)
      expect(mio, 'mi hueco no está entre los que devuelve').toBeTruthy()
      expect(mio.reason).toBe('left_the_company')
      expect(
        mio.candidates.some((c) => c.viable),
        'no ofrece a nadie que pueda cubrirlo',
      ).toBe(true)
    })
  })

  test('y un cuadrante sano no enseña el panel', async ({ page }) => {
    /** El contraste, y hace falta: sin él, todo lo de arriba pasaría igual si
     *  el panel saliera siempre y listara todos los turnos del mes. */
    await irA(page, '/panel/cuadrante', 'Cuadrante')
    const limpio = await api(
      page,
      `/shifts/coverage/?from=${DENTRO_DE(200)}&to=${DENTRO_DE(201)}`,
    )

    expect(limpio.status).toBe(200)
    expect(limpio.body.uncovered).toEqual([])
  })
})
