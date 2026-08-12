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
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import EditNoteIcon from '@mui/icons-material/EditNote'

import { getCorrections, getPunches, requestCorrection } from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader, Panel, SourceChip, StatusChip } from '../../components/common.jsx'
import { dateOf, hhmm, timeOf } from '../../components/format.js'
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

export default function MyTime() {
  const { session } = useAuth()
  const zone = session?.tenant?.time_zone
  const me = session?.user?.id
  const queryClient = useQueryClient()

  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)

  const { data: punches, isLoading } = useQuery({
    queryKey: ['punches', 'mine'],
    queryFn: () => getPunches({ employee: me, ordering: '-timestamp' }),
    enabled: Boolean(me),
  })

  const { data: corrections } = useQuery({
    queryKey: ['corrections', 'mine'],
    queryFn: () => getCorrections({ employee: me }),
    enabled: Boolean(me),
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

  const correctionRows = corrections?.rows ?? []
  const days = byDay(punches?.rows ?? [], zone)

  return (
    <>
      <PageHeader
        title="Mi jornada"
        subtitle="Tu registro completo. Tienes derecho a consultarlo, y se conserva cuatro años."
        action={
          <Button variant="outlined" startIcon={<EditNoteIcon />} onClick={() => setAsking(true)}>
            Pedir una corrección
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {correctionRows.length > 0 && (
        <Panel title="Mis solicitudes de corrección" sx={{ mb: 3 }}>
          <Stack sx={{ gap: 1 }}>
            {correctionRows.slice(0, 5).map((correction) => (
              <Stack
                key={correction.id}
                direction="row"
                sx={{ gap: 2, alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" noWrap>
                    {correction.kind_display} · {dateOf(correction.created_at)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {correction.reason}
                  </Typography>
                </Box>
                <StatusChip status={correction.status} label={correction.status_display} />
              </Stack>
            ))}
          </Stack>
        </Panel>
      )}

      {isLoading ? (
        <Loading rows={5} />
      ) : days.length === 0 ? (
        <Empty>Todavía no tienes fichajes registrados.</Empty>
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
    </>
  )
}
