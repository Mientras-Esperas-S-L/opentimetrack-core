import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Snackbar from '@mui/material/Snackbar'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import EditCalendarIcon from '@mui/icons-material/EditCalendar'
import BackspaceOutlinedIcon from '@mui/icons-material/BackspaceOutlined'

import {
  assignShifts,
  clearShifts,
  getRoster,
  getHolidays,
  getShiftPatterns,
  paintShifts,
  getCoverage,
  reviewRoster,
} from '../../services/api.js'
import EmployeePicker from '../../components/EmployeePicker.jsx'
import CoberturaPendiente from '../../components/CoberturaPendiente.jsx'
import { ConfirmDialog, Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import { capitalised, dateOf, monthName } from '../../components/format.js'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

const iso = (year, month, day) =>
  `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
const daysIn = (year, month) => new Date(year, month + 1, 0).getDate()
/** Monday-first. JS counts Sunday as 0, and a Spanish roster starting on Sunday
 *  looks broken to everyone reading it. */
const weekdayOf = (year, month, day) => (new Date(year, month, day).getDay() + 6) % 7

const hhmm = (minutes) => `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`

function AssignDialog({ open, patterns, month, onClose, onSubmit, saving, error }) {
  const first = iso(month.year, month.month, 1)
  const last = iso(month.year, month.month, daysIn(month.year, month.month))

  const [form, setForm] = useState({
    employees: [],
    pattern: '',
    date_from: first,
    date_to: last,
    weekdays: [0, 1, 2, 3, 4],
  })

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(form)
        }}
      >
        <DialogTitle>Asignar turno</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              select
              required
              fullWidth
              label="Turno"
              value={form.pattern}
              onChange={set('pattern')}
            >
              {patterns.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name} · {hhmm(p.minutes)}
                </MenuItem>
              ))}
            </TextField>

            {/* Was a plain multi-select of the whole workforce, which meant
                scrolling to find each person --- and, because the list came from
                a paginated endpoint, only ever offered the first fifty. In a
                company of two hundred, three quarters of the staff could not be
                rostered at all and nothing on screen said so. */}
            <EmployeePicker
              multiple
              required
              label="A quién"
              value={form.employees}
              onChange={(ids) => setForm({ ...form, employees: ids })}
              helperText="Escribe para buscar. Se puede asignar a varias personas a la vez."
            />

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                type="date"
                label="Desde"
                value={form.date_from}
                onChange={set('date_from')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                fullWidth
                type="date"
                label="Hasta"
                value={form.date_to}
                onChange={set('date_to')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>

            <Box>
              <Typography variant="caption" color="text.secondary">
                Solo estos días
              </Typography>
              <ToggleButtonGroup
                size="small"
                value={form.weekdays}
                onChange={(_, next) => setForm({ ...form, weekdays: next })}
                sx={{ display: 'flex', mt: 0.5 }}
              >
                {WEEKDAYS.map((label, index) => (
                  <ToggleButton key={label} value={index} sx={{ flex: 1 }}>
                    {label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>

            <Alert severity="info" variant="outlined">
              Si ya había turno esos días, se sustituye. El turno dice cuándo se puede trabajar; no
              es un fichaje ni lo genera.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          {/* Sin días marcados no hay nada que asignar, y decirlo aquí es
              mejor que dejar pulsar y devolver un error. Vienen puestos de
              lunes a viernes, así que solo se llega a cero quitándolos todos
              a mano --- que es exactamente cuando alguien se ha liado. */}
          <Button
            type="submit"
            variant="contained"
            disabled={saving || !form.pattern || form.weekdays.length === 0}
          >
            Asignar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** The shift being painted, or the rubber.
 *
 *  A palette rather than a dropdown because the choice stays made across many
 *  strokes: you pick "mañana" once and then draw a fortnight of it. A select
 *  would close after each use and put the same two clicks in front of every
 *  block.
 *
 *  Nothing is selected to begin with, so the first drag on the grid cannot
 *  change a roster by accident. Picking a tool is the consent.
 */
function Palette({ patterns, tool, onPick }) {
  if (!patterns.length) return null

  return (
    <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', alignItems: 'center', mb: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mr: 0.5 }}>
        Pinta arrastrando:
      </Typography>
      {patterns.map((pattern) => {
        const picked = tool?.kind === 'paint' && tool.pattern.id === pattern.id
        return (
          <Chip
            key={pattern.id}
            label={`${pattern.name} · ${hhmm(pattern.minutes)}`}
            onClick={() => onPick(picked ? null : { kind: 'paint', pattern })}
            variant={picked ? 'filled' : 'outlined'}
            sx={{
              cursor: 'pointer',
              borderColor: pattern.colour,
              bgcolor: picked ? pattern.colour : 'transparent',
              color: picked ? '#fff' : 'text.primary',
              fontWeight: picked ? 700 : 400,
              '&:hover': { bgcolor: picked ? pattern.colour : 'action.hover' },
            }}
          />
        )
      })}
      <Chip
        icon={<BackspaceOutlinedIcon />}
        label="Borrar"
        onClick={() => onPick(tool?.kind === 'erase' ? null : { kind: 'erase' })}
        variant={tool?.kind === 'erase' ? 'filled' : 'outlined'}
        color={tool?.kind === 'erase' ? 'error' : 'default'}
        sx={{ cursor: 'pointer' }}
      />
      <Typography variant="caption" color="text.secondary">
        {tool
          ? 'Arrastra sobre el cuadrante. Esc para soltar la herramienta.'
          : 'Sin herramienta, arrastra un turno para moverlo de día o de persona.'}
      </Typography>
    </Stack>
  )
}

/** What the roster departs from, and on what basis.
 *
 *  Shown as a list rather than a count: "3 avisos" is something to dismiss,
 *  while "Ana, 8 h de descanso el 2 de septiembre, art. 34.3 ET" is something
 *  to fix. And the article is there so it can be argued with.
 */
//: Cuántos se enseñan antes de plegar. Ocho llena el aviso sin taparlo todo.
const FINDINGS_VISIBLE = 8

function Findings({ findings }) {
  //: Plegado de entrada y desplegable a mano. Hasta el 14/08/2026 el resto no
  //: era un enlace sino un «y 39 más.» muerto, así que con cuarenta y siete
  //: avisos había treinta y nueve que no se podían leer de ninguna manera.
  const [todos, setTodos] = useState(false)

  if (!findings?.length) return null

  const ocultos = findings.length - FINDINGS_VISIBLE
  const visibles = todos ? findings : findings.slice(0, FINDINGS_VISIBLE)

  return (
    <Alert severity="warning" sx={{ mb: 2 }}>
      <AlertTitle>
        El cuadrante se aparta de las reglas configuradas en {findings.length}{' '}
        {findings.length === 1 ? 'punto' : 'puntos'}
      </AlertTitle>
      <Typography variant="body2" sx={{ mb: 1 }}>
        No se impide guardarlo: hay sectores con jornadas especiales donde esto es legal. La
        decisión es de la empresa.
      </Typography>
      <Stack component="ul" sx={{ m: 0, pl: 2.5, gap: 0.5 }}>
        {visibles.map((finding, i) => (
          <Typography component="li" variant="body2" key={i}>
            <strong>{finding.employee_name}</strong>
            {/* One row per person and kind. Somebody whose pattern is nine
                hours continuous is owed a break every day of the month, and
                twenty-one identical lines bury the three that were about
                something else. */}
            {finding.count > 1
              ? `, ${finding.count} días desde el ${dateOf(finding.day)}: `
              : `, ${dateOf(finding.day)}: `}
            {finding.message}{' '}
            {finding.basis && (
              <Typography component="span" variant="caption" color="text.secondary">
                ({finding.basis})
              </Typography>
            )}
          </Typography>
        ))}
        {ocultos > 0 && (
          <Box component="li" sx={{ listStyle: 'none', ml: -2.5 }}>
            <Button
              size="small"
              color="inherit"
              onClick={() => setTodos((antes) => !antes)}
              sx={{ textTransform: 'none' }}
            >
              {todos ? `Ver solo los ${FINDINGS_VISIBLE} primeros` : `Ver los ${ocultos} restantes`}
            </Button>
          </Box>
        )}
      </Stack>
    </Alert>
  )
}

export default function Roster() {
  const queryClient = useQueryClient()
  const today = new Date()
  const [month, setMonth] = useState({ year: today.getFullYear(), month: today.getMonth() })
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(null)

  // What gets painted, and the rectangle being dragged right now.
  const [tool, setTool] = useState(null)
  const [drag, setDrag] = useState(null)
  // What the last stroke covered up. One level, deliberately: a stack invites
  // people to trust it, and the roster is not the record --- if the undo runs
  // out, the answer is to redraw, not to hunt through history.
  const [undo, setUndo] = useState(null)
  // Held in a ref as well: the window-level pointerup handler is registered
  // once and would otherwise close over the drag as it was when it mounted.
  const dragRef = useRef(null)

  // People brought into the grid who have no shifts yet. Without this the only
  // rows are the ones already rostered, so a new hire can never be drawn in ---
  // and the workforce endpoint pages at fifty, so listing everybody would
  // silently show three quarters of a large company and no sign of the rest.
  const [invited, setInvited] = useState([])

  const total = daysIn(month.year, month.month)
  const from = iso(month.year, month.month, 1)
  const to = iso(month.year, month.month, total)

  const { data: patterns = [] } = useQuery({
    queryKey: ['shift-patterns'],
    queryFn: getShiftPatterns,
  })
  const { data: shifts, isLoading } = useQuery({
    queryKey: ['roster', from, to],
    queryFn: () => getRoster(from, to),
  })
  // La misma clave que usa el panel de cobertura, así que es la misma consulta:
  // React Query la sirve de su caché y el mes no se pide dos veces.
  const { data: coverage } = useQuery({
    queryKey: ['coverage', from, to],
    queryFn: () => getCoverage(from, to),
  })
  const sinCubrir = useMemo(
    () => new Set((coverage?.uncovered ?? []).map((h) => h.shift_id)),
    [coverage],
  )

  const { data: review } = useQuery({
    queryKey: ['roster-review', from, to],
    queryFn: () => reviewRoster(from, to),
  })
  // Los festivos del mes. Se marcan en la cabecera igual que el fin de semana:
  // un día en el que casi nadie trabaja tiene que parecerlo antes de que
  // alguien pinte un turno encima.
  const { data: holidays = [] } = useQuery({
    queryKey: ['holidays', month.year],
    queryFn: () => getHolidays({ year: month.year }),
  })
  // Solo los de toda la empresa: los locales son de un centro, y sombrear la
  // columna entera diría que ese día libra gente que no libra.
  const holidayByDay = new Map(holidays.filter((h) => !h.workplace).map((h) => [h.day, h.name]))

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['roster'] })
    queryClient.invalidateQueries({ queryKey: ['roster-review'] })
  }

  const assign = useMutation({
    mutationFn: assignShifts,
    onSuccess: () => {
      setAssigning(false)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  // A stroke, and what the cells it touched held before it. Kept together so
  // undo is one call with the same shape --- restoring a drag that crossed four
  // different shifts and two blanks is not something a range endpoint can say.
  const paint = useMutation({
    mutationFn: paintShifts,
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const wipe = useMutation({
    mutationFn: clearShifts,
    onSuccess: refresh,
    onError: setError,
  })

  const move = (delta) => {
    const next = new Date(month.year, month.month + delta, 1)
    setMonth({ year: next.getFullYear(), month: next.getMonth() })
  }

  const rows = shifts ?? []
  const byPerson = new Map()
  for (const person of invited) {
    byPerson.set(person.id, { id: person.id, name: person.name, days: {} })
  }
  for (const shift of rows) {
    if (!byPerson.has(shift.employee)) {
      byPerson.set(shift.employee, { id: shift.employee, name: shift.employee_name, days: {} })
    }
    byPerson.get(shift.employee).days[shift.day] = shift
  }
  const rostered = [...byPerson.values()].sort((a, b) => a.name.localeCompare(b.name))

  const dayNumbers = Array.from({ length: total }, (_, i) => i + 1)
  const totalHours = rows.reduce((sum, s) => sum + s.minutes, 0) / 60

  // ---------------------------------------------------------------- painting
  //
  // A drag selects a rectangle: some people, some consecutive days. That is not
  // a limitation dressed up --- it is the shape the assign endpoint already
  // takes, and it is how a roster is actually built, a block of the team across
  // a block of the calendar.

  const painting = assign.isPending || wipe.isPending || paint.isPending

  /** A cell as the paint endpoint wants it: its pattern, or its bare spans.
   *
   *  Both, because a day can exist without a pattern --- a one-off, a
   *  twelve-hour night somebody typed in --- and undo has to put those back as
   *  they were rather than approximating them with the nearest pattern.
   */
  const asCell = (person, day, shift) => ({
    employee: person.id,
    day,
    ...(shift?.pattern ? { pattern: shift.pattern } : {}),
    ...(shift && !shift.pattern ? { segments: shift.segments } : {}),
  })

  const box = drag && {
    top: Math.min(drag.anchor.row, drag.focus.row),
    bottom: Math.max(drag.anchor.row, drag.focus.row),
    left: Math.min(drag.anchor.day, drag.focus.day),
    right: Math.max(drag.anchor.day, drag.focus.day),
  }
  const inBox = (row, day) =>
    box && row >= box.top && row <= box.bottom && day >= box.left && day <= box.right

  const startDrag = (row, day) => (event) => {
    if (painting) return

    // With a tool picked, dragging paints. Without one, dragging an existing
    // block MOVES it --- the gesture everybody tries first on a grid like
    // this, and the one that used to do nothing.
    if (!tool) {
      const person = rostered[row]
      const held = person?.days[iso(month.year, month.month, day)]
      if (!held) return
      event.currentTarget.releasePointerCapture?.(event.pointerId)
      event.preventDefault()
      const next = { kind: 'move', anchor: { row, day }, focus: { row, day }, shift: held }
      dragRef.current = next
      setDrag(next)
      return
    }

    // Without this the first cell captures the pointer and no other cell ever
    // sees `pointerenter`, so the drag paints one square. It is the default on
    // touch, and it is why this used mouse events and did not work on a tablet.
    event.currentTarget.releasePointerCapture?.(event.pointerId)
    event.preventDefault()
    const next = { kind: 'brush', anchor: { row, day }, focus: { row, day } }
    dragRef.current = next
    setDrag(next)
  }

  // On move rather than on enter. `pointerenter` does not bubble, so React
  // synthesises it from `pointerover`, and on touch the browser retargets every
  // event of a gesture to the element the finger went down on --- between the
  // two, a dragged selection would stay one cell wide. `pointermove` fires
  // straight at whatever is under the pointer, on both.
  const extendDrag = (row, day) => () => {
    const current = dragRef.current
    if (!current) return
    if (current.focus.row === row && current.focus.day === day) return
    const next = { ...current, focus: { row, day } }
    dragRef.current = next
    setDrag(next)
  }

  // Registered once on the window, not on the grid: a drag that ends outside
  // the table --- which is most of the ones that end near its edge --- has to
  // commit rather than leave a selection stuck to the cursor.
  useEffect(() => {
    const finish = () => {
      const current = dragRef.current
      dragRef.current = null
      setDrag(null)
      if (!current) return

      if (current.kind === 'move') {
        const { anchor, focus, shift } = current
        if (anchor.row === focus.row && anchor.day === focus.day) return
        const source = rostered[anchor.row]
        const target = rostered[focus.row]
        if (!source || !target) return

        const fromDay = iso(month.year, month.month, anchor.day)
        const toDay = iso(month.year, month.month, focus.day)
        // Move = the destination becomes what was held and the origin is
        // rubbed out, in ONE stroke, so undo restores both cells at once ---
        // including whatever the destination held before being covered.
        const before = [
          asCell(target, toDay, target.days[toDay]),
          asCell(source, fromDay, source.days[fromDay]),
        ]
        paint.mutate(
          [
            {
              employee: target.id,
              day: toDay,
              ...(shift.pattern ? { pattern: shift.pattern } : { segments: shift.segments }),
            },
            { employee: source.id, day: fromDay },
          ],
          // Only once it actually saved: offering to undo a stroke that never
          // landed would "restore" cells that never changed.
          { onSuccess: () => setUndo(before) },
        )
        return
      }

      if (!tool) return

      const top = Math.min(current.anchor.row, current.focus.row)
      const bottom = Math.max(current.anchor.row, current.focus.row)
      const left = Math.min(current.anchor.day, current.focus.day)
      const right = Math.max(current.anchor.day, current.focus.day)

      const stroke = []
      const before = []
      for (const person of rostered.slice(top, bottom + 1)) {
        for (let day = left; day <= right; day += 1) {
          const on = iso(month.year, month.month, day)
          before.push(asCell(person, on, person.days[on]))
          stroke.push({
            employee: person.id,
            day: on,
            ...(tool.kind === 'paint' ? { pattern: tool.pattern.id } : {}),
          })
        }
      }

      // Only worth offering if something actually changes. Painting mornings
      // over mornings is a no-op, and an undo button for a no-op is noise.
      const changed = stroke.some(
        (cell, i) => (cell.pattern ?? null) !== (before[i].pattern ?? null) || before[i].segments,
      )
      paint.mutate(stroke, { onSuccess: () => setUndo(changed ? before : null) })
    }

    const escape = (event) => {
      if (event.key !== 'Escape') return
      dragRef.current = null
      setDrag(null)
      setTool(null)
    }

    window.addEventListener('pointerup', finish)
    window.addEventListener('keydown', escape)
    return () => {
      window.removeEventListener('pointerup', finish)
      window.removeEventListener('keydown', escape)
    }
  })

  return (
    <>
      <PageHeader
        title="Cuadrante"
        subtitle="Cuándo se espera que trabaje cada persona. El turno no es el registro: lo fichado se guarda aparte y es lo que vale como prueba."
        action={
          <Button
            variant="contained"
            startIcon={<EditCalendarIcon />}
            onClick={() => setAssigning(true)}
            disabled={patterns.length === 0}
          >
            Asignar turno
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {/* Antes de la rejilla y antes de los avisos: es lo único de esta
          pantalla que hay que resolver hoy. Los avisos describen en qué se
          aparta el cuadrante de las reglas; esto son turnos que nadie va a
          trabajar, y mientras sigan así esa persona sale cada día como
          ausencia sin justificar. */}
      <CoberturaPendiente from={from} to={to} />

      {patterns.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Todavía no hay turnos definidos. Créalos en <strong>Turnos</strong> antes de montar el
          cuadrante.
        </Alert>
      )}

      <Stack direction="row" sx={{ alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <IconButton onClick={() => move(-1)} aria-label="Mes anterior">
          <ChevronLeftIcon />
        </IconButton>
        <Typography sx={{ fontWeight: 600, minWidth: 190 }}>
          {capitalised(monthName(month))}
        </Typography>
        <IconButton onClick={() => move(1)} aria-label="Mes siguiente">
          <ChevronRightIcon />
        </IconButton>
        <Box sx={{ flexGrow: 1 }} />
        {painting && <Chip size="small" variant="outlined" color="primary" label="Guardando…" />}
        {rows.length > 0 && (
          <Chip size="small" variant="outlined" label={`${totalHours.toFixed(0)} h planificadas`} />
        )}
        {/* Somebody with no shifts has no row, so there is nothing to draw on.
            Adding them here rather than listing the whole company keeps the
            grid to the size of a team and sidesteps a workforce endpoint that
            pages at fifty. */}
        <EmployeePicker
          size="small"
          label="Añadir al cuadrante"
          value=""
          sx={{ minWidth: 240 }}
          onChange={(id, person) => {
            if (!id || byPerson.has(id)) return
            const name =
              `${person?.first_name ?? ''} ${person?.last_name ?? ''}`.trim() ||
              (person?.email ?? '')
            setInvited([...invited, { id, name }])
          }}
        />
      </Stack>

      <Palette patterns={patterns} tool={tool} onPick={setTool} />

      <Findings findings={review?.findings} />

      {isLoading ? (
        <Loading rows={4} />
      ) : rostered.length === 0 ? (
        <Empty>No hay turnos asignados este mes.</Empty>
      ) : (
        <Paper variant="outlined" sx={{ overflowX: 'auto' }}>
          <Box sx={{ minWidth: 34 * total + 190 }}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: `190px repeat(${total}, 1fr)`,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Box sx={{ p: 1 }} />
              {dayNumbers.map((day) => {
                const weekday = weekdayOf(month.year, month.month, day)
                const feast = holidayByDay.get(iso(month.year, month.month, day))
                return (
                  <Tooltip key={day} title={feast ?? ''}>
                    <Box
                      sx={{
                        py: 0.75,
                        textAlign: 'center',
                        bgcolor: feast
                          ? 'warning.main'
                          : weekday >= 5
                            ? 'action.hover'
                            : 'transparent',
                        opacity: feast ? 0.28 : 1,
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ display: 'block', fontSize: '0.6rem', color: 'text.secondary' }}
                      >
                        {WEEKDAYS[weekday]}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ fontSize: '0.68rem', fontVariantNumeric: 'tabular-nums' }}
                      >
                        {day}
                      </Typography>
                    </Box>
                  </Tooltip>
                )
              })}
            </Box>

            {rostered.map((person, index) => {
              const hours = Object.values(person.days).reduce((s, x) => s + x.minutes, 0) / 60
              return (
                <Box
                  key={person.id}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `190px repeat(${total}, 1fr)`,
                    borderBottom: index < rostered.length - 1 ? 1 : 0,
                    borderColor: 'divider',
                    minHeight: 38,
                  }}
                >
                  <Stack sx={{ px: 1.5, justifyContent: 'center' }}>
                    <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                      {person.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {hours.toFixed(0)} h
                    </Typography>
                  </Stack>

                  {dayNumbers.map((day) => {
                    const shift = person.days[iso(month.year, month.month, day)]
                    const weekday = weekdayOf(month.year, month.month, day)
                    const moving = drag?.kind === 'move'
                    const isMoveSource =
                      moving && drag.anchor.row === index && drag.anchor.day === day
                    const isMoveTarget =
                      moving && !isMoveSource && drag.focus.row === index && drag.focus.day === day
                    const selected = drag?.kind === 'brush' && inBox(index, day)

                    // While something is being dragged, the cells it covers
                    // show what they are about to become. Painting a fortnight
                    // --- or dropping a shift --- and finding out afterwards is
                    // not a preview.
                    const preview =
                      selected && tool?.kind === 'paint'
                        ? { colour: tool.pattern.colour, letter: tool.pattern.name.slice(0, 1) }
                        : isMoveTarget
                          ? {
                              colour: drag.shift.colour,
                              letter: drag.shift.pattern_name || '·',
                            }
                          : null
                    const erasing = selected && tool?.kind === 'erase'

                    const cell = {
                      m: 0.3,
                      borderRadius: 0.5,
                      display: 'grid',
                      placeItems: 'center',
                      cursor: tool ? 'crosshair' : shift ? 'grab' : 'default',
                      touchAction: tool ? 'none' : 'auto',
                      outline: selected || isMoveTarget ? '2px solid' : 'none',
                      outlineColor: erasing ? 'error.main' : 'primary.main',
                      outlineOffset: '-1px',
                      // The origin fades while it is being carried, so the eye
                      // reads "from here, to there" without a legend.
                      opacity: erasing || isMoveSource ? 0.35 : 1,
                    }
                    const handlers = {
                      onPointerDown: startDrag(index, day),
                      onPointerMove: extendDrag(index, day),
                    }

                    if (!shift && !preview) {
                      return (
                        <Box
                          key={day}
                          {...handlers}
                          sx={{
                            ...cell,
                            bgcolor: weekday >= 5 ? 'action.hover' : 'transparent',
                          }}
                        />
                      )
                    }

                    const huerfano = Boolean(shift && sinCubrir.has(shift.id))
                    const colour = preview?.colour ?? shift.colour
                    const letter = (preview?.letter ?? shift.pattern_name ?? '·')
                      .slice(0, 1)
                      .toUpperCase()

                    return (
                      <Tooltip
                        key={day}
                        // Suppressed mid-drag: a tooltip following the cursor
                        // across thirty cells covers the very selection you are
                        // trying to see.
                        title={
                          drag || !shift
                            ? ''
                            : `${shift.pattern_name || 'Turno'} · ${shift.segments
                                .map((s) => `${s.start}–${s.end}`)
                                .join(' y ')}${huerfano ? ' · sin cubrir' : ''}`
                        }
                      >
                        <Box
                          {...handlers}
                          sx={{
                            ...cell,
                            bgcolor: colour,
                            // Sin nadie que lo trabaje. Rayado y no solo de otro
                            // color: la rejilla ya usa el color para decir qué
                            // turno es, y meter un color más ahí lo haría
                            // ilegible para quien no distinga dos de ellos. El
                            // rayado se ve aunque el color no.
                            ...(huerfano && {
                              backgroundImage:
                                'repeating-linear-gradient(45deg, rgba(0,0,0,.45) 0 3px, transparent 3px 6px)',
                              outline: '2px dashed',
                              outlineColor: 'warning.main',
                              outlineOffset: '-2px',
                            }),
                          }}
                        >
                          {/* The initial, not only the colour: a roster read on
                              a phone in sunlight, or by somebody who does not
                              distinguish two of them, still has to be legible. */}
                          <Typography sx={{ fontSize: '0.6rem', color: '#fff', fontWeight: 700 }}>
                            {letter}
                          </Typography>
                        </Box>
                      </Tooltip>
                    )
                  })}
                </Box>
              )
            })}
          </Box>
        </Paper>
      )}

      {rostered.length > 0 && (
        <Button
          size="small"
          color="inherit"
          sx={{ mt: 2 }}
          disabled={wipe.isPending}
          onClick={() =>
            setConfirming({
              title: 'Vaciar el mes',
              body: dateOf(from, { month: 'long', year: 'numeric', day: undefined }),
              // The one action here that cannot be undone, and it used to
              // happen on the first click. Saying how much it removes is the
              // difference between a warning and a formality.
              detail: `Se borran ${rows.length} ${rows.length === 1 ? 'turno' : 'turnos'} de ${rostered.length} ${rostered.length === 1 ? 'persona' : 'personas'}. Los fichajes ya registrados no se tocan: el cuadrante es lo previsto, no lo trabajado.`,
              verb: 'Vaciar',
              run: () =>
                // Sin `weekdays`: omitirlo es lo que significa «todos los días
                // del mes», que es de lo que va este botón. Mandarlo vacío
                // significa ninguno, y el servidor ya lo rechaza --- antes las
                // dos cosas llegaban iguales.
                wipe.mutate({
                  employees: rostered.map((p) => p.id),
                  pattern: patterns[0]?.id,
                  date_from: from,
                  date_to: to,
                }),
            })
          }
        >
          Vaciar el mes
        </Button>
      )}

      {/* Not a toast that fades. A stroke can cover a fortnight of somebody's
          life, and three seconds is not long enough to notice, look, and
          decide. It stays until the next stroke or until it is dismissed. */}
      <Snackbar
        open={Boolean(undo)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        onClose={(_, reason) => reason !== 'clickaway' && setUndo(null)}
      >
        <Alert
          severity="success"
          variant="filled"
          onClose={() => setUndo(null)}
          action={
            <Button
              size="small"
              color="inherit"
              disabled={paint.isPending}
              onClick={() => {
                paint.mutate(undo)
                setUndo(null)
              }}
            >
              Deshacer
            </Button>
          }
        >
          Cuadrante actualizado en {undo?.length} {undo?.length === 1 ? 'día' : 'días'}.
        </Alert>
      </Snackbar>

      <ConfirmDialog
        request={confirming}
        busy={wipe.isPending}
        onClose={() => setConfirming(null)}
      />

      <AssignDialog
        open={assigning}
        patterns={patterns}
        month={month}
        saving={assign.isPending}
        error={error}
        onClose={() => {
          setAssigning(false)
          setError(null)
        }}
        onSubmit={assign.mutate}
      />
    </>
  )
}
