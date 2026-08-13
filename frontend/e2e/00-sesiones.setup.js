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

import { CLAVE, EMPRESA } from './apoyo.js'

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
  const renovado = await page.evaluate(async (r) => {
    const respuesta = await fetch('http://localhost:8000/api/auth/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: r }),
    })
    if (!respuesta.ok) return null
    const datos = await respuesta.json()
    localStorage.setItem('ott.access', datos.access)
    localStorage.setItem('ott.refresh', datos.refresh)
    return datos.access
  }, refresco)

  return Boolean(renovado)
}

for (const { perfil, correo } of SESIONES) {
  setup(`sesión de ${perfil}`, async ({ page }) => {
    mkdirSync(CARPETA, { recursive: true })
    const fichero = `${CARPETA}/${perfil}.json`

    if (!(await siguenValiendo(page, fichero))) {
      await page.goto('/')
      const email = page.getByLabel('Correo electrónico')
      await email.fill('')
      await email.fill(correo)
      await page.getByLabel('Contraseña').fill(CLAVE)
      await page.getByRole('button', { name: 'Entrar' }).click()
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
