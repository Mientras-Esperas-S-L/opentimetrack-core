import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
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
import AttachFileIcon from '@mui/icons-material/AttachFile'

import {
  cancelAbsence,
  downloadJustification,
  getAbsences,
  getLeaveBalance,
  PAGE_SIZE,
  requestAbsence,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pager,
  Panel,
  StatusChip,
} from '../../components/common.jsx'
import LeaveDialog from '../../components/LeaveDialog.jsx'
import { dateOf, dayRange, leaveLabel, leaveLength } from '../../components/format.js'

/** The balance, as a bar plus the three numbers behind it.
 *
 *  Pending days are drawn separately from taken ones: they are not spent yet,
 *  but they are not available either, and a single figure hides which is which.
 */
function Balance({ balance }) {
  const { entitled, taken, pending, remaining, period_start, period_end } = balance
  const pct = (value) => (entitled > 0 ? (value / entitled) * 100 : 0)
  // Which unit the three figures are in. Without it "quedan 9" is ambiguous by
  // about a third, which is exactly how far the balance used to be wrong.
  const unit = balance.working_days ? 'laborables' : 'naturales'

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
          {remaining === 1 ? 'día' : 'días'} {unit} de {entitled}
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

/** El grupo al que pertenece cada permiso, para agrupar el desplegable.
 *
 *  Diecisiete entradas en una lista plana son diecisiete entradas que hay que
 *  leer enteras. Agrupadas son cuatro decisiones: si son vacaciones, una baja,
 *  un permiso retribuido o uno sin sueldo.
 */
export default function MyLeave() {
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [confirming, setConfirming] = useState(null)

  const { data: balance } = useQuery({ queryKey: ['leave-balance'], queryFn: () => getLeaveBalance() })
  const { data: absences, isLoading } = useQuery({
    queryKey: ['absences', 'mine', page],
    queryFn: () => getAbsences({ page }),
    placeholderData: (previous) => previous,
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

  const rows = absences?.rows ?? []

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
                  {/* El nombre arriba y la duración abajo, con las fechas. Estuvo
                      un rato diciendo «Visita médica · 1 días» y repitiendo la
                      duración dos líneas seguidas: la de arriba contaba días
                      completos incluso cuando la ausencia eran dos horas y
                      media. */}
                  <Typography sx={{ fontWeight: 600 }}>{leaveLabel(absence)}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {dayRange(absence.start_date, absence.end_date)} · {leaveLength(absence)}
                    {absence.basis && (
                      <Typography component="span" variant="caption" sx={{ ml: 1 }}>
                        ({absence.basis})
                      </Typography>
                    )}
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
                  {absence.has_justification && (
                    <Button
                      size="small"
                      startIcon={<AttachFileIcon />}
                      onClick={() => downloadJustification(absence.id)}
                    >
                      Justificante
                    </Button>
                  )}
                  <StatusChip status={absence.status} label={absence.status_display} />
                  {absence.status === 'PENDING' && (
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() =>
                        setConfirming({
                          title: 'Retirar la solicitud',
                          body: `${leaveLabel(absence)} · ${dayRange(absence.start_date, absence.end_date)}`,
                          detail:
                            'Deja de estar pendiente de respuesta. Puedes volver a pedirla, pero esta solicitud queda retirada en el historial.',
                          verb: 'Retirar',
                          run: () => withdraw.mutate(absence.id),
                        })
                      }
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

      <Pager
        count={absences?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        noun="solicitudes"
      />

      <ConfirmDialog
        request={confirming}
        busy={withdraw.isPending}
        onClose={() => setConfirming(null)}
      />

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
