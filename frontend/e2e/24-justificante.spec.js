/** Adjuntar el justificante de un permiso.
 *
 *  El hueco: la API lo aceptaba desde el principio, el modelo lo guarda, la
 *  lista enseñaba un distintivo de «tiene justificante» y hay hasta un endpoint
 *  para descargarlo con su control de acceso probado --- y **ninguna pantalla lo
 *  subía nunca**. El permiso que lo pide se solicitaba con un texto y nada más.
 *
 *  Peor: el propio diálogo prometía que «se puede adjuntar después», y no se
 *  podía ni antes ni después. Todo el camino de vuelta estaba montado menos la
 *  ida.
 */

import { expect, test } from '@playwright/test'

import { api, irA, vigilarConsola } from './apoyo.js'

const MARCA = 'Prueba justificante 24'

const UN_PDF = Buffer.from(
  '%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n',
)

async function limpiar(page) {
  const mias = await api(page, '/absences/?status=PENDING')
  for (const fila of mias.body?.results ?? mias.body ?? []) {
    if ((fila.reason ?? '').startsWith(MARCA)) {
      await api(page, `/absences/${fila.id}/cancel/`, { method: 'POST' })
    }
  }
}

test.describe('Mis ausencias · el justificante', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('un permiso que lo pide deja adjuntarlo, y llega al servidor', async ({ page }) => {
    const ruido = vigilarConsola(page)
    await irA(page, '/mis-ausencias', 'Mis ausencias')
    await limpiar(page)

    await page.getByRole('button', { name: 'Solicitar' }).click()
    const dialogo = page.getByRole('dialog')

    // Matrimonio: art. 37.3.a, quince días naturales y con justificante.
    await dialogo.getByRole('combobox', { name: /Qué pides/ }).click()
    await page
      .getByRole('option', { name: /matrimonio/i })
      .first()
      .click()

    const adjuntar = dialogo.getByRole('button', { name: /Adjuntar el justificante/ })
    await expect(adjuntar).toBeVisible()
    await dialogo.locator('input[type="file"]').setInputFiles({
      name: 'libro-de-familia.pdf',
      mimeType: 'application/pdf',
      buffer: UN_PDF,
    })
    await expect(dialogo.getByText('libro-de-familia.pdf')).toBeVisible()

    await dialogo.getByLabel('Desde *').fill('2027-05-10')
    await dialogo.getByLabel('Hasta *').fill('2027-05-24')
    await dialogo.getByLabel('Motivo').fill(`${MARCA}: me caso`)
    await dialogo.getByRole('button', { name: /Solicitar|Enviar/ }).click()
    await expect(dialogo).toBeHidden()

    const creadas = await api(page, '/absences/?status=PENDING')
    const mia = (creadas.body?.results ?? []).find((a) => (a.reason ?? '').startsWith(MARCA))
    expect(mia, 'la solicitud no llegó').toBeTruthy()
    expect(mia.has_justification, 'el fichero no se subió').toBe(true)

    await limpiar(page)
    expect(ruido()).toEqual([])
  })

  test('una baja no ofrece adjuntar nada', async ({ page }) => {
    // El contraste, y no es cosmético: desde el RD 1060/2022 el parte médico no
    // se le entrega a la empresa, el servidor rechaza el fichero, y ofrecerlo
    // sería invitar a subir un dato de salud que no debe estar ahí.
    await irA(page, '/mis-ausencias', 'Mis ausencias')

    await page.getByRole('button', { name: 'Solicitar' }).click()
    const dialogo = page.getByRole('dialog')

    await dialogo.getByRole('combobox', { name: /Qué pides/ }).click()
    await page
      .getByRole('option', { name: /baja|incapacidad/i })
      .first()
      .click()

    await expect(dialogo.getByRole('button', { name: /Adjuntar el justificante/ })).toHaveCount(0)
  })
})

test.describe('Cuando la subida tarda', () => {
  test.use({ storageState: 'e2e/.sesiones/operario.json' })

  /** La pantalla anuncia «PDF o foto, hasta 10 MB». Con los diez segundos fijos
   *  de siempre, ese límite solo se cumplía si la subida iba a más de 8 Mb/s
   *  sostenidos; por debajo, axios abortaba **con el cuerpo ya enviado**. El
   *  servidor creaba la solicitud y a la persona se le decía que no había
   *  conexión: se iba creyendo que no había pedido el permiso mientras su
   *  responsable lo veía en la cola.
   */
  test('el plazo lo pone el peso del fichero, no un número fijo', async ({ page }) => {
    await irA(page, '/mis-ausencias', 'Mis ausencias')

    const plazos = await page.evaluate(async () => {
      const { plazoParaSubir } = await import('/src/services/api.js')
      const mb = (n) => n * 1024 * 1024
      return {
        sinFichero: plazoParaSubir(0),
        ochoMegas: plazoParaSubir(mb(8)),
        diezMegas: plazoParaSubir(mb(10)),
      }
    })

    // Ocho megas por 4G malo no caben en diez segundos ni de lejos.
    expect(plazos.ochoMegas).toBeGreaterThan(60_000)
    // Y el máximo que la pantalla promete tiene que caber en el plazo.
    expect(plazos.diezMegas).toBeGreaterThanOrEqual(plazos.ochoMegas)
    // Sin fichero no se alarga nada: una petición de texto sigue siendo corta.
    expect(plazos.sinFichero).toBeLessThanOrEqual(10_000 + 1_000)
  })
})
