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

/** Dónde está la API, para las llamadas que estas pruebas hacen a pelo.
 *
 *  Parametrizada como `baseURL` en la configuración, y por el mismo motivo: los
 *  puertos del compose se pueden mover para convivir con otra pila, y una suite
 *  que solo sabe hablar con el 8000 deja de servir justo cuando alguien usa esa
 *  posibilidad. Peor: no falla diciendo «no encuentro la API», falla en el
 *  arranque de sesión con un `null` en el almacén, que no señala a ninguna
 *  parte.
 *
 *      OTT_URL=http://localhost:3010 OTT_API_URL=http://localhost:8100/api \
 *          npx playwright test
 */
export const API = process.env.OTT_API_URL ?? 'http://localhost:8000/api'

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
    async ([ruta, opciones, api]) => {
      const token = localStorage.getItem('ott.access')
      const respuesta = await fetch(`${api}${ruta}`, {
        method: opciones.method ?? 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: opciones.body ? JSON.stringify(opciones.body) : undefined,
      })
      let body
      try {
        body = await respuesta.json()
      } catch {
        body = null
      }
      return { status: respuesta.status, body }
    },
    [ruta, opciones, API],
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
  return page.evaluate(
    async ([ruta, api]) => {
      const respuesta = await fetch(`${api}${ruta}`)
      return { status: respuesta.status }
    },
    [ruta, API],
  )
}

/** Da de baja a las personas que una prueba creó.
 *
 *  De baja, no borradas: la API no borra a nadie ---los fichajes viven cuatro
 *  años--- y un ayudante que prometiera otra cosa mentiría. Con esto dejan de
 *  salir en las listas, que es lo que hace falta para que la base de
 *  desarrollo no acabe enseñando «Prueba De Playwright» junto a la plantilla
 *  real.
 *
 *  Lo que quede de verdad se limpia a mano al resembrar (`seed_demo --reset`).
 */
export async function darDeBajaLasDePrueba(page, sufijo) {
  const encontradas = await api(page, `/employees/?search=${sufijo}&is_active=true`)
  for (const persona of encontradas.body?.results ?? []) {
    await api(page, `/employees/${persona.id}/`, { method: 'DELETE' })
  }
}

/** Lo que la consola dice y no cuenta como fallo del producto.
 *
 *  Cada línea lleva su motivo: una lista de excepciones que crece sin
 *  justificarse acaba tapando justo lo que había que ver.
 */
const RUIDO_DE_CONSOLA = [
  /\[vite\]/, // recarga en caliente del servidor de desarrollo
  /Download the React DevTools/,
  // Avisos de rendimiento de Chrome, no errores: saltan porque en desarrollo
  // React va sin compilar y algún manejador tarda de más.
  /\[Violation\]/,
  // Lo emite MUI al abrir un diálogo, por cómo React 19 devuelve el foco.
  // Es de la biblioteca y no hay nada nuestro que tocar.
  /Blocked aria-hidden on an element/,
]

/** Empieza a vigilar la consola, y devuelve con qué se quejó.
 *
 *  El motivo de que esto exista está en el historial del 13/08: de los fallos
 *  que aparecieron probando a mano, tres ---el `undefined` del cuadrante, las
 *  dos personas con la misma clave de React, la consulta de permisos que
 *  devolvía indefinido--- **ya estaban en la consola** antes de que nadie
 *  abriera la pantalla. Escucharla es la prueba más barata que hay.
 *
 *  Se llama antes de `goto`, porque lo que se pierde no se recupera:
 *
 *      const ruido = vigilarConsola(page)
 *      await irA(page, '/panel/centros', 'Centros de trabajo')
 *      ...
 *      expect(ruido()).toEqual([])
 */
export function vigilarConsola(page) {
  const problemas = []
  page.on('console', (mensaje) => {
    if (mensaje.type() !== 'error' && mensaje.type() !== 'warning') return
    const texto = mensaje.text()
    if (!RUIDO_DE_CONSOLA.some((patron) => patron.test(texto))) {
      problemas.push(`${mensaje.type()}: ${texto.slice(0, 240)}`)
    }
  })
  page.on('pageerror', (error) => problemas.push(`excepción: ${error.message.slice(0, 240)}`))
  return () => problemas
}

/** Los datos que no llegaron y se ven en pantalla.
 *
 *  Los tres primeros van con límite de palabra ---«NaN» dentro de «Fernández»
 *  no es un hueco, ni «null» dentro de «anulado»---. El cuarto va como texto
 *  literal a propósito: sus corchetes lo convierten en una clase de caracteres,
 *  y `\b[object Object]\b` casa con cualquier letra suelta de la pantalla. Con
 *  esa versión el primer barrido dio 29 pantallas en rojo, todas por el fallo
 *  de la prueba.
 */
export async function huecosVisibles(page) {
  const texto = await page.locator('body').innerText()
  const huecos = ['undefined', 'NaN', 'null'].filter((señal) =>
    new RegExp(`\\b${señal}\\b`).test(texto),
  )
  if (texto.includes('[object Object]')) huecos.push('[object Object]')
  return huecos
}
