import { useState } from 'react'
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
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import EditCalendarIcon from '@mui/icons-material/EditCalendar'

import {
  assignShifts,
  clearShifts,
  getEmployees,
  getRoster,
  getShiftPatterns,
  reviewRoster,
} from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import { dateOf } from '../../components/format.js'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

const iso = (year, month, day) =>
  `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
const daysIn = (year, month) => new Date(year, month + 1, 0).getDate()
/** Monday-first. JS counts Sunday as 0, and a Spanish roster starting on Sunday
 *  looks broken to everyone reading it. */
const weekdayOf = (year, month, day) => (new Date(year, month, day).getDay() + 6) % 7

const hhmm = (minutes) => `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`

function AssignDialog({ open, people, patterns, month, onClose, onSubmit, saving, error }) {
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

            <TextField
              select
              required
              fullWidth
              label="A quién"
              value={form.employees}
              onChange={set('employees')}
              slotProps={{ select: { multiple: true } }}
              helperText="Se puede asignar a varias personas a la vez."
            >
              {people.map((person) => (
                <MenuItem key={person.id} value={person.id}>
                  {`${person.first_name} ${person.last_name}`.trim() || person.email}
                </MenuItem>
              ))}
            </TextField>

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
              Si ya había turno esos días, se sustituye. El turno dice cuándo se puede trabajar;
              no es un fichaje ni lo genera.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving || !form.pattern}>
            Asignar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** What the roster departs from, and on what basis.
 *
 *  Shown as a list rather than a count: "3 avisos" is something to dismiss,
 *  while "Ana, 8 h de descanso el 2 de septiembre, art. 34.3 ET" is something
 *  to fix. And the article is there so it can be argued with.
 */
function Findings({ findings, people }) {
  if (!findings?.length) return null

  const nameOf = (id) => {
    const person = people.find((p) => p.id === id)
    return person ? `${person.first_name} ${person.last_name}`.trim() : ''
  }

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
        {findings.slice(0, 8).map((finding, i) => (
          <Typography component="li" variant="body2" key={i}>
            <strong>{nameOf(finding.employee)}</strong>, {dateOf(finding.day)}: {finding.message}{' '}
            <Typography component="span" variant="caption" color="text.secondary">
              ({finding.basis})
            </Typography>
          </Typography>
        ))}
        {findings.length > 8 && (
          <Typography component="li" variant="body2" color="text.secondary">
            y {findings.length - 8} más.
          </Typography>
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

  const total = daysIn(month.year, month.month)
  const from = iso(month.year, month.month, 1)
  const to = iso(month.year, month.month, total)

  const { data: patterns = [] } = useQuery({
    queryKey: ['shift-patterns'],
    queryFn: getShiftPatterns,
  })
  const { data: people = [] } = useQuery({
    queryKey: ['employees', 'for-roster'],
    queryFn: () => getEmployees({ is_active: true }),
  })
  const { data: shifts, isLoading } = useQuery({
    queryKey: ['roster', from, to],
    queryFn: () => getRoster(from, to),
  })
  const { data: review } = useQuery({
    queryKey: ['roster-review', from, to],
    queryFn: () => reviewRoster(from, to),
  })

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
  for (const shift of rows) {
    if (!byPerson.has(shift.employee)) {
      byPerson.set(shift.employee, { id: shift.employee, name: shift.employee_name, days: {} })
    }
    byPerson.get(shift.employee).days[shift.day] = shift
  }
  const rostered = [...byPerson.values()].sort((a, b) => a.name.localeCompare(b.name))

  const dayNumbers = Array.from({ length: total }, (_, i) => i + 1)
  const totalHours = rows.reduce((sum, s) => sum + s.minutes, 0) / 60

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
        <Typography sx={{ fontWeight: 600, minWidth: 190, textTransform: 'capitalize' }}>
          {new Date(month.year, month.month, 1).toLocaleDateString('es-ES', {
            month: 'long',
            year: 'numeric',
          })}
        </Typography>
        <IconButton onClick={() => move(1)} aria-label="Mes siguiente">
          <ChevronRightIcon />
        </IconButton>
        <Box sx={{ flexGrow: 1 }} />
        {rows.length > 0 && (
          <Chip size="small" variant="outlined" label={`${totalHours.toFixed(0)} h planificadas`} />
        )}
      </Stack>

      <Findings findings={review?.findings} people={people} />

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
                return (
                  <Box
                    key={day}
                    sx={{
                      py: 0.75,
                      textAlign: 'center',
                      bgcolor: weekday >= 5 ? 'action.hover' : 'transparent',
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

                    if (!shift) {
                      return (
                        <Box
                          key={day}
                          sx={{
                            m: 0.3,
                            borderRadius: 0.5,
                            bgcolor: weekday >= 5 ? 'action.hover' : 'transparent',
                          }}
                        />
                      )
                    }

                    return (
                      <Tooltip
                        key={day}
                        title={`${shift.pattern_name || 'Turno'} · ${shift.segments
                          .map((s) => `${s.start}–${s.end}`)
                          .join(' y ')}`}
                      >
                        <Box
                          sx={{
                            m: 0.3,
                            borderRadius: 0.5,
                            bgcolor: shift.colour,
                            display: 'grid',
                            placeItems: 'center',
                          }}
                        >
                          {/* The initial, not only the colour: a roster read on
                              a phone in sunlight, or by somebody who does not
                              distinguish two of them, still has to be legible. */}
                          <Typography
                            sx={{ fontSize: '0.6rem', color: '#fff', fontWeight: 700 }}
                          >
                            {(shift.pattern_name || '·').slice(0, 1).toUpperCase()}
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
            wipe.mutate({
              employees: rostered.map((p) => p.id),
              pattern: patterns[0]?.id,
              date_from: from,
              date_to: to,
              weekdays: [],
            })
          }
        >
          Vaciar el mes
        </Button>
      )}

      <AssignDialog
        open={assigning}
        people={people}
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
