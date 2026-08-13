import { defineConfig, devices } from '@playwright/test'

/** Pruebas de la interfaz, contra la pila de desarrollo que ya está levantada.
 *
 *  No arranca nada: da por hecho que `podman compose up` corre y que la base
 *  tiene la semilla (`manage.py seed_demo`). Es deliberado --- levantar la pila
 *  desde aquí duplicaría la receta de arranque y las dos se desincronizarían.
 *
 *  En serie y con un solo trabajador: estas pruebas escriben en la base de
 *  desarrollo, y dos a la vez tocando la misma empresa se pisan. Con una suite
 *  de este tamaño la diferencia de tiempo no compensa el ruido de una prueba
 *  que falla una de cada cinco veces.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  // Sin reintentos: aquí un fallo intermitente es información, no ruido que
  // haya que esconder repitiendo hasta que pase.
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e-report' }]],
  use: {
    baseURL: process.env.OTT_URL ?? 'http://localhost:3000',
    locale: 'es-ES',
    timezoneId: 'Europe/Madrid',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    // Para mirar lo que hacen las pruebas con los ojos, no solo el resultado:
    //
    //     OTT_SLOW_MO=350 npx playwright test --headed e2e/12-...
    //
    // Sin la variable no frena nada, así que no cuesta tiempo en las tandas
    // normales. Se mira una vez y se entiende más que leyendo veinte
    // aserciones.
    launchOptions: { slowMo: Number(process.env.OTT_SLOW_MO ?? 0) },
  },
  projects: [
    // Abre una sesión por perfil y la deja guardada. Ver 00-sesiones.setup.js:
    // la puerta de entrada está limitada a cinco por minuto, así que una suite
    // que entra en cada prueba se estrella contra su propia defensa.
    { name: 'sesiones', testMatch: /.*\.setup\.js/ },
    {
      name: 'entrada',
      testMatch: /01-entrada\.spec\.js/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium',
      testIgnore: [/01-entrada\.spec\.js/, /.*\.setup\.js/],
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['sesiones'],
    },
  ],
})
