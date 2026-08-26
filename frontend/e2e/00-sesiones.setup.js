/** Abre una sesión por perfil y la guarda, para que el resto no vuelva a entrar.
 *
 *  No es una optimización, es lo que hace que la suite pase: `/api/auth/token/`
 *  está limitado a cinco por minuto **y con razón** --- es la puerta contra la
 *  que se prueban contraseñas. Con una entrada por prueba, de la sexta en
 *  adelante todo fallaba con 429 y el fallo parecía de la aplicación.
 *
 *  Y reutiliza la sesión de la vuelta anterior si sigue viva, porque el
 *  arranque se repite en cada ejecución: sin esto, lanzar la suite dos veces
 *  seguidas gastaba ocho entradas en un minuto y volvía a chocar con el mismo
 *  límite. La sesión dura siete días, así que en la práctica se entra una vez
 *  al día.
 *
 *  Las pruebas que van *sobre* la entrada (`01-entrada.spec.js`) siguen usando
 *  el formulario: ahí lo que se prueba es justamente eso.
 */

import { existsSync, mkdirSync, readFileSync } from 'node:fs'

import { expect, test as setup } from '@playwright/test'

import { API, CLAVE, EMPRESA } from './apoyo.js'

const CARPETA = 'e2e/.sesiones'

const SESIONES = [
  { perfil: 'admin', correo: EMPRESA.propia.admin },
  { perfil: 'responsable', correo: EMPRESA.propia.responsable },
  { perfil: 'operario', correo: EMPRESA.propia.operario },
  { perfil: 'vecina', correo: EMPRESA.vecina.admin },
]

/** ¿Sirve todavía lo guardado? Se comprueba contra el servidor, no por la fecha
 *  del fichero: un token puede estar caducado, invalidado o de una base que se
 *  volvió a sembrar. */
async function siguenValiendo(page, fichero) {
  if (!existsSync(fichero)) return false

  let guardado
  try {
    guardado = JSON.parse(readFileSync(fichero, 'utf8'))
  } catch {
    return false
  }
  const almacen = guardado.origins?.[0]?.localStorage ?? []
  const acceso = almacen.find((x) => x.name === 'ott.access')?.value
  const refresco = almacen.find((x) => x.name === 'ott.refresh')?.value
  if (!acceso || !refresco) return false

  await page.goto('/')
  await page.evaluate(
    ([a, r]) => {
      localStorage.setItem('ott.access', a)
      localStorage.setItem('ott.refresh', r)
    },
    [acceso, refresco],
  )

  // Por el refresco y no por el acceso: el acceso dura quince minutos, así que
  // preguntar por él daría «no vale» casi siempre y volveríamos a entrar.
  const renovado = await page.evaluate(
    async ([r, api]) => {
      const respuesta = await fetch(`${api}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: r }),
      })
      if (!respuesta.ok) return null
      const datos = await respuesta.json()
      localStorage.setItem('ott.access', datos.access)
      localStorage.setItem('ott.refresh', datos.refresh)
      return datos.access
    },
    [refresco, API],
  )

  return Boolean(renovado)
}

for (const { perfil, correo } of SESIONES) {
  setup(`sesión de ${perfil}`, async ({ page }) => {
    // Margen para esperar a que se reponga el cupo de intentos. El límite es de
    // un minuto, así que con los treinta de serie no daba tiempo ni a un
    // reintento.
    setup.setTimeout(120_000)
    mkdirSync(CARPETA, { recursive: true })
    const fichero = `${CARPETA}/${perfil}.json`

    if (!(await siguenValiendo(page, fichero))) {
      // Se limpia lo que dejó el intento anterior: `siguenValiendo` inyecta los
      // testigos viejos para probarlos, y si no valían la aplicación arranca
      // con ellos, tarda en darse cuenta y enseña el panel un instante --- con
      // lo que el formulario de entrada no está donde se le espera.
      await page.goto('/')
      await page.evaluate(() => localStorage.clear())
      await page.goto('/')

      // Con reintento si el cupo de intentos está lleno.
      //
      // El límite es de cinco por minuto **y va por dirección IP**, así que lo
      // comparten todas las sesiones y también la prueba que lo agota a
      // propósito en `17-la-puerta`. Dos tandas seguidas ---algo que pasa solo
      // en cuanto hay un bucle de auditoría--- encontraban la puerta cerrada y
      // fallaba el arranque, no la aplicación.
      //
      // Esperar es lo correcto: el cupo se repone en un minuto y aquí no hay
      // prisa. Fallar dejaría toda la tanda en rojo por algo que se arregla
      // solo.
      for (let intento = 0; intento < 4; intento += 1) {
        const email = page.getByLabel('Correo electrónico')
        await email.fill('')
        await email.fill(correo)
        await page.getByLabel('Contraseña').fill(CLAVE)
        await page.getByRole('button', { name: 'Entrar' }).click()
        await page.waitForTimeout(800)

        const puesto = await page.evaluate(() => localStorage.getItem('ott.access'))
        if (puesto) break

        const aviso = await page
          .getByRole('alert')
          .first()
          .innerText()
          .catch(() => '')
        if (!/Demasiados intentos/.test(aviso)) break

        // Lo que el propio aviso dice que falta, más un segundo de cortesía.
        // Esperar un plazo fijo era adivinar: demasiado corto no sirve y
        // demasiado largo agota el tiempo de la prueba.
        const faltan = Number(aviso.match(/en (\d+) segundos/)?.[1] ?? 30)
        await page.waitForTimeout((faltan + 1) * 1000)
      }
    }

    // Hasta que el testigo esté puesto: sin esto se guardaría un estado vacío y
    // las pruebas siguientes empezarían sin sesión, fallando por todas partes
    // con un motivo que no tiene nada que ver.
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem('ott.access')), { timeout: 15_000 })
      .toBeTruthy()

    await page.context().storageState({ path: fichero })
  })
}
