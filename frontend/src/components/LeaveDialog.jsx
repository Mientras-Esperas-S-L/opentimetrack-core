import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'

import { getLeaveTypes, getLeaveUsage } from '../services/api.js'
import EmployeePicker from './EmployeePicker.jsx'
import { ErrorNote } from './common.jsx'

/** Pedir una ausencia, o registrarla la empresa. Un solo formulario.
 *
 *  Vivía dentro de Mis ausencias y salió de allí cuando apareció el segundo
 *  uso: dirección registrando lo que no se solicita —un ERTE, una huelga, una
 *  suspensión disciplinaria—. Dos copias de un formulario con esta cantidad de
 *  reglas habrían divergido a la primera corrección.
 *
 *  Los dos modos difieren en tres cosas y el resto es idéntico: `forPerson`
 *  añade el selector de persona, ofrece también los tipos que registra la
 *  empresa, y lo que crea con esos tipos entra directamente en vigor (eso lo
 *  decide el servidor, no este formulario).
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

const weekdaysBetween = (from, to) => {
  let n = 0
  const day = new Date(from)
  const end = new Date(to)
  while (day <= end) {
    const weekday = day.getDay()
    if (weekday !== 0 && weekday !== 6) n += 1
    day.setDate(day.getDate() + 1)
  }
  return n
}

/** Cuánto se está pidiendo, en la unidad del permiso.
 *
 *  La conversión es el arreglo entero: el permiso parental da ocho *semanas*,
 *  y comparar el tope contra un recuento de días hacía saltar el aviso a
 *  cualquiera que pidiera más de ocho días de un permiso de ocho semanas.
 *  Null significa que no hay comparación con sentido (un permiso de horas
 *  pedido en días completos).
 */
const requestedInUnit = (kind, startDate, endDate, days) => {
  if (!kind || kind.unit === 'HOURS') return null
  if (kind.unit === 'WEEKS') return Math.round((days / 7) * 100) / 100
  if (kind.unit === 'DAYS_WORKING') return weekdaysBetween(startDate, endDate)
  return days
}

const today = () => new Date().toISOString().slice(0, 10)

const EMPTY = {
  leave_type: null,
  start_date: '',
  end_date: '',
  start_time: '',
  end_time: '',
  reduction_share: '',
  reason: '',
}

export default function LeaveDialog({ open, onClose, onSubmit, saving, error, forPerson = false }) {
  const [form, setForm] = useState(EMPTY)
  const [person, setPerson] = useState('')
  const [partial, setPartial] = useState(false)
  const [loaded, setLoaded] = useState(false)

  // Rellena las fechas al abrir y limpia al cerrar, sin efecto.
  if (open && !loaded) {
    setLoaded(true)
    setForm({ ...EMPTY, start_date: today(), end_date: today() })
    setPerson('')
    setPartial(false)
  }
  if (!open && loaded) setLoaded(false)

  // El catálogo y el consumo se consultan aquí, no en cada página que abre el
  // diálogo: así los dos usos no pueden divergir, y el consumo llega fresco en
  // cada apertura en vez de quedarse con el de la última vez.
  const { data: allTypes = [] } = useQuery({
    queryKey: ['leave-types'],
    queryFn: () => getLeaveTypes(),
    enabled: open,
  })
  const subject = forPerson ? person : 'me'
  const { data: usage = [] } = useQuery({
    queryKey: ['leave-usage', subject],
    queryFn: () => getLeaveUsage(forPerson && person ? { employee: person } : {}),
    enabled: open && (!forPerson || Boolean(person)),
  })

  // Lo que la empresa registra —un ERTE, una huelga— no se ofrece a quien pide
  // para sí: el servidor lo rechazaría, y un desplegable que ofrece lo que
  // luego se niega es una trampa.
  const types = forPerson ? allTypes : allTypes.filter((t) => t.initiated_by !== 'COMPANY')

  const kind = types.find((type) => type.id === form.leave_type) ?? null
  const isSick = kind?.family === 'SICK_LEAVE'
  const companyRecorded = kind?.initiated_by === 'COMPANY'
  // Las vacaciones se cuentan en días contra un saldo en días. Medio día
  // redondearía o convertiría el saldo en un decimal que la ley no usa, así que
  // el servidor lo rechaza y aquí ni se ofrece.
  const canBePartial = Boolean(kind) && kind.family !== 'VACATION'
  // Un ERTE puede suspender el contrato o reducir la jornada. Solo se pregunta
  // en una suspensión: en cualquier otro sitio parecería un ajuste y no haría
  // nada, que es la peor clase de campo.
  const canReduce = kind?.family === 'SUSPENSION'
  // Lo que queda de este permiso, si tiene tope y se acumula. Aquí y no en
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
    // Nunca para una suspensión: un ERTE «sin tope fijo» son meses, no horas,
    // y arrancar en horas lo descubrió la primera prueba con el formulario.
    setPartial(
      Boolean(chosen?.measured_in_hours) &&
        chosen?.family !== 'VACATION' &&
        chosen?.family !== 'SUSPENSION'
    )
  }

  const days = (new Date(form.end_date) - new Date(form.start_date)) / 86400000 + 1 || 0
  const hours = hoursBetween(form.start_time, form.end_time)

  // Aviso, no impedimento: el convenio mejora cualquiera de estas cifras, y la
  // copia de la empresa puede llevar la del Estatuto sin haberse actualizado.
  // La comparación va en la unidad del permiso, que es lo que hacía falso el
  // aviso: seis semanas de permiso parental no se pasan de ocho.
  const asked = requestedInUnit(kind, form.start_date, form.end_date, days)
  const overAllowance =
    kind?.amount != null && !partial && kind.period === 'EVENT' && asked != null
      ? asked > Number(kind.amount)
      : false

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit({
            ...(forPerson ? { employee: person } : {}),
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
        <DialogTitle>{forPerson ? 'Registrar ausencia' : 'Solicitar ausencia'}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            {forPerson && (
              <EmployeePicker
                required
                label="De quién"
                value={person}
                onChange={(id) => setPerson(id ?? '')}
              />
            )}

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
                        {option.initiated_by === 'COMPANY' ? ' · lo registra la empresa' : ''}
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
                      : forPerson
                        ? 'Escribe para buscar. Incluye lo que registra la empresa: ERTE, huelga…'
                        : 'Escribe para buscar entre los permisos de tu empresa.'
                  }
                />
              )}
            />

            {companyRecorded && (
              <Alert severity="info" variant="outlined">
                Esto no pasa por la cola: se registra directamente en vigor, como hecho o como
                decisión de la empresa, y queda en la auditoría a tu nombre.
              </Alert>
            )}

            {left && (
              <Alert severity={left.remaining <= 0 ? 'warning' : 'info'} variant="outlined">
                {forPerson ? 'Lleva' : 'Llevas'} <strong>{formatAmount(left.used)}</strong> de{' '}
                {formatAmount(left.allowance)} {UNITS[left.unit] ?? ''} {PERIODS[left.period] ?? ''}
                .{' '}
                {left.remaining > 0
                  ? `${forPerson ? 'Le quedan' : 'Te quedan'} ${formatAmount(left.remaining)}.`
                  : 'No queda nada de este permiso en este periodo.'}
                {left.estimated &&
                  ' La duración de la jornada se ha estimado: no hay cuadrante de ese día.'}
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
                No hace falta adjuntar el parte, y el sistema no lo guarda. Desde 2023 lo recibe
                la empresa directamente del INSS: basta con registrar las fechas.
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
                    Son <strong>{days}</strong> {days === 1 ? 'día' : 'días'}
                    {asked != null && kind?.unit !== 'DAYS_CALENDAR' && (
                      <> ({formatAmount(asked)} {UNITS[kind.unit]})</>
                    )}
                    .
                    {kind?.family === 'VACATION' &&
                      ' Del saldo solo salen los que se iban a trabajar: ni fines de semana ni festivos.'}
                  </Typography>
                )}

            {overAllowance && (
              <Alert severity="warning" variant="outlined">
                {kind.name} da {kind.allowance}, y se están pidiendo {formatAmount(asked)}{' '}
                {UNITS[kind.unit]}. No se impide: el convenio puede dar más de lo que consta
                aquí.
                {Number(kind.extra_when_travelling) > 0 &&
                  ` Si hay desplazamiento, son ${Number(kind.extra_when_travelling)} días más.`}
              </Alert>
            )}

            {canReduce && (
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
                    ? 'Este permiso pide justificante. Se puede adjuntar después.'
                    : 'Lo verá quien resuelva la solicitud.'
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={saving || !form.leave_type || (forPerson && !person)}
          >
            {forPerson ? (companyRecorded ? 'Registrar' : 'Registrar solicitud') : 'Solicitar'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
