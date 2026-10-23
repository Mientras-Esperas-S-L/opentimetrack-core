/** Cómo se dice un cambio de turno. Lo comparten el aviso a la persona y la
 *  lista de quien gestiona, para que los dos lo cuenten igual. */

/** `08:00-15:00 y 17:00-20:00`. */
export function tramos(segments, t) {
  const partes = (segments ?? []).map((s) => `${s.start}–${s.end}`)
  if (partes.length <= 1) return partes[0] ?? ''
  return t('{{primeros}} y {{ultimo}}', {
    primeros: partes.slice(0, -1).join(', '),
    ultimo: partes.at(-1),
  })
}

/** Un día que cambió, dicho como lo diría quien organiza el cuadrante. */
export function queCambio(cambio, t) {
  if (!cambio.before) return t('turno nuevo, {{ahora}}', { ahora: tramos(cambio.after, t) })
  if (!cambio.after) return t('sin turno, antes {{antes}}', { antes: tramos(cambio.before, t) })
  return t('{{antes}}, ahora {{ahora}}', {
    antes: tramos(cambio.before, t),
    ahora: tramos(cambio.after, t),
  })
}
