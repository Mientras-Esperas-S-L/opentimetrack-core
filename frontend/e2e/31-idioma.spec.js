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

    // Los que tienen catálogo, **cada uno con su propio nombre**: quien abre
    // esta lista puede no entender el idioma en el que está la pantalla, que es
    // justo por lo que la abre. Por eso «English» y no «Inglés» --- antes iba a
    // medias, con dos en castellano y dos en el suyo.
    for (const real of ['Español', 'Català', 'Galego', 'English']) {
      expect(opciones, `falta ${real}`).toContain(real)
    }
    // Y los que no lo tienen siguen fuera: ofrecerlos era prometer algo que no
    // pasaba, porque se contestaba en castellano igual. Van escritos en las dos
    // formas ---la suya y la castellana--- para que esto no dependa de con cuál
    // se añadan el día que se añadan.
    for (const sinCatalogo of [
      'Euskara',
      'Français',
      'Francés',
      'Português',
      'Portugués',
      'Deutsch',
      'Alemán',
    ]) {
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

    // La baja va en un `finally`: sin él, cualquier fallo de aquí en adelante
    // deja a la persona activa para siempre, y como el nombre lleva la marca de
    // la tanda se acumula una por corrida rota. Así aparecieron las que había
    // que barrer a mano.
    try {
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
    } finally {
      const baja = await api(page, `/employees/${alta.body.id}/`, {
        method: 'PATCH',
        body: { is_active: false },
      })
      expect(baja.status, 'la limpieza no dio de baja a la persona de prueba').toBe(200)
    }
  })
})
