/** Rechazar una ausencia dice por qué, y la persona lo lee.
 *
 *  Dos fallos juntos. En el calendario, «Rechazar» rechazaba al primer clic, sin
 *  confirmar ni pedir motivo. Y en «Por decidir», que sí lo pedía y decía «lo
 *  leerá la persona que lo solicitó», el motivo no se enviaba: el servidor no
 *  tenía dónde guardarlo. El «no» llegaba sin explicación por los dos caminos.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

const iso = (fecha) => fecha.toLocaleDateString('sv-SE')

test('desde el calendario se rechaza con motivo y la persona lo ve', async ({ browser }) => {
  const operario = await browser.newPage({ storageState: 'e2e/.sesiones/operario.json' })
  const admin = await browser.newPage({ storageState: 'e2e/.sesiones/admin.json' })
  await operario.goto('/mis-ausencias')

  // Un día suelto del mes que viene, para que no choque con lo sembrado.
  const dia = new Date()
  dia.setMonth(dia.getMonth() + 1, 9)
  while ([0, 6].includes(dia.getDay())) dia.setDate(dia.getDate() + 1)
  const tipos = (await api(operario, '/leave-types/')).body.results
  const vacaciones = tipos.find((tipo) => tipo.family === 'VACATION')
  const pedida = await api(operario, '/absences/', {
    method: 'POST',
    body: {
      leave_type: vacaciones.id,
      absence_type: 'VACATION',
      start_date: iso(dia),
      end_date: iso(dia),
      reason: 'Prueba de rechazo con motivo',
    },
  })
  expect(pedida.status, JSON.stringify(pedida.body)).toBe(201)
  const yo = (await api(operario, '/auth/me/')).body
  const nombre = yo.full_name ?? yo.user?.full_name ?? yo.first_name ?? yo.user?.first_name

  try {
    await irA(admin, '/panel/calendario', 'Calendario del equipo')
    await admin.getByRole('button', { name: 'Mes siguiente' }).click()
    const fila = admin.getByRole('row').filter({ hasText: nombre })
    await fila.getByRole('button', { name: /sin resolver/ }).first().click()

    await admin.getByRole('dialog').getByRole('button', { name: 'Rechazar' }).click()
    const motivo = admin.getByRole('dialog', { name: 'Rechazar la solicitud' })
    await motivo.getByLabel(/Motivo del rechazo/).fill('Esa semana cerramos el parque')
    await motivo.getByRole('button', { name: 'Rechazar' }).click()
    await expect(motivo).toBeHidden()

    const suya = (await api(operario, `/absences/${pedida.body.id}/`)).body
    expect(suya.status).toBe('REJECTED')
    expect(suya.resolution_note).toBe('Esa semana cerramos el parque')

    await operario.reload()
    await expect(
      operario.getByText('Motivo del rechazo: Esa semana cerramos el parque'),
    ).toBeVisible()
  } finally {
    await admin.close()
    await operario.close()
  }
})
