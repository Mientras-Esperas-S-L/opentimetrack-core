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
