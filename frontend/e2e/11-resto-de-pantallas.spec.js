/** Lo que quedaba sin probar: fichajes, decisiones, departamentos y lo de cada uno.
 *
 *  Cierra el barrido empezado en `07-pantallas`. Aquellas comprobaban que las
 *  pantallas cargasen limpias; estas las usan.
 *
 *  Incluye una comprobación que no es de comportamiento sino de idioma: que la
 *  paginación esté en castellano. Va aquí y no en un fichero aparte porque el
 *  fallo se ve exactamente igual que cualquier otro --- se abre Fichajes y pone
 *  «Go to next page» --- y porque una traducción que falta no la caza ningún
 *  linter ni ningún test de backend. Solo se ve mirando la pantalla.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, marca, vigilarConsola } from './apoyo.js'

/** El identificador de quien se llama así, preguntándoselo al servidor.
 *
 *  La pantalla enseña nombres y la API filtra por identificador, y escribirlo a
 *  mano en la prueba lo ata a una semilla concreta: en cuanto se resiembra, el
 *  identificador es otro.
 */
async function idDe(page, nombre) {
  const { status, body } = await api(page, `/employees/?search=${encodeURIComponent(nombre)}`)
  expect(status).toBe(200)
  expect(body.results.length, `no hay nadie que se llame ${nombre}`).toBeGreaterThan(0)
  return body.results[0].id
}

test.describe('Fichajes', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('filtra por persona y por fechas', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/fichajes', 'Fichajes')

    // Las filas llegan con la consulta, no con la pantalla. Contar antes de
    // que respondan da cero y la prueba falla contando su propia prisa.
    const filas = () => page.getByRole('row').filter({ hasNotText: 'Origen' })
    await expect(filas().first()).toBeVisible()

    await page.getByRole('combobox', { name: /Persona/ }).fill('Hugo')
    await page.getByRole('option', { name: /Hugo Bermejo/ }).click()

    // La pantalla **retiene las filas de antes** mientras llega la respuesta
    // filtrada ---`placeholderData: (previous) => previous`, y está bien que lo
    // haga: evita el parpadeo en blanco---. Así que esperar por reloj y contar
    // era una carrera: 900 ms bastaban casi siempre y fallaban cuando la API
    // tardaba más, y el fallo salía como «filtrar no quitó nada», acusando al
    // producto de un defecto que no tenía. Se espera por la condición.
    // **No** «quedan menos filas»: con una persona elegida la pantalla trae el
    // periodo entero en vez de la primera página ---la unidad que se lee ahí es
    // la jornada, y partirla era el defecto que arregló `44-el-dia-no-se-parte`
    // ---, así que filtrar puede acabar enseñando **más** filas que la vista
    // sin filtrar. Contar filas medía el tamaño de la página, no el filtro.
    //
    // Se mide contra lo que el servidor dice que tiene esa persona, que es la
    // única vara que no cambia con la paginación.
    // Con el mismo rango que tiene puesto la pantalla: preguntar por todos sus
    // fichajes daba su histórico entero ---106--- contra los 66 del mes que se
    // está viendo, y el desajuste parecía un fallo de la tabla.
    const desde = await page.getByLabel('Desde').inputValue()
    const hasta = await page.getByLabel('Hasta').inputValue()
    const rango = [
      `employee=${await idDe(page, 'Hugo')}`,
      desde && `date_from=${desde}`,
      hasta && `date_to=${hasta}`,
    ]
      .filter(Boolean)
      .join('&')

    const losDeHugo = await api(page, `/punches/?${rango}`)
    expect(losDeHugo.status).toBe(200)
    expect(losDeHugo.body.count, 'Hugo no tiene fichajes en el periodo').toBeGreaterThan(0)

    // Las filas incluyen el encabezado de cada día, así que son unas cuantas
    // más que los fichajes; lo que se comprueba es que están **todos**, no que
    // la tabla se quedó en la primera página.
    await expect
      .poll(() => filas().count(), { message: 'la tabla no acabó de traer los suyos' })
      .toBeGreaterThanOrEqual(losDeHugo.body.count)

    // Filtrado por una persona, la columna «Persona» desaparece: repetir el
    // mismo nombre en cada fila no informa de nada. Está bien pensado, y por
    // eso la prueba comprueba **eso** y no que cada fila lleve el nombre.
    await expect(page.getByRole('columnheader', { name: 'Persona' })).toHaveCount(0)

    // Y que de verdad sean los suyos, que por pantalla ya no se puede leer.
    // Comprobar solo el 200 no decía nada: un filtro que ignora el término
    // devuelve 200 con la empresa entera. Se mira lo que trae.
    const suyos = await api(page, '/punches/?search=Hugo')
    expect(suyos.status).toBe(200)
    const nombres = new Set(
      (suyos.body.results ?? suyos.body).map((p) => p.employee_name ?? p.employee),
    )
    expect(nombres.size, 'el filtro trajo fichajes de más de una persona').toBe(1)

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })

  test('no queda nada en inglés en los mandos de MUI', async ({ page }) => {
    await irA(page, '/panel/fichajes', 'Fichajes')

    // Los rótulos que MUI pone por su cuenta venían en inglés: «Go to next
    // page» en la paginación y «Clear» / «Open» en el buscador de personas. No
    // se ven ---son `aria-label`--- y por eso aguantaron sin que nadie los
    // reportara: los lee quien navega con lector de pantalla o deja el ratón
    // encima, que es justo la persona a la que peor le viene otro idioma.
    //
    // Se comprueban aquí los tres a la vez porque el arreglo es uno solo: el
    // paquete de español aplicado al tema. Si alguien lo quita, esto cae.
    await expect(page.getByRole('button', { name: /Go to|^page \d|^Clear$|^Open$/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Ir a la página siguiente' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Abrir' })).toBeVisible()
  })

  test('un fichaje se corrige de uno en uno, nunca en bloque', async ({ page }) => {
    await irA(page, '/panel/fichajes', 'Fichajes')

    // No es una limitación pendiente de arreglar: es el art. 4.b. Corregir
    // asientos del registro en masa es lo que la norma quiere impedir, así que
    // si algún día aparece aquí una casilla de «seleccionar todo», esta prueba
    // tiene que ponerse roja y obligar a discutirlo.
    await expect(page.getByRole('checkbox')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Corregir' }).first()).toBeVisible()
  })
})

test.describe('Por decidir', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('las cinco colas se abren y cuentan lo que enseñan', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/decisiones', 'Por decidir')

    for (const cola of [
      'Ausencias',
      'Fichajes',
      'Sin acuerdo',
      'Horas extra',
      'Vacaciones por recuperar',
    ]) {
      const pestaña = page.getByRole('tab', { name: new RegExp(`^${cola}`) })
      await expect(pestaña, `falta la cola de ${cola}`).toBeVisible()
      // El número tarda lo que tarde su consulta; sin esperarlo se lee el
      // rótulo a medias y la prueba se queja de que no lleva contador.
      await expect(pestaña).toContainText(/\d/)

      // El número del rótulo es el que hay que creerse: es lo que decide si
      // alguien entra a mirar. Una cola que dice 22 y enseña 0 es peor que no
      // tener el número.
      //
      // El `\+?` no es adorno: el contador es un Badge de MUI y por encima de
      // su tope pinta «125+». Sin contemplarlo, el número no casaba, salía -1 y
      // la prueba decía «no lleva contador» de una pestaña que sí lo llevaba.
      const rotulo = await pestaña.innerText()
      const cuantas = Number(rotulo.match(/(\d+)\+?\s*$/)?.[1] ?? -1)
      expect(cuantas, `la cola de ${cola} no lleva su contador`).toBeGreaterThanOrEqual(0)

      await pestaña.click()
      // Sin espera: la única aserción que sigue es un `toBeVisible`, que ya
      // reintenta hasta el plazo. El reloj solo hacía la tanda más lenta.
      if (cuantas === 0) {
        // Vacía se explica, no se queda en blanco.
        await expect(page.getByText(/no hay|nada|ninguna|al día/i).first()).toBeVisible()
      }
    }

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })
})

test.describe('Departamentos', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('alta con responsable, y mientras lo tenga no se ofrece borrarlo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const nombre = `Depto ${marca()}`

    await irA(page, '/panel/departamentos', 'Departamentos')
    await page.getByRole('button', { name: 'Nuevo' }).click()

    const dialogo = page.getByRole('dialog')
    await dialogo.getByRole('textbox', { name: /^Nombre/ }).fill(nombre)
    await dialogo.getByRole('combobox', { name: /Quién lo lleva/ }).fill('Ana')
    await page.getByRole('option', { name: /Ana García/ }).click()
    await dialogo.getByRole('button', { name: /Guardar|Crear/ }).click()
    await expect(dialogo).toBeHidden()

    await page.reload()
    const fila = page.getByRole('listitem').filter({ hasText: nombre })
    await expect(fila).toBeVisible()
    await expect(fila).toContainText('0 personas')

    // Vacío de gente pero no de mando, y eso basta para no ofrecerlo: retirar
    // el departamento de quien lo dirige la deja «al mando de nada», y eso
    // **amplía** lo que puede leer a toda la empresa. El servidor lo rechaza
    // con 409, así que un botón aquí sería proponer algo que va a fallar.
    await expect(
      fila.getByRole('button', { name: new RegExp(`Eliminar el departamento ${nombre}`) }),
    ).toHaveCount(0)

    // La vía correcta: primero se le quita el mando, y entonces sí.
    const creado = (await api(page, `/departments/?search=${encodeURIComponent(nombre)}`)).body
    const id = (creado?.results ?? creado ?? [])[0]?.id
    expect(id, 'no se encontró el departamento recién creado').toBeTruthy()
    const sinMando = await api(page, `/departments/${id}/`, {
      method: 'PATCH',
      body: { managers: [] },
    })
    expect(sinMando.status).toBe(200)

    await page.reload()
    const otraVez = page.getByRole('listitem').filter({ hasText: nombre })
    await otraVez
      .getByRole('button', { name: new RegExp(`Eliminar el departamento ${nombre}`) })
      .click()
    const confirmacion = page.getByRole('dialog')
    if (await confirmacion.isVisible().catch(() => false)) {
      await confirmacion.getByRole('button', { name: /Eliminar|Confirmar/ }).click()
    }
    await expect(page.getByRole('listitem').filter({ hasText: nombre })).toHaveCount(0)

    expect(ruido()).toEqual([])
  })

  test('el que tiene gente dentro no ofrece borrarse', async ({ page }) => {
    await irA(page, '/panel/departamentos', 'Departamentos')

    // Borrar uno con gente los dejaría sin responsable y sin alcance de un
    // plumazo. El botón sencillamente no está, que es mejor que estar y fallar.
    for (const fila of await page.getByRole('listitem').all()) {
      const texto = await fila.innerText()
      if (/\b0 personas\b/.test(texto)) continue
      await expect(
        fila.getByRole('button', { name: 'Eliminar' }),
        `«${texto.split('\n')[0]}» tiene gente y ofrece borrarse`,
      ).toHaveCount(0)
    }
  })
})

test.describe('Lo de cada uno', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('los recordatorios se apagan y se quedan apagados', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mi-jornada', 'Mi jornada')

    const interruptor = () => page.getByLabel('Recordatorios')
    const antes = await interruptor().isChecked()

    await interruptor().click()
    await page.waitForTimeout(700)
    await page.reload()
    await expect(interruptor()).toBeChecked({ checked: !antes })

    // Se deja como estaba: la preferencia es de esa persona y las demás
    // pruebas comparten la misma cuenta.
    await interruptor().click()
    await page.waitForTimeout(700)
    await expect(interruptor()).toBeChecked({ checked: antes })

    expect(ruido()).toEqual([])
  })

  test('un operario ve su registro pero no puede descargarlo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/actividad', 'Registro de actividad')

    // Ve quién ha mirado su ficha ---eso es suyo y el producto se lo enseña a
    // propósito--- pero el volcado completo es de gestión.
    await expect(page.getByRole('button', { name: 'Descargar' })).toHaveCount(0)

    await page.getByLabel('Desde').fill('2026-08-01')
    await page.getByLabel('Hasta').fill('2026-08-13')
    await page.waitForTimeout(600)
    expect(await huecosVisibles(page)).toEqual([])

    expect(ruido()).toEqual([])
  })

  test('un operario no ve ni por API lo que no es suyo', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    // Sin pantalla de gestión y sin permiso por debajo: las dos cosas, porque
    // esconder el menú no impide escribir la dirección.
    for (const ruta of ['/employees/', '/applications/']) {
      const respuesta = await api(page, ruta)
      expect([403, 404], `${ruta} respondió ${respuesta.status}`).toContain(respuesta.status)
    }

    // `/audit/` sí responde, y está bien: es su propio registro de accesos
    // ---quién ha mirado su ficha--- y el producto se lo enseña a propósito.
    // Lo que hay que sostener es que solo salga lo suyo.
    const mio = await api(page, '/audit/')
    expect(mio.status).toBe(200)
    const yo = await api(page, '/auth/me/')
    const soyYo = yo.body.user?.id ?? yo.body.id
    const mias = mio.body?.results ?? mio.body ?? []
    for (const linea of mias) {
      const sobreMi = linea.target_id === soyYo || linea.actor === soyYo
      expect(sobreMi, `una línea del registro no le incumbe: ${JSON.stringify(linea)}`).toBe(true)

      // Y ninguna línea lleva dirección IP, de nadie. Antes sí la llevaba y se
      // tapaba enseñándosela solo a quien administraba o a quien había actuado
      // desde ella; ahora no se guarda, porque la tabla es inmutable y una IP
      // guardada ahí no se podía borrar ni para atender una solicitud del art.
      // 17. Se comprueba que el campo no está, no que venga vacío: vacío era la
      // solución vieja.
      expect(
        Object.keys(linea).some((clave) => clave.toLowerCase().includes('ip')),
        `el registro vuelve a traer una dirección: ${JSON.stringify(linea)}`,
      ).toBe(false)
    }
  })
})

test.describe('Tema claro y oscuro', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('las tres opciones están, y la elegida sobrevive a la recarga', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // Tres opciones, no dos: un interruptor de dos posiciones pierde la única
    // respuesta que acierta sin preguntar, la del sistema.
    await page.getByRole('button', { name: 'Cambiar entre claro y oscuro' }).click()
    for (const opcion of ['El del sistema', 'Claro', 'Oscuro']) {
      await expect(page.getByRole('menuitem', { name: opcion })).toBeVisible()
    }

    await page.getByRole('menuitem', { name: 'Oscuro' }).click()
    const guardado = () => page.evaluate(() => localStorage.getItem('ott.theme'))
    expect(await guardado()).toBe('dark')

    // Que sobreviva a la recarga es la mitad que importa: un tema que se
    // reinicia en cada visita es peor que no poder cambiarlo.
    await page.reload()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await guardado()).toBe('dark')

    // Y que de verdad esté oscuro, no solo apuntado: el fondo del cuerpo es
    // lo que se ve, y comprobar la preferencia sin comprobar el color dejaría
    // pasar un tema que se guarda y no se aplica.
    const fondo = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    const [r, g, b] = fondo.match(/\d+/g).map(Number)
    expect((r + g + b) / 3, `el fondo no es oscuro: ${fondo}`).toBeLessThan(90)

    await page.getByRole('button', { name: 'Cambiar entre claro y oscuro' }).click()
    await page.getByRole('menuitem', { name: 'El del sistema' }).click()
  })
})
