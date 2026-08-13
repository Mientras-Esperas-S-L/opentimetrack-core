/** Lo que comparten todas las pruebas de interfaz.
 *
 *  Dan por hecho la pila de desarrollo levantada y la semilla puesta:
 *
 *      podman compose up -d
 *      podman exec opentimetrack_api_1 python manage.py seed_demo --reset
 *
 *  La semilla es fija (`SEED` en el comando), así que dos ejecuciones producen
 *  la misma empresa. Aun así, todo lo que estas pruebas crean lleva un sufijo
 *  irrepetible: una prueba que solo pasa con la base recién sembrada es una
 *  prueba que nadie vuelve a ejecutar.
 */

import { expect } from '@playwright/test'

export const CLAVE = 'demo-password-2026'

/** Las dos empresas de la semilla. La vecina existe para una sola cosa: que se
 *  pueda intentar entrar en ella con identificadores suyos. */
export const EMPRESA = {
  propia: {
    nombre: 'Jardines Demo S.L.',
    admin: 'admin@demo.local',
    responsable: 'manager@demo.local',
    operario: 'operario@demo.local',
  },
  vecina: {
    nombre: 'Vecina S.L.',
    admin: 'admin@vecina.local',
    operario: 'operario@vecina.local',
  },
}

/** Un sufijo distinto en cada ejecución, para que crear no choque con lo de
 *  ayer. Sin esto, la segunda vuelta falla por «ya existe» y se acaba
 *  ejecutando la suite solo tras sembrar. */
export const marca = () => `p${Date.now().toString().slice(-7)}`

/** Entra por el formulario, como una persona.
 *
 *  Por el formulario y no metiendo un testigo en el almacenamiento: la mitad de
 *  lo que hay que probar --- que la sesión se restablece, que el perfil decide
 *  el menú --- ocurre justo en ese camino.
 */
export async function entrar(page, correo, clave = CLAVE) {
  await page.goto('/')
  // El navegador rellena solo el último correo usado, así que se vacía antes.
  const email = page.getByLabel('Correo electrónico')
  await email.fill('')
  await email.fill(correo)
  await page.getByLabel('Contraseña').fill(clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 })
}

export async function salir(page) {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
}

/** El testigo de la sesión abierta, para hablar con la API desde la prueba. */
export const testigo = (page) => page.evaluate(() => localStorage.getItem('ott.access'))

/** Llama a la API con la sesión de la página. Devuelve `{status, body}`.
 *
 *  Es lo que permite comprobar la seguridad de verdad: la interfaz puede
 *  esconder un botón, y eso no prueba nada. Lo que prueba algo es que el
 *  servidor diga que no cuando alguien llama directamente.
 */
export async function api(page, ruta, opciones = {}) {
  return page.evaluate(
    async ([ruta, opciones]) => {
      const token = localStorage.getItem('ott.access')
      const respuesta = await fetch(`http://localhost:8000/api${ruta}`, {
        method: opciones.method ?? 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: opciones.body ? JSON.stringify(opciones.body) : undefined,
      })
      let body = null
      try {
        body = await respuesta.json()
      } catch {
        body = null
      }
      return { status: respuesta.status, body }
    },
    [ruta, opciones],
  )
}

/** Abre una pantalla del panel y espera a que su título esté puesto. */
export async function irA(page, ruta, titulo) {
  await page.goto(ruta)
  await expect(page.getByRole('heading', { name: titulo, level: 1 })).toBeVisible()
}

/** El aviso de error que la pantalla enseña, si hay alguno.
 *
 *  Por rol y no por clase de MUI: `MuiAlert-outlinedError` dejó de existir en
 *  MUI 9 --- ahora son dos clases, `MuiAlert-colorError` y `MuiAlert-outlined`
 *  --- y una prueba atada al nombre de una clase interna falla en la
 *  actualización siguiente sin que nada se haya roto. */
export const errorVisible = (page) => page.getByRole('alert').filter({ hasText: /./ })

/** Igual que `api`, pero deliberadamente **sin** cabecera de autorización.
 *
 *  Para el caso «sin sesión»: crear un contexto nuevo no basta, porque las
 *  opciones de `test.use` se heredan y el contexto llega con la sesión puesta.
 *  Lo que prueba algo aquí es la petición desnuda.
 */
export async function apiSinSesion(page, ruta) {
  return page.evaluate(async (ruta) => {
    const respuesta = await fetch(`http://localhost:8000/api${ruta}`)
    return { status: respuesta.status }
  }, ruta)
}
