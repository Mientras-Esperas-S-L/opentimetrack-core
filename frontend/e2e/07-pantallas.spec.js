/** Todas las pantallas, con la consola escuchando.
 *
 *  Esta es la prueba que había que escribir antes que ninguna otra, y se ve en
 *  el historial del 13/08: casi todos los fallos que aparecieron probando a
 *  mano **ya estaban gritando en la consola** antes de que nadie los viera.
 *
 *  - El campo del cuadrante que pintaba «undefined» avisaba en cada render.
 *  - Dos personas con el mismo nombre daban «two children with the same key».
 *  - La consulta del consumo de permisos devolvía indefinido y React Query lo
 *    decía por consola --- el aviso de «llevas X de Y» no se enseñó nunca.
 *
 *  Tres de tres, visibles sin abrir la pantalla siquiera. Así que aquí se
 *  recorre todo lo que hay, con cada perfil, y **un `console.error` es un
 *  fallo de la prueba**. No es exagerado: si no hay que arreglarlo, hay que
 *  callarlo, porque una consola con ruido de fondo es una consola que nadie
 *  mira, y el día que aparezca lo grave estará entre lo demás.
 *
 *  También se comprueba que la pantalla no enseñe literalmente `undefined`,
 *  `NaN` ni `[object Object]`, que es cómo se ve un dato que no llegó.
 */

import { expect, test } from '@playwright/test'

import { huecosVisibles, vigilarConsola } from './apoyo.js'

const DE_GESTION = [
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/departamentos', 'Departamentos'],
  ['/panel/centros', 'Centros de trabajo'],
  ['/panel/calendario', 'Calendario del equipo'],
  ['/panel/cuadrante', 'Cuadrante'],
  ['/panel/turnos', 'Turnos'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/fichajes', 'Fichajes'],
  ['/panel/decisiones', 'Por decidir'],
  ['/panel/informes', 'Informes'],
  ['/panel/aplicaciones', 'Aplicaciones'],
  ['/panel/ajustes', 'Ajustes de la empresa'],
]

const DE_CADA_UNO = [
  ['/', 'Hola'],
  ['/mi-jornada', 'Mi jornada'],
  ['/mis-ausencias', 'Mis ausencias'],
  ['/actividad', 'Registro de actividad'],
]

/** Peticiones con basura en la URL.
 *
 *  `queryFn: getDepartments` en vez de `queryFn: () => getDepartments()` hace
 *  que React Query pase su propio contexto como parámetros de consulta, y la
 *  petición sale como
 *  `/departments/?client=[object Object]&queryKey[]=departments&signal=...`.
 *
 *  No rompe nada mientras DRF ignore lo que no conoce, y por eso estuvo ahí sin
 *  que nadie lo viera hasta que apareció en una consola. Se vigila en todas las
 *  pantallas porque el fallo se escribe en un renglón y se repite solo: la
 *  forma correcta y la incorrecta se diferencian en seis caracteres.
 */
function vigilarUrls(page) {
  const sucias = []
  page.on('request', (peticion) => {
    const url = peticion.url()
    if (!url.includes('/api/')) return
    if (/[?&](client|queryKey|signal|meta)(\[|=)/.test(url)) {
      sucias.push(url.split('/api')[1].slice(0, 120))
    }
  })
  return () => sucias
}

function recorrer(perfil, sesion, pantallas) {
  test.describe(`Pantallas · ${perfil}`, () => {
    test.use({ storageState: sesion })

    for (const [ruta, titulo] of pantallas) {
      test(`${ruta} carga limpia`, async ({ page }) => {
        const ruido = vigilarConsola(page)
        const urls = vigilarUrls(page)

        await page.goto(ruta)
        await expect(page.getByRole('heading', { level: 1 })).toContainText(titulo)
        // Un respiro para que entren las consultas: media pantalla pinta
        // después de su respuesta, y los avisos salen entonces.
        await page.waitForLoadState('networkidle').catch(() => {})
        await page.waitForTimeout(600)

        expect(ruido(), `la consola se quejó en ${ruta}`).toEqual([])
        expect(urls(), `peticiones con el contexto de React Query dentro`).toEqual([])
        expect(await huecosVisibles(page), `hay datos sin llegar en ${ruta}`).toEqual([])
        // Y ninguna pantalla arranca con un error rojo puesto.
        await expect(
          page.getByRole('alert').filter({ hasText: /no se pudo|error|inválid/i }),
        ).toHaveCount(0)
      })
    }
  })
}

recorrer('administración', 'e2e/.sesiones/admin.json', [...DE_GESTION, ...DE_CADA_UNO])
recorrer('responsable', 'e2e/.sesiones/responsable.json', [
  ['/panel', 'Resumen'],
  ['/panel/personas', 'Personas'],
  ['/panel/calendario', 'Calendario del equipo'],
  ['/panel/cuadrante', 'Cuadrante'],
  ['/panel/permisos', 'Permisos'],
  ['/panel/decisiones', 'Por decidir'],
  ...DE_CADA_UNO,
])
recorrer('operario', 'e2e/.sesiones/operario.json', DE_CADA_UNO)

test.describe('Lo que solo pide un navegador de verdad', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('el icono de la pestaña y el manifiesto existen', async ({ page }) => {
    // Salió mirando una tanda **con ventana**, y no podía salir de otra forma:
    // Chrome sin ventana no pide el favicon, así que la suite entera estaba en
    // verde mientras cada visita real se llevaba un 404 y una pestaña con el
    // globo genérico. En una aplicación que se deja abierta todo el día entre
    // otras veinte, la pestaña se busca por el icono.
    //
    // Se piden a mano porque aquí tampoco los pedirá el navegador.
    await page.goto('/')

    for (const recurso of [
      '/favicon.svg',
      '/favicon.ico',
      '/manifest.webmanifest',
      '/icono-192.png',
      '/icono-maskable-512.png',
    ]) {
      const respuesta = await page.request.get(recurso)
      expect(respuesta.status(), `falta ${recurso}`).toBe(200)
    }
  })

  test('el manifiesto promete solo iconos que existen', async ({ page }) => {
    // Un manifiesto que nombra ficheros que no están instala la aplicación con
    // un cuadrado en blanco, y no lo dice: el navegador se lo calla.
    await page.goto('/')
    const manifiesto = await (await page.request.get('/manifest.webmanifest')).json()

    expect(manifiesto.name).toBeTruthy()
    expect(manifiesto.icons.length).toBeGreaterThan(0)
    for (const icono of manifiesto.icons) {
      const respuesta = await page.request.get(icono.src)
      expect(respuesta.status(), `el manifiesto nombra ${icono.src} y no está`).toBe(200)
    }
  })
})
