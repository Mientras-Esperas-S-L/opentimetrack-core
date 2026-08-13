/** Filtrar, marcar varias y actuar sobre ellas.
 *
 *  Lo que no existía en ninguna de las dieciséis pantallas. Cualquier
 *  reorganización era abrir y cerrar diálogos: meter quince personas en un
 *  departamento eran quince diálogos, y en la pantalla que se llama
 *  «Departamentos» ni siquiera se podía.
 *
 *  Las pruebas de aquí sostienen tres cosas que es fácil romper sin notarlo:
 *
 *  1. Que «seleccionar todo» sea **de esta página**, no de la empresa.
 *  2. Que dar de baja a varias **pregunte diciendo cuántas**.
 *  3. Que cada cambio deje su apunte **con nombre y apellidos** en el registro
 *     de actividad. Una reorganización de veinte personas no puede aparecer
 *     como un solo apunte: cambiar de departamento decide quién puede leer el
 *     registro de quién.
 */

import { expect, test } from '@playwright/test'

import { api, huecosVisibles, irA, marca, vigilarConsola } from './apoyo.js'

/** La barra flotante de acciones. Por su rol y no por su texto: su contador
 *  dice «19 personas» y el del paginador de abajo también. */
const barra = (page) => page.getByRole('toolbar', { name: 'Acciones sobre lo seleccionado' })

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Deshace lo que estas pruebas mueven: todo el mundo a su sitio de antes. */
async function devolver(page, cambios) {
  for (const [id, department] of cambios) {
    await api(page, `/employees/${id}/`, { method: 'PATCH', body: { department } })
  }
}

test.describe('Personas', () => {
  test('los tres filtros acotan, y «sin departamento» es una opción', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/personas', 'Personas')

    // Esperar a que la tabla traiga filas antes de contarlas: contar la propia
    // prisa da cero y el rojo apunta al filtro, que no tiene la culpa.
    const filas = () => page.getByRole('row').filter({ hasNotText: 'Perfil' })
    await expect(filas().first()).toBeVisible()
    const todas = await filas().count()
    expect(todas).toBeGreaterThan(3)

    // «Sin departamento» no se puede pedir con el desplegable vacío ---un
    // parámetro vacío es igual que no mandarlo--- así que es su propia opción.
    // Y es la primera pregunta al reorganizar: quién se ha quedado suelto.
    await page.getByRole('combobox', { name: 'Departamento' }).click()
    await page.getByRole('option', { name: 'Sin departamento' }).click()
    await page.waitForTimeout(800)
    const sueltas = await filas().count()
    expect(sueltas).toBeLessThan(todas)

    // Y que sea verdad: ninguna de las que quedan tiene departamento.
    const respuesta = await api(page, '/employees/?is_active=true&no_department=true')
    for (const persona of respuesta.body?.results ?? []) {
      expect(persona.department, `${persona.email} sí tiene departamento`).toBeFalsy()
    }

    await page.getByRole('combobox', { name: 'Departamento' }).click()
    await page.getByRole('option', { name: 'Todos' }).click()
    await page.getByRole('combobox', { name: 'Perfil' }).click()
    await page.getByRole('option', { name: 'Administración' }).click()
    await page.waitForTimeout(800)
    expect(await filas().count()).toBeLessThan(todas)

    expect(ruido()).toEqual([])
    expect(await huecosVisibles(page)).toEqual([])
  })

  test('marcar varias y moverlas de departamento, con su rastro', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/panel/personas', 'Personas')

    // Un departamento de usar y tirar, para no mover a nadie de donde estaba
    // sin poder devolverlo.
    const nombre = `Depto ${marca()}`
    const creado = await api(page, '/departments/', { method: 'POST', body: { name: nombre } })
    expect([200, 201]).toContain(creado.status)
    await page.reload()

    const marcar = page.getByRole('checkbox', { name: /^Seleccionar a/ })
    await expect(marcar.first()).toBeVisible()
    const cuantas = 3
    const antes = []
    for (let i = 0; i < cuantas; i += 1) {
      await marcar.nth(i).check()
    }
    // El rótulo lo pone la barra compartida ---la misma que «Por decidir»---
    // así que dice «3 personas», no «3 seleccionadas».
    await expect(barra(page)).toContainText('3 personas')

    // De quiénes se trata, para poder devolverlas al terminar.
    const plantilla = await api(page, '/employees/?is_active=true')
    for (const persona of (plantilla.body?.results ?? []).slice(0, cuantas)) {
      antes.push([persona.id, persona.department ?? null])
    }

    await page.getByRole('button', { name: 'Mover a departamento…' }).click()
    await page.getByRole('menuitem', { name: nombre }).click()
    await page.waitForTimeout(2500)

    // Movidas de verdad, no solo en la pantalla.
    const dentro = await api(page, `/employees/?department=${creado.body.id}`)
    expect((dentro.body?.results ?? []).length).toBe(cuantas)

    // Y con su apunte cada una. Un solo apunte para tres personas sería un
    // registro que no sirve para lo que existe.
    const registro = await api(page, '/audit/?action=PERSON_UPDATED')
    const conNombre = (registro.body?.results ?? []).filter((linea) =>
      antes.some(([id]) => linea.target_id === id),
    )
    expect(conNombre.length, 'faltan apuntes de las personas movidas').toBeGreaterThanOrEqual(
      cuantas,
    )
    for (const linea of conNombre.slice(0, cuantas)) {
      expect(linea.target_label, 'un apunte sin nombre').toBeTruthy()
    }

    await devolver(page, antes)
    await api(page, `/departments/${creado.body.id}/`, { method: 'DELETE' })

    expect(ruido()).toEqual([])
  })

  test('«todas» son las de esta página, no las de la empresa', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    const marcables = page.getByRole('checkbox', { name: /^Seleccionar a/ })
    await expect(marcables.first()).toBeVisible()
    const enPantalla = await marcables.count()
    await page.getByRole('checkbox', { name: 'Seleccionar todas las de esta página' }).check()

    // Marcar «todas» no puede alcanzar a quien no se está viendo: sería actuar
    // sobre gente que nadie ha mirado.
    await expect(barra(page)).toContainText(`${enPantalla} personas`)

    const total = (await api(page, '/employees/?is_active=true')).body?.count ?? 0
    if (total > enPantalla) {
      await expect(barra(page)).not.toContainText(`${total} personas`)
    }
  })

  test('dar de baja a varias pregunta, y la pregunta dice cuántas', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    await page
      .getByRole('checkbox', { name: /^Seleccionar a/ })
      .nth(0)
      .check()
    await page
      .getByRole('checkbox', { name: /^Seleccionar a/ })
      .nth(1)
      .check()
    await page.getByRole('button', { name: 'Dar de baja' }).click()

    // «¿Estás seguro?» no es una pregunta: no dice a cuánta gente afecta.
    const confirmacion = page.getByRole('dialog')
    await expect(confirmacion).toContainText('Dar de baja a 2 personas')
    await expect(confirmacion).toContainText(/no se borra nada/i)

    // Y se cancela sin haber tocado a nadie.
    await confirmacion.getByRole('button', { name: 'Cancelar' }).click()
    const activas = await api(page, '/employees/?is_active=true')
    expect((activas.body?.results ?? []).length).toBeGreaterThan(0)
  })
})

test.describe('Departamentos', () => {
  test('los miembros se ponen desde el propio departamento', async ({ page }) => {
    const ruido = vigilarConsola(page)
    const nombre = `Depto ${marca()}`

    await irA(page, '/panel/departamentos', 'Departamentos')
    await page.getByRole('button', { name: 'Nuevo' }).click()

    const dialogo = page.getByRole('dialog')
    await dialogo.getByRole('textbox', { name: /^Nombre/ }).fill(nombre)

    // Esto es lo que no existía: componer el departamento sin salir de aquí.
    await dialogo.getByRole('combobox', { name: /Quién está dentro/ }).fill('Hugo')
    await page.getByRole('option', { name: /Hugo Bermejo/ }).click()
    await dialogo.getByRole('button', { name: 'Guardar' }).click()
    await expect(dialogo).toBeHidden()

    await page.reload()
    const fila = page.getByRole('listitem').filter({ hasText: nombre })
    await expect(fila).toContainText('1 persona')

    // Quitarlo de aquí lo deja sin departamento, no lo da de baja.
    const creado = (await api(page, `/departments/?search=${encodeURIComponent(nombre)}`)).body
    const id = (creado?.results ?? creado ?? [])[0]?.id
    expect(id, 'no se encontró el departamento recién creado').toBeTruthy()

    const vaciado = await api(page, `/departments/${id}/`, {
      method: 'PATCH',
      body: { members: [] },
    })
    expect(vaciado.status).toBe(200)

    const hugo = (await api(page, '/employees/?search=Hugo')).body?.results?.[0]
    expect(hugo.is_active, 'quitarlo del departamento lo dio de baja').toBe(true)
    expect(hugo.department).toBeFalsy()

    await api(page, `/departments/${id}/`, { method: 'DELETE' })
    expect(ruido()).toEqual([])
  })

  test('renombrar sin tocar los miembros no vacía el departamento', async ({ page }) => {
    await irA(page, '/panel/departamentos', 'Departamentos')

    // El fallo que este campo podía introducir: si «omitido» y «vacío» se
    // trataran igual, renombrar un departamento dejaría sin departamento a
    // toda su gente. Se prueba por API porque es donde vive la diferencia.
    const lista = (await api(page, '/departments/')).body
    const conGente = (lista?.results ?? lista ?? []).find((d) => d.people_count > 0)
    expect(conGente, 'hacía falta un departamento con gente').toBeTruthy()

    const original = conGente.name
    const renombrado = await api(page, `/departments/${conGente.id}/`, {
      method: 'PATCH',
      body: { name: `${original} (probando)` },
    })
    expect(renombrado.status).toBe(200)
    expect(renombrado.body.people_count, 'renombrar vació el departamento').toBe(
      conGente.people_count,
    )

    await api(page, `/departments/${conGente.id}/`, { method: 'PATCH', body: { name: original } })
  })
})
