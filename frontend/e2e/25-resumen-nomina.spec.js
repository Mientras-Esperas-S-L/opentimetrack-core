/** El resumen que acompaña a la nómina, para quien lo cobra.
 *
 *  Estaba entero en el servidor y su documentación decía «read for the person
 *  concerned» --- y ninguna pantalla se lo daba a esa persona: quien lleva la
 *  nómina podía generarlos desde Informes, y quien trabaja no podía verlos.
 *
 *  El periodo lo pone la empresa y no la petición, porque el artículo lo ata al
 *  «periodo fijado para el abono»: dejar elegir fechas produciría resúmenes que
 *  no cuadran con ninguna nómina.
 */

import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

test.describe('Mi jornada · el resumen del periodo', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('un operario ve sus cifras del periodo', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mi-jornada', 'Mi jornada')

    await expect(page.getByText('Lo que va del periodo de nómina')).toBeVisible()

    // Contra el servidor, no contra una cifra escrita a mano: lo que se enseña
    // tiene que ser lo mismo que lo que sale en el documento.
    const suyo = await api(page, '/reports/payroll-summary/')
    expect(suyo.status).toBe(200)
    expect(suyo.body.period?.label).toBeTruthy()
    await expect(page.getByText(suyo.body.period.label, { exact: false })).toBeVisible()

    expect(ruido()).toEqual([])
  })

  test('y se lo puede llevar en PDF', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    const espera = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar el resumen' }).click()
    const descarga = await espera

    // Los bytes, no la extensión: comprobar solo el nombre daría verde con el
    // fichero roto, que es como se coló el zip con nombre de PDF en su día.
    const bytes = readFileSync(await descarga.path())
    expect(bytes.subarray(0, 4).toString()).toBe('%PDF')
  })

  test('sigue sin poder pedir el de otra persona', async ({ page }) => {
    await irA(page, '/mi-jornada', 'Mi jornada')

    const ajeno = '00000000-0000-0000-0000-000000000001'
    const respuesta = await api(page, `/reports/payroll-summary/?employee=${ajeno}`)

    // 409 es la convención del proyecto para «no se puede hacer», frente al 400
    // de «lo has escrito mal».
    expect([400, 403, 404, 409]).toContain(respuesta.status)
    // Y lo que importa: que no venga el resumen de nadie más.
    expect(respuesta.body?.total_seconds).toBeUndefined()
    expect(respuesta.body?.employee_name).toBeUndefined()
  })
})
