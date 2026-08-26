/** Entrar y recuperar el acceso.
 *
 *  Es la única pantalla que ve alguien que todavía no es nadie, y la única
 *  contra la que se prueba desde fuera. Dos cosas importan aquí y ninguna se ve
 *  a simple vista: que no diga qué correos existen, y que lo que dice cuando
 *  algo va mal se entienda.
 *
 *  Sesión limpia en todo el fichero: `storageState` vacío. Sin eso las pruebas
 *  heredan la sesión del proyecto y comprueban una puerta ya abierta.
 *
 *  **Este fichero va el último a propósito.** La última prueba agota el límite
 *  de cinco intentos por minuto, que va por dirección IP y es el mismo que usa
 *  el arranque de sesiones. Cualquier fichero que corra después ---y los
 *  ficheros van por orden alfabético--- se encontraría la puerta cerrada y
 *  fallaría sin tener la culpa. Si hace falta añadir uno detrás, que sea un
 *  `18-…` que no necesite entrar, o mueve esta prueba a su propio fichero al
 *  final del orden.
 */

import { expect, test } from '@playwright/test'

import { API, vigilarConsola } from './apoyo.js'

test.use({ storageState: { cookies: [], origins: [] } })

/** Una petición desnuda, sin la sesión de nadie. */
async function pedir(page, ruta, cuerpo) {
  return page.evaluate(
    async ([ruta, cuerpo, api]) => {
      const respuesta = await fetch(`${api}${ruta}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo),
      })
      return { status: respuesta.status, cuerpo: await respuesta.text() }
    },
    [ruta, cuerpo, API],
  )
}

test('no dice qué correos existen', async ({ page }) => {
  await page.goto('/entrar')

  // Recuperar la contraseña de una cuenta que existe y de una que no tiene que
  // dar exactamente lo mismo. Cualquier diferencia ---el código, el cuerpo, un
  // «no encontrado»--- convierte el formulario en un comprobador de plantillas:
  // se prueban mil correos y se sabe quién trabaja aquí.
  const existe = await pedir(page, '/auth/password-reset/', { email: 'admin@demo.local' })
  const noExiste = await pedir(page, '/auth/password-reset/', {
    email: 'no-existe-en-absoluto@demo.local',
  })

  expect(existe.status).toBe(204)
  expect(noExiste.status).toBe(existe.status)
  expect(noExiste.cuerpo).toBe(existe.cuerpo)
})

test('el error de entrar es el mismo se equivoque en lo que se equivoque', async ({ page }) => {
  await page.goto('/entrar')

  const claveMala = await pedir(page, '/auth/token/', {
    email: 'admin@demo.local',
    password: 'esta-no-es-la-buena',
  })
  const nadie = await pedir(page, '/auth/token/', {
    email: 'no-existe-en-absoluto@demo.local',
    password: 'esta-no-es-la-buena',
  })

  expect(claveMala.status).toBe(400)
  expect(nadie.status).toBe(claveMala.status)
  expect(nadie.cuerpo).toBe(claveMala.cuerpo)
  expect(claveMala.cuerpo).toContain('Credenciales incorrectas')
})

test('sin sesión, una pantalla de gestión pide entrar', async ({ page }) => {
  const ruido = vigilarConsola(page)
  await page.goto('/panel/personas')

  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  await expect(page.getByLabel('Contraseña *')).toBeVisible()
  // Y nada de la pantalla que se pedía se cuela por detrás.
  await expect(page.getByText('Dar de alta')).toHaveCount(0)

  expect(ruido()).toEqual([])
})

test('los campos se rellenan solos como toca', async ({ page }) => {
  await page.goto('/entrar')

  // `autocomplete` no es decoración: sin él los gestores de contraseñas no
  // ofrecen la cuenta, y quien tiene una contraseña larga y única acaba
  // poniéndose una corta que se sepa de memoria.
  await expect(page.getByLabel('Correo electrónico *')).toHaveAttribute('autocomplete', 'username')
  await expect(page.getByLabel('Contraseña *')).toHaveAttribute('autocomplete', 'current-password')
})

test('recuperar la contraseña se explica y se vuelve atrás', async ({ page }) => {
  const ruido = vigilarConsola(page)
  await page.goto('/entrar')

  await page.getByRole('button', { name: 'He olvidado mi contraseña' }).click()
  await expect(page.getByText('Recupera el acceso a tu cuenta.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Enviarme un enlace' })).toBeVisible()

  // Y se puede desandar: entrar aquí por error no puede ser un callejón.
  await page.getByRole('button', { name: 'Volver a entrar con mi contraseña' }).click()
  await expect(page.getByLabel('Contraseña *')).toBeVisible()

  expect(ruido()).toEqual([])
})

test('al agotar los intentos lo dice en castellano y con el plazo', async ({ page }) => {
  await page.goto('/entrar')

  // Cinco por minuto. El sexto se rechaza, y lo que se leía era la traducción
  // automática de DRF: «Solicitud fue regulada (throttled). Se espera que esté
  // disponible en 58 segundos.» Sin artículo, con una palabra en inglés entre
  // paréntesis, y en el peor momento --- lo lee quien acaba de fallar cinco
  // veces la contraseña.
  for (let intento = 1; intento <= 6; intento += 1) {
    await page.getByLabel('Correo electrónico *').fill('admin@demo.local')
    await page.getByLabel('Contraseña *').fill(`no-es-la-buena-${intento}`)
    await page.getByRole('button', { name: 'Entrar' }).click()
    await page.waitForTimeout(450)
  }

  const aviso = page.getByRole('alert').first()
  await expect(aviso).toContainText('Demasiados intentos')
  // Con el plazo, que es lo único accionable: saber si esperar o irse a por
  // café. La versión de DRF lo daba, y eso sí valía la pena conservarlo.
  await expect(aviso).toContainText(/en \d+ (segundos|minutos?)/)
  await expect(aviso).not.toContainText('throttled')
})
