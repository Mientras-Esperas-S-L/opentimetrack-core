/** El buscador de personas, que es donde más caro sale equivocarse.
 *
 *  Aparece en media aplicación: registrar una ausencia, asignar un turno,
 *  sacar un informe, poner responsable a un departamento. Y en todos esos
 *  sitios elegir mal no es un error de forma --- es la ausencia de otra
 *  persona, el turno de otra persona, el informe de otra persona.
 *
 *  Ya dio dos fallos que se vieron a mano: no dejaba teclear (el valor viajaba
 *  como objeto y MUI perdía lo escrito) y dos personas con el mismo nombre
 *  chocaban de clave en React. Este fichero cubre el tercero, que era el peor
 *  de los tres porque no se veía:
 *
 *  **La lista tardaba 1,4 s en filtrar y mientras tanto enseñaba la anterior,
 *  entera.** Escribiendo «Hugo» y pulsando rápido, la primera opción seguía
 *  siendo «Jose Almenara». Salió escribiendo las pruebas del calendario, y la
 *  pista fue que la ausencia apareció a nombre de quien no era.
 */

import { expect, test } from '@playwright/test'

import { irA, vigilarConsola } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

/** Abre el diálogo de ausencia y devuelve su buscador de personas. */
async function buscadorDeAusencia(page) {
  await irA(page, '/panel/calendario', 'Calendario del equipo')
  await page.getByRole('button', { name: 'Registrar ausencia' }).click()
  const dialogo = page.getByRole('dialog')
  await expect(dialogo).toBeVisible()
  return { dialogo, campo: dialogo.getByRole('combobox', { name: /De quién/ }) }
}

test('lo que se teclea filtra al momento, sin esperar al servidor', async ({ page }) => {
  const { campo } = await buscadorDeAusencia(page)

  await campo.click()
  await expect(page.getByRole('option').first()).toBeVisible()
  const todas = await page.getByRole('option').count()
  expect(todas, 'la lista debería traer a toda la plantilla').toBeGreaterThan(5)

  await campo.fill('Hugo')

  // A los 300 ms el servidor todavía no ha contestado --- espera a que se deje
  // de teclear y luego va y vuelve. Lo que no puede es seguir ofreciendo a
  // dieciocho personas que no se llaman Hugo.
  await page.waitForTimeout(300)
  for (const texto of await page.getByRole('option').allInnerTexts()) {
    expect(texto, 'opción que no casa con lo tecleado').toMatch(/hugo/i)
  }

  // Y cuando llega la respuesta del servidor, sigue estando bien.
  await page.waitForTimeout(1500)
  await expect(page.getByRole('option')).toHaveCount(1)
  await expect(page.getByRole('option').first()).toContainText('Hugo')
})

test('pulsar deprisa elige a quien se ha escrito', async ({ page }) => {
  const { campo } = await buscadorDeAusencia(page)

  // Sin pausa entre escribir y pulsar: la prisa es la condición del fallo.
  await campo.fill('Hugo')
  await page.getByRole('option').first().click()

  // Solo el valor del campo. El texto del diálogo no sirve para comprobarlo:
  // lo que hay dentro de un `input` no aparece en el texto de la página.
  await expect(campo).toHaveValue(/Hugo/)
})

test('busca sin acentos', async ({ page }) => {
  const { campo } = await buscadorDeAusencia(page)

  // «Ibáñez» se escribe con dos acentos y nadie los pone buscando. El recorte
  // en cliente los ignora, y el del servidor también.
  await campo.fill('ibanez')
  await page.waitForTimeout(300)
  await expect(page.getByRole('option').first()).toContainText('Ibáñez')
})

test('dos personas con el mismo nombre no chocan', async ({ page }) => {
  const ruido = vigilarConsola(page)
  const { campo } = await buscadorDeAusencia(page)

  // MUI saca la clave de React del rótulo si no se le da otra cosa, así que
  // dos «Prueba De Playwright» producían «two children with the same key» y una
  // de las dos desaparecía de la lista. Ahora la clave es el identificador.
  await campo.fill('Prueba')
  await page.waitForTimeout(1600)

  const cuantas = await page.getByRole('option').count()
  if (cuantas > 1) {
    expect(ruido().filter((r) => /same key/i.test(r))).toEqual([])
  }
  expect(ruido()).toEqual([])
})

test('un selector múltiple obligatorio deja enviar el formulario', async ({ page }) => {
  // El fallo más caro de los que salieron escribiendo estas pruebas, y el más
  // difícil de ver: `required` acaba en el campo de texto de dentro del
  // selector, y en modo múltiple ese campo está vacío por diseño --- lo elegido
  // vive en las fichas. Así que el navegador consideraba el formulario
  // inválido pasara lo que pasara y cancelaba el envío **sin decir nada**.
  //
  // En «Asignar turno»: elegías turno, personas y fechas, pulsabas «Asignar» y
  // no ocurría nada. Ni petición, ni aviso, ni el diálogo cerrándose.
  await irA(page, '/panel/cuadrante', 'Cuadrante')
  await page.getByRole('button', { name: 'Asignar turno' }).click()

  const dialogo = page.getByRole('dialog')
  await dialogo.getByLabel('Turno').click()
  await page.getByRole('option').first().click()
  await dialogo.getByRole('combobox', { name: /A quién/ }).fill('Ana')
  await page.waitForTimeout(300)
  await page.getByRole('option').first().click()

  // Con alguien elegido, el formulario tiene que ser válido para el navegador.
  // Se pregunta directamente porque es quien cancelaba el envío, y lo hacía en
  // silencio: por pantalla no había ninguna diferencia entre esto y un error.
  const valido = await dialogo.evaluate((nodo) => nodo.querySelector('form')?.checkValidity())
  expect(valido, 'el navegador seguiría cancelando el envío').toBe(true)
})

test('sin resultados lo dice, en vez de quedarse en blanco', async ({ page }) => {
  const { campo } = await buscadorDeAusencia(page)

  await campo.fill('Zzzznadie')
  await page.waitForTimeout(1600)

  await expect(page.getByRole('option')).toHaveCount(0)
  await expect(page.getByText('Nadie coincide.')).toBeVisible()
})
