/** Formatting shared by every screen.
 *
 *  Apart from the components on purpose: a module that exports both components
 *  and plain functions breaks fast refresh, which is why `useAuth` lives in its
 *  own file too.
 *
 *  Everything is rendered in the company's time zone, never the browser's. A
 *  worker in the Canaries reading a Madrid record must see the hours the record
 *  actually holds.
 */

const pad = (n) => String(n).padStart(2, '0')


export function hhmm(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return `${pad(hours)}:${pad(minutes)}`
}

export function timeOf(iso, timeZone) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })
}

export function dateOf(value, options = {}) {
  if (!value) return '—'
  const asDate = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  return asDate.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', ...options })
}

export function dayRange(from, to) {
  return from === to ? dateOf(from) : `${dateOf(from)} → ${dateOf(to)}`
}

/** Today, as the `yyyy-mm-dd` an `<input type="date">` wants.
 *
 *  `toISOString()` would be wrong here: it converts to UTC first, so anybody
 *  west of Greenwich gets yesterday for most of the evening and anybody east
 *  gets tomorrow in the small hours. `sv-SE` is the shortest way to ask the
 *  browser for the local date already in ISO order.
 */
export const today = () => new Date().toLocaleDateString('sv-SE')

/** The first of the current month, same format. The default window for the
 *  screens that show history: a period somebody recognises, rather than "the
 *  most recent fifty rows". */
export const firstOfThisMonth = () => {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), 1).toLocaleDateString('sv-SE')
}

/** First and last day of a month, as the strings a date filter wants.
 *
 *  Built from the local calendar rather than from UTC: `new Date(y, m, 0)`
 *  gives the last day of month `m`, and using `toISOString` on it would shift
 *  the boundary for anybody not on Greenwich.
 */
export const monthBounds = ({ year, month }) => ({
  from: new Date(year, month, 1).toLocaleDateString('sv-SE'),
  to: new Date(year, month + 1, 0).toLocaleDateString('sv-SE'),
})

/** "agosto de 2026", for a month header. */
export const monthName = ({ year, month }) =>
  new Date(year, month, 1).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
