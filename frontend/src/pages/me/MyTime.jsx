import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Switch from '@mui/material/Switch'
import FormControlLabel from '@mui/material/FormControlLabel'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import EditNoteIcon from '@mui/icons-material/EditNote'

import {
  acceptCorrection,
  disputeCorrection,
  getCorrections,
  getPunches,
  requestCorrection,
  updateMe,
} from '../../services/api.js'
import {
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Panel,
  SourceChip,
  StatusChip,
} from '../../components/common.jsx'
import { dateOf, hhmm, monthBounds, monthName, timeOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

/** Pairs the day's events into segments and adds them up.
 *
 *  An unmatched clock-in is left open rather than guessed at: inventing a
 *  closing time would put a number on screen that is not in the record.
 */
function summarise(events, zone) {
  const ordered = [...events].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  const segments = []
  let open = null

  for (const event of ordered) {
    if (event.punch_type === 'IN') {
      open = event
    } else if (open) {
      segments.push({ from: open.timestamp, to: event.timestamp })
      open = null
    }
  }

  const seconds = segments.reduce(
    (total, s) => total + (new Date(s.to) - new Date(s.from)) / 1000,
    0,
  )
  return { segments, seconds, openSince: open?.timestamp ?? null, zone }
}

function byDay(punches, zone) {
  const groups = new Map()
  for (const punch of punches) {
    if (punch.is_active === false) continue
    const day = new Date(punch.timestamp).toLocaleDateString('sv-SE', { timeZone: zone })
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day).push(punch)
  }
  return [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]))
}

function CorrectionDialog({ open, onClose, onSubmit, saving, error }) {
  const [form, setForm] = useState({
    kind: 'ADD',
    proposed_type: 'OUT',
    proposed_timestamp: '',
    reason: '',
  })

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSubmit({
      kind: form.kind,
      proposed_type: form.kind === 'ADD' ? form.proposed_type : undefined,
      proposed_timestamp: form.proposed_timestamp
        ? new Date(form.proposed_timestamp).toISOString()
        : undefined,
      reason: form.reason,
    })
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>Pedir una corrección</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Tu registro no se cambia ahora: se envía la petición y la resuelve un responsable. El
            fichaje original nunca se borra.
          </Typography>
          <Stack sx={{ gap: 2, pt: 0.5 }}>
            <TextField select label="Qué pasó" value={form.kind} onChange={set('kind')} fullWidth>
              <MenuItem value="ADD">Olvidé fichar</MenuItem>
              <MenuItem value="MODIFY">La hora registrada no es la real</MenuItem>
            </TextField>

            {form.kind === 'ADD' && (
              <TextField
                select
                label="Qué falta"
                value={form.proposed_type}
                onChange={set('proposed_type')}
                fullWidth
              >
                <MenuItem value="IN">La entrada</MenuItem>
                <MenuItem value="OUT">La salida</MenuItem>
              </TextField>
            )}

            <TextField
              required
              fullWidth
              type="datetime-local"
              label="Hora real"
              value={form.proposed_timestamp}
              onChange={set('proposed_timestamp')}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText="No puede ser una hora futura."
            />

            <TextField
              required
              fullWidth
              multiline
              minRows={3}
              label="Motivo"
              placeholder="Por ejemplo: me quedé sin batería y no pude fichar la salida."
              value={form.reason}
              onChange={set('reason')}
              helperText="Obligatorio. Una corrección sin motivo no se distingue de una manipulación."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            Enviar solicitud
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** Where somebody says they do not agree, and what they think happened.
 *
 *  Art. 4.b needs their authorisation to change an entry, and when it is not
 *  given it needs their version recorded next to the company's. So the account
 *  is required: a bare "no" leaves the record with a disagreement and nothing
 *  to weigh against it, which helps nobody --- least of all the person, whose
 *  side is the one that would be missing.
 */
function DisputeDialog({ open, correction, onClose, onConfirm, busy }) {
  const [account, setAccount] = useState('')

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onConfirm(account)
          setAccount('')
        }}
      >
        <DialogTitle>No estoy de acuerdo</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Tu versión queda guardada junto a la de la empresa y se informa a la representación
            legal. La empresa puede seguir adelante, y si lo hace el registro dirá que se aplicó
            sin tu conformidad y llevará esto al lado.
          </Typography>
          {correction?.reason && (
            <Typography
              variant="body2"
              sx={{ mb: 2, pl: 1.5, borderLeft: 2, borderColor: 'divider', fontStyle: 'italic' }}
            >
              {correction.reason}
            </Typography>
          )}
          <TextField
            autoFocus
            required
            fullWidth
            multiline
            minRows={3}
            label="Qué pasó según tú"
            placeholder="Por ejemplo: salí a las 18:15, no a las 17:00. Estuve cerrando el riego del parque."
            value={account}
            onChange={(event) => setAccount(event.target.value)}
            helperText="Obligatorio. Es tu versión de ese día."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Volver
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="secondary"
            disabled={busy || account.trim().length < 5}
          >
            Enviar mi versión
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** One correction in the worker's list.
 *
 *  Only those waiting on them carry buttons. The rest are history and read as
 *  history --- but they are still shown, because a change that was imposed is
 *  something the person is entitled to see afterwards, not only at the moment
 *  they were asked.
 */
function CorrectionRow({ correction, zone, onAccept, onDispute, busy }) {
  const waiting = correction.status === 'AWAITING_EMPLOYEE'
  // Having said no keeps it waiting --- the company still has to decide --- but it
  // is not the same as not having answered, and offering "no estoy de acuerdo"
  // again would suggest the first one did not register. Accepting stays
  // available: somebody may talk it over and change their mind.
  const saidNo = waiting && correction.employee_responded_at && !correction.employee_agreed

  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{ gap: 1.5, justifyContent: 'space-between', alignItems: { sm: 'flex-start' } }}
      >
        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {correction.kind_display}
            {correction.proposed_timestamp && (
              <>
                {' · '}
                <Box component="span" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {timeOf(correction.proposed_timestamp, zone)}
                </Box>{' '}
                del {dateOf(correction.proposed_timestamp)}
              </>
            )}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            Pedida el {dateOf(correction.created_at)}
          </Typography>
          {correction.reason && (
            <Typography
              variant="body2"
              sx={{ mt: 1, pl: 1.5, borderLeft: 2, borderColor: 'divider', fontStyle: 'italic' }}
            >
              {correction.reason}
            </Typography>
          )}
          {correction.employee_dissent && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Tu versión:</strong> {correction.employee_dissent}
            </Typography>
          )}
          {saidNo && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Se ha informado a la representación legal. La empresa decide ahora si aplica el
              cambio; si lo hace, constará que fue sin tu conformidad.
            </Typography>
          )}
          {correction.applied_without_agreement && (
            <Typography variant="caption" color="secondary.main" sx={{ display: 'block', mt: 1 }}>
              Aplicada sin tu conformidad. Tu versión consta en el registro y va al informe de
              Inspección.
            </Typography>
          )}
        </Box>

        <Stack sx={{ gap: 1, alignItems: { xs: 'flex-start', sm: 'flex-end' }, flexShrink: 0 }}>
          {/* Without a label the chip uses our own wording, which is written
              from this person's side: the server says "esperando a la persona
              afectada", true for the company and odd to read about yourself. */}
          <StatusChip
            status={correction.status}
            label={
              // Ours for the two art. 4.b states: the server's wording is
              // written for the record ("aplicada sin acuerdo, con la
              // discrepancia registrada") and the line underneath already says
              // that in full. The rest keep the server's.
              saidNo
                ? 'Has dicho que no'
                : ['AWAITING_EMPLOYEE', 'DISPUTED'].includes(correction.status)
                  ? undefined
                  : correction.status_display
            }
          />
          {waiting && (
            <Stack direction="row" sx={{ gap: 1 }}>
              {!saidNo && (
                <Button size="small" color="inherit" disabled={busy} onClick={onDispute}>
                  No estoy de acuerdo
                </Button>
              )}
              <Button size="small" variant="contained" disabled={busy} onClick={onAccept}>
                Aceptar
              </Button>
            </Stack>
          )}
        </Stack>
      </Stack>
    </Paper>
  )
}

const thisMonth = () => {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() }
}

export default function MyTime() {
  const { session, setSession } = useAuth()
  // El interruptor de recordatorios: autoservicio, como promete el correo. El
  // servidor solo deja tocar las preferencias propias.
  const remind = useMutation({
    mutationFn: (on) => updateMe({ wants_punch_reminders: on }),
    onSuccess: (user) => {
      if (session) setSession({ ...session, user: { ...session.user, ...user } })
    },
  })
  const zone = session?.tenant?.time_zone
  const me = session?.user?.id
  const queryClient = useQueryClient()

  const [asking, setAsking] = useState(false)
  const [disputing, setDisputing] = useState(null)
  // The screen showed the fifty most recent events --- about twenty-five days ---
  // with no way to look further back. This is somebody's own record, which the
  // law says they may consult and which is kept for four years, so "as far back
  // as the page happened to reach" is not an answer.
  const [month, setMonth] = useState(thisMonth)
  const [error, setError] = useState(null)

  const range = monthBounds(month)
  const { data: punches, isLoading } = useQuery({
    queryKey: ['punches', 'mine', range],
    queryFn: () =>
      getPunches({ employee: me, date_from: range.from, date_to: range.to, ordering: '-timestamp' }),
    placeholderData: (previous) => previous,
    enabled: Boolean(me),
  })

  const { data: corrections } = useQuery({
    queryKey: ['corrections', 'mine'],
    queryFn: () => getCorrections({ employee: me }),
    enabled: Boolean(me),
  })

  const answer = useMutation({
    mutationFn: ({ action, id, account }) => action(id, account),
    onSuccess: () => {
      setDisputing(null)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['corrections'] })
      queryClient.invalidateQueries({ queryKey: ['punches'] })
    },
    onError: setError,
  })

  const ask = useMutation({
    mutationFn: requestCorrection,
    onSuccess: () => {
      setAsking(false)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['corrections'] })
    },
    onError: setError,
  })

  const moveMonth = (delta) => {
    const next = new Date(month.year, month.month + delta, 1)
    setMonth({ year: next.getFullYear(), month: next.getMonth() })
  }
  const now = new Date()
  const isThisMonth = month.year === now.getFullYear() && month.month === now.getMonth()

  const correctionRows = corrections?.rows ?? []
  // Two lists, because they ask different things. One is waiting on this
  // person; the other is what has already happened, including changes applied
  // over their objection, which they are entitled to keep seeing.
  const waiting = correctionRows.filter((c) => c.status === 'AWAITING_EMPLOYEE')
  const history = correctionRows.filter((c) => c.status !== 'AWAITING_EMPLOYEE')
  const days = byDay(punches?.rows ?? [], zone)

  return (
    <>
      <PageHeader
        title="Mi jornada"
        subtitle="Tu registro completo. Tienes derecho a consultarlo, y se conserva cuatro años."
        action={
          <Stack direction="row" sx={{ gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
            <Tooltip title="Aviso si empieza tu turno y no has fichado, o si dejas la jornada abierta. Empuja al fichaje real, nunca lo hace por ti.">
              <FormControlLabel
                sx={{ mr: 0 }}
                control={
                  <Switch
                    size="small"
                    checked={session?.user?.wants_punch_reminders !== false}
                    disabled={remind.isPending}
                    onChange={(event) => remind.mutate(event.target.checked)}
                  />
                }
                label={<Typography variant="body2">Recordatorios</Typography>}
              />
            </Tooltip>
            <Button variant="outlined" startIcon={<EditNoteIcon />} onClick={() => setAsking(true)}>
              Pedir una corrección
            </Button>
          </Stack>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {/* Anything the company has proposed on this person's record, first and
          apart. Art. 4.b needs their authorisation, and until this existed the
          screen showed a chip saying their answer was awaited with no way to
          give one --- the proposal simply hung. */}
      {waiting.length > 0 && (
        <Panel
          title={waiting.length === 1 ? 'Un cambio en tu registro' : 'Cambios en tu registro'}
          hint="La empresa propone cambiar lo que quedó registrado. Sin tu conformidad no se aplica todavía, y si finalmente se aplica constará que fue sin acuerdo."
          sx={{ mb: 3 }}
        >
          <Stack sx={{ gap: 1 }}>
            {waiting.map((correction) => (
              <CorrectionRow
                key={correction.id}
                correction={correction}
                zone={zone}
                busy={answer.isPending}
                onAccept={() => answer.mutate({ action: acceptCorrection, id: correction.id })}
                onDispute={() => setDisputing(correction)}
              />
            ))}
          </Stack>
        </Panel>
      )}

      {history.length > 0 && (
        <Panel title="Mis solicitudes de corrección" sx={{ mb: 3 }}>
          <Stack sx={{ gap: 1 }}>
            {history.slice(0, 5).map((correction) => (
              <CorrectionRow key={correction.id} correction={correction} zone={zone} />
            ))}
          </Stack>
        </Panel>
      )}

      <Stack
        direction="row"
        sx={{ alignItems: 'center', gap: 1, mb: 2, justifyContent: 'space-between' }}
      >
        <Stack direction="row" sx={{ alignItems: 'center', gap: 1 }}>
          <IconButton size="small" onClick={() => moveMonth(-1)} aria-label="Mes anterior">
            <ChevronLeftIcon />
          </IconButton>
          <Typography sx={{ fontWeight: 600, minWidth: 170, textAlign: 'center' }}>
            {monthName(month)}
          </Typography>
          <IconButton
            size="small"
            onClick={() => moveMonth(1)}
            aria-label="Mes siguiente"
            // Nothing to see ahead: a future month is always empty, and an
            // arrow that leads to an empty screen reads like a fault.
            disabled={isThisMonth}
          >
            <ChevronRightIcon />
          </IconButton>
        </Stack>
        {!isThisMonth && (
          <Button size="small" onClick={() => setMonth(thisMonth())}>
            Volver a este mes
          </Button>
        )}
      </Stack>

      {isLoading ? (
        <Loading rows={5} />
      ) : days.length === 0 ? (
        <Empty>No hay fichajes en {monthName(month)}.</Empty>
      ) : (
        <Stack sx={{ gap: 1.5 }}>
          {days.map(([day, events]) => {
            const summary = summarise(events, zone)
            return (
              <Paper key={day} variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction="row"
                  sx={{ justifyContent: 'space-between', alignItems: 'baseline', gap: 2, mb: 1 }}
                >
                  <Typography sx={{ fontWeight: 600, textTransform: 'capitalize' }}>
                    {dateOf(day, { weekday: 'long', year: undefined })}
                  </Typography>
                  <Typography
                    // A span: the Chip below renders a div, and a div inside a
                    // p is invalid HTML. React was logging it on every render.
                    component="span"
                    sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 650, fontSize: '1.1rem' }}
                  >
                    {hhmm(summary.seconds)}
                    {summary.openSince && (
                      <Chip
                        size="small"
                        color="success"
                        label="abierto"
                        sx={{ ml: 1, height: 20, fontSize: '0.68rem' }}
                      />
                    )}
                  </Typography>
                </Stack>

                <Divider sx={{ mb: 1 }} />

                <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap' }}>
                  {summary.segments.map((segment) => (
                    <Typography
                      key={segment.from}
                      variant="body2"
                      sx={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {timeOf(segment.from, zone)} – {timeOf(segment.to, zone)}
                    </Typography>
                  ))}
                  {summary.openSince && (
                    <Typography
                      variant="body2"
                      color="success.main"
                      sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}
                    >
                      {timeOf(summary.openSince, zone)} – sin cerrar
                    </Typography>
                  )}
                </Stack>

                <Stack direction="row" sx={{ gap: 0.5, mt: 1.5, flexWrap: 'wrap' }}>
                  {[...new Set(events.map((e) => e.source))]
                    .filter((source) => source !== 'WEB' && source !== 'MOBILE')
                    .map((source) => (
                      <SourceChip key={source} source={source} />
                    ))}
                </Stack>
              </Paper>
            )
          })}
        </Stack>
      )}

      <CorrectionDialog
        open={asking}
        saving={ask.isPending}
        error={error}
        onClose={() => {
          setAsking(false)
          setError(null)
        }}
        onSubmit={ask.mutate}
      />

      <DisputeDialog
        open={Boolean(disputing)}
        correction={disputing}
        busy={answer.isPending}
        onClose={() => setDisputing(null)}
        onConfirm={(account) =>
          answer.mutate({ action: disputeCorrection, id: disputing.id, account })
        }
      />
    </>
  )
}
