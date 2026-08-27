/** Los filtros que faltaban, y el aviso de lo que está sin guardar.
 *
 *  Cierra la lista de la revisión de interfaz del 13/08. Cada uno responde a
 *  una pregunta concreta que antes no se podía hacer:
 *
 *  - Fichajes: «¿cuáles registró el terminal?», «¿cuáles hizo una aplicación en
 *    su nombre?». El origen era una columna que se enseñaba y no se podía usar
 *    para buscar, y esas dos son justo las que la Inspección mira primero.
 *  - Actividad: «¿qué ha hecho esta persona?».
 *  - Mis ausencias: «¿las de este año?», con tres años de antigüedad detrás.
 *  - Calendario: «¿quién tiene vacaciones en agosto?» sin el resto encima.
 *
 *  Y en Ajustes, diecinueve campos con un solo botón: qué se ha tocado.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, vigilarConsola } from './apoyo.js'

test.describe('Fichajes', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('filtra por tipo y por origen', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/fichajes', 'Fichajes')

    const filas = () => page.getByRole('row').filter({ hasNotText: 'Origen' })
    await expect(filas().first()).toBeVisible()

    // El total, no las filas de la página: la lista viene paginada de cincuenta
    // en cincuenta, así que filtrar a la mitad deja igualmente cincuenta a la
    // vista. Contar la página habría dado verde con el filtro desconectado.
    const cuantos = async (consulta) => (await api(page, `/punches/${consulta}`)).body?.count ?? 0
    const todos = await cuantos('?date_from=2026-08-01&date_to=2026-08-13')

    await page.getByRole('combobox', { name: 'Tipo' }).click()
    await page.getByRole('option', { name: 'Entrada' }).click()

    // Filtrado a entradas, no puede quedar ninguna salida en pantalla.
    //
    // Como «no hay ninguna que incumpla» y no recorriendo las filas: un
    // `for (const fila of await filas().all())` itera **una foto** tomada
    // cuando se pidió, así que sin la espera por reloj de antes recorría las
    // filas viejas ---y con ella, las recorría casi siempre---. Un locator
    // filtrado reintenta hasta el plazo, que es lo que se quería decir.
    await expect(filas().filter({ hasText: 'Salida' })).toHaveCount(0)
    // Y que no pasó por quedarse vacía: sin esto un grid en blanco lo cumple.
    await expect(filas().first()).toBeVisible()

    expect(await cuantos('?date_from=2026-08-01&date_to=2026-08-13&punch_type=IN')).toBeLessThan(
      todos,
    )

    // Y el origen, que es lo que se enseñaba sin poder buscarse.
    await page.getByRole('combobox', { name: 'Tipo' }).click()
    await page.getByRole('option', { name: 'Todos' }).click()
    await page.getByRole('combobox', { name: 'Origen' }).click()
    await page.getByRole('option', { name: 'Móvil' }).click()

    await expect(filas().filter({ hasNotText: 'Móvil' })).toHaveCount(0)
    await expect(filas().first()).toBeVisible()

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })
})

test.describe('Registro de actividad', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('filtra por quién lo hizo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/actividad', 'Registro de actividad')

    await page.getByRole('combobox', { name: /Quién/ }).fill('Ana')
    await page.getByRole('option', { name: /Ana García/ }).click()
    await page.waitForTimeout(1200)

    // Lo que quede tiene que ser suyo. Se comprueba contra el servidor porque
    // la pantalla agrupa y no siempre repite el nombre en cada línea.
    const yo = await api(page, '/employees/?search=Ana%20Garc')
    const ana = (yo.body?.results ?? [])[0]
    const filtrado = await api(page, `/audit/?actor=${ana.id}`)
    expect(filtrado.status).toBe(200)
    for (const linea of filtrado.body?.results ?? []) {
      expect(linea.actor).toBe(ana.id)
    }

    expect(ruido()).toEqual([])
  })
})

test.describe('Mis ausencias', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('filtra por año y por estado, y el vacío no miente', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mis-ausencias', 'Mis ausencias')

    // Un año sin nada. El mensaje de vacío tiene que decir que **no coincide**,
    // no que no haya solicitado ninguna: lo segundo sería mentira, y una que
    // se cree, porque el filtro está arriba y el mensaje abajo.
    await page.getByRole('combobox', { name: 'Año' }).click()
    await page.getByRole('option', { name: '2024', exact: true }).click()
    await page.waitForTimeout(1000)

    const vacio = page.getByText(/Ninguna ausencia coincide|Todavía no has solicitado/)
    if (await vacio.isVisible().catch(() => false)) {
      await expect(vacio).toContainText('Ninguna ausencia coincide')
    }

    await page.getByRole('combobox', { name: 'Año' }).click()
    await page.getByRole('option', { name: '2026', exact: true }).click()
    await page.getByRole('combobox', { name: 'Estado' }).click()
    await page.getByRole('option', { name: 'Aprobada' }).click()
    await page.waitForTimeout(1000)

    const mias = await api(page, '/absences/?year=2026&status=APPROVED')
    expect(mias.status).toBe(200)
    for (const fila of mias.body?.results ?? []) {
      expect(fila.status).toBe('APPROVED')
      expect(fila.start_date.startsWith('2026')).toBe(true)
    }

    expect(ruido()).toEqual([])
  })
})

test.describe('Calendario del equipo', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('filtra por tipo y por estado, con el número exacto', async ({ page }) => {
    /** Esta prueba comprobaba `personas().count() <= todas`, con el comentario
     *  «o quedan menos filas o el mes no tenía de ese tipo; lo que no vale es
     *  que no cambie nada nunca». Y eso es justo lo que dejaba pasar: con el
     *  filtro **desconectado** el conteo no cambia, y «no cambia» cumple
     *  `<=`. La aserción admitía el defecto que venía a impedir.
     *
     *  Ahora se cuenta contra los datos que la propia pantalla trajo. El
     *  filtrado es en el cliente sobre una sola petición ---se ve en
     *  `TeamCalendar.jsx`: `todo.filter(...)`--- así que el número esperado se
     *  puede calcular exactamente, y de paso no hace falta esperar ninguna
     *  respuesta: lo que hay que esperar es el repintado, y de eso ya se
     *  encarga `toHaveCount`.
     */
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/calendario', 'Calendario del equipo')

    // Por el rol, no por descarte de texto: la fila de cabecera lleva los
    // números del mes y el `hasNotText: 'lun'` de antes no la excluía ---por eso
    // salían nueve filas para ocho personas---. Una fila de persona es la que
    // tiene su nombre como cabecera de fila.
    const personas = () => page.getByRole('row').filter({ has: page.getByRole('rowheader') })

    // El mes que la pantalla está mirando al abrirse, que es el corriente.
    const hoy = new Date()
    const dosCifras = (n) => String(n).padStart(2, '0')
    const desde = `${hoy.getFullYear()}-${dosCifras(hoy.getMonth() + 1)}-01`
    const hasta = `${hoy.getFullYear()}-${dosCifras(hoy.getMonth() + 1)}-${dosCifras(
      new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate(),
    )}`

    const { status, body } = await api(page, `/absences/calendar/?from=${desde}&to=${hasta}`)
    expect(status).toBe(200)
    const tramos = body?.results ?? body ?? []

    // Una fila por persona con algo en el mes, no una por ausencia.
    const cuantasFilas = (pasa) => new Set(tramos.filter(pasa).map((a) => a.employee)).size

    await expect(personas()).toHaveCount(cuantasFilas(() => true))

    await page.getByRole('combobox', { name: 'Tipo' }).click()
    await page.getByRole('option', { name: 'Baja', exact: true }).click()
    await expect(personas()).toHaveCount(cuantasFilas((a) => a.absence_type === 'SICK_LEAVE'))

    await page.getByRole('combobox', { name: 'Tipo' }).click()
    await page.getByRole('option', { name: 'Todos' }).click()
    await page.getByRole('combobox', { name: 'Estado' }).click()
    await page.getByRole('option', { name: 'Sin resolver' }).click()
    await expect(personas()).toHaveCount(cuantasFilas((a) => a.status === 'PENDING'))

    // El contraste, porque los tres números podrían ser el mismo y entonces no
    // se habría comprobado nada: al menos uno de los filtros tiene que quitar
    // filas. Si esto falla, es que el mes de la demostración se ha quedado sin
    // variedad y hay que sembrar más, no relajar la comprobación.
    const conFiltro = [
      cuantasFilas((a) => a.absence_type === 'SICK_LEAVE'),
      cuantasFilas((a) => a.status === 'PENDING'),
    ]
    expect(
      Math.min(...conFiltro),
      'ningún filtro quita ni una fila este mes, así que los tres conteos de arriba ' +
        'podrían pasar con el filtrado desconectado',
    ).toBeLessThan(cuantasFilas(() => true))

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })
})

test.describe('Ajustes de la empresa', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('dice qué se ha tocado antes de guardarlo', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    // Sin tocar nada, no hay nada que guardar y el botón lo dice.
    await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()

    await page.getByLabel('Margen de entrada (min)').fill('7')

    // Qué cambia, de qué a qué. Diecinueve campos en cuatro bloques con un
    // solo botón: sin esto, quien vuelve después de un rato no sabe si tocó
    // algo, y la única forma de averiguarlo era recargar y perderlo.
    const aviso = page.getByRole('alert').filter({ hasText: 'Sin guardar' })
    await expect(aviso).toBeVisible()
    await expect(aviso).toContainText('Margen de entrada')
    await expect(aviso).toContainText('7')
    await expect(page.getByRole('button', { name: 'Guardar 1 cambio' })).toBeEnabled()

    // Y al deshacerlo desaparece: un aviso que se queda puesto deja de leerse.
    const original = (await api(page, '/working-time-rules/')).body.entry_tolerance_minutes
    await page.getByLabel('Margen de entrada (min)').fill(String(original))
    await expect(aviso).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
  })
})
