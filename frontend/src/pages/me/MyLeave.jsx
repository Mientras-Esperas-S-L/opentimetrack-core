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
  getLeaveTypes,
  getLeaveUsage,
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
import { dateOf, dayRange, leaveLabel, leaveLength } from '../../components/format.js'

const today = () => new Date().toISOString().slice(0, 10)

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
const FAMILIES = {
  VACATION: 'Vacaciones',
  SICK_LEAVE: 'Bajas',
  PAID_LEAVE: 'Permisos retribuidos',
  UNPAID_LEAVE: 'Sin sueldo',
  SUSPENSION: 'Suspensión del contrato',
}

const UNITS = {
  DAYS_CALENDAR: 'días naturales',
  DAYS_WORKING: 'días laborables',
  HOURS: 'horas',
  WEEKS: 'semanas',
}

const PERIODS = {
  YEAR: 'este año',
  MONTH: 'este mes',
  WEEK: 'esta semana',
  DAY: 'hoy',
}

/** Sin decimales cuando no los tiene: «2 de 4», no «2,00 de 4,00». */
const formatAmount = (value) => {
  const n = Number(value ?? 0)
  return (n % 1 === 0 ? n.toString() : n.toFixed(2).replace(/0$/, '')).replace('.', ',')
}

const hoursBetween = (from, to) => {
  if (!from || !to) return 0
  const [h1, m1] = from.split(':').map(Number)
  const [h2, m2] = to.split(':').map(Number)
  return Math.max(0, (h2 * 60 + m2 - (h1 * 60 + m1)) / 60)
}

function LeaveDialog({ open, onClose, onSubmit, saving, error, types, usage }) {
  const [form, setForm] = useState({
    leave_type: null,
    start_date: today(),
    end_date: today(),
    start_time: '',
    end_time: '',
    reduction_share: '',
    reason: '',
  })
  const [partial, setPartial] = useState(false)

  const kind = types.find((type) => type.id === form.leave_type) ?? null
  const isSick = kind?.family === 'SICK_LEAVE'
  // Las vacaciones se cuentan en días contra un saldo en días. Medio día
  // redondearía o convertiría el saldo en un decimal que la ley no usa, así que
  // el servidor lo rechaza y aquí ni se ofrece.
  const canBePartial = Boolean(kind) && kind.family !== 'VACATION'
  // Un ERTE puede suspender el contrato o reducir la jornada. Solo se pregunta
  // en una suspensión: en cualquier otro sitio parecería un ajuste y no haría
  // nada, que es la peor clase de campo.
  const canReduce = kind?.family === 'SUSPENSION'
  // Lo que le queda de este permiso, si tiene tope y se acumula. Aquí y no en
  // otra pantalla: es justo antes de pedir cuando sirve de algo.
  const left = usage?.find((row) => row.leave_type === kind?.id) ?? null

  const set = (field) => (event) => {
    const next = { ...form, [field]: event.target.value }
    // Mover el inicio más allá del fin casi siempre es un clic torcido, no la
    // intención de reservar hacia atrás. El fin sigue al inicio en vez de dar
    // un error.
    if (field === 'start_date' && next.end_date < next.start_date) {
      next.end_date = next.start_date
    }
    setForm(next)
  }

  const pick = (chosen) => {
    setForm({ ...form, leave_type: chosen?.id ?? null })
    // Los que no tienen tope y los que se cuentan en horas —una consulta, un
    // examen, los cuatro días del art. 37.9— se piden por horas casi siempre.
    // Se ofrece esa forma primero en vez de esconderla tras un interruptor.
    setPartial(Boolean(chosen?.measured_in_hours) && chosen?.family !== 'VACATION')
  }

  const days = (new Date(form.end_date) - new Date(form.start_date)) / 86400000 + 1 || 0
  const hours = hoursBetween(form.start_time, form.end_time)

  // Aviso, no impedimento: el convenio mejora cualquiera de estas cifras, y la
  // copia de la empresa puede llevar la del Estatuto sin haberse actualizado.
  const overAllowance =
    kind?.amount != null &&
    !partial &&
    kind.period === 'EVENT' &&
    kind.unit !== 'HOURS' &&
    days > Number(kind.amount)

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit({
            leave_type: form.leave_type,
            start_date: form.start_date,
            end_date: partial ? form.start_date : form.end_date,
            start_time: partial ? form.start_time : null,
            end_time: partial ? form.end_time : null,
            reduction_share:
              canReduce && form.reduction_share !== '' ? Number(form.reduction_share) : null,
            reason: form.reason,
          })
        }}
      >
        <DialogTitle>Solicitar ausencia</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <Autocomplete
              options={[...types].sort((a, b) =>
                (FAMILIES[a.family] ?? '').localeCompare(FAMILIES[b.family] ?? '')
              )}
              groupBy={(option) => FAMILIES[option.family] ?? 'Otros'}
              getOptionLabel={(option) => option.name}
              value={kind}
              onChange={(_, chosen) => pick(chosen)}
              isOptionEqualToValue={(option, chosen) => option.id === chosen.id}
              renderOption={(props, option) => {
                const { key, ...rest } = props
                return (
                  <li key={key} {...rest}>
                    <Stack sx={{ py: 0.25 }}>
                      <Typography variant="body2">{option.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {option.allowance}
                        {option.basis ? ` · ${option.basis}` : ''}
                        {option.paid ? '' : ' · sin sueldo'}
                      </Typography>
                    </Stack>
                  </li>
                )
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  required
                  label="Qué pides"
                  helperText={
                    kind
                      ? [kind.allowance, kind.basis].filter(Boolean).join(' · ')
                      : 'Escribe para buscar entre los permisos de tu empresa.'
                  }
                />
              )}
            />

            {left && (
              <Alert
                severity={left.remaining <= 0 ? 'warning' : 'info'}
                variant="outlined"
              >
                Llevas <strong>{formatAmount(left.used)}</strong> de{' '}
                {formatAmount(left.allowance)} {UNITS[left.unit] ?? ''}{' '}
                {PERIODS[left.period] ?? ''}.{' '}
                {left.remaining > 0
                  ? `Te quedan ${formatAmount(left.remaining)}.`
                  : 'No te queda nada de este permiso en este periodo.'}
                {left.estimated &&
                  ' La duración de tu jornada se ha estimado: no hay cuadrante de ese día.'}
              </Alert>
            )}

            {/* La nota del artículo, cuando la hay. Es lo que evita la consulta
                a la gestoría: quién cuenta como familiar, si hay que avisar,
                hasta cuándo se puede pedir. */}
            {kind?.note && (
              <Alert severity="info" variant="outlined">
                {kind.note}
              </Alert>
            )}

            {isSick && (
              <Typography variant="body2" color="text.secondary">
                No hace falta que adjuntes el parte, y el sistema no lo guarda. Desde 2023 lo
                recibe la empresa directamente del INSS: basta con registrar las fechas.
              </Typography>
            )}

            {canBePartial && (
              <ToggleButtonGroup
                exclusive
                size="small"
                value={partial ? 'part' : 'whole'}
                onChange={(_, next) => next && setPartial(next === 'part')}
              >
                <ToggleButton value="whole">Días completos</ToggleButton>
                <ToggleButton value="part">Parte de un día</ToggleButton>
              </ToggleButtonGroup>
            )}

            {partial ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  required
                  fullWidth
                  type="date"
                  label="Día"
                  value={form.start_date}
                  onChange={set('start_date')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  required
                  type="time"
                  label="Desde"
                  value={form.start_time}
                  onChange={set('start_time')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  required
                  type="time"
                  label="Hasta"
                  value={form.end_time}
                  onChange={set('end_time')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Stack>
            ) : (
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
            )}

            {partial
              ? hours > 0 && (
                  <Typography variant="body2" color="text.secondary">
                    Son <strong>{hours.toString().replace('.', ',')}</strong>{' '}
                    {hours === 1 ? 'hora' : 'horas'}.
                  </Typography>
                )
              : days > 0 && (
                  <Typography variant="body2" color="text.secondary">
                    Son <strong>{days}</strong> {days === 1 ? 'día' : 'días'}.
                    {kind?.family === 'VACATION' &&
                      ' Del saldo solo salen los que ibas a trabajar: ni fines de semana ni festivos.'}
                  </Typography>
                )}

            {overAllowance && (
              <Alert severity="warning" variant="outlined">
                {kind.name} da {kind.allowance}, y estás pidiendo {days}. No se impide: el
                convenio puede dar más de lo que consta aquí. Quien lo resuelva lo verá.
                {Number(kind.extra_when_travelling) > 0 &&
                  ` Si hay desplazamiento, son ${Number(kind.extra_when_travelling)} días más.`}
              </Alert>
            )}

            {canReduce && (
              <>
                <TextField
                  fullWidth
                  type="number"
                  label="Reducción de jornada (%)"
                  value={form.reduction_share}
                  onChange={set('reduction_share')}
                  slotProps={{ htmlInput: { min: 1, max: 100, step: 1 } }}
                  helperText={
                    form.reduction_share === '' || Number(form.reduction_share) >= 100
                      ? 'Vacío o 100 suspende el contrato entero: no se espera jornada.'
                      : `Se sigue trabajando el ${100 - Number(form.reduction_share)} %. El cuadrante pasa a medirse contra esa jornada.`
                  }
                />
              </>
            )}

            <TextField
              fullWidth
              multiline
              minRows={2}
              label={kind?.needs_justification ? 'Motivo' : 'Motivo (opcional)'}
              required={Boolean(kind?.needs_justification) && !isSick}
              value={form.reason}
              onChange={set('reason')}
              helperText={
                isSick
                  ? 'No hace falta indicar la dolencia.'
                  : kind?.needs_justification
                    ? 'Este permiso pide justificante. Puedes adjuntarlo después.'
                    : 'Lo verá quien resuelva la solicitud.'
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving || !form.leave_type}>
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
  const [page, setPage] = useState(1)
  const [confirming, setConfirming] = useState(null)

  const { data: balance } = useQuery({ queryKey: ['leave-balance'], queryFn: () => getLeaveBalance() })
  const { data: leaveTypes = [] } = useQuery({
    queryKey: ['leave-types'],
    queryFn: () => getLeaveTypes(),
  })
  const { data: leaveUsage = [] } = useQuery({
    queryKey: ['leave-usage'],
    queryFn: () => getLeaveUsage(),
  })
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
        types={leaveTypes}
        usage={leaveUsage}
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
