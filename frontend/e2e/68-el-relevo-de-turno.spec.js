/** El descanso que se debe por un relevo de turno (art. 19.a RD 1561/1995).
 *
 *  «Cuando el trabajador cambie de turno de trabajo y no pueda disfrutar del
 *  descanso mínimo entre jornadas [...] se podrá reducir el mismo, en el día en
 *  que así ocurra, hasta un mínimo de siete horas, **compensándose la diferencia
 *  hasta las doce horas** establecidas con carácter general en los días
 *  inmediatamente siguientes.»
 *
 *  Dos pantallas y una corrección. El cuadrante avisaba del descanso corto y
 *  decía que se devolvía **en cuatro semanas**: esas son del apartado b, que es
 *  del descanso semanal, y dan mucho más margen del que la norma concede aquí.
 *  Y el saldo no llevaba la cuenta, así que la otra mitad del artículo ---la que
 *  obliga a devolverlo--- no se cumplía desde el producto.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const elSaldo = (page) => page.getByRole('alert').filter({ hasText: /descanso/i })

/** Seis semanas hacia atrás y dos hacia delante.
 *
 *  La semilla coloca el relevo la semana pasada ---esquivando el festivo, así
 *  que puede caer dos o tres atrás--- y la pantalla del cuadrante abre en el mes
 *  en curso. Una ventana de un mes lo dejaría fuera según el día en que se
 *  ejecute la tanda, que es la peor clase de prueba: la que va y viene.
 */
function ventana() {
  const hoy = new Date()
  const dia = (offset) => {
    const d = new Date(hoy)
    d.setDate(d.getDate() + offset)
    return d.toISOString().slice(0, 10)
  }
  return { desde: dia(-42), hasta: dia(14) }
}

test.describe('El relevo de turno en el saldo', () => {
  test.describe('quien rota entre equipos', () => {
    test.use({ storageState: 'e2e/.sesiones/rotativo.json' })

    test('lo ve en su saldo, con el artículo del RD', async ({ page }) => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const {
        body: { rest_debt: deuda },
      } = await api(page, '/absences/balance/')

      const relevo = deuda.sources.find((f) => f.source === 'changeover')
      expect(relevo, 'la semilla ya no ficha un relevo de turno').toBeTruthy()
      expect(relevo.citation).toBe('Art. 19.a RD 1561/1995')

      await expect(elSaldo(page)).toContainText('19.a')
      // Con su nombre en cristiano, no con la clave del backend.
      await expect(elSaldo(page)).toContainText(/relevos de turno/i)
      await expect(elSaldo(page)).not.toContainText(/\bchangeover\b/)
    })

    test('«en los días siguientes», que no es «sin plazo»', async ({ page }) => {
      // **La corrección de esta vuelta, en pantalla.** El art. 19.a no da una
      // fecha, pero exige devolverlo en los días inmediatamente siguientes: es
      // más estricto que cualquier fecha, no menos. Leerlo como «sin plazo»
      // ---que es lo que le pasa al festivo trabajado--- daría la impresión
      // contraria a la que da el artículo.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const texto = await elSaldo(page).first().innerText()
      const linea = texto.split('\n').find((l) => /relevos de turno/i.test(l))

      expect(linea).toMatch(/en los días siguientes/)
      expect(linea).not.toMatch(/sin plazo/)
      expect(linea).not.toMatch(/hasta el/)
    })

    test('y el saldo tiene más de una fuente, cada una con lo suyo', async ({ page }) => {
      // El desglose sólo aparece con dos o más, y esta persona hace noches
      // además de rotar: es el caso que obliga a que cada línea diga su plazo.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const texto = await elSaldo(page).first().innerText()
      const lineas = texto.split('\n').filter((l) => /^\d/.test(l))

      expect(lineas.length).toBeGreaterThan(1)
      for (const linea of lineas) {
        expect(linea, `sin artículo: ${linea}`).toMatch(/Art\./)
        expect(linea, `sin estado de plazo: ${linea}`).toMatch(
          /hasta el|sin plazo|fuera de plazo|en los días siguientes/,
        )
      }
    })
  })

  test.describe('quien no rota', () => {
    test.use({ storageState: 'e2e/.sesiones/operario.json' })

    test('no tiene relevos en su saldo', async ({ page }) => {
      // El contraste. Un descanso corto de quien no rota es el art. 34.3 a
      // secas: un incumplimiento, no una excepción con deuda.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const {
        body: { rest_debt: deuda },
      } = await api(page, '/absences/balance/')

      expect(deuda.sources.map((f) => f.source)).not.toContain('changeover')
      await expect(elSaldo(page)).not.toContainText('19.a')
    })
  })

  test.describe('quien revisa el cuadrante', () => {
    test.use({ storageState: 'e2e/.sesiones/admin.json' })

    test('el aviso ya no promete cuatro semanas que el artículo no da', async ({ page }) => {
      // **El defecto que motivó la vuelta.** El aviso citaba el plazo del
      // apartado b ---cuatro semanas, del descanso semanal--- como si fuera el
      // del a. Dos apartados del mismo artículo, y el que se citaba da mucho
      // más margen.
      await irA(page, '/panel/cuadrante', 'Cuadrante')
      const { desde, hasta } = ventana()
      const { body: revision } = await api(page, `/shifts/review/?from=${desde}&to=${hasta}`)
      const avisos = (revision.findings ?? []).filter((f) => f.code === 'changeover_rest_owed')

      expect(avisos.length, 'la semilla ya no planifica un relevo de turno').toBeGreaterThan(0)
      for (const aviso of avisos) {
        expect(aviso.message).toMatch(/días siguientes|days that follow/)
        expect(aviso.message, 'sigue prometiendo cuatro semanas').not.toMatch(/4 semanas|4 weeks/)
        expect(aviso.citation ?? aviso.basis).toContain('19.a')
      }
    })

    test('y está en castellano, como el resto de la pantalla', async ({ page }) => {
      // Al reescribir el texto, la traducción quedó huérfana y el aviso salía
      // en inglés en mitad de una pantalla en castellano. Se vio abriéndola.
      await irA(page, '/panel/cuadrante', 'Cuadrante')
      const { desde, hasta } = ventana()
      const { body: revision } = await api(page, `/shifts/review/?from=${desde}&to=${hasta}`)
      const aviso = (revision.findings ?? []).find((f) => f.code === 'changeover_rest_owed')

      expect(aviso.message, 'el aviso salió sin traducir').not.toMatch(/of rest at a shift/)
    })
  })
})
