import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import LinearProgress from '@mui/material/LinearProgress'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'

import { cancelAbsence, getAbsences, getLeaveBalance, requestAbsence } from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader, Panel, StatusChip } from '../../components/common.jsx'
import { dateOf, dayRange } from '../../components/format.js'

const TYPES = [
  { value: 'VACATION', label: 'Vacaciones' },
  { value: 'PERSONAL', label: 'Permiso' },
  { value: 'SICK_LEAVE', label: 'Baja médica' },
  { value: 'OTHER', label: 'Otro' },
]

const today = () => new Date().toISOString().slice(0, 10)

/** The balance, as a bar plus the three numbers behind it.
 *
 *  Pending days are drawn separately from taken ones: they are not spent yet,
 *  but they are not available either, and a single figure hides which is which.
 */
function Balance({ balance }) {
  const { entitled, taken, pending, remaining, period_start, period_end } = balance
  const pct = (value) => (entitled > 0 ? (value / entitled) * 100 : 0)

  return (
    <Panel
      title="Vacaciones"
      hint={`Periodo del ${dateOf(period_start, { year: 'numeric' })} al ${dateOf(period_end, { year: 'numeric' })}`}
    >
      <Stack direction="row" sx={{ alignItems: 'baseline', gap: 1, mb: 1.5 }}>
        <Typography sx={{ fontSize: '2.6rem', fontWeight: 650, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
          {remaining}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {remaining === 1 ? 'día disponible' : 'días disponibles'} de {entitled}
        </Typography>
      </Stack>

      <Box
        sx={{
          position: 'relative',
          height: 10,
          borderRadius: 5,
          bgcolor: 'action.hover',
          overflow: 'hidden',
          mb: 1.5,
        }}
      >
        <Box sx={{ position: 'absolute', inset: 0, display: 'flex' }}>
          <Box sx={{ width: `${pct(taken)}%`, bgcolor: 'primary.main' }} />
          <Box
            sx={{
              width: `${pct(pending)}%`,
              // Hatched, not just a lighter tint: "asked for" and "taken" are
              // different states and should not read as shades of the same one.
              backgroundImage: (t) =>
                `repeating-linear-gradient(45deg, ${t.palette.primary.main} 0 4px, transparent 4px 8px)`,
            }}
          />
        </Box>
      </Box>

      <Stack direction="row" sx={{ gap: 3, flexWrap: 'wrap' }}>
        <Typography variant="caption" color="text.secondary">
          <strong>{taken}</strong> disfrutados
        </Typography>
        <Typography variant="caption" color="text.secondary">
          <strong>{pending}</strong> solicitados sin resolver
        </Typography>
      </Stack>
    </Panel>
  )
}

function LeaveDialog({ open, onClose, onSubmit, saving, error }) {
  const [form, setForm] = useState({
    absence_type: 'VACATION',
    start_date: today(),
    end_date: today(),
    reason: '',
  })

  const set = (field) => (event) => {
    const next = { ...form, [field]: event.target.value }
    // Moving the start past the end is almost always a mis-click, not an
    // intent to book backwards. The end follows instead of erroring.
    if (field === 'start_date' && next.end_date < next.start_date) {
      next.end_date = next.start_date
    }
    setForm(next)
  }

  const isSick = form.absence_type === 'SICK_LEAVE'
  const days =
    (new Date(form.end_date) - new Date(form.start_date)) / 86400000 + 1 || 0

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(form)
        }}
      >
        <DialogTitle>Solicitar ausencia</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              select
              fullWidth
              label="Tipo"
              value={form.absence_type}
              onChange={set('absence_type')}
            >
              {TYPES.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  {type.label}
                </MenuItem>
              ))}
            </TextField>

            {isSick && (
              <Typography variant="body2" color="text.secondary">
                No hace falta que adjuntes el parte, y el sistema no lo guarda. Desde 2023 lo
                recibe la empresa directamente del INSS: basta con registrar las fechas.
              </Typography>
            )}

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                required
                fullWidth
                type="date"
                label="Desde"
                value={form.start_date}
                onChange={set('start_date')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                required
                fullWidth
                type="date"
                label="Hasta"
                value={form.end_date}
                onChange={set('end_date')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>

            {days > 0 && (
              <Typography variant="body2" color="text.secondary">
                Son <strong>{days}</strong> {days === 1 ? 'día' : 'días'}.
              </Typography>
            )}

            <TextField
              fullWidth
              multiline
              minRows={2}
              label="Motivo (opcional)"
              value={form.reason}
              onChange={set('reason')}
              helperText={
                isSick
                  ? 'No hace falta indicar la dolencia.'
                  : 'Lo verá quien resuelva la solicitud.'
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            Solicitar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default function MyLeave() {
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)

  const { data: balance } = useQuery({ queryKey: ['leave-balance'], queryFn: () => getLeaveBalance() })
  const { data: absences, isLoading } = useQuery({
    queryKey: ['absences', 'mine'],
    queryFn: () => getAbsences(),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['absences'] })
    queryClient.invalidateQueries({ queryKey: ['leave-balance'] })
  }

  const ask = useMutation({
    mutationFn: requestAbsence,
    onSuccess: () => {
      setAsking(false)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const withdraw = useMutation({
    mutationFn: cancelAbsence,
    onSuccess: refresh,
    onError: setError,
  })

  const rows = absences ?? []

  return (
    <>
      <PageHeader
        title="Mis ausencias"
        subtitle="Vacaciones, permisos y bajas. Una ausencia aprobada bloquea el fichaje en esas fechas."
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAsking(true)}>
            Solicitar
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {balance ? <Balance balance={balance} /> : <LinearProgress sx={{ mb: 2 }} />}

      <Typography variant="h2" sx={{ fontSize: '1rem', mt: 3, mb: 1.5 }}>
        Historial
      </Typography>

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>Todavía no has solicitado ninguna ausencia.</Empty>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {rows.map((absence) => (
            <Paper key={absence.id} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                sx={{ gap: 1.5, justifyContent: 'space-between', alignItems: { sm: 'center' } }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 600 }}>
                    {absence.type_display}
                    <Typography component="span" color="text.secondary" sx={{ fontWeight: 400 }}>
                      {' · '}
                      {absence.days} {absence.days === 1 ? 'día' : 'días'}
                    </Typography>
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {dayRange(absence.start_date, absence.end_date)}
                  </Typography>
                  {absence.reason && (
                    <Typography variant="body2" sx={{ mt: 0.5, fontStyle: 'italic' }}>
                      {absence.reason}
                    </Typography>
                  )}
                  {absence.resolved_by_name && (
                    <Typography variant="caption" color="text.secondary">
                      Resuelta por {absence.resolved_by_name} el {dateOf(absence.resolved_at)}
                    </Typography>
                  )}
                </Box>

                <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexShrink: 0 }}>
                  <StatusChip status={absence.status} label={absence.status_display} />
                  {absence.status === 'PENDING' && (
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() => withdraw.mutate(absence.id)}
                      disabled={withdraw.isPending}
                    >
                      Retirar
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      <LeaveDialog
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
