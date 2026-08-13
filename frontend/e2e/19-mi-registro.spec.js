/** Que cada persona pueda llevarse su propio registro.
 *
 *  Art. 34.9: los registros «permanecerán a disposición de las personas
 *  trabajadoras, de sus representantes legales y de la Inspección de Trabajo».
 *
 *  La API ya dejaba a cualquiera pedir el suyo ---por omisión es el de quien
 *  llama--- pero la única pantalla que lo ofrecía estaba detrás del panel de
 *  gestión. O sea que a su disposición lo tenía quien administra, y no la
 *  persona de la que habla el artículo.
 *
 *  Y poder mirarlo no es lo mismo que poder llevárselo: lo que se enseña a un
 *  juzgado o a la Inspección es el documento con su huella, y esa la calcula el
 *  servidor. Por eso la prueba mira **los bytes**: un PDF empieza por «%PDF», y
 *  comprobar solo la extensión daría verde con el fichero roto.
 */

import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

test.describe('Mi jornada · un operario', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  test('se descarga su propio registro del mes', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mi-jornada', 'Mi jornada')

    const boton = page.getByRole('button', { name: /^Descargar / })
    await expect(boton).toBeVisible()

    const espera = page.waitForEvent('download')
    await boton.click()
    const descarga = await espera

    const bytes = readFileSync(await descarga.path())
    expect(bytes.subarray(0, 4).toString(), 'no es un PDF').toBe('%PDF')
    // Y con el nombre que eligió el servidor, no un apaño: lleva el apellido y
    // el rango, que es lo que distingue un documento de otro en una carpeta.
    expect(descarga.suggestedFilename()).toMatch(/^working-time_.+\.pdf$/)

    expect(ruido()).toEqual([])
  })

  test('el botón sigue al mes que se está mirando', async ({ page }) => {
    // Si bajara siempre el mes en curso, quien retrocede para revisar marzo se
    // llevaría abril sin enterarse: el nombre del fichero es lo único que lo
    // diría, y se lee después.
    await irA(page, '/mi-jornada', 'Mi jornada')

    const antes = await page.getByRole('button', { name: /^Descargar / }).textContent()
    await page.getByRole('button', { name: 'Mes anterior' }).click()
    const despues = await page.getByRole('button', { name: /^Descargar / }).textContent()

    expect(despues).not.toBe(antes)
  })

  test('sigue sin poder pedir el de otra persona', async ({ page }) => {
    // El botón nuevo no abre una puerta: se comprueba por API, que es por donde
    // se intentaría. Un botón ausente no demuestra nada sobre lo que el
    // servidor acepta.
    await irA(page, '/mi-jornada', 'Mi jornada')

    // Por el ayudante, que apunta al servidor de la API. Con una URL relativa
    // la petición se la queda el servidor de desarrollo del frontend y devuelve
    // el index.html con un 200: la comprobación pasaba sin comprobar nada.
    const otra = '00000000-0000-0000-0000-000000000001'
    const respuesta = await api(page, `/reports/working-time/?employee=${otra}`)

    expect(respuesta.status).toBe(400)
  })
})
