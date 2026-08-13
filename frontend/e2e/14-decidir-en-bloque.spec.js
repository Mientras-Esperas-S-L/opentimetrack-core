/** Resolver varias cosas a la vez, y dónde eso no vale.
 *
 *  «Por decidir» tenía veinticinco cambios sin acuerdo y veintidós tandas de
 *  horas extra. Una cola así de una en una no se vacía: se abandona, y quien la
 *  abandona deja gente esperando respuesta.
 *
 *  Pero no todo se puede resolver en bloque, y las pruebas de aquí sostienen
 *  las dos mitades:
 *
 *  - **Sí:** ausencias, correcciones pedidas por la persona, retirar
 *    propuestas, horas extra y vacaciones por recuperar.
 *  - **No:** «Aplicar sin acuerdo». Es la excepción del art. 4.b ---un cambio
 *    unilateral sobre el registro de otra persona--- y veinticinco de esas con
 *    un clic convertiría lo excepcional en lo cómodo.
 *
 *  Y una condición que vale para todas: cada decisión deja **su propio apunte**
 *  en el registro. Veinte decisiones son veinte apuntes con nombre, no uno.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, marca, vigilarConsola } from './apoyo.js'

/** Dos personas recién creadas, solo para esta pasada.
 *
 *  No se reutiliza la plantilla de demostración, y el motivo es que esta prueba
 *  **aprueba** lo que crea --- y una ausencia aprobada ya no se puede cancelar:
 *  el producto responde `already_resolved`, y hace bien, una decisión tomada no
 *  se deshace borrándola.
 *
 *  Así que deja rastro por diseño. Con gente de la casa eso significa ir
 *  llenando el calendario de días ocupados hasta que una pasada choca con lo
 *  que dejó otra ---pasó en la primera tanda del bucle--- y el rojo apunta a
 *  donde no es. Con personas nuevas cada vez, no hay con qué chocar: estrenan
 *  calendario.
 *
 *  Se las da de baja al terminar, que es todo lo que el producto permite y todo
 *  lo que hace falta para que no salgan en las listas.
 */
async function genteDeUsarYTirar(page, cuantas = 2) {
  const creadas = []
  for (let i = 0; i < cuantas; i += 1) {
    const sufijo = `${marca()}${i}`
    const alta = await api(page, '/employees/', {
      method: 'POST',
      body: {
        first_name: 'Prueba',
        last_name: `Bloque ${sufijo}`,
        email: `bloque-${sufijo}@demo.local`,
        role: 'EMPLOYEE',
      },
    })
    expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
    creadas.push(alta.body)
  }
  return creadas
}

test.use({ storageState: 'e2e/.sesiones/admin.json' })

const barra = (page) => page.getByRole('toolbar', { name: 'Acciones sobre lo seleccionado' })

/** Abre una cola y dice si tiene algo dentro.
 *
 *  No se lee el número de la pestaña: llega con su propia consulta y hasta
 *  entonces pone «0», así que leerlo pronto da cero para una cola con
 *  veintidós cosas --- y la prueba se salta sola sin que nadie se entere.
 *
 *  Se pregunta a la casilla de «seleccionar todo», que el producto desactiva
 *  cuando no hay filas. Es el propio producto diciendo si hay algo que hacer.
 */
async function abrirCola(page, nombre) {
  await irA(page, '/panel/decisiones', 'Por decidir')
  await page.getByRole('tab', { name: new RegExp(`^${nombre}`) }).click()
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(700)
  return page.getByRole('checkbox', { name: 'Seleccionar todo' }).isEnabled()
}

test('las cinco colas ofrecen seleccionar, salvo donde no debe', async ({ page }) => {
  const ruido = vigilarConsola(page)

  for (const cola of ['Ausencias', 'Fichajes', 'Sin acuerdo', 'Horas extra']) {
    if (!(await abrirCola(page, cola))) continue

    // La casilla de cabecera vive en la barra de filtros y es común a las
    // cinco. Antes solo aparecía en las dos primeras, con un `tab < 2` que
    // había que acordarse de ampliar al añadir una cola.
    await expect(
      page.getByRole('checkbox', { name: 'Seleccionar todo' }),
      `la cola de ${cola} no deja seleccionar`,
    ).toBeVisible()
  }

  expect(ruido()).toEqual([])
  expect(await huecosVisibles(page)).toEqual([])
})

test('«sin acuerdo» deja retirar en bloque pero no aplicar', async ({ page }) => {
  const hay = await abrirCola(page, 'Sin acuerdo')
  test.skip(!hay, 'no hay propuestas abiertas en la base de demostración')

  await page.getByRole('checkbox', { name: 'Seleccionar todo' }).check()
  await expect(barra(page)).toBeVisible()

  // Retirar sí: no toca el registro de nadie, deja las cosas como estaban, y
  // una cola de propuestas viejas que ya no vienen a cuento se limpia entera.
  await expect(barra(page).getByRole('button', { name: 'Retirar la propuesta' })).toBeVisible()

  // Aplicar no, y esto es lo que hay que sostener: si algún día aparece aquí,
  // esta prueba tiene que ponerse roja y obligar a discutirlo. Aplicar sin
  // acuerdo es la excepción del art. 4.b, y una excepción cómoda deja de ser
  // una excepción.
  await expect(barra(page).getByRole('button', { name: /Aplicar/ })).toHaveCount(0)

  // De una en una sigue estando, que es como debe hacerse.
  await expect(page.getByRole('button', { name: 'Aplicar sin acuerdo' }).first()).toBeVisible()
})

test('las horas extra se saldan en bloque, y con las dos formas separadas', async ({ page }) => {
  const hay = await abrirCola(page, 'Horas extra')
  test.skip(!hay, 'no hay horas extra por resolver')

  await page.getByRole('checkbox', { name: 'Seleccionar todo' }).check()

  // Pagada y con descanso por separado, sin un «autorizar y ya». Son dos
  // consecuencias distintas del art. 35.1, y las compensadas con descanso
  // además no cuentan para el tope de ochenta horas al año: un botón único
  // obligaría a un valor por defecto, y el que se eligiera sería el que se
  // aplicara sin pensar.
  await expect(barra(page).getByRole('button', { name: 'Autorizar con descanso' })).toBeVisible()
  await expect(barra(page).getByRole('button', { name: 'Autorizar pagadas' })).toBeVisible()
  await expect(barra(page).getByRole('button', { name: 'No autorizar' })).toBeVisible()
})

test('resolver varias ausencias deja un apunte por cada una', async ({ page }) => {
  const ruido = vigilarConsola(page)

  // Navegar antes de usar la API: el ayudante lee el testigo de `localStorage`
  // y en `about:blank` el navegador lo prohíbe.
  await irA(page, '/panel/decisiones', 'Por decidir')

  const tipos = await api(page, '/leave-types/')
  const vacaciones = (tipos.body?.results ?? tipos.body ?? []).find((t) =>
    /vacacion/i.test(t.name ?? ''),
  )
  expect(vacaciones, 'hacía falta el permiso de vacaciones').toBeTruthy()

  const gente = await genteDeUsarYTirar(page)
  const creadas = []
  for (const [indice, persona] of gente.entries()) {
    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: persona.id,
        leave_type: vacaciones.id,
        start_date: `2027-03-0${2 + indice * 2}`,
        end_date: `2027-03-0${3 + indice * 2}`,
        reason: `Prueba bloque ${indice}`,
      },
    })
    expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
    creadas.push(alta.body.id)
  }

  await abrirCola(page, 'Ausencias')
  await page.getByRole('checkbox', { name: 'Seleccionar todo' }).check()
  await expect(barra(page)).toBeVisible()
  await barra(page).getByRole('button', { name: 'Aprobar' }).click()
  await page.waitForTimeout(2500)

  // Aprobadas de verdad, y **una a una** en el registro: veinte decisiones son
  // veinte apuntes con nombre, no un apunte que dice «veinte».
  const registro = await api(page, '/audit/?action=ABSENCE_APPROVED')
  const apuntes = registro.body?.results ?? []
  const mios = apuntes.filter((linea) => gente.some((p) => linea.target_id === p.id))
  expect(mios.length, 'faltan apuntes de las ausencias aprobadas').toBeGreaterThanOrEqual(2)
  for (const linea of mios.slice(0, 2)) {
    expect(linea.target_label, 'un apunte sin nombre').toBeTruthy()
  }

  for (const persona of gente) {
    await api(page, `/employees/${persona.id}/`, { method: 'DELETE' })
  }
  expect(ruido()).toEqual([])
})
