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

import { api, huecosVisibles, irA, vigilarConsola } from './apoyo.js'

/** Dos personas recién creadas, solo para esta pasada.
 *
 *  Esta prueba **aprueba** lo que crea, y una ausencia aprobada ya no se puede
 *  cancelar: el producto responde `already_resolved`, y hace bien, una decisión
 *  tomada no se deshace borrándola. Así que deja rastro por diseño.
 *
 *  Durante un tiempo eso se resolvió creando gente nueva cada pasada, para que
 *  estrenara calendario. Funcionaba y salía caro: esas personas no se pueden
 *  borrar ---tienen una ausencia que explicar--- así que solo cabía darlas de
 *  baja, y se acumulaban a dos por tanda. El guard del sedimento saltó dos
 *  veces en dos días.
 *
 *  Lo que hacía falta no era gente nueva sino **calendario libre**, y eso
 *  también se consigue moviéndose de fechas. Dos personas fijas, creadas la
 *  primera vez y reutilizadas después, y unos días distintos en cada pasada.
 */
const LOS_DOS = [
  { email: 'bloque.uno@demo.local', last_name: 'Bloque Uno' },
  { email: 'bloque.dos@demo.local', last_name: 'Bloque Dos' },
]

async function losDosDeSiempre(page) {
  const gente = []
  for (const quien of LOS_DOS) {
    const busca = await api(page, `/employees/?search=${encodeURIComponent(quien.email)}`)
    const ya = (busca.body?.results ?? []).find((p) => p.email === quien.email)
    if (ya) {
      gente.push(ya)
      continue
    }
    const alta = await api(page, '/employees/', {
      method: 'POST',
      body: { first_name: 'Prueba', role: 'EMPLOYEE', ...quien },
    })
    expect([200, 201], JSON.stringify(alta.body)).toContain(alta.status)
    gente.push(alta.body)
  }
  return gente
}

/** Dos días de 2027, repartidos por el instante y por el intento. */
function dosDias(indice, intento) {
  const dias = (Math.floor(Date.now() / 1000) % 300) + indice * 3 + intento * 7
  const desde = new Date(Date.UTC(2027, 0, 1) + dias * 86_400_000)
  return [
    desde.toISOString().slice(0, 10),
    new Date(desde.getTime() + 86_400_000).toISOString().slice(0, 10),
  ]
}

/** Pide unas vacaciones en los primeros días que estén libres.
 *
 *  **Pregunta en vez de calcular**, y esa es toda la gracia. El primer intento
 *  derivaba las fechas del reloj y confiaba en no repetirse; falló a la primera
 *  ---dos pasadas seguidas dentro del mismo segundo--- con un
 *  `overlapping_absence` que no apuntaba a ningún defecto del producto.
 *
 *  Una prueba que depende de que el reloj no se repita es una prueba que falla
 *  sola de vez en cuando, y eso enseña a mirar los rojos de reojo. Si el sitio
 *  está ocupado se prueba el siguiente, que es lo que haría cualquiera.
 */
async function pedirVacaciones(page, persona, tipo, indice) {
  for (let intento = 0; intento < 20; intento += 1) {
    const [desde, hasta] = dosDias(indice, intento)
    const alta = await api(page, '/absences/', {
      method: 'POST',
      body: {
        employee: persona.id,
        leave_type: tipo.id,
        start_date: desde,
        end_date: hasta,
        reason: `Prueba bloque ${indice}`,
      },
    })
    if (alta.status === 200 || alta.status === 201) return alta.body
    expect(
      alta.body?.error?.code,
      `el alta falló por algo que no es una fecha ocupada: ${JSON.stringify(alta.body)}`,
    ).toBe('overlapping_absence')
  }
  throw new Error('veinte semanas de 2027 ocupadas: algo no está limpiando lo que crea')
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

  const gente = await losDosDeSiempre(page)
  const creadas = []
  for (const [indice, persona] of gente.entries()) {
    creadas.push((await pedirVacaciones(page, persona, vacaciones, indice)).id)
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

  // No se dan de baja: se quedan de alta para la próxima pasada. Darlas de baja
  // y volver a crearlas cada vez es exactamente lo que llenaba la lista.
  expect(ruido()).toEqual([])
})
