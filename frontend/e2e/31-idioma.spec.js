/** El idioma: el de la empresa y el de cada persona.
 *
 *  Dos cosas salieron al mirar este eje.
 *
 *  Los ajustes ofrecían **ocho idiomas** y solo hay catálogo de castellano.
 *  Elegir «Catalán» dejaba el producto en castellano sin decir nada. Ofrecer un
 *  idioma y contestar en otro es peor que no ofrecerlo: quien lo elige se queda
 *  pensando que algo no funciona, y no hay nada que arreglar.
 *
 *  Y esa misma pantalla decía «cada persona puede usar otro distinto» --- con el
 *  campo en el modelo, en la API, y **sin ningún sitio donde elegirlo**. Es la
 *  tercera vez que un texto de esta aplicación promete una salida que no existe:
 *  antes fueron «se puede adjuntar después» y «usa los filtros para llegar al
 *  resto».
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.describe('Idioma', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('los ajustes solo ofrecen los idiomas que existen', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    await page.getByRole('combobox', { name: 'Idioma' }).click()
    const opciones = await page.getByRole('option').allInnerTexts()

    // Los cinco que tienen catálogo.
    for (const real of ['Español', 'Català', 'Galego', 'Euskara', 'Inglés']) {
      expect(opciones, `falta ${real}`).toContain(real)
    }
    // Y los tres que no lo tienen siguen fuera: ofrecerlos era prometer algo
    // que no pasaba, porque se contestaba en castellano igual.
    for (const sinCatalogo of ['Francés', 'Portugués', 'Alemán']) {
      expect(opciones, `sigue ofreciendo ${sinCatalogo}`).not.toContain(sinCatalogo)
    }
    await page.keyboard.press('Escape')
  })

  test('cada persona puede tener el suyo, que es lo que decía el texto', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    // Sobre alguien de usar y tirar: el idioma decide en qué lengua le llegan
    // los recordatorios, y cambiárselo a la plantilla real sería cambiarle el
    // correo a alguien por una prueba.
    const marca = `Idioma ${Date.now()}`
    const alta = await api(page, '/employees/', {
      method: 'POST',
      body: { email: `idioma${Date.now()}@prueba.local`, first_name: 'Prueba', last_name: marca },
    })
    expect(alta.status, JSON.stringify(alta.body)).toBe(201)

    const guardado = await api(page, `/employees/${alta.body.id}/`, {
      method: 'PATCH',
      body: { locale: 'en' },
    })
    expect(guardado.status).toBe(200)
    expect(guardado.body.locale).toBe('en')

    // Y la pantalla lo ofrece, que es lo que faltaba.
    await page.reload()
    await page.getByPlaceholder('Buscar por nombre, correo o número').fill(marca)
    await page.getByRole('button', { name: `Editar Prueba ${marca}` }).click()
    const dialogo = page.getByRole('dialog')
    await expect(dialogo.getByRole('combobox', { name: 'Idioma' })).toBeVisible()
    await page.keyboard.press('Escape')

    await api(page, `/employees/${alta.body.id}/`, {
      method: 'PATCH',
      body: { is_active: false },
    })
  })
})
