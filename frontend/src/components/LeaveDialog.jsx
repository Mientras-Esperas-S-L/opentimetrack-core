import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import AttachFileIcon from '@mui/icons-material/AttachFile'
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

import { getLeaveBalance, getLeaveTypes, getLeaveUsage } from '../services/api.js'
import EmployeePicker from './EmployeePicker.jsx'
import { ErrorNote } from './common.jsx'
import { alCatalogo } from '../i18n/index.js'
import { plural, today } from './format.js'

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
  VACATION: alCatalogo('Vacaciones'),
  SICK_LEAVE: alCatalogo('Bajas'),
  PAID_LEAVE: alCatalogo('Permisos retribuidos'),
  UNPAID_LEAVE: alCatalogo('Sin sueldo'),
  SUSPENSION: alCatalogo('Suspensión del contrato'),
}

const UNITS = {
  DAYS_CALENDAR: alCatalogo('días naturales'),
  DAYS_WORKING: alCatalogo('días laborables'),
  HOURS: alCatalogo('horas'),
  WEEKS: alCatalogo('semanas'),
}

//: En singular, para cuando la cifra es uno. «1 horas» se lee mal en una
//: pantalla que por lo demás cuida el idioma, y la lactancia es exactamente una
//: hora al día, así que salía en el primer permiso que alguien abre.
const UNITS_ONE = {
  DAYS_CALENDAR: alCatalogo('día natural'),
  DAYS_WORKING: alCatalogo('día laborable'),
  HOURS: alCatalogo('hora'),
  WEEKS: alCatalogo('semana'),
}

/** Las notas del catálogo llevan `**énfasis**`, y hasta hoy salía en crudo.
 *
 *  No es decoración: lo que va destacado es justo lo que se confunde ---«al
 *  menos la mitad» frente a «como máximo la mitad» en los dos párrafos del mismo
 *  artículo, o el «no retribuido» del permiso parental---. Leerlo con los
 *  asteriscos puestos hace pensar que el texto está a medio escribir.
 *
 *  Se parte por los dobles asteriscos en vez de interpretar Markdown entero: las
 *  notas las escribe el catálogo del país o la empresa en su copia, y meter un
 *  intérprete de marcado ---o peor, HTML sin filtrar--- por unas negritas sería
 *  abrir una puerta que nadie ha pedido.
 */
function conEnfasis(texto) {
  if (!texto) return texto
  return String(texto)
    .split('**')
    .map((trozo, i) => (i % 2 ? <strong key={i}>{trozo}</strong> : trozo))
}

/** El nombre de la unidad, concordado con la cifra que la acompaña. */
function unidadDe(t, unit, cuantos) {
  if (!UNITS[unit]) return ''
  return Number(cuantos) === 1 ? t(UNITS_ONE[unit]) : t(UNITS[unit])
}

const PERIODS = {
  YEAR: alCatalogo('este año'),
  MONTH: alCatalogo('este mes'),
  WEEK: alCatalogo('esta semana'),
  DAY: alCatalogo('hoy'),
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

// `today` sale de `format.js`, que lo calcula en la fecha **local**. El que
// había aquí usaba `toISOString()`, o sea UTC, y su propio helper compartido
// avisa de esto en un comentario: al este de Greenwich, en las primeras horas de
// la madrugada, proponía **el día de ayer**. En España, cada noche entre las
// 00:00 y las 02:00 en verano, quien pedía un permiso sin fijarse lo pedía para
// ayer.

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
  const { t } = useTranslation()
  const [form, setForm] = useState(EMPTY)
  const [person, setPerson] = useState('')
  const [partial, setPartial] = useState(false)
  const [justificante, setJustificante] = useState(null)
  const [loaded, setLoaded] = useState(false)

  // Rellena las fechas al abrir y limpia al cerrar, sin efecto.
  if (open && !loaded) {
    setLoaded(true)
    setForm({ ...EMPTY, start_date: today(), end_date: today() })
    setPerson('')
    setPartial(false)
  }
  if (!open && loaded) setLoaded(false)
  // Y el fichero se olvida al cerrar: adjuntar el justificante de un permiso a
  // la solicitud siguiente sería peor que no tenerlo.
  if (!open && justificante) setJustificante(null)

  // El catálogo y el consumo se consultan aquí, no en cada página que abre el
  // diálogo: así los dos usos no pueden divergir, y el consumo llega fresco en
  // cada apertura en vez de quedarse con el de la última vez.
  const { data: allTypes = [], isSuccess: typesLoaded } = useQuery({
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
  // Lo dice el propio permiso, que es el único que lo sabe. Antes se adivinaba
  // ---«suspensión que registra la empresa»--- y se equivocaba en ocho de los
  // treinta y cuatro tipos, en las dos direcciones: no ofrecía la fracción en la
  // lactancia ni en la reducción por guarda legal, que son derechos de quien
  // trabaja y se ejercen precisamente reduciendo, y sí la ofrecía en la huelga,
  // el cierre patronal y la prisión provisional, que no reducen la jornada sino
  // que la paran.
  const canReduce = Boolean(kind?.can_reduce_the_day)
  // Y si además **para** el contrato, que no es lo mismo. El texto de ayuda de
  // la fracción decía «vacío o 100 suspende el contrato entero» para cualquier
  // permiso que la ofreciera, y en la lactancia eso es falso: dejarla vacía es
  // pedirla como la hora de ausencia del art. 37.4, no suspender nada.
  const suspende = kind?.family === 'SUSPENSION'
  // Lo que queda de este permiso, si tiene tope y se acumula. Aquí y no en
  // otra pantalla: es justo antes de pedir cuando sirve de algo.
  const left = usage?.find((row) => row.leave_type === kind?.id) ?? null

  // El descanso compensatorio no tiene tope en el catálogo ---el art. 35.1 no da
  // cifra: lo que se devuelve lo fija lo que se debe--- así que la línea de
  // arriba no encuentra nada y este permiso se pedía **a ciegas**. El tope que
  // tiene es el saldo, y el saldo existe: se calcula, se enseña en «Mis
  // ausencias» y no llegaba ni aquí ni a la pantalla de quien aprueba.
  //
  // Justo antes de pedir es donde más sirve: enterarse de que se piden ochenta
  // horas cuando constan veinticuatro debería pasar al escribirlo, no al recibir
  // el rechazo.
  const esDescansoCompensatorio = kind?.code === 'es.compensatory_rest'
  const { data: saldoDeDescanso } = useQuery({
    queryKey: ['leave-balance', subject],
    queryFn: () => getLeaveBalance(forPerson && person ? person : undefined),
    enabled: open && esDescansoCompensatorio && (!forPerson || Boolean(person)),
  })
  const deuda = esDescansoCompensatorio ? (saldoDeDescanso?.rest_debt ?? null) : null

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
        chosen?.family !== 'SUSPENSION',
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
            // El justificante. La API lo aceptaba desde el principio y ninguna
            // pantalla lo mandaba nunca: el permiso que lo pide se solicitaba
            // con un texto y nada más, mientras el propio diálogo prometía que
            // «se puede adjuntar después».
            justification: justificante,
          })
        }}
      >
        <DialogTitle>{forPerson ? t('Registrar ausencia') : t('Solicitar ausencia')}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            {forPerson && (
              <EmployeePicker
                required
                label={t('De quién')}
                value={person}
                onChange={(id) => setPerson(id ?? '')}
              />
            )}

            <Autocomplete
              options={[...types].sort((a, b) =>
                t(FAMILIES[a.family] ?? '').localeCompare(t(FAMILIES[b.family] ?? '')),
              )}
              groupBy={(option) =>
                FAMILIES[option.family] ? t(FAMILIES[option.family]) : t('Otros')
              }
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
                        {option.paid ? '' : ` ${t('· sin sueldo')}`}
                        {option.initiated_by === 'COMPANY'
                          ? ` ${t('· lo registra la empresa')}`
                          : ''}
                      </Typography>
                    </Stack>
                  </li>
                )
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  required
                  label={t('Qué pides')}
                  helperText={
                    kind
                      ? [kind.allowance, kind.basis].filter(Boolean).join(' · ')
                      : forPerson
                        ? t(
                            'Escribe para buscar. Incluye lo que registra la empresa: ERTE, huelga…',
                          )
                        : t('Escribe para buscar entre los permisos de tu empresa.')
                  }
                />
              )}
            />

            {/* Un desplegable vacío no dice nada, y aquí lo que calla es que la
                empresa se quedó sin catálogo: era lo que le pasaba a toda
                empresa recién dada de alta, y quien abría esto veía una lista
                sin opciones y ninguna pista de por qué. Se espera a que la
                consulta responda para no acusar de vacío lo que aún no llegó. */}
            {typesLoaded && types.length === 0 && (
              <Alert severity="warning" variant="outlined">
                {t(
                  'Esta empresa no tiene permisos configurados, así que no se puede pedir ninguno. Quien administre puede cargar el catálogo del país desde los ajustes de la empresa.',
                )}
              </Alert>
            )}

            {companyRecorded && (
              <Alert severity="info" variant="outlined">
                {t(
                  'Esto no pasa por la cola: se registra directamente en vigor, como hecho o como decisión de la empresa, y queda en la auditoría a tu nombre.',
                )}
              </Alert>
            )}

            {left && (
              <Alert severity={left.remaining <= 0 ? 'warning' : 'info'} variant="outlined">
                <Trans
                  i18nKey={
                    forPerson
                      ? 'Lleva <destacado>{{usado}}</destacado> de {{total}} {{unidad}} {{periodo}}.'
                      : 'Llevas <destacado>{{usado}}</destacado> de {{total}} {{unidad}} {{periodo}}.'
                  }
                  values={{
                    usado: formatAmount(left.used),
                    total: formatAmount(left.allowance),
                    unidad: unidadDe(t, left.unit, left.allowance),
                    periodo: PERIODS[left.period] ? t(PERIODS[left.period]) : '',
                  }}
                  components={{ destacado: <strong /> }}
                />{' '}
                {left.remaining > 0
                  ? forPerson
                    ? t('Le quedan {{cuanto}}.', { cuanto: formatAmount(left.remaining) })
                    : t('Te quedan {{cuanto}}.', { cuanto: formatAmount(left.remaining) })
                  : t('No queda nada de este permiso en este periodo.')}
                {left.estimated &&
                  ` ${t('La duración de la jornada se ha estimado: no hay cuadrante de ese día.')}`}
              </Alert>
            )}

            {esDescansoCompensatorio && (
              <Alert
                severity={deuda && deuda.remaining_hours > 0 ? 'info' : 'warning'}
                variant="outlined"
              >
                {deuda && deuda.remaining_hours > 0
                  ? forPerson
                    ? t('Le constan {{cuanto}} h de descanso por disfrutar.', {
                        cuanto: deuda.remaining_hours,
                      })
                    : t('Te constan {{cuanto}} h de descanso por disfrutar.', {
                        cuanto: deuda.remaining_hours,
                      })
                  : /* Cero no es «poco»: es que no consta ninguna deuda. Decirlo
                       con la misma frase que «te quedan 3 h» haría pensar que el
                       sistema ha contado y ha salido bajo. */
                    forPerson
                    ? t('No le consta ningún descanso pendiente de disfrutar.')
                    : t('No te consta ningún descanso pendiente de disfrutar.')}{' '}
                {t(
                  'Es lo que el sistema sabe: no cuenta los descansos que fije el convenio ni los de ampliación sectorial.',
                )}
              </Alert>
            )}

            {/* La nota del artículo, cuando la hay. Es lo que evita la consulta
                a la gestoría: quién cuenta como familiar, si hay que avisar,
                hasta cuándo se puede pedir. */}
            {kind?.note && (
              <Alert severity="info" variant="outlined">
                {conEnfasis(kind.note)}
              </Alert>
            )}

            {isSick && (
              <Typography variant="body2" color="text.secondary">
                {t(
                  'No hace falta adjuntar el parte, y el sistema no lo guarda. Desde 2023 lo recibe la empresa directamente del INSS: basta con registrar las fechas.',
                )}
              </Typography>
            )}

            {canBePartial && (
              <ToggleButtonGroup
                exclusive
                size="small"
                value={partial ? 'part' : 'whole'}
                onChange={(_, next) => next && setPartial(next === 'part')}
              >
                <ToggleButton value="whole">{t('Días completos')}</ToggleButton>
                <ToggleButton value="part">{t('Parte de un día')}</ToggleButton>
              </ToggleButtonGroup>
            )}

            {partial ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  required
                  fullWidth
                  type="date"
                  label={t('Día')}
                  value={form.start_date}
                  onChange={set('start_date')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  required
                  type="time"
                  label={t('Desde')}
                  value={form.start_time}
                  onChange={set('start_time')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  required
                  type="time"
                  label={t('Hasta')}
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
                  label={t('Desde')}
                  value={form.start_date}
                  onChange={set('start_date')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  required
                  fullWidth
                  type="date"
                  label={t('Hasta')}
                  value={form.end_date}
                  onChange={set('end_date')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Stack>
            )}

            {partial
              ? hours > 0 && (
                  <Typography variant="body2" color="text.secondary">
                    <Trans
                      i18nKey="Son <destacado>{{cuantas}}</destacado> {{unidad}}."
                      values={{
                        cuantas: hours.toString().replace('.', ','),
                        unidad: plural(hours, t('hora'), t('horas')),
                      }}
                      components={{ destacado: <strong /> }}
                    />
                  </Typography>
                )
              : days > 0 && (
                  <Typography variant="body2" color="text.secondary">
                    <Trans
                      i18nKey="Son <destacado>{{cuantos}}</destacado> {{unidad}}{{aclaracion}}."
                      values={{
                        cuantos: days,
                        unidad: plural(days, t('día'), t('días')),
                        aclaracion:
                          asked != null && kind?.unit !== 'DAYS_CALENDAR'
                            ? ` (${formatAmount(asked)} ${unidadDe(t, kind.unit, asked)})`
                            : '',
                      }}
                      components={{ destacado: <strong /> }}
                    />
                    {kind?.family === 'VACATION' &&
                      ` ${t('Del saldo solo salen los que se iban a trabajar: ni fines de semana ni festivos.')}`}
                  </Typography>
                )}

            {overAllowance && (
              <Alert severity="warning" variant="outlined">
                {t(
                  '{{permiso}} da {{cuanto}}, y se están pidiendo {{pedido}} {{unidad}}. No se impide: el convenio puede dar más de lo que consta aquí.',
                  {
                    permiso: kind.name,
                    cuanto: kind.allowance,
                    pedido: formatAmount(asked),
                    unidad: unidadDe(t, kind.unit, kind.amount),
                  },
                )}
                {Number(kind.extra_when_travelling) > 0 &&
                  ` ${t('Si hay desplazamiento, son {{cuantos}} {{unidad}} más.', {
                    cuantos: Number(kind.extra_when_travelling),
                    unidad: plural(kind.extra_when_travelling, t('día'), t('días')),
                  })}`}
              </Alert>
            )}

            {canReduce && (
              <TextField
                fullWidth
                type="number"
                label={t('Reducción de jornada (%)')}
                value={form.reduction_share}
                onChange={set('reduction_share')}
                slotProps={{ htmlInput: { min: 1, max: 100, step: 1 } }}
                helperText={
                  form.reduction_share !== '' && Number(form.reduction_share) < 100
                    ? t(
                        'Se sigue trabajando el {{porcentaje}} %. El cuadrante pasa a medirse contra esa jornada.',
                        { porcentaje: 100 - Number(form.reduction_share) },
                      )
                    : suspende
                      ? t('Vacío o 100 suspende el contrato entero: no se espera jornada.')
                      : t(
                          'Vacío se pide como ausencia; con un número se reduce la jornada en esa parte y se sigue trabajando el resto.',
                        )
                }
              />
            )}

            <TextField
              fullWidth
              multiline
              minRows={2}
              label={kind?.needs_justification ? t('Motivo') : t('Motivo (opcional)')}
              required={Boolean(kind?.needs_justification) && !isSick}
              value={form.reason}
              onChange={set('reason')}
              helperText={
                isSick
                  ? t('No hace falta indicar la dolencia.')
                  : kind?.needs_justification
                    ? t('Este permiso pide justificante.')
                    : t('Lo verá quien resuelva la solicitud.')
              }
            />

            {/* Solo donde el permiso lo pide, y nunca en una baja: desde el RD
                1060/2022 el parte no se le entrega a la empresa, y el servidor
                rechaza el fichero. Ofrecerlo aquí sería invitar a subir un dato
                de salud que no debe estar. */}
            {kind?.needs_justification && !isSick && (
              <Box>
                <Button component="label" variant="outlined" startIcon={<AttachFileIcon />}>
                  {justificante ? t('Cambiar el justificante') : t('Adjuntar el justificante')}
                  <input
                    hidden
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif"
                    onChange={(event) => setJustificante(event.target.files?.[0] ?? null)}
                  />
                </Button>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 0.5 }}
                >
                  {justificante
                    ? justificante.name
                    : t(
                        'PDF o foto, hasta 10 MB. Opcional ahora: la solicitud se puede enviar sin él.',
                      )}
                </Typography>
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            {t('Cancelar')}
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={saving || !form.leave_type || (forPerson && !person)}
          >
            {forPerson
              ? companyRecorded
                ? t('Registrar')
                : t('Registrar solicitud')
              : t('Solicitar')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
