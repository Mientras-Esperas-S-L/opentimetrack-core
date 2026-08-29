/** El descanso que se debe por trabajar de noche, y dónde se decide (art. 36.2).
 *
 *  «El trabajo nocturno tendrá una retribución específica que se determinará en
 *  la negociación colectiva, salvo que el salario se haya establecido atendiendo
 *  a que el trabajo sea nocturno por su propia naturaleza o se haya acordado la
 *  compensación de este trabajo por descansos».
 *
 *  Tres salidas, y solo la tercera deja saldo. Cuál eligió el convenio **lo dice
 *  la empresa**, y por eso la mitad de esta prueba está en la pantalla de
 *  ajustes: la cifra existía y solo se podía poner por la API, así que el saldo
 *  salía siempre a cero sin que nadie pudiera averiguar por qué desde el
 *  producto ---y eso, para quien lo usa, es lo mismo que si no existiera---.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const elAviso = (page) => page.getByRole('alert').filter({ hasText: /descanso/i })

test.describe('La noche en el saldo de descanso', () => {
  test.describe('quien la trabaja', () => {
    test.use({ storageState: 'e2e/.sesiones/operario.json' })

    test('la ve en su saldo, con el artículo del que sale', async ({ page }) => {
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const {
        body: { rest_debt: deuda },
      } = await api(page, '/absences/balance/')

      const noche = deuda.sources.find((f) => f.source === 'night')
      expect(noche, 'la semilla ya no genera un turno de noche').toBeTruthy()
      expect(noche.citation).toBe('Art. 36.2 ET')

      await expect(elAviso(page)).toContainText('36.2')
      // Y con su nombre en cristiano, no con la clave del backend: `night` en
      // mitad de una frase en castellano es una fuga de la implementación.
      await expect(elAviso(page)).toContainText(/trabajo nocturno/i)
      await expect(elAviso(page)).not.toContainText(/\bnight\b/)
    })

    test('el artículo no da plazo, y la pantalla lo dice', async ({ page }) => {
      // No es un descuido: el art. 36.2 no pone fecha, al revés que el 35.1.
      // Enseñar «hasta el ...» inventado sería peor que no decir nada, y dejarlo
      // en blanco hace pensar que el dato falta.
      await irA(page, '/mis-ausencias', 'Mis ausencias')
      const texto = await elAviso(page).first().innerText()
      const linea = texto.split('\n').find((l) => /nocturno/i.test(l))

      expect(linea).toMatch(/sin plazo/)
      expect(linea).not.toMatch(/hasta el/)
    })
  })

  test.describe('quien la configura', () => {
    test.use({ storageState: 'e2e/.sesiones/admin.json' })

    test('elige en Ajustes cómo se compensa, y con qué multiplicador', async ({ page }) => {
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

      const cual = page.getByLabel('El trabajo nocturno se compensa')
      await expect(cual).toBeVisible()
      // Con el valor puesto, no vacío: un desplegable que no refleja lo
      // guardado hace pensar que no hay nada elegido. Pasó ---la pantalla
      // ofrecía `NIGHT_REST` y el modelo guarda `REST`--- y desde fuera se veía
      // igual que si el ajuste no se hubiera guardado nunca.
      await expect(cual).toContainText(/con descanso/i)

      const cuanto = page.getByLabel('Horas de descanso por hora de noche')
      await expect(cuanto).toBeVisible()
      await expect(cuanto).toBeEnabled()
    })

    test('las tres salidas del artículo están, no solo la que deja saldo', async ({ page }) => {
      // Un desplegable con «descanso» y nada más obliga a las otras dos empresas
      // a dejarlo en blanco, y en blanco significa «sin decidir», que no es lo
      // que les pasa.
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      await page.getByLabel('El trabajo nocturno se compensa').click()

      for (const opcion of [/con descanso/i, /plus en nómina/i, /va en el salario/i]) {
        await expect(page.getByRole('option', { name: opcion })).toBeVisible()
      }
      await page.keyboard.press('Escape')
    })

    test('el multiplicador se apaga cuando lo que se elige no deja descanso', async ({ page }) => {
      // El contraste de lo anterior: con un plus en nómina no hay horas de
      // descanso que ajustar, y un campo editable que no se usa es una promesa
      // falsa. No se guarda ---sale de la pantalla sin pasar por Guardar---.
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      await page.getByLabel('El trabajo nocturno se compensa').click()
      await page.getByRole('option', { name: /plus en nómina/i }).click()

      await expect(page.getByLabel('Horas de descanso por hora de noche')).toBeDisabled()
    })

    test('y el ajuste dice de qué artículo sale', async ({ page }) => {
      // La cita no se escribe en la pantalla: la sirve el marco legal del país,
      // que es lo que permite que una empresa de fuera vea el suyo.
      await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
      const { body: reglas } = await api(page, '/working-time-rules/')

      expect(reglas.citations.night_worked_compensation?.basis).toBe('Art. 36.2 ET')
      await expect(page.getByText(/Art\. 36\.2 ET/)).toBeVisible()
    })
  })

  test.describe('la duración que sale en pantalla', () => {
    test.use({ storageState: 'e2e/.sesiones/operario.json' })

    test('lleva el signo delante y no repartido', async ({ page }) => {
      // **El defecto que se vio abriendo la pantalla de fichar.** Un tramo
      // abierto cuya entrada quedaba por delante de la hora del servidor salía
      // como `-3:-60`: en JavaScript el resto conserva el signo del dividendo,
      // así que el menos se colaba también en los minutos. No es una hora, no es
      // una duración, y no hay forma de leerlo.
      await irA(page, '/', 'Hola')
      const casos = await page.evaluate(async () => {
        const { hhmm } = await import('/src/components/format.js')
        return [-14340, -3540, -60, 0, 3600, 36000].map((s) => hhmm(s))
      })

      expect(casos).toEqual(['−03:59', '−00:59', '−00:01', '00:00', '01:00', '10:00'])
      for (const salida of casos) {
        expect(salida, `minutos con signo: ${salida}`).not.toMatch(/:.*[-−]/)
      }
    })
  })
})
