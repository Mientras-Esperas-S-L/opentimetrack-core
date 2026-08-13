/** Que conocer un identificador no sirva de nada.
 *
 *  Es la prueba que decide si esto se puede vender: en una herramienta con
 *  varias empresas dentro, un fallo aquí no es un error, es el final del
 *  producto. Y no vale con que la interfaz esconda el botón --- eso lo salta
 *  cualquiera con la consola abierta --- así que aquí se llama a la API
 *  directamente desde la sesión del atacante.
 *
 *  El método: la sesión de la empresa vecina averigua sus propios
 *  identificadores por la vía legítima, y luego la sesión de la primera empresa
 *  intenta usarlos.
 */

import { expect, test } from '@playwright/test'

import { EMPRESA, api, apiSinSesion } from './apoyo.js'

/** Lo que la vecina puede ver de sí misma, para intentar robárselo después. */
async function identificadoresDeLaVecina(browser) {
  const contexto = await browser.newContext({ storageState: 'e2e/.sesiones/vecina.json' })
  const page = await contexto.newPage()
  await page.goto('/panel')

  const suyo = {}
  const gente = await api(page, '/employees/')
  suyo.persona = gente.body?.results?.[0]?.id
  const departamentos = await api(page, '/departments/')
  suyo.departamento = departamentos.body?.results?.[0]?.id
  const empresa = await api(page, '/company/')
  suyo.empresa = empresa.body?.id
  suyo.nombreEmpresa = empresa.body?.name

  await contexto.close()
  return suyo
}

test.describe('Aislamiento entre empresas', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('la vecina existe y tiene datos propios', async ({ browser }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    expect(suyo.nombreEmpresa).toBe(EMPRESA.vecina.nombre)
    expect(suyo.persona).toBeTruthy()
    expect(suyo.departamento).toBeTruthy()
  })

  test('con el id de una persona ajena, la API dice que no existe', async ({ page, browser }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    await page.goto('/panel')

    const leer = await api(page, `/employees/${suyo.persona}/`)
    // 404 y no 403: contestar «existe pero no es tuyo» ya es decir que existe.
    expect(leer.status).toBe(404)

    const escribir = await api(page, `/employees/${suyo.persona}/`, {
      method: 'PATCH',
      body: { role: 'ADMIN' },
    })
    expect(escribir.status).toBe(404)
  })

  test('con el id de un departamento ajeno, tampoco', async ({ page, browser }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    await page.goto('/panel')

    expect((await api(page, `/departments/${suyo.departamento}/`)).status).toBe(404)
    expect(
      (
        await api(page, `/departments/${suyo.departamento}/`, {
          method: 'PATCH',
          body: { name: 'Secuestrado' },
        })
      ).status,
    ).toBe(404)
  })

  test('no se puede poner a alguien de otra empresa al mando de un departamento', async ({
    page,
    browser,
  }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    await page.goto('/panel')

    const propios = await api(page, '/departments/')
    const mio = propios.body.results[0].id

    const intento = await api(page, `/departments/${mio}/`, {
      method: 'PATCH',
      body: { managers: [suyo.persona] },
    })
    expect(intento.status).toBe(400)
    expect(JSON.stringify(intento.body)).toContain('no pertenece a esta empresa')
  })

  test('el identificador de empresa que se manda en el cuerpo se ignora', async ({
    page,
    browser,
  }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    await page.goto('/panel')

    const creado = await api(page, '/departments/', {
      method: 'POST',
      body: { name: `Colado ${Date.now()}`, tenant: suyo.empresa },
    })
    expect(creado.status).toBe(201)

    // Cayó en la empresa de quien llama, no en la que decía el cuerpo: la
    // empresa sale de quién eres, nunca de lo que mandas.
    const desdeLaVecina = await browser.newContext({
      storageState: 'e2e/.sesiones/vecina.json',
    })
    const suPagina = await desdeLaVecina.newPage()
    await suPagina.goto('/panel')
    const susDepartamentos = await api(suPagina, '/departments/')
    const nombres = susDepartamentos.body.results.map((d) => d.name)
    expect(nombres.some((n) => n.startsWith('Colado'))).toBe(false)
    await desdeLaVecina.close()

    await api(page, `/departments/${creado.body.id}/`, { method: 'DELETE' })
  })

  test('los fichajes y las ausencias ajenas no salen ni preguntando por su persona', async ({
    page,
    browser,
  }) => {
    const suyo = await identificadoresDeLaVecina(browser)
    await page.goto('/panel')

    for (const ruta of ['/punches/', '/absences/', '/corrections/', '/shifts/']) {
      const respuesta = await api(page, `${ruta}?employee=${suyo.persona}`)
      const filas = respuesta.body?.results ?? respuesta.body ?? []
      expect(filas, `${ruta} devolvió filas de otra empresa`).toHaveLength(0)
    }
  })

  test('navegar a la URL de una persona ajena no enseña su ficha', async ({ page, browser }) => {
    const suyo = await identificadoresDeLaVecina(browser)

    await page.goto(`/panel/personas?employee=${suyo.persona}`)
    await expect(page.getByRole('heading', { name: 'Personas', level: 1 })).toBeVisible()
    // Nada de la vecina aparece en pantalla.
    await expect(page.getByText('Vecin', { exact: false })).toHaveCount(0)
  })

  test('sin sesión, la API no contesta nada', async ({ browser }) => {
    const anonimo = await browser.newContext()
    const page = await anonimo.newPage()
    await page.goto('/')

    for (const ruta of ['/employees/', '/punches/', '/departments/', '/company/', '/overtime/']) {
      const respuesta = await apiSinSesion(page, ruta)
      expect(respuesta.status, `${ruta} contestó sin sesión`).toBe(401)
    }
    await anonimo.close()
  })
})

test.describe('Lo que un operario no puede hacer', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('no llega a las pantallas de gestión', async ({ page }) => {
    await page.goto('/panel/personas')
    // Le devuelve a lo suyo en vez de enseñarle la plantilla.
    await expect(page.getByRole('heading', { name: 'Personas', level: 1 })).toHaveCount(0)
  })

  test('la API le niega lo de gestión aunque llame directamente', async ({ page }) => {
    await page.goto('/')

    const prohibido = [
      ['/employees/', 'GET'],
      ['/overtime/', 'GET'],
      ['/applications/', 'GET'],
    ]
    for (const [ruta, metodo] of prohibido) {
      const respuesta = await api(page, ruta, { method: metodo })
      expect(respuesta.status, `${ruta} le contestó a un operario`).toBe(403)
    }
  })

  test('el registro de actividad sí le contesta, pero solo con lo suyo', async ({ page }) => {
    // No es un descuido que /audit/ conteste a un operario: su pantalla de
    // Actividad existe justamente para que pueda ver quién ha mirado su ficha.
    // Lo que hay que comprobar es que ahí no aparezca nada ajeno.
    await page.goto('/')
    const yo = await api(page, '/auth/me/')
    const miId = yo.body?.user?.id ?? yo.body?.id

    const respuesta = await api(page, '/audit/')
    expect(respuesta.status).toBe(200)
    for (const fila of respuesta.body.results ?? []) {
      const esMio = fila.actor === miId || fila.target_id === miId
      expect(esMio, `asiento ajeno visible: ${fila.action} sobre ${fila.target_label}`).toBe(true)
    }
  })

  test('no puede ascenderse a sí mismo', async ({ page }) => {
    await page.goto('/')
    const yo = await api(page, '/auth/me/')
    const miId = yo.body?.user?.id ?? yo.body?.id

    const intento = await api(page, `/employees/${miId}/`, {
      method: 'PATCH',
      body: { role: 'ADMIN' },
    })
    expect([403, 404]).toContain(intento.status)

    const despues = await api(page, '/auth/me/')
    expect((despues.body?.user ?? despues.body).role).toBe('EMPLOYEE')
  })

  test('no puede leer el registro de un compañero', async ({ page, browser }) => {
    // El id del compañero se consigue por la vía legítima, desde administración.
    const admin = await browser.newContext({ storageState: 'e2e/.sesiones/admin.json' })
    const suPagina = await admin.newPage()
    await suPagina.goto('/panel')
    const gente = await api(suPagina, '/employees/')
    const otro = gente.body.results.find((p) => p.email !== EMPRESA.propia.operario)
    await admin.close()

    await page.goto('/')
    const fichajes = await api(page, `/punches/?employee=${otro.id}`)
    const filas = fichajes.body?.results ?? []
    expect(filas).toHaveLength(0)
  })
})
