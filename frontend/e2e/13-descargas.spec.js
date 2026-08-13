/** Que lo descargado se pueda abrir.
 *
 *  Suena a perogrullada y era el fallo: pedir el informe de **toda la empresa**
 *  bajaba un `informe.pdf` que no abría ningún visor. No estaba roto el
 *  documento --- es que la entrega de toda la empresa no es un PDF, es un zip
 *  con un PDF por persona, y se estaba guardando con el nombre equivocado.
 *
 *  La causa no estaba en el informe sino en CORS: `Content-Disposition` no es
 *  una cabecera que el navegador deje leer salvo que el servidor la exponga, y
 *  no lo hacía. Sin ella la pantalla no sabía cómo se llamaba el fichero y caía
 *  en un apaño ---«informe» más la extensión pedida---, que para el zip era
 *  mentira. La misma familia que el desfase del reloj de la semana pasada, que
 *  también era una cabecera invisible.
 *
 *  Así que estas pruebas miran **los bytes**, no el nombre: un zip empieza por
 *  «PK» y un PDF por «%PDF». Comprobar solo la extensión habría dado verde
 *  durante todo el tiempo que estuvo roto.
 */

import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { irA, vigilarConsola } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

const PERIODO = { desde: '2026-06-29', hasta: '2026-08-13' }

/** Los primeros bytes del fichero, que es lo que dice qué es de verdad. */
async function contenido(descarga) {
  return readFileSync(await descarga.path())
}

async function prepararInformes(page, dequien) {
  await irA(page, '/panel/informes', 'Informes')
  await page.getByRole('combobox', { name: /De quién/ }).click()
  await page.getByRole('option', { name: dequien }).click()
  await page.getByLabel('Desde').fill(PERIODO.desde)
  await page.getByLabel('Hasta').fill(PERIODO.hasta)
  await page.waitForTimeout(400)
}

test('el informe de toda la empresa baja como zip, y es un zip', async ({ page }) => {
  const ruido = vigilarConsola(page)
  await prepararInformes(page, 'Toda la empresa')

  const espera = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar PDF' }).click()
  const descarga = await espera

  // El nombre lo pone el servidor y dice de qué empresa y de qué periodo es.
  // «informe.pdf» no decía ninguna de las dos cosas, además de mentir.
  expect(descarga.suggestedFilename()).toBe(
    `working-time_B00000001_${PERIODO.desde}_${PERIODO.hasta}.zip`,
  )

  // Y los bytes: «PK» es la firma de un zip. Sin esto la prueba pasaría con un
  // fichero corrupto que se llamara bien.
  expect((await contenido(descarga)).subarray(0, 2).toString('latin1')).toBe('PK')

  expect(ruido()).toEqual([])
})

test('el de una persona sí es un PDF de verdad', async ({ page }) => {
  await prepararInformes(page, 'Una persona')
  await page.getByRole('combobox', { name: /^Persona/ }).fill('Hugo')
  await page.getByRole('option', { name: /Hugo Bermejo/ }).click()

  const espera = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar PDF' }).click()
  const descarga = await espera

  expect(descarga.suggestedFilename()).toMatch(/^working-time_.*\.pdf$/)
  expect((await contenido(descarga)).subarray(0, 4).toString('latin1')).toBe('%PDF')
})

test('el CSV se lee en cualquier sitio', async ({ page }) => {
  await prepararInformes(page, 'Toda la empresa')

  const espera = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar CSV' }).click()
  const texto = (await contenido(await espera)).toString('utf8')

  // Sin «\r\n». No es una manía: el «\r» se queda pegado a la última columna,
  // así que un `awk -F";"` o un `split(";")` devuelve «05:00\r» donde esperaba
  // «05:00», y eso no se ve hasta que alguien compara horas y no le cuadran.
  expect(texto).not.toContain('\r')

  // Y sin marca de orden de bytes: la pone Excel y la arrastra medio mundo,
  // pero se cuela en el primer campo de la primera fila de cualquier lector
  // que no la espere.
  expect(texto.charCodeAt(0)).not.toBe(0xfeff)

  // Que además tenga dentro lo que promete, no solo la forma correcta.
  expect(texto).toContain('Jardines Demo')
  expect(texto).toMatch(/Huella de verificación;[0-9a-f]{64}/)
})

test('el registro de actividad se descarga con el mismo criterio', async ({ page }) => {
  await irA(page, '/actividad', 'Registro de actividad')

  const espera = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar' }).click()
  const descarga = await espera
  const texto = (await contenido(descarga)).toString('utf8')

  // El mismo `csv.writer` está en dos sitios, así que el arreglo también.
  expect(texto).not.toContain('\r')
  expect(descarga.suggestedFilename()).toMatch(/\.csv$/)
})
