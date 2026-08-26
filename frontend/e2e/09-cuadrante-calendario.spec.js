/** Cuadrante y calendario del equipo: las dos pantallas con más interacción.
 *
 *  Son las que más se tocan y las que menos se habían probado. El cuadrante
 *  tiene diálogo de asignación, navegación por meses, pintado arrastrando y un
 *  vaciado que borra un mes entero; el calendario registra ausencias y las
 *  aprueba. Entre las dos concentran casi todo lo que puede salir mal al
 *  pulsar, y hasta hoy solo se sabía que cargaban.
 *
 *  Todo lo que estas pruebas crean va a **diciembre de 2026**, un mes vacío a
 *  propósito. No se pisan con los datos de demostración, y el propio «Vaciar el
 *  mes» sirve de limpieza --- que de paso es la forma de probarlo.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, marca, vigilarConsola } from './apoyo.js'

/** Un mes lejano y vacío, para no pisar los datos de demostración. */
const MES = { año: 2026, mes: 12, desde: '2026-12-01', hasta: '2026-12-31' }

/** Deja diciembre sin turnos antes de empezar.
 *
 *  La misma lección que con las ausencias, aprendida dos veces: una prueba que
 *  se cae a mitad deja lo que había creado, y la siguiente pasada lo encuentra
 *  y falla por ello. Aquí se vio claro --- una pasada anterior había asignado
 *  los 31 días de diciembre, y la siguiente cazaba el sábado 5 creyendo que
 *  acababa de crearlo.
 */
async function vaciarDiciembre(page) {
  const plantilla = await api(page, '/employees/?is_active=true')
  const todos = (plantilla.body?.results ?? []).map((persona) => persona.id)
  if (todos.length === 0) return
  // Sin `weekdays`: omitirlo es lo que significa «todos los días».
  await api(page, '/shifts/clear/', {
    method: 'POST',
    body: { employees: todos, date_from: MES.desde, date_to: MES.hasta },
  })
}

/** Retira las ausencias que dejó una pasada anterior.
 *
 *  Antes de crear, no solo después. Limpiar al final es lo que uno escribe
 *  primero, y no sirve: en cuanto una prueba se cae a mitad, la ausencia se
 *  queda y la siguiente pasada choca contra ella con «ya hay una ausencia
 *  registrada». La prueba se vuelve roja por lo que dejó la anterior, que es la
 *  peor forma de rojo --- el fallo no está donde apunta.
 */
async function limpiarAusenciasDePrueba(page) {
  const existentes = await api(page, '/absences/?status=PENDING')
  for (const fila of existentes.body?.results ?? existentes.body ?? []) {
    // Solo las pendientes, y por eso se piden ya filtradas: una ausencia
    // **aprobada** no se puede cancelar ---el producto responde
    // `already_resolved`, y hace bien--- así que intentarlo llenaba la consola
    // de 409 y tumbaba la comprobación de ruido de la propia prueba.
    if ((fila.reason ?? '').startsWith('Prueba')) {
      await api(page, `/absences/${fila.id}/cancel/`, { method: 'POST' })
    }
  }
}

/** Lleva el cuadrante o el calendario hasta ese mes pulsando «Mes siguiente».
 *
 *  A botonazos y no por la URL porque es lo que hace una persona, y porque una
 *  navegación que solo funciona escribiendo la dirección no sirve de nada.
 */
async function avanzarHasta(page, etiqueta) {
  for (let intento = 0; intento < 12; intento += 1) {
    if (
      await page
        .getByText(etiqueta, { exact: false })
        .first()
        .isVisible()
        .catch(() => false)
    )
      return
    await page.getByRole('button', { name: 'Mes siguiente' }).click()
    await page.waitForTimeout(150)
  }
  throw new Error(`No se llegó a ${etiqueta} en doce meses`)
}

test.describe('Cuadrante', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('asignar un turno a una persona, verlo, y vaciar el mes', async ({ page }) => {
    const ruido = vigilarConsola(page)

    await irA(page, '/panel/cuadrante', 'Cuadrante')
    await vaciarDiciembre(page)
    await page.reload()
    await avanzarHasta(page, 'diciembre')

    await page.getByRole('button', { name: 'Asignar turno' }).click()
    const dialogo = page.getByRole('dialog')
    await expect(dialogo).toBeVisible()

    // Sin turno elegido no hay nada que asignar, y el botón lo dice antes de
    // intentarlo en vez de después.
    await expect(dialogo.getByRole('button', { name: 'Asignar' })).toBeDisabled()

    await dialogo.getByLabel('Turno').click()
    await page.getByRole('option').first().click()

    // Se espera a que la opción sea la de Ana antes de pulsarla, y se comprueba
    // que quedó elegida. Pulsar «la primera» sin mirar es lo que hacía esta
    // prueba, y elegía a quien la lista tuviera puesto en ese instante --- que
    // con el desplegable recién abierto no es quien se escribió.
    await dialogo.getByRole('combobox', { name: /A quién/ }).fill('Ana')
    await page.getByRole('option', { name: /Ana García/ }).click()
    await expect(dialogo.getByText('Ana García')).toBeVisible()

    await dialogo.getByLabel('Desde').fill(MES.desde)
    await dialogo.getByLabel('Hasta').fill(MES.hasta)

    // Los días vienen ya marcados de lunes a viernes, y son botones de
    // alternar: pulsarlos los **quita**. La primera versión de esta prueba los
    // pulsaba uno a uno creyendo que los ponía, se quedaba sin ninguno, y el
    // servidor entendía «todos» --- así apareció un turno el sábado 5.
    await expect(dialogo.locator('button[aria-pressed=true]')).toHaveCount(5)

    // Quitar el último día deja el botón desactivado, en vez de asignar los
    // siete. Se comprueba aquí y se deshace, que es la mitad barata de la
    // prueba: sin esto el fallo vuelve sin que nadie lo note.
    for (const dia of ['L', 'M', 'X', 'J', 'V']) {
      await dialogo.getByRole('button', { name: dia, exact: true }).click()
    }
    await expect(dialogo.getByRole('button', { name: 'Asignar' })).toBeDisabled()
    for (const dia of ['L', 'M', 'X', 'J', 'V']) {
      await dialogo.getByRole('button', { name: dia, exact: true }).click()
    }

    await expect(dialogo.getByRole('button', { name: 'Asignar' })).toBeEnabled()
    await dialogo.getByRole('button', { name: 'Asignar' }).click()
    await expect(dialogo).toBeHidden()

    // Que se pinte no basta. Lo que demuestra que llegó al servidor es
    // preguntárselo a él.
    const puestos = await api(page, `/shifts/roster/?from=${MES.desde}&to=${MES.hasta}`)
    expect(puestos.status).toBe(200)
    const filas = puestos.body?.results ?? puestos.body ?? []
    expect(filas.length, 'diciembre debería tener los turnos recién puestos').toBeGreaterThan(15)

    // Y ni un sábado ni un domingo, que es lo que se pidió.
    for (const turno of filas) {
      const dia = new Date(`${turno.day}T00:00:00`).getDay()
      expect(dia, `${turno.day} cayó en fin de semana`).not.toBe(0)
      expect(dia, `${turno.day} cayó en fin de semana`).not.toBe(6)
    }

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])

    // Y ahora el vaciado, en la misma prueba a propósito: el botón solo existe
    // cuando el mes tiene turnos, así que separarlo en otra prueba la ataría al
    // orden de ejecución --- y una prueba que depende de que otra haya corrido
    // antes miente en cuanto se ejecutan sueltas.
    await page.reload()
    await avanzarHasta(page, 'diciembre')
    await page.getByRole('button', { name: 'Vaciar el mes' }).click()

    // Borra el cuadrante de todo el mundo. Si algún día deja de preguntar, esto
    // tiene que ponerse rojo: es de las pocas acciones del producto que no se
    // pueden deshacer desde la pantalla.
    const confirmacion = page.getByRole('dialog')
    await expect(confirmacion).toBeVisible()
    await expect(confirmacion).toContainText('Se borran')
    await confirmacion.getByRole('button', { name: 'Vaciar' }).click()
    await expect(confirmacion).toBeHidden()

    // Esperando a que quede vacío, no preguntando una vez. El diálogo se cierra
    // en cuanto se pulsa, y el borrado sigue viajando: en una tanda cargada la
    // consulta llegaba antes que el DELETE y la prueba fallaba enseñando los
    // veintitrés turnos que estaban a punto de irse. Aislada pasaba siempre, que
    // es la firma de una carrera y no de un defecto.
    await expect
      .poll(async () => {
        const despues = await api(page, `/shifts/roster/?from=${MES.desde}&to=${MES.hasta}`)
        return (despues.body?.results ?? despues.body ?? []).length
      })
      .toBe(0)
  })

  test('cancelar el vaciado no borra nada', async ({ page }) => {
    await irA(page, '/panel/cuadrante', 'Cuadrante')

    // En el mes de verdad, que es donde el fallo dolería.
    const antes = await api(page, '/shifts/roster/?from=2026-08-01&to=2026-08-31')
    const cuantos = (antes.body?.results ?? antes.body ?? []).length

    await page.getByRole('button', { name: 'Vaciar el mes' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Cancelar' }).click()

    const despues = await api(page, '/shifts/roster/?from=2026-08-01&to=2026-08-31')
    expect((despues.body?.results ?? despues.body ?? []).length).toBe(cuantos)
  })
})

test.describe('Calendario del equipo', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('registrar una ausencia deja la solicitud sin resolver', async ({ page }) => {
    const ruido = vigilarConsola(page)

    await irA(page, '/panel/calendario', 'Calendario del equipo')
    await limpiarAusenciasDePrueba(page)
    await page.getByRole('button', { name: 'Registrar ausencia' }).click()

    const dialogo = page.getByRole('dialog')
    await expect(dialogo.getByRole('button', { name: 'Registrar solicitud' })).toBeDisabled()

    await dialogo.getByRole('combobox', { name: /De quién/ }).fill('Hugo')
    await page.getByRole('option').first().click()

    // Vacaciones por su nombre, no «la primera opción del desplegable». Con la
    // primera salían los permisos por horas, y entonces «Desde» y «Hasta» no
    // son fechas sino horas --- el formulario cambia de forma según lo que se
    // pida, que es justo lo que una prueba a ciegas no ve.
    await dialogo.getByRole('combobox', { name: /Qué pides/ }).click()
    await page
      .getByRole('option', { name: /vacaciones/i })
      .first()
      .click()

    // **Días propios de esta tanda, no dos fijos.** Con el 14 y el 15 de
    // siempre, la ausencia que esta prueba deja adrede sin resolver choca con la
    // de la tanda anterior en cuanto una queda aprobada: la limpieza no puede
    // cancelar una aprobada ---el producto contesta `already_resolved` y hace
    // bien--- así que el alta nueva se solapa y el diálogo no se cierra. Falló
    // así, y el mismo residuo ya había roto antes la búsqueda de más abajo.
    //
    // El mes se queda en diciembre porque la navegación del calendario avanza
    // hasta él a botonazos; lo que cambia es el día.
    const dia = 3 + (Date.now() % 20)
    const desde = `2026-12-${String(dia).padStart(2, '0')}`
    const hasta = `2026-12-${String(dia + 1).padStart(2, '0')}`
    await dialogo.getByLabel('Desde *').fill(desde)
    await dialogo.getByLabel('Hasta *').fill(hasta)
    const mimarca = `Prueba calendario ${marca()}`
    await dialogo.getByLabel('Motivo (opcional)').fill(mimarca)

    await dialogo.getByRole('button', { name: 'Registrar solicitud' }).click()
    await expect(dialogo).toBeHidden()

    // Sin resolver, no aprobada. Es la regla entera del producto: quien
    // registra no decide, ni siquiera cuando quien registra manda. Se ve rayada
    // en el calendario, y el contador del mes lo dice con palabras.
    // La búsqueda va **al servidor** con la marca propia, no filtrando en el
    // cliente una página de «Prueba». La versión anterior pedía `search=Prueba`
    // y buscaba la suya en la respuesta: como la suite deja ausencias de prueba
    // que quedan aprobadas ---y una aprobada no se puede cancelar, así que la
    // limpieza no se las lleva--- llegaron a acumularse cincuenta y cuatro, la
    // página se llenó con las cincuenta primeras y la recién creada no salía.
    // Fallaba diciendo «no llegó al servidor» cuando sí había llegado.
    const creada = await api(page, `/absences/?search=${encodeURIComponent(mimarca)}`)
    const filas = creada.body?.results ?? creada.body ?? []
    const mia = filas.find((a) => a.reason === mimarca)
    expect(mia, 'la ausencia no llegó al servidor').toBeTruthy()
    expect(mia.status).toBe('PENDING')
    await expect(page.getByText(/sin resolver/i).first()).toBeVisible()

    await limpiarAusenciasDePrueba(page)

    expect(ruido()).toEqual([])
  })

  test('quien registra una ausencia no puede aprobarla', async ({ page }) => {
    await irA(page, '/panel/calendario', 'Calendario del equipo')
    await limpiarAusenciasDePrueba(page)

    // La sesión es la de Ana García, que administra. Se registra una ausencia
    // para sí misma y acto seguido intenta aprobarla, por API y sin pasar por
    // la pantalla --- que es como se intentaría de verdad, y la única forma de
    // probarlo: por pantalla el botón sencillamente no se pinta, y un botón
    // ausente no demuestra nada sobre lo que el servidor acepta.
    const yo = await api(page, '/auth/me/')
    const tipos = await api(page, '/leave-types/')
    const vacaciones = (tipos.body?.results ?? tipos.body ?? []).find((t) =>
      /vacacion/i.test(t.name ?? ''),
    )
    expect(vacaciones, 'hacía falta el permiso de vacaciones').toBeTruthy()

    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: yo.body.user?.id ?? yo.body.id,
        leave_type: vacaciones.id,
        start_date: '2026-12-21',
        end_date: '2026-12-22',
        reason: `Prueba ${marca()}`,
      },
    })
    expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)

    const suya = await api(page, `/absences/${alta.body.id}/approve/`, { method: 'POST' })

    // Las cuatro manos del art. 4.b: la misma persona no puede ser sujeto y
    // decisor. Que Ana administre no la habilita --- administrar da alcance, no
    // quita la separación.
    //
    // 409 y no 403 a propósito: no es que le falte permiso, es que en este caso
    // concreto choca consigo misma. Con otra persona delante, el mismo botón
    // funciona.
    expect(suya.status, JSON.stringify(suya.body)).toBe(409)
    expect(suya.body?.error?.code).toBe('cannot_decide_your_own')

    // Y que la frase esté bien escrita en castellano. Decía «una ausencia
    // tuyo», porque la traducción pegaba un posesivo masculino a un sustantivo
    // que cambia de género según el caso --- ausencia, horas extraordinarias,
    // recuperación de vacaciones. Dos de esos tres ni siquiera se traducían.
    expect(suya.body?.error?.message).toContain('la persona afectada eres tú')
    expect(suya.body?.error?.message).not.toMatch(/tuyo|overtime|holiday recovery/)

    await limpiarAusenciasDePrueba(page)
  })
})

test.describe('Desde la empresa de al lado', () => {
  test.use({ storageState: 'e2e/.sesiones/vecina.json' })

  test('no puede poner turnos ni ausencias a gente ajena', async ({ page }) => {
    await irA(page, '/panel', 'Resumen')

    // El identificador de una persona de Jardines Demo, conseguido como se
    // consigue de verdad: preguntándole al servidor con la sesión legítima. Lo
    // que se prueba aquí es que **conocerlo no sirve de nada**.
    const contexto = page.context()
    const otra = await contexto.browser().newContext({ storageState: 'e2e/.sesiones/admin.json' })
    const espía = await otra.newPage()
    await espía.goto('/panel')
    const plantilla = await api(espía, '/employees/?is_active=true')
    const ajena = (plantilla.body?.results ?? [])[0]
    await otra.close()
    expect(ajena, 'hacía falta alguien de la otra empresa').toBeTruthy()

    const turno = await api(page, '/shifts/', {
      method: 'POST',
      body: { employee: ajena.id, day: '2026-12-07', starts_at: '09:00', ends_at: '17:00' },
    })
    expect([400, 403, 404], `dejó poner un turno: ${turno.status}`).toContain(turno.status)

    const ausencia = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: ajena.id,
        absence_type: 'VACATION',
        date_from: '2026-12-07',
        date_to: '2026-12-08',
      },
    })
    expect([400, 403, 404], `dejó poner una ausencia: ${ausencia.status}`).toContain(
      ausencia.status,
    )
  })
})
