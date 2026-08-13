import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import TodayIcon from '@mui/icons-material/Today'

import {
  approveAbsence,
  getAbsenceCalendar,
  rejectAbsence,
  requestAbsence,
} from '../../services/api.js'
import AddIcon from '@mui/icons-material/Add'

import LeaveDialog from '../../components/LeaveDialog.jsx'
import { Empty, Loading, PageHeader, StatusChip } from '../../components/common.jsx'
import { dayRange, leaveLabel, leaveLength } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'
import { PickFilter } from '../../components/filters.jsx'

/** What is behind a coloured band, and what can be done about it.
 *
 *  The calendar was read-only: you could see that somebody had asked for August
 *  and had to go to another screen to answer. Deciding is exactly what this
 *  view is for --- "can I approve August?" is the question it exists to answer
 *  --- so the answer belongs here.
 */
function AbsenceDialog({ absence, canDecide, busy, onClose, onApprove, onReject }) {
  const pending = absence?.status === 'PENDING'

  return (
    <Dialog open={Boolean(absence)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{absence?.employee_name}</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 1 }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography sx={{ fontWeight: 600 }}>{leaveLabel(absence)}</Typography>
            <StatusChip status={absence?.status} label={absence?.status_display} />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {absence && dayRange(absence.start_date, absence.end_date)} · {absence?.days}{' '}
            {absence?.days === 1 ? 'día' : 'días'}
          </Typography>
          {absence?.reason && (
            <Typography
              variant="body2"
              sx={{ mt: 1, pl: 1.5, borderLeft: 2, borderColor: 'divider', fontStyle: 'italic' }}
            >
              {absence.reason}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">
          Cerrar
        </Button>
        {canDecide && pending && (
          <>
            <Button onClick={onReject} disabled={busy} color="inherit">
              Rechazar
            </Button>
            <Button onClick={onApprove} disabled={busy} variant="contained">
              Aprobar
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  )
}

/** Colour by kind, not by person.
 *
 *  The question this screen answers is "can I approve August?", and what
 *  matters for that is how many people are away and why --- not who is who. A
 *  palette per person would need a legend nobody reads and would run out at
 *  twelve people.
 */
/** Los tipos que el calendario distingue, con su nombre.
 *
 *  En una constante y no escritos dos veces: los usan la leyenda de colores y
 *  el filtro, y si se separan acaban diciendo cosas distintas para lo mismo.
 */
const KIND_LABELS = {
  VACATION: 'Vacaciones',
  SICK_LEAVE: 'Baja',
  PAID_LEAVE: 'Permiso',
  UNPAID_LEAVE: 'Sin sueldo',
  SUSPENSION: 'Suspensión',
}

const KIND_COLOUR = {
  VACATION: 'primary.main',
  SICK_LEAVE: 'secondary.main',
  PAID_LEAVE: 'success.main',
  UNPAID_LEAVE: 'warning.main',
  // Meses sin jornada esperada (o con jornada reducida): lo contrario de
  // invisible. Estuvo sin color y la fila de alguien en ERTE salía vacía,
  // como si no pasara nada.
  SUSPENSION: 'info.main',
  // Los dos de antes del catálogo, para que los registros viejos no pierdan
  // su color.
  PERSONAL: 'success.main',
  OTHER: 'text.disabled',
}

const monthLabel = (year, month) =>
  new Date(year, month, 1).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })

const iso = (year, month, day) =>
  `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`

const daysIn = (year, month) => new Date(year, month + 1, 0).getDate()

/** Monday-first weekday index. JS gives Sunday as 0, and a Spanish calendar
 *  starting on Sunday looks broken to everyone reading it. */
const weekdayOf = (year, month, day) => (new Date(year, month, day).getDay() + 6) % 7

export default function TeamCalendar() {
  const today = new Date()
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() })

  const total = daysIn(cursor.year, cursor.month)
  const from = iso(cursor.year, cursor.month, 1)
  const to = iso(cursor.year, cursor.month, total)

  const [open, setOpen] = useState(null)
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const canManage = ['MANAGER', 'ADMIN'].includes(session?.user?.role)

  const { data: absences, isLoading } = useQuery({
    queryKey: ['absence-calendar', from, to],
    queryFn: () => getAbsenceCalendar(from, to),
  })

  const decide = useMutation({
    mutationFn: ({ action, id }) => action(id),
    onSuccess: () => {
      setOpen(null)
      queryClient.invalidateQueries({ queryKey: ['absence-calendar'] })
      queryClient.invalidateQueries({ queryKey: ['absences'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
  })

  // Registrar una ausencia en nombre de alguien: la baja que llama por
  // teléfono, y lo que no se solicita porque lo decide la empresa --- un ERTE,
  // una huelga, una suspensión. El servidor pone en vigor directamente lo que
  // registra la empresa; lo demás entra en la cola como siempre.
  const [recording, setRecording] = useState(false)
  //: Qué se enseña del mes. Con una plantilla grande el calendario se llena y
  //: la pregunta concreta ---«¿quién tiene vacaciones en agosto?», «¿qué queda
  //: sin resolver?»--- se pierde entre lo demás.
  const [kind, setKind] = useState('')
  const [state, setState] = useState('')
  const [recordError, setRecordError] = useState(null)
  const record = useMutation({
    mutationFn: requestAbsence,
    onSuccess: () => {
      setRecording(false)
      setRecordError(null)
      queryClient.invalidateQueries({ queryKey: ['absence-calendar'] })
      queryClient.invalidateQueries({ queryKey: ['absences'] })
      queryClient.invalidateQueries({ queryKey: ['leave-usage'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: setRecordError,
  })

  const move = (delta) => {
    const next = new Date(cursor.year, cursor.month + delta, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }

  const todo = absences ?? []
  const rows = todo.filter(
    (span) => (!kind || span.absence_type === kind) && (!state || span.status === state),
  )

  // One row per person, so a name is not repeated down the grid.
  const byPerson = new Map()
  for (const absence of rows) {
    if (!byPerson.has(absence.employee)) {
      byPerson.set(absence.employee, { name: absence.employee_name, spans: [] })
    }
    byPerson.get(absence.employee).spans.push(absence)
  }
  const people = [...byPerson.values()].sort((a, b) => a.name.localeCompare(b.name))

  const dayNumbers = Array.from({ length: total }, (_, i) => i + 1)
  const isToday = (day) =>
    cursor.year === today.getFullYear() &&
    cursor.month === today.getMonth() &&
    day === today.getDate()

  /** Which absence, if any, covers this day for this person. */
  const spanOn = (spans, day) => {
    const stamp = iso(cursor.year, cursor.month, day)
    return spans.find((s) => s.start_date <= stamp && s.end_date >= stamp)
  }

  return (
    <>
      <PageHeader
        title="Calendario del equipo"
        subtitle="Quién está fuera y cuándo. Las solicitudes sin resolver aparecen rayadas: cuentan para decidir, pero todavía no son un hecho."
        action={
          canManage && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setRecording(true)}>
              Registrar ausencia
            </Button>
          )
        }
      />

      <LeaveDialog
        forPerson
        open={recording}
        saving={record.isPending}
        error={recordError}
        onClose={() => {
          setRecording(false)
          setRecordError(null)
        }}
        onSubmit={record.mutate}
      />

      <Stack direction="row" sx={{ alignItems: 'center', gap: 1, mb: 2 }}>
        <IconButton onClick={() => move(-1)} aria-label="Mes anterior">
          <ChevronLeftIcon />
        </IconButton>
        <Typography sx={{ fontWeight: 600, minWidth: 190, textTransform: 'capitalize' }}>
          {monthLabel(cursor.year, cursor.month)}
        </Typography>
        <IconButton onClick={() => move(1)} aria-label="Mes siguiente">
          <ChevronRightIcon />
        </IconButton>
        <IconButton
          onClick={() => setCursor({ year: today.getFullYear(), month: today.getMonth() })}
          aria-label="Volver a hoy"
        >
          <TodayIcon />
        </IconButton>

        <PickFilter
          label="Tipo"
          value={kind}
          onChange={setKind}
          options={Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label }))}
          all="Todos"
          width={160}
        />
        <PickFilter
          label="Estado"
          value={state}
          onChange={setState}
          options={[
            { value: 'PENDING', label: 'Sin resolver' },
            { value: 'APPROVED', label: 'Concedidas' },
          ]}
          all="Todos"
          width={160}
        />

        <Box sx={{ flexGrow: 1 }} />

        <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
          {Object.entries(KIND_LABELS).map(([kind, label]) => (
            <Stack key={kind} direction="row" sx={{ alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: KIND_COLOUR[kind] }} />
              <Typography variant="caption" color="text.secondary">
                {label}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </Stack>

      <AbsenceDialog
        absence={open}
        canDecide={canManage}
        busy={decide.isPending}
        onClose={() => setOpen(null)}
        onApprove={() => decide.mutate({ action: approveAbsence, id: open.id })}
        onReject={() => decide.mutate({ action: rejectAbsence, id: open.id })}
      />

      {isLoading ? (
        <Loading rows={4} />
      ) : people.length === 0 ? (
        <Empty>Nadie tiene ausencias este mes.</Empty>
      ) : (
        <Paper variant="outlined" sx={{ overflowX: 'auto' }}>
          <Box sx={{ minWidth: 40 * total + 180 }}>
            {/* Day numbers. Weekends are tinted so a span reads at a glance
                without counting cells. */}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: `180px repeat(${total}, 1fr)`,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Box sx={{ p: 1 }} />
              {dayNumbers.map((day) => {
                const weekday = weekdayOf(cursor.year, cursor.month, day)
                return (
                  <Box
                    key={day}
                    sx={{
                      py: 1,
                      textAlign: 'center',
                      bgcolor: weekday >= 5 ? 'action.hover' : 'transparent',
                      ...(isToday(day) && {
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                      }),
                    }}
                  >
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

            {people.map((person, index) => (
              <Box
                key={person.name + index}
                sx={{
                  display: 'grid',
                  gridTemplateColumns: `180px repeat(${total}, 1fr)`,
                  borderBottom: index < people.length - 1 ? 1 : 0,
                  borderColor: 'divider',
                  minHeight: 40,
                }}
              >
                <Typography
                  variant="body2"
                  noWrap
                  sx={{ px: 1.5, alignSelf: 'center', fontWeight: 500 }}
                >
                  {person.name}
                </Typography>

                {dayNumbers.map((day) => {
                  const span = spanOn(person.spans, day)
                  const weekday = weekdayOf(cursor.year, cursor.month, day)
                  const colour = span ? KIND_COLOUR[span.absence_type] : null
                  const pending = span?.status === 'PENDING'

                  const cell = (
                    <Box
                      // A span is clickable; an empty cell is not. Before this
                      // the calendar was the only screen in the panel where
                      // nothing could be done: you could see that somebody had
                      // asked for August and had to go elsewhere to answer.
                      {...(span && {
                        role: 'button',
                        tabIndex: 0,
                        onClick: () => setOpen(span),
                        onKeyDown: (event) => ['Enter', ' '].includes(event.key) && setOpen(span),
                      })}
                      sx={{
                        m: 0.4,
                        ...(span && { cursor: 'pointer' }),
                        borderRadius: 0.5,
                        bgcolor: weekday >= 5 && !span ? 'action.hover' : 'transparent',
                        ...(span &&
                          (pending
                            ? {
                                // Hatched, not a lighter shade: asked-for and
                                // granted are different states, not degrees.
                                backgroundImage: (t) =>
                                  `repeating-linear-gradient(45deg, ${
                                    t.palette[
                                      span.absence_type === 'SICK_LEAVE' ? 'secondary' : 'primary'
                                    ].main
                                  } 0 3px, transparent 3px 7px)`,
                              }
                            : { bgcolor: colour })),
                      }}
                    />
                  )

                  return span ? (
                    <Tooltip
                      key={day}
                      title={`${leaveLabel(span)}${pending ? ' (sin resolver)' : ''} · ${leaveLength(span)}`}
                    >
                      {cell}
                    </Tooltip>
                  ) : (
                    <Box key={day} sx={{ display: 'contents' }}>
                      {cell}
                    </Box>
                  )
                })}
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {rows.some((a) => a.status === 'PENDING') && (
        <Chip
          size="small"
          color="warning"
          sx={{ mt: 2 }}
          label={`${rows.filter((a) => a.status === 'PENDING').length} sin resolver este mes`}
        />
      )}
    </>
  )
}
