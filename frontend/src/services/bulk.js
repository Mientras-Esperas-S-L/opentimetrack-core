/** Hacer lo mismo con varias cosas, y contar cómo fue.
 *
 *  Aparte de los componentes por el refresco rápido, igual que el hook.
 */

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

/** «3 aprobadas. 1 no se pudo: ya estaba resuelta.» */
export function bulkSummary({ ok, failed }, { done = 'resueltas' } = {}) {
  if (!failed.length) return null
  const first = failed[0].error?.message || 'no se pudo'
  return {
    code: 'bulk_partial',
    message:
      `${ok} ${done}. ${failed.length} no se ${failed.length === 1 ? 'pudo' : 'pudieron'}: ` +
      `${first}${failed.length > 1 ? ' (y otras)' : ''}`,
  }
}
