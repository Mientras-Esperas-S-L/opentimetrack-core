/** Hacer lo mismo con varias cosas, y contar cómo fue.
 *
 *  Aparte de los componentes por el refresco rápido, igual que el hook. Y por
 *  eso el resumen llama a `i18next` directamente en vez de a un hook: aquí no
 *  hay componente al que engancharlo.
 */

import i18next from '../i18n/index.js'
import { plural } from '../components/format.js'

/** Ejecuta la misma acción sobre varios y cuenta cómo fue.
 *
 *  En serie, no en paralelo: veinte peticiones a la vez contra el mismo
 *  recurso es una forma tonta de encontrarse con el limitador de la API, y el
 *  usuario no gana nada --- la barra ya le dice que está trabajando.
 *
 *  Un fallo no para al resto. Que la número siete estuviera ya resuelta por
 *  otra persona no es razón para dejar sin responder a las trece siguientes.
 */
export async function runBulk(items, action) {
  const failed = []
  let ok = 0
  for (const item of items) {
    try {
      await action(item)
      ok += 1
    } catch (error) {
      failed.push({ item, error })
    }
  }
  return { ok, failed }
}

/** «3 aprobadas. 1 no se pudo: ya estaba resuelta.»
 *
 *  `done` llega ya traducido de quien llama: es el participio de la acción
 *  ---«aprobadas», «autorizadas»--- y solo allí se sabe cuál. */
export function bulkSummary({ ok, failed }, { done } = {}) {
  if (!failed.length) return null
  const t = i18next.t.bind(i18next)
  const first = failed[0].error?.message || t('no se pudo')
  return {
    code: 'bulk_partial',
    message: t('{{cuantas}} {{accion}}. {{fallidas}} no se {{pudieron}}: {{motivo}}{{yOtras}}', {
      cuantas: ok,
      accion: done ?? t('resueltas'),
      fallidas: failed.length,
      pudieron: plural(failed.length, t('pudo'), t('pudieron')),
      motivo: first,
      yOtras: failed.length > 1 ? ` ${t('(y otras)')}` : '',
    }),
  }
}
