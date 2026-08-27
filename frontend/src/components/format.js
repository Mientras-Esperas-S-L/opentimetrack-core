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

import i18next from '../i18n/index.js'
import { localeDeFechas } from '../i18n/index.js'

const pad = (n) => String(n).padStart(2, '0')

export function hhmm(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return `${pad(hours)}:${pad(minutes)}`
}

/** Una duración en minutos, dicha como la diría una persona.
 *
 *  «5 min», no «0,1 h»: cinco minutos en decimales de hora no se leen, y donde
 *  esto se usa —lo que sobra o falta de una jornada— la cifra pequeña es
 *  justamente la habitual.
 */
export function durationOf(totalMinutes) {
  const total = Math.max(0, Math.round(Number(totalMinutes) || 0))
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  if (!hours) return `${minutes} min`
  return minutes ? `${hours} h ${minutes} min` : `${hours} h`
}

/** `HH:MM:SS`. Para el contador de la pantalla de fichar y nada más.
 *
 *  Los segundos no aportan información —una jornada no se mide al segundo— pero
 *  sí aportan una cosa que importa: que se vea que el contador está vivo. Sin
 *  ellos parecía congelado, y un contador congelado hace dudar de si el fichaje
 *  llegó a registrarse.
 */
export function hhmmss(totalSeconds) {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  return `${pad(hours)}:${pad(minutes)}:${pad(safe % 60)}`
}

/** La palabra que toca según sean uno o varios.
 *
 *  «1 personas de alta» es lo que sale de escribir el plural a pelo, y solo se
 *  ve cuando hay exactamente uno --- o sea, en una empresa recién creada, que es
 *  la primera pantalla que ve un cliente nuevo. El número va aparte porque a
 *  veces lleva su propio formato o su `<strong>`.
 *
 *      {n} {plural(n, 'día', 'días')}
 */
export function plural(count, one, many) {
  return Number(count) === 1 ? one : many
}

/** La primera letra en mayúscula, y solo la primera.
 *
 *  `text-transform: capitalize` sube **cada** palabra, que en inglés es lo que
 *  se quiere y en castellano no: `toLocaleDateString` devuelve «agosto de 2026»
 *  y el CSS lo dejaba en «Agosto De 2026». Igual en catalán y gallego, donde
 *  además la preposición cambia. Aquí se resuelve en el idioma, no en la hoja
 *  de estilos, y los meses ingleses ya vienen capitalizados de fábrica.
 */
export function capitalised(text) {
  if (!text) return text
  return text.charAt(0).toLocaleUpperCase() + text.slice(1)
}

export function timeOf(iso, timeZone) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString(localeDeFechas(), {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })
}

/** La hora al segundo. Para nombrar un fichaje, no para enseñarlo.
 *
 *  En pantalla los segundos sobran, pero un rótulo de lector de pantalla tiene
 *  que **distinguir**: cuatro fichajes de la misma persona dentro del mismo
 *  minuto dan cuatro botones que se oyen idénticos, y quien navega así no puede
 *  saber cuál está pulsando. Al segundo sí se distinguen siempre, porque la
 *  guarda del doble toque no deja dos eventos de la misma persona a menos de
 *  cinco segundos.
 */
export function timeOfWithSeconds(iso, timeZone) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString(localeDeFechas(), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone,
  })
}

export function dateOf(value, options = {}) {
  if (!value) return '—'
  const asDate = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  return asDate.toLocaleDateString(localeDeFechas(), { day: '2-digit', month: 'short', ...options })
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
  new Date(year, month, 1).toLocaleDateString(localeDeFechas(), { month: 'long', year: 'numeric' })

/** Cómo se llama una ausencia y cuánto dura, en una línea.
 *
 *  Vivía repetido en cuatro pantallas cuando solo había cuatro tipos y todas
 *  las ausencias eran de días completos. Ahora hay un catálogo de diecisiete y
 *  las hay de parte de un día, así que las cuatro copias habrían divergido a la
 *  primera: unas dirían «Permiso» donde otras dicen «Visita médica», y ninguna
 *  diría las horas.
 */
export const leaveLabel = (absence) => absence?.leave_type_name || absence?.type_display || ''

export const leaveLength = (absence) => {
  const t = i18next.t.bind(i18next)
  if (!absence) return ''
  if (absence.start_time && absence.end_time) {
    const hours = Number(absence.hours ?? 0)
    const shown = hours.toFixed(hours % 1 === 0 ? 0 : 1).replace('.', ',')
    return `${absence.start_time.slice(0, 5)}–${absence.end_time.slice(0, 5)} · ${shown} h`
  }
  // Una suspensión que reduce en vez de parar es OTRA cosa que «91 días
  // fuera», y quien la lee —sobre todo quien la aprueba— necesita el dato que
  // la define.
  if (absence.reduction_share != null && Number(absence.reduction_share) < 100) {
    const share = Number(absence.reduction_share)
    return t('{{cuantos}} {{unidad}} · reduce la jornada un {{porcentaje}} %', {
      cuantos: absence.days,
      unidad: plural(absence.days, t('día'), t('días')),
      porcentaje: share % 1 === 0 ? share : share.toFixed(1).replace('.', ','),
    })
  }
  return `${absence.days} ${plural(absence.days, t('día'), t('días'))}`
}
