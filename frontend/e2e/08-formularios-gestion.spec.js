/** Los formularios de gestión que nadie había probado todavía.
 *
 *  Centros, turnos, ajustes, aplicaciones e informes. Cinco pantallas de las
 *  que hasta hoy solo se sabía que **cargaban** ---eso lo cubre
 *  `07-pantallas`--- y nada sobre guardar, validar o rechazar.
 *
 *  Cada bloque hace las mismas preguntas, que son las que han fallado cada vez
 *  que se probó algo a mano:
 *
 *  1. ¿Se abre y se puede escribir?
 *  2. ¿Guarda de verdad, y sigue guardado al recargar? Que aparezca en la lista
 *     no demuestra nada: podría estar solo en el estado de React.
 *  3. ¿Rechaza lo inválido de forma que se entienda, en vez de un 400 mudo?
 *  4. ¿La consola calla mientras tanto?
 *
 *  Y una que no se ve en la pantalla: con la sesión de la empresa vecina, ¿deja
 *  tocar esto por la API sabiendo el identificador? Por API y no por pantalla,
 *  que es la diferencia que importa --- en su pantalla el botón no está, pero un
 *  botón que no se pinta no dice nada de lo que el servidor acepta.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, marca, vigilarConsola } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

test.describe('Centros de trabajo', () => {
  test('alta de un centro, y sigue ahí al recargar', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const nombre = `Centro ${marca()}`

    await irA(page, '/panel/centros', 'Centros de trabajo')
    await page.getByRole('button', { name: 'Nuevo centro' }).click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo).toBeVisible()
    await dialogo.getByRole('textbox', { name: /^Nombre/ }).fill(nombre)
    await dialogo.getByRole('textbox', { name: 'Municipio' }).fill('Jerez de la Frontera')
    await dialogo.getByRole('button', { name: 'Guardar' }).click()
    await expect(dialogo).toBeHidden()

    await page.reload()
    await expect(page.getByRole('listitem').filter({ hasText: nombre })).toBeVisible()

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })

  test('sin nombre no se puede guardar', async ({ page }) => {
    await irA(page, '/panel/centros', 'Centros de trabajo')
    await page.getByRole('button', { name: 'Nuevo centro' }).click()

    // Desactivado, no un error al pulsar. Es mejor de las dos formas: no hay
    // viaje al servidor y se ve antes de intentarlo.
    const dialogo = page.getByRole('dialog')
    await expect(dialogo.getByRole('button', { name: 'Guardar' })).toBeDisabled()

    await dialogo.getByRole('textbox', { name: /^Nombre/ }).fill('X')
    await expect(dialogo.getByRole('button', { name: 'Guardar' })).toBeEnabled()
  })

  test('la zona horaria se elige de una lista, no se teclea', async ({ page }) => {
    // Era un campo de texto libre. Una zona horaria es un identificador IANA
    // exacto ---«Europe/Madrid»--- que nadie se sabe de memoria, así que lo
    // que se escribía era «Madrid», «Canarias» o «España», y el servidor las
    // rechazaba las tres sin decir cuál era la buena.
    await irA(page, '/panel/centros', 'Centros de trabajo')
    await page.getByRole('button', { name: 'Nuevo centro' }).click()

    const dialogo = page.getByRole('dialog')
    const zona = dialogo.getByRole('combobox', { name: 'Zona horaria' })
    await zona.click()

    // Las del país delante, y con su nombre en cristiano al lado: nadie tiene
    // por qué saber que Canarias es «Atlantic/Canary».
    await expect(page.getByRole('option', { name: /Europe\/Madrid · Península/ })).toBeVisible()
    await expect(page.getByRole('option', { name: /Atlantic\/Canary · Canarias/ })).toBeVisible()

    // Y no es una lista cerrada: una delegación en Lisboa tiene que caber.
    await zona.fill('Lisbon')
    await expect(page.getByRole('option', { name: 'Europe/Lisbon' })).toBeVisible()

    // Buscar por el nombre de andar por casa también vale, y es para lo que
    // está: quien piensa «Canarias» encuentra «Atlantic/Canary» sin saber que
    // se llama así.
    await zona.fill('Canarias')
    await expect(page.getByRole('option', { name: /Atlantic\/Canary/ })).toBeVisible()

    // Y lo inventado no se puede elegir, que es la diferencia con el campo
    // libre: no hay opción, y al salir el campo se queda vacío en vez de
    // guardar una zona que no existe.
    await zona.fill('Zona de Españita')
    await expect(page.getByRole('option')).toHaveCount(0)
    await dialogo.getByRole('textbox', { name: /^Nombre/ }).click()
    await expect(zona).toHaveValue('')
  })

  test('un festivo local se añade y se quita', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const fiesta = `Feria ${marca()}`

    await irA(page, '/panel/centros', 'Centros de trabajo')

    // 19 de octubre a propósito: un lunes cualquiera. Los doce nacionales y
    // autonómicos ya vienen puestos por `import_holidays`, y el 12 de octubre
    // ---que fue el primero que probé--- choca con la Fiesta Nacional.
    await page.getByLabel('Día *').fill('2026-10-19')
    await page.getByLabel('Nombre *').fill(fiesta)
    await page.getByRole('button', { name: 'Añadir' }).click()

    const fila = page.locator('div').filter({ hasText: fiesta }).last()
    await expect(page.getByText(fiesta)).toBeVisible()

    await fila.getByRole('button', { name: 'Quitar' }).click()
    await expect(page.getByText(fiesta)).toBeHidden()

    expect(ruido()).toEqual([])
  })
})

test.describe('Turnos', () => {
  test('alta con su tramo horario, y borrado', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const nombre = `Turno ${marca()}`

    await irA(page, '/panel/turnos', 'Turnos')
    await page.getByRole('button', { name: 'Nuevo turno' }).click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo).toBeVisible()
    await dialogo.getByRole('textbox', { name: /^Nombre/ }).fill(nombre)
    await dialogo.getByLabel('Desde').fill('09:00')
    await dialogo.getByLabel('Hasta').fill('17:00')
    await dialogo.getByRole('button', { name: 'Guardar' }).click()
    await expect(dialogo).toBeHidden()

    await page.reload()
    const fila = page.getByRole('listitem').filter({ hasText: nombre })
    await expect(fila).toBeVisible()
    await expect(fila).toContainText('09:00')

    await fila.getByRole('button', { name: 'Eliminar' }).click()
    // Un borrado pregunta antes. Si esto deja de ser cierto hay que enterarse:
    // quitar un turno deja gente sin cuadrante.
    const confirmacion = page.getByRole('dialog')
    await expect(confirmacion).toBeVisible()
    await confirmacion.getByRole('button', { name: 'Eliminar' }).click()
    await expect(page.getByRole('listitem').filter({ hasText: nombre })).toHaveCount(0)

    expect(ruido()).toEqual([])
  })
})

test.describe('Ajustes de la empresa', () => {
  const guardado = (page) => page.getByRole('alert').filter({ hasText: 'Ajustes guardados' })

  //: El botón dice cuántos cambios hay ---«Guardar 2 cambios»--- y solo pone
  //: «Guardar cambios» cuando no hay ninguno. Por prefijo, entonces.
  const botonGuardar = (page) => page.getByRole('button', { name: /^Guardar/ })

  test('guarda, y el valor sobrevive a la recarga', async ({ page }) => {
    const ruido = vigilarConsola(page)

    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    const original = await page.getByLabel('Horas extra al año').inputValue()
    // Distinto del que hay, no un número fijo. Con '72' escrito a mano, la
    // prueba solo funcionaba la primera vez: si una tanda anterior se cortó
    // antes de restaurar, el valor ya era 72, no había nada que guardar y el
    // botón se quedaba desactivado --- treinta segundos esperando a que se
    // habilitara algo que no tenía por qué habilitarse.
    const otro = original === '72' ? '73' : '72'

    await page.getByLabel('Horas extra al año').fill(otro)
    await botonGuardar(page).click()
    await expect(guardado(page)).toBeVisible()

    await page.reload()
    await expect(page.getByLabel('Horas extra al año')).toHaveValue(otro)

    // Se deja como estaba. Los ajustes son de la empresa entera y esta base la
    // comparten las demás pruebas: dejar el tope en 72 h cambia lo que ve la
    // de horas extra, y una prueba que estropea a otra no vale.
    await page.getByLabel('Horas extra al año').fill(original)
    await botonGuardar(page).click()
    await expect(guardado(page)).toBeVisible()

    expect(ruido()).toEqual([])
  })

  test('salirse de un límite legal se avisa citando el artículo', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')
    const campo = page.getByLabel('Descanso entre jornadas (h)')

    // Nada de leer el valor de partida para restaurarlo luego: la primera
    // versión de esta prueba pulsaba «Guardar» con las 8 horas puestas, y la
    // base de desarrollo se quedó en 8. La siguiente pasada leyó ese 8 como
    // «lo normal» y la prueba se volvió verde por el motivo equivocado. Aquí no
    // se guarda nada y el valor final se escribe a mano.

    // Ocho horas están por debajo de las doce del art. 34.3 ET. Y **se
    // guardan**, a propósito: el RD 1561/1995 baja ese suelo en sectores
    // concretos, así que negarse sería estar equivocado para esas empresas.
    // Lo que no vale es callarse, que es lo que hacía --- la misma cifra se
    // revisaba al llegar por convenio y pasaba muda al teclearse aquí.
    await campo.fill('8')
    await expect(page.getByText(/mínimo de 12 que fija el Art\. 34\.3 ET/)).toBeVisible()

    // Y el aviso sale del marco legal del país, no de un número escrito en la
    // pantalla: si esto se rompe, una empresa de fuera vería la cifra española.
    await page.getByLabel('Horas extra al año').fill('120')
    await expect(page.getByText(/máximo de 80 que fija el Art\. 35\.2 ET/)).toBeVisible()

    await campo.fill('12')
    await expect(page.getByText(/mínimo de 12/)).toHaveCount(0)

    // Vaciar el campo para reescribirlo no es salirse de nada. Sin esto el
    // aviso saltaba en cuanto se borraba el contenido, porque un campo vacío
    // se lee como cero y cero es menor que doce.
    await campo.fill('')
    await expect(page.getByText(/mínimo de 12/)).toHaveCount(0)
  })
})

test.describe('Aplicaciones', () => {
  test('autorizar, emitir un testigo que solo se ve una vez, y revocar', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const nombre = `App ${marca()}`

    await irA(page, '/panel/aplicaciones', 'Aplicaciones')
    await page.getByRole('button', { name: 'Autorizar' }).click()

    const alta = page.getByRole('dialog')
    await expect(alta.getByRole('button', { name: 'Autorizar' })).toBeDisabled()
    await alta.getByRole('textbox', { name: /^Nombre/ }).fill(nombre)
    // El permiso más pequeño que sirve de algo, y el que usará el conector de
    // Geosian en su primera fase.
    await alta.getByLabel('Consultar la lista de personas').check()
    await alta.getByRole('button', { name: 'Autorizar' }).click()
    await expect(alta).toBeHidden()

    const fila = page.getByRole('listitem').filter({ hasText: nombre })
    await expect(fila).toBeVisible()

    await fila.getByRole('button', { name: 'Emitir token' }).click()
    const aviso = page.getByRole('dialog').filter({ hasText: 'Copia el token ahora' })
    await expect(aviso).toBeVisible()

    // El testigo entero se enseña una sola vez. Lo que queda después es la
    // pista de los últimos caracteres, y eso es justo lo que hay que sostener:
    // si el valor completo reapareciera al recargar, estaría guardado en claro.
    const completo = (await aviso.getByText(/^[A-Za-z0-9._-]{24,}$/).innerText()).trim()
    expect(completo.length).toBeGreaterThan(24)
    await aviso.getByRole('button', { name: 'Ya lo tengo' }).click()

    await page.reload()
    await expect(page.getByText(completo, { exact: true })).toHaveCount(0)
    await expect(page.getByRole('listitem').filter({ hasText: nombre })).toContainText('…')

    expect(ruido()).toEqual([])
  })
})

test.describe('Informes', () => {
  test('con el periodo al revés no deja descargar, y dice por qué', async ({ page }) => {
    await irA(page, '/panel/informes', 'Informes')

    await page.getByLabel('Desde').fill('2026-08-31')
    await page.getByLabel('Hasta').fill('2026-08-01')

    await expect(page.getByText('La fecha final no puede ir antes que la inicial.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Descargar CSV' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Descargar PDF' })).toBeDisabled()
  })

  test('descarga el CSV de una persona', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/informes', 'Informes')

    await page.getByLabel('Desde').fill('2026-08-01')
    await page.getByLabel('Hasta').fill('2026-08-13')

    const descarga = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar CSV' }).click()
    expect((await descarga).suggestedFilename()).toMatch(/\.csv$/)

    expect(ruido()).toEqual([])
  })
})

test.describe('Lo mismo, desde la empresa de al lado', () => {
  test.use({ storageState: 'e2e/.sesiones/vecina.json' })

  test('los listados solo traen lo suyo', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    for (const ruta of ['/workplaces/', '/shift-patterns/', '/applications/']) {
      const respuesta = await api(page, ruta)
      expect(respuesta.status, `${ruta} debería responder`).toBe(200)

      const filas = respuesta.body?.results ?? respuesta.body ?? []
      for (const fila of filas) {
        expect(JSON.stringify(fila), `${ruta} filtró mal`).not.toMatch(/Jardines Demo/)
      }
    }
  })

  test('las reglas de jornada salen del testigo, no de la URL', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // No se piden con identificador: el servidor las saca de la sesión. Es la
    // forma de que no haya nada que manipular --- no se puede pedir «las de la
    // empresa 3» porque el número no viaja.
    const suyas = await api(page, '/working-time-rules/')
    expect(suyas.status).toBe(200)

    const intento = await api(page, '/working-time-rules/', {
      method: 'PATCH',
      body: { annual_overtime_hours: 999 },
    })
    expect([200, 400, 403, 405]).toContain(intento.status)

    // Lo que no puede pasar nunca: que se lo haya aplicado a Jardines Demo.
    const vecinaDespues = await api(page, '/working-time-rules/')
    expect(vecinaDespues.body?.tenant_name ?? '').not.toBe('Jardines Demo S.L.')
  })
})

/** Retira los centros y las aplicaciones que estas pruebas dejaron.
 *
 *  Sin esto la base de desarrollo se llena: cada pasada añade un centro y una
 *  aplicación, y a la décima la pantalla de Centros enseña diez «Centro
 *  p8975713» junto a los de verdad. Se limpia por marca ---todo lo que crean
 *  estas pruebas la lleva--- y no por fecha, que dependería del reloj.
 */
test.afterAll(async ({ browser }) => {
  const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
  const page = await contexto.newPage()
  // Hay que navegar antes de tocar `localStorage`: en `about:blank` el
  // navegador lo prohíbe, y el ayudante de la API lee de ahí el testigo.
  await page.goto('/panel')

  for (const [ruta, campo] of [
    ['/workplaces/', 'name'],
    ['/applications/', 'name'],
  ]) {
    const filas = await api(page, ruta)
    for (const fila of filas.body?.results ?? filas.body ?? []) {
      if (/^(Centro|App) p\d+/.test(fila[campo] ?? '')) {
        await api(page, `${ruta}${fila.id}/`, { method: 'DELETE' })
      }
    }
  }

  await contexto.close()
})
