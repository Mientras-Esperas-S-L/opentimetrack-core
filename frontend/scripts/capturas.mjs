/** Las capturas del dossier comercial, generadas y no coleccionadas.
 *
 *  Un dossier de producto sin pantallas es una tabla de funcionalidades, y una
 *  carpeta de capturas hechas a mano envejece: al tercer cambio de interfaz
 *  enseña algo que ya no existe, y nadie se entera porque las mira marketing y
 *  no quien programa.
 *
 *  Así que se generan. Corre contra la empresa de demostración ---jardinería,
 *  catorce personas, datos inventados--- así que **no sale ningún dato real**,
 *  y eso no es casualidad: es la única base contra la que esto puede correr.
 *
 *  Hacen falta las sesiones de la suite. Si no están:
 *
 *      npx playwright test 00-sesiones
 *
 *  Y luego:
 *
 *      node scripts/capturas.mjs            # a scripts/capturas/
 *
 *  Las imágenes no se versionan ---están en `.gitignore`--- porque el sitio
 *  donde viven es el dossier, incrustadas. Lo que se versiona es esto: la
 *  receta para volver a hacerlas.
 *
 *  Y hace falta la demostración limpia. Las tandas de pruebas dejan cientos de
 *  fichajes en la misma empresa, así que si las capturas salen con entradas y
 *  salidas repetidas a la misma hora, lo que toca antes es:
 *
 *      python manage.py seed_demo --reset   # en el contenedor de la API
 */

import { chromium } from '@playwright/test'
import { mkdir, readdir } from 'node:fs/promises'
import { join } from 'node:path'

const URL_BASE = process.env.OTT_URL ?? 'http://localhost:3010'
const SESIONES = 'e2e/.sesiones'
const DESTINO = 'scripts/capturas'

/** Qué se enseña, y por qué esa y no otra.
 *
 *  Cinco, no quince: un dossier con una captura por pantalla se lee como un
 *  manual. Cada una responde a una pregunta distinta de quien decide comprar.
 */
const CAPTURAS = [
  {
    nombre: 'fichar',
    sesion: 'operario',
    ruta: '/',
    espera: 'Hola,',
    porque: 'El producto en una imagen: un botón y la hora del servidor.',
  },
  {
    nombre: 'registro',
    sesion: 'admin',
    ruta: '/panel/fichajes',
    espera: 'Fichajes',
    porque: 'Cada fichaje con su origen, y las correcciones señaladas.',
  },
  {
    nombre: 'por-decidir',
    sesion: 'admin',
    ruta: '/panel/decisiones',
    espera: 'Por decidir',
    porque: 'Las cinco colas de lo que espera respuesta.',
  },
  {
    nombre: 'cuadrante',
    sesion: 'admin',
    ruta: '/panel/cuadrante',
    espera: 'Cuadrante',
    porque: 'Lo previsto, que es contra lo que se compara lo trabajado.',
  },
  {
    nombre: 'informes',
    sesion: 'admin',
    ruta: '/panel/informes',
    espera: 'Informes',
    porque: 'El documento que se entrega a la Inspección, y qué lleva dentro.',
  },
]

const navegador = await chromium.launch()
await mkdir(DESTINO, { recursive: true })

const sesiones = new Set(
  (await readdir(SESIONES).catch(() => [])).map((f) => f.replace('.json', '')),
)
for (const { sesion } of CAPTURAS) {
  if (!sesiones.has(sesion)) {
    console.error(`Falta ${SESIONES}/${sesion}.json. Corre antes: npx playwright test 00-sesiones`)
    process.exit(1)
  }
}

for (const { nombre, sesion, ruta, espera, porque } of CAPTURAS) {
  const contexto = await navegador.newContext({
    storageState: join(SESIONES, `${sesion}.json`),
    viewport: { width: 1280, height: 820 },
    // Al doble, y luego se reduce: una captura al tamaño justo se ve borrosa
    // en cuanto el documento la escala.
    deviceScaleFactor: 2,
    // Claro y no «lo que diga el sistema»: la máquina que las genera no tiene
    // por qué estar en el mismo tema que el documento.
    colorScheme: 'light',
    locale: 'es-ES',
  })
  const pagina = await contexto.newPage()
  await pagina.goto(`${URL_BASE}${ruta}`)

  // Una sesión caducada no da error: devuelve la pantalla de entrar, y sin
  // esto lo que se ve es medio minuto de espera y un timeout que no dice por
  // qué. Las sesiones duran poco y esto pasa a diario.
  if (await pagina.getByRole('button', { name: 'Entrar' }).count()) {
    console.error(
      `La sesión de «${sesion}» ha caducado: ${ruta} devuelve la pantalla de entrar.\n` +
        'Regenéralas con: npx playwright test 00-sesiones',
    )
    process.exit(1)
  }

  await pagina.getByRole('heading', { name: espera, level: 1 }).first().waitFor()
  // Que la red se calme: media captura con los esqueletos de carga puestos es
  // exactamente lo que no se quiere enseñar.
  await pagina.waitForLoadState('networkidle').catch(() => {})
  await pagina.waitForTimeout(900)

  const fichero = join(DESTINO, `${nombre}.png`)
  await pagina.screenshot({ path: fichero })
  await contexto.close()
  console.log(`${fichero}  ${porque}`)
}

await navegador.close()
console.log(`\n${CAPTURAS.length} capturas en ${DESTINO}/. Optimizar antes de incrustarlas.`)
