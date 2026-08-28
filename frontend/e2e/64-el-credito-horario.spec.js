/** El crédito horario de la representación legal (art. 68.e ET).
 *
 *  «Un crédito de horas mensuales retribuidas cada uno de los miembros del comité
 *  o delegado de personal **en cada centro de trabajo**», con una escala por
 *  tamaño: quince horas hasta cien personas, veinte hasta doscientas cincuenta, y
 *  así hasta cuarenta.
 *
 *  Va en la suite de navegador por lo que se ve y no se calcula: el catálogo no
 *  puede guardar esa cifra ---depende del centro de cada persona, así que dos
 *  compañeros pueden tener topes distintos--- y hasta hoy la pantalla decía que
 *  este permiso duraba «el tiempo indispensable», que hace pensar que no tiene
 *  tope ninguno.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

test.use({ storageState: 'e2e/.sesiones/admin.json' })

const CODIGO = 'es.union_duties'

async function elTipo(page) {
  const { body: tipos } = await api(page, '/leave-types/?page_size=100')
  return (tipos.results ?? tipos).find((x) => x.code === CODIGO)
}

test.describe('El crédito horario', () => {
  test('no dice que dure «el tiempo indispensable»', async ({ page }) => {
    await irA(page, '/panel/permisos', 'Permisos')
    const tipo = await elTipo(page)

    // Sin cifra en el catálogo, la pantalla caía en la frase de los permisos que
    // **paran** la jornada por el rato que haga falta. Este tiene tope, y lo
    // fija una escala legal.
    expect(tipo.allowance).not.toMatch(/tiempo indispensable/i)
    expect(tipo.allowance).toMatch(/escala/i)
  })

  test('el catálogo no trae cifra, y es a propósito', async ({ page }) => {
    await irA(page, '/panel/permisos', 'Permisos')
    const tipo = await elTipo(page)

    // **El contraste de todo lo demás.** Si alguien pusiera aquí una cifra fija,
    // todos los centros tendrían la misma y la escala del artículo dejaría de
    // aplicarse. La cifra de la empresa manda cuando la hay ---el convenio
    // amplía este crédito a menudo--- pero de fábrica no la hay.
    expect(tipo.amount).toBeNull()
  })

  test('a quien representa se le da el tope de su centro', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')
    const { body: gente } = await api(page, '/employees/?page_size=100')
    const quien = (gente.results ?? gente).find((p) => p.is_worker_representative)
    expect(quien, 'la demostración ya no tiene representantes').toBeTruthy()

    const { body: saldo } = await api(page, `/absences/balance/?employee=${quien.id}`)
    expect(saldo).toBeTruthy()
  })
})
