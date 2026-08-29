import { useMemo, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Badge from '@mui/material/Badge'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Collapse from '@mui/material/Collapse'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import Divider from '@mui/material/Divider'
import DialogTitle from '@mui/material/DialogTitle'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import {
  PAGE_SIZE,
  applyCorrectionAnyway,
  approveAbsence,
  approveCorrection,
  confirmHolidayRecovery,
  decideOvertime,
  getCorrections,
  getHolidayRecoveries,
  getPendingAbsences,
  getPendingOvertime,
  getScheduleAdaptations,
  rejectAbsence,
  rejectCorrection,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pager,
  SourceChip,
  StatusChip,
} from '../../components/common.jsx'
import {
  dateOf,
  dayRange,
  durationOf,
  leaveLabel,
  leaveLength,
  plural,
  timeOf,
} from '../../components/format.js'
import AdaptationQueue from '../../components/AdaptationQueue.jsx'
import ChangeOnTheRecord from '../../components/ChangeOnTheRecord.jsx'
import { FilterBar, PickFilter, SearchField } from '../../components/filters.jsx'
import { matches, peopleIn } from '../../components/filtering.js'
import { SelectAllBox, SelectBox, SelectionBar } from '../../components/selection.jsx'
import { bulkSummary, runBulk } from '../../services/bulk.js'
import { alFallar } from '../../services/stale.js'
import { useAuth } from '../../hooks/useAuth.js'
import { alCatalogo } from '../../i18n/index.js'
import { useSelection } from '../../hooks/useSelection.js'

const KIND_LABELS = {
  ADD: alCatalogo('Añadir un fichaje que falta'),
  MODIFY: alCatalogo('Cambiar la hora'),
  VOID: alCatalogo('Anular un fichaje'),
}

/** Las horas extra de una persona, resueltas de una vez o día a día.
 *
 *  Agrupado por persona a propósito: quien se queda cinco minutos de más cada
 *  tarde llena la cola de un mes con la misma decisión, y una lista de
 *  cuarenta tarjetas iguales no se lee, se cierra. El caso frecuente ---
 *  «esto es así todo el mes, autorízalo»--- es un clic; el día suelto que
 *  merece mirarse sigue teniendo el suyo.
 *
 *  Autorizar pide decir cómo se salda (art. 35.1); rechazar no, porque no hay
 *  nada que saldar: el registro sigue mostrando el tiempo real y la decisión
 *  solo dice que esa parte no se autoriza.
 */
function OvertimePersonCard({ group, busy, onDecide, select }) {
  const { t } = useTranslation()
  const [settlement, setSettlement] = useState('PAID')
  const [showDays, setShowDays] = useState(false)
  const { rows } = group
  const single = rows.length === 1
  const total = rows.reduce((sum, row) => sum + row.minutes, 0)
  const reopened = rows.filter((row) => row.previous).length
  const used = rows[0]?.used_this_year
  // Art. 36.1: «Los trabajadores nocturnos no podrán realizar horas
  // extraordinarias.» El aviso del cuadrante ya mencionaba esta prohibición y
  // aquí, que es donde se autorizan, no la nombraba nadie.
  const nocturno = rows.some((row) => row.night_worker)
  // La noche que los relojes se atrasan, toda la plantilla de noche aparece
  // aquí con sesenta minutos y filas idénticas. La cifra es correcta ---esa
  // gente trabajó nueve horas de verdad--- pero decidir sobre ella sin saber de
  // dónde sale no es decidir.
  const cambioDeHora = rows.find((row) => row.clock_change_minutes)?.clock_change_minutes ?? 0

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        sx={{ gap: 2, justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        {select}
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600 }}>{group.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {single ? (
              <Trans
                i18nKey="{{dia}} · <destacado>{{exceso}}</destacado> de más ({{trabajadas}} trabajadas de {{previstas}} previstas)"
                values={{
                  dia: dateOf(rows[0].day),
                  exceso: durationOf(rows[0].minutes),
                  trabajadas: durationOf(rows[0].worked_minutes),
                  previstas: durationOf(rows[0].expected_minutes),
                }}
                components={{ destacado: <strong /> }}
              />
            ) : (
              <Trans
                i18nKey="{{cuantos}} días · <destacado>{{exceso}}</destacado> de más en total · {{periodo}}"
                values={{
                  cuantos: rows.length,
                  exceso: durationOf(total),
                  periodo: dayRange(rows[0].day, rows[rows.length - 1].day),
                }}
                components={{ destacado: <strong /> }}
              />
            )}
          </Typography>
          {nocturno && (
            <Typography variant="caption" color="error.main" sx={{ display: 'block', mt: 0.5 }}>
              {t(
                'Tiene la condición de trabajadora o trabajador nocturno, y el art. 36.1 ET prohíbe las horas extraordinarias a quien la tenga. Las horas ya se trabajaron y hay que clasificarlas; lo que no puede es repetirse.',
              )}
            </Typography>
          )}
          {cambioDeHora !== 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {cambioDeHora < 0
                ? t(
                    'Esa noche los relojes se atrasaron una hora, así que el turno duró una hora más de lo previsto. La hora se trabajó de verdad y por eso aparece aquí; qué se hace con ella lo dice el convenio.',
                  )
                : t(
                    'Esa noche los relojes se adelantaron una hora, así que el turno duró una hora menos de lo previsto.',
                  )}
            </Typography>
          )}
          {/* El tope del art. 35.2. Autorizar sin saber que esta persona va
              por 78 de 80 es decidir a ciegas sobre un límite legal --- y el
              ajuste existía desde el principio sin que nadie lo leyera. */}
          {used && used.cap_hours > 0 && (
            <Typography
              variant="caption"
              color={used.over_the_cap ? 'error.main' : 'text.secondary'}
              sx={{ display: 'block' }}
            >
              {used.over_the_cap
                ? t(
                    'Ya lleva {{horas}} h autorizadas este año, por encima del tope de {{tope}} h (art. 35.2 ET).',
                    { horas: fmt(used.hours), tope: used.cap_hours },
                  )
                : t(
                    'Lleva {{horas}} h de {{tope}} este año. Las compensadas con descanso no cuentan.',
                    {
                      horas: fmt(used.hours),
                      tope: used.cap_hours,
                    },
                  )}
            </Typography>
          )}
          {reopened > 0 && (
            <Typography variant="caption" color="warning.main">
              {reopened === 1
                ? t('Un día ya resuelto vuelve a revisión: la cifra ha cambiado.')
                : t('{{cuantos}} días ya resueltos vuelven a revisión: la cifra ha cambiado.', {
                    cuantos: reopened,
                  })}
            </Typography>
          )}
        </Box>

        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            select
            size="small"
            label={t('Se salda')}
            value={settlement}
            onChange={(event) => setSettlement(event.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="PAID">{t('Pagada')}</MenuItem>
            <MenuItem value="REST">{t('Con descanso')}</MenuItem>
          </TextField>
          <Button
            variant="contained"
            disabled={busy}
            onClick={() =>
              onDecide({ days: rows.map((row) => row.day), authorise: true, settlement })
            }
          >
            {single ? t('Autorizar') : t('Autorizar todo')}
          </Button>
          <Button
            color="inherit"
            disabled={busy}
            onClick={() => onDecide({ days: rows.map((row) => row.day), authorise: false })}
          >
            {single ? t('No autorizar') : t('No autorizar nada')}
          </Button>
        </Stack>
      </Stack>

      {!single && (
        <>
          <Button
            size="small"
            color="inherit"
            sx={{ mt: 1, ml: -1 }}
            onClick={() => setShowDays((open) => !open)}
          >
            {showDays
              ? t('Ocultar los días')
              : t('Ver los {{cuantos}} días', { cuantos: rows.length })}
          </Button>
          <Collapse in={showDays} unmountOnExit>
            <Stack divider={<Divider flexItem />} sx={{ mt: 1 }}>
              {rows.map((row) => (
                <Stack
                  key={row.day}
                  direction="row"
                  sx={{ gap: 2, py: 1, alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <Typography variant="body2" color="text.secondary">
                    <Trans
                      i18nKey="{{dia}} · <destacado>{{exceso}}</destacado> de más ({{trabajadas}} de {{previstas}} previstas)"
                      values={{
                        dia: dateOf(row.day),
                        exceso: durationOf(row.minutes),
                        trabajadas: durationOf(row.worked_minutes),
                        previstas: durationOf(row.expected_minutes),
                      }}
                      components={{ destacado: <strong /> }}
                    />
                    {row.previous && (
                      <Typography component="span" variant="caption" color="warning.main">
                        {' '}
                        {t('· resuelto antes con {{antes}}', {
                          antes: durationOf(row.previous.minutes),
                        })}
                      </Typography>
                    )}
                  </Typography>
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button
                      size="small"
                      disabled={busy}
                      onClick={() => onDecide({ days: [row.day], authorise: true, settlement })}
                    >
                      {t('Autorizar')}
                    </Button>
                    <Button
                      size="small"
                      color="inherit"
                      disabled={busy}
                      onClick={() => onDecide({ days: [row.day], authorise: false })}
                    >
                      No
                    </Button>
                  </Stack>
                </Stack>
              ))}
            </Stack>
          </Collapse>
        </>
      )}
    </Paper>
  )
}

/** «2,5», no «2.5»: los decimales del aviso se leen en español. */
const fmt = (value) => {
  const n = Number(value ?? 0)
  return (n % 1 === 0 ? n.toString() : n.toFixed(2).replace(/0$/, '')).replace('.', ',')
}

/** One request, with everything needed to decide it visible at once.
 *
 *  Approving is one click; refusing opens a box for the note. That asymmetry is
 *  deliberate: a refusal is what the person will read and ask about, and it
 *  should not be as effortless as a yes.
 */
function RequestCard({ title, meta, reason, children, onApprove, onReject, busy, select }) {
  const { t } = useTranslation()
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        sx={{ gap: 2, justifyContent: 'space-between', alignItems: { md: 'flex-start' } }}
      >
        {select}
        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
          <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            {meta}
          </Typography>
          {children}
          {reason && (
            <Typography
              variant="body2"
              sx={{
                mt: 1.5,
                pl: 1.5,
                borderLeft: 2,
                borderColor: 'divider',
                fontStyle: 'italic',
                maxWidth: '68ch',
              }}
            >
              {reason}
            </Typography>
          )}
        </Box>

        <Stack direction="row" sx={{ gap: 1, flexShrink: 0 }}>
          <Button size="small" onClick={onReject} disabled={busy} color="inherit">
            {t('Rechazar')}
          </Button>
          <Button size="small" variant="contained" onClick={onApprove} disabled={busy}>
            {t('Aprobar')}
          </Button>
        </Stack>
      </Stack>
    </Paper>
  )
}

/** Dice que la lista viene recortada, cuando lo viene.
 *
 *  Las colas de correcciones llegan de cincuenta en cincuenta y no hay
 *  paginador: sin este aviso, cincuenta y cinco pendientes se ven como
 *  cincuenta y las otras cinco no existen para nadie. Un recorte callado es
 *  peor que una lista larga, porque se lee como «ya está todo».
 *
 *  Con los filtros de arriba se llega a las que faltan; decirlo es lo que
 *  convierte el filtro en la salida y no en un adorno.
 */
function ListaRecortada({ total, mostradas }) {
  const { t } = useTranslation()
  if (!total || total <= mostradas) return null
  return (
    <Alert severity="info" variant="outlined">
      {/* Con los números dentro de la frase: en otro idioma no van
          necesariamente en este orden, y partir el texto para intercalarlos
          obliga a traducir trozos que por separado no significan nada. */}
      {t(
        'Se muestran {{mostradas}} de {{total}}. Usa los filtros de arriba para llegar al resto.',
        {
          mostradas,
          total,
        },
      )}
    </Alert>
  )
}

/** Lo que hay marcado de una lista. Se repetía en cada barra. */
const seleccionadas = (filas, seleccion) => filas.filter((fila) => seleccion.isSelected(fila))

/** El «no», de una en una o de varias a la vez.
 *
 *  Rechazar en bloque pasa por el mismo cuadro que rechazar una, y con el mismo
 *  motivo obligatorio donde lo es: el texto que va a leer la persona no puede
 *  depender de por qué botón se llegó. Y un motivo compartido por varias se
 *  avisa, para que nadie escriba «no procede» pensando en un caso y se lo
 *  mande a cinco.
 */
function RejectDialog({ open, onClose, onConfirm, needsNote, count = 1, busy }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  const many = count > 1

  const confirm = () => {
    onConfirm(note)
    setNote('')
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {many
          ? t('Rechazar {{cuantas}} solicitudes', { cuantas: count })
          : t('Rechazar la solicitud')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {many
            ? t(
                'El mismo motivo se enviará a todas. Se conservan rechazadas: que alguien lo pidiera y se le dijera que no también es parte del historial.',
              )
            : t(
                'La solicitud se conserva rechazada: que alguien lo pidiera y se le dijera que no también es parte del historial.',
              )}
        </Typography>
        <TextField
          autoFocus
          fullWidth
          multiline
          minRows={3}
          label={needsNote ? t('Motivo del rechazo') : t('Motivo del rechazo (opcional)')}
          placeholder={
            many
              ? t('Lo leerán todas las personas afectadas.')
              : t('Lo leerá la persona que lo solicitó.')
          }
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">
          {t('Volver')}
        </Button>
        <Button
          onClick={confirm}
          variant="contained"
          color="secondary"
          disabled={busy || (needsNote && !note.trim())}
        >
          {many ? t('Rechazar las {{cuantas}}', { cuantas: count }) : t('Rechazar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default function Decisions() {
  const { t } = useTranslation()
  const { session } = useAuth()
  // Respaldo. Cada corrección dice el huso de la persona a la que afecta: en
  // una empresa con delegaciones, leer todas las horas en el de la central es
  // proponer un cambio a una hora que esa persona no reconoce.
  const zone = session?.tenant?.time_zone
  const queryClient = useQueryClient()

  const [tab, setTab] = useState(0)
  const [error, setError] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [confirming, setConfirming] = useState(null)

  const absences = useQuery({ queryKey: ['absences', 'pending'], queryFn: getPendingAbsences })

  // Solo estas dos colas paginan: `/absences/pending/`, las horas extra y las
  // recuperaciones son acciones que devuelven la cola entera. Aquí llegaban de
  // cincuenta en cincuenta, y a las que faltaban solo se llegaba filtrando ---
  // un aviso decía que había más y no había forma de pasar a verlas.
  const [paginaCorrecciones, setPaginaCorrecciones] = useState(1)
  const [paginaEspera, setPaginaEspera] = useState(1)

  const corrections = useQuery({
    queryKey: ['corrections', 'pending', paginaCorrecciones],
    queryFn: () => getCorrections({ status: 'PENDING', page: paginaCorrecciones }),
    placeholderData: (previous) => previous,
  })

  // Art. 4.b. A change the company proposed on somebody else's record waits for
  // their authorisation, and if they disagree it waits for the company to
  // decide whether to go ahead. Neither state appeared anywhere: the proposal
  // left this screen the moment it was made and never came back.
  //
  // Only AWAITING_EMPLOYEE. Despite the name, DISPUTED does not mean "arguing
  // about it": the backend sets it when the company has already applied the
  // change without agreement, so those are finished and belong in the record,
  // not in a list of things to decide.
  const waiting = useQuery({
    queryKey: ['corrections', 'awaiting', paginaEspera],
    queryFn: () => getCorrections({ status: 'AWAITING_EMPLOYEE', page: paginaEspera }),
    placeholderData: (previous) => previous,
  })

  // Horas extra pendientes de autorizar. La cola por excepción del tiempo: días
  // que se pasaron de lo previsto y que nadie ha resuelto.
  const overtime = useQuery({ queryKey: ['overtime', 'pending'], queryFn: getPendingOvertime })

  // Art. 38.3: días de vacaciones que una baja se comió. Se detectan solos; los
  // confirma una persona, porque devolver días al saldo sin que nadie lo mire
  // es de lo que después no se sabe explicar.
  const recoveries = useQuery({
    queryKey: ['holiday-recoveries', 'pending'],
    queryFn: getHolidayRecoveries,
  })

  // Art. 34.8: las adaptaciones de jornada sin contestar. Aquí y no en una
  // pantalla propia porque es lo mismo que las demás colas ---algo que espera a
  // que alguien decida--- y porque el plazo corre: quince días.
  const adaptations = useQuery({
    queryKey: ['schedule-adaptations', 'pending'],
    queryFn: () => getScheduleAdaptations({ status: 'PENDING' }),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['absences'] })
    queryClient.invalidateQueries({ queryKey: ['punches'] })
    queryClient.invalidateQueries({ queryKey: ['corrections'] })
    queryClient.invalidateQueries({ queryKey: ['overview'] })
  }

  const decide = useMutation({
    mutationFn: ({ action, id, note }) => action(id, note),
    onSuccess: () => {
      setError(null)
      setRejecting(null)
      refresh()
    },
    // Si otra persona resolvió esto antes, además de decirlo hay que quitarlo
    // de la lista: si no, la fila sigue ahí invitando a pulsar otra vez.
    onError: alFallar(setError, refresh),
  })

  const ruleRecovery = useMutation({
    mutationFn: confirmHolidayRecovery,
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['holiday-recoveries'] })
      queryClient.invalidateQueries({ queryKey: ['absences'] })
    },
    onError: alFallar(setError, refresh),
  })

  const ruleOvertime = useMutation({
    mutationFn: decideOvertime,
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['overtime'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: alFallar(setError, refresh),
  })

  const openReject = (action, id, needsNote) => setRejecting({ action, id, needsNote })

  // La misma decisión sobre varias solicitudes de golpe. En serie y sin parar
  // en el primer fallo: que una estuviera ya resuelta por otra persona no es
  // razón para dejar sin responder a las trece siguientes.
  const [bulking, setBulking] = useState(false)
  const decideMany = async (rows, action, { done }) => {
    setBulking(true)
    try {
      const outcome = await runBulk(rows, (row) => action(row.id))
      setError(bulkSummary(outcome, { done }))
      refresh()
    } finally {
      setBulking(false)
    }
  }

  /** Resuelve las horas extra de varias personas con el mismo criterio.
   *
   *  Una llamada por persona, no una con todo el mundo dentro: cada decisión
   *  es de una persona y tiene que quedar así en el registro. Y `days` va
   *  entero por persona, que es lo que ya hace la tarjeta individual.
   */
  const decidirHorasExtra = async (grupos, authorise, settlement) => {
    setBulking(true)
    try {
      const outcome = await runBulk(grupos, (group) =>
        decideOvertime({
          employee: group.employee,
          days: group.rows.map((row) => row.day),
          authorise,
          ...(authorise ? { settlement } : {}),
        }),
      )
      setError(bulkSummary(outcome, { done: authorise ? t('autorizadas') : t('denegadas') }))
      refresh()
    } finally {
      setBulking(false)
    }
  }

  /** Devuelve al saldo las vacaciones que varias personas tenían que recuperar. */
  const decidirRecuperaciones = async (filas, accept) => {
    setBulking(true)
    try {
      const outcome = await runBulk(filas, (row) =>
        confirmHolidayRecovery({ recovery: row.id, accept }),
      )
      setError(bulkSummary(outcome, { done: accept ? t('devueltas') : t('descartadas') }))
      refresh()
    } finally {
      setBulking(false)
    }
  }

  // El filtro es de cada pestaña: lo que se busca en ausencias no se parece a
  // lo que se busca en correcciones, y arrastrar el texto de una a otra deja
  // la siguiente vacía sin que se entienda por qué.
  const [search, setSearch] = useState('')
  const [who, setWho] = useState('')
  const clearFilters = () => {
    setSearch('')
    setWho('')
  }

  /** Cuántas hay de verdad en cada cola.
   *
   *  De `count` y no de las filas que llegaron: las dos colas de correcciones
   *  vienen paginadas de cincuenta en cincuenta, así que contar lo recibido
   *  decía «50» habiendo 55 --- y las cinco que faltaban no se podían alcanzar
   *  desde ninguna parte. Es el fallo que el propio `Pager` documenta como ya
   *  ocurrido una vez en todas las pantallas.
   *
   *  El número de la pestaña es lo que decide si alguien entra a mirar, así que
   *  redondear a la baja es peor que no ponerlo.
   */
  /** El tope del contador de una pestaña.
   *
   *  MUI corta en 99 por defecto, así que una cola de 125 se pintaba «99+»
   *  mientras el Resumen decía 125 --- dos pantallas de la misma aplicación
   *  contando lo mismo y diciendo cosas distintas. Es el mismo pecado que
   *  documenta `cuantasHay` un piso más abajo: redondear a la baja el número
   *  que decide si alguien entra a mirar.
   */
  const cuantasHay = (consulta, filas) => consulta.data?.count ?? filas.length

  const absenceRows = absences.data ?? []
  const correctionRows = corrections.data?.rows ?? []
  // Those who have answered first: the company can act on them now, whereas
  // the silent ones are still inside their window to reply.
  const overtimeRows = overtime.data ?? []
  const recoveryRows = recoveries.data ?? []
  const adaptationRows = adaptations.data?.rows ?? []
  // Por persona, y quien más tiempo acumula primero: la cola es de excepciones
  // y la excepción grande no puede quedar debajo de treinta días de cinco
  // minutos. Los días llegan ya ordenados por fecha desde el servidor.
  const overtimeGroups = useMemo(() => {
    const byPerson = new Map()
    for (const row of overtime.data ?? []) {
      const group = byPerson.get(row.employee) ?? {
        employee: row.employee,
        name: row.employee_name,
        rows: [],
        total: 0,
      }
      group.rows.push(row)
      group.total += row.minutes
      byPerson.set(row.employee, group)
    }
    return [...byPerson.values()].sort((a, b) => b.total - a.total)
  }, [overtime.data])
  const openRows = [...(waiting.data?.rows ?? [])].sort(
    (a, b) => Boolean(b.employee_responded_at) - Boolean(a.employee_responded_at),
  )

  const peopleHere = peopleIn(
    tab === 0 ? absenceRows : tab === 1 ? correctionRows : tab === 2 ? openRows : overtimeRows,
  )
  // Al resolver la última solicitud de alguien, esa persona desaparece de la
  // lista y el filtro se quedaba apuntando a nadie: la pantalla decía «ninguna
  // coincide» escondiendo las que sí quedaban. Se suelta al leer --- filtrar
  // por quien ya no tiene nada pendiente no significa nada.
  const forWhom = peopleHere.some((person) => person.value === who) ? who : ''

  // Lo que se ve tras el filtro. Todo lo demás --- la selección, «todo», las
  // acciones masivas --- opera sobre esto y nunca sobre la lista entera:
  // aprobar de golpe cosas que no están en pantalla es aprobar sin mirar.
  const mine = (row) => !forWhom || String(row.employee) === forWhom
  const shownAbsences = absenceRows.filter(
    (row) => mine(row) && matches(search, row.employee_name, leaveLabel(row), row.reason),
  )
  const shownCorrections = correctionRows.filter(
    (row) => mine(row) && matches(search, row.employee_name, t(KIND_LABELS[row.kind]), row.reason),
  )
  const shownOpen = openRows.filter(
    (row) => mine(row) && matches(search, row.employee_name, t(KIND_LABELS[row.kind]), row.reason),
  )
  const shownOvertime = overtimeGroups.filter((group) => mine(group) && matches(search, group.name))

  const absencePick = useSelection(shownAbsences)
  const correctionPick = useSelection(shownCorrections)
  // «Sin acuerdo» solo se selecciona para **retirar**, nunca para aplicar en
  // bloque. Ver la barra de esa pestaña.
  const openPick = useSelection(shownOpen)
  const overtimePick = useSelection(shownOvertime, (group) => group.employee)
  const recoveryPick = useSelection(recoveryRows)

  /** La selección y las filas de la pestaña que se está viendo.
   *
   *  En un sitio y no repartido por cinco condicionales: la casilla de
   *  «seleccionar todo» vive en la barra de filtros, que es común, así que
   *  necesita saber de qué cola habla. Antes solo cubría las dos primeras
   *  colas ---las únicas que tenían selección--- con un `tab < 2` que había
   *  que acordarse de ampliar.
   *
   *  Y seguía habiendo que acordarse: al añadir la sexta cola ---las
   *  adaptaciones de jornada, que se contestan de una en una--- este índice
   *  devolvió `undefined` y la pantalla entera se cayó con un
   *  `Cannot read properties of undefined`. Un comentario que dice «ya no hay
   *  que acordarse» al lado de un sitio donde sí hay que acordarse es peor que
   *  no tener el comentario.
   *
   *  **`undefined` aquí significa «esta cola no tiene selección», y es una
   *  respuesta válida**: no toda cola la necesita, y obligar a inventarle una a
   *  la siguiente sería pedirle que se parezca a las demás para poder existir.
   */
  const colaActual = [
    { pick: absencePick, filas: shownAbsences },
    { pick: correctionPick, filas: shownCorrections },
    { pick: openPick, filas: shownOpen },
    { pick: overtimePick, filas: shownOvertime },
    { pick: recoveryPick, filas: recoveryRows },
  ][tab]

  const filtering = Boolean(search || forWhom)

  return (
    <>
      <PageHeader
        title={t('Por decidir')}
        subtitle={t(
          'Solicitudes esperando respuesta. Toda decisión queda registrada con su autor y su momento.',
        )}
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {/* Cambiar de pestaña con un filtro puesto dejaba la siguiente vacía sin
          explicación. Se limpia al cambiar. */}
      <Tabs
        value={tab}
        onChange={(_, next) => {
          setTab(next)
          clearFilters()
        }}
        sx={{ mb: 2 }}
      >
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(absences, absenceRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Ausencias')}
            </Badge>
          }
        />
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(corrections, correctionRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Fichajes')}
            </Badge>
          }
        />
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(waiting, openRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Sin acuerdo')}
            </Badge>
          }
        />
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(overtime, overtimeRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Horas extra')}
            </Badge>
          }
        />
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(recoveries, recoveryRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Vacaciones por recuperar')}
            </Badge>
          }
        />
        <Tab
          label={
            <Badge
              max={999}
              badgeContent={cuantasHay(adaptations, adaptationRows)}
              color="secondary"
              sx={{ pr: 1.5 }}
            >
              {t('Adaptaciones de jornada')}
            </Badge>
          }
        />
      </Tabs>

      {/* Filtrar y seleccionar van juntos: «aprobar todo» sobre veinte cosas
          mezcladas da miedo con razón; sobre las cuatro de una persona es
          justo lo que alguien quiere hacer. */}
      <FilterBar>
        {colaActual && <SelectAllBox selection={colaActual.pick} count={colaActual.filas.length} />}
        <SearchField
          value={search}
          onChange={setSearch}
          placeholder={t('Nombre, tipo, motivo…')}
          width={260}
        />
        <PickFilter
          label={t('Persona')}
          value={forWhom}
          onChange={setWho}
          options={peopleHere}
          all={t('Todas las personas')}
          width={220}
        />
        {filtering && (
          <Button size="small" color="inherit" onClick={clearFilters}>
            {t('Quitar filtros')}
          </Button>
        )}
      </FilterBar>

      {tab === 0 &&
        (absences.isLoading ? (
          <Loading />
        ) : shownAbsences.length === 0 ? (
          <Empty>
            {filtering
              ? t('Ninguna ausencia coincide con el filtro.')
              : t('No hay ausencias esperando respuesta.')}
          </Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            {shownAbsences.map((absence) => (
              <RequestCard
                key={absence.id}
                busy={decide.isPending || bulking}
                select={<SelectBox selection={absencePick} item={absence} />}
                title={absence.employee_name}
                meta={`${leaveLabel(absence)} · ${dayRange(absence.start_date, absence.end_date)} · ${leaveLength(absence)}`}
                reason={absence.reason}
                onApprove={() => decide.mutate({ action: approveAbsence, id: absence.id })}
                onReject={() => openReject(rejectAbsence, absence.id, false)}
              >
                {/* Aquí y no en otra pantalla: quien decide lo necesita **al
                    decidir**, y si hay que ir a buscarlo nadie lo mira. No
                    impide aprobar: todos los topes del catálogo son el suelo
                    legal y el convenio mejora cualquiera. */}
                {absence.over_the_limit && (
                  <Alert severity="warning" variant="outlined" sx={{ mt: 1.5 }}>
                    {absence.over_the_limit.kind === 'rest_debt' ? (
                      /* El descanso compensatorio no tiene tope en el catálogo
                         ---el art. 35.1 no da cifra--- pero sí lo tiene en el
                         saldo: lo que se debe. Sin esta rama el producto
                         calculaba «te quedan 24 h», lo enseñaba en la pantalla
                         de quien las disfruta, y no lo decía en la única
                         pantalla donde alguien aprueba. */
                      <>
                        {absence.over_the_limit.asked_hours === null ? (
                          <Trans
                            i18nKey="Constan <destacado>{{deben}}</destacado> por disfrutar, y lo que pide no se puede contar en horas."
                            values={{ deben: `${absence.over_the_limit.owed_hours} h` }}
                            components={{ destacado: <strong /> }}
                          />
                        ) : (
                          <Trans
                            i18nKey="Pide <destacado>{{pedido}}</destacado> y constan {{deben}} por disfrutar."
                            values={{
                              pedido: `${absence.over_the_limit.asked_hours} h`,
                              deben: `${absence.over_the_limit.owed_hours} h`,
                            }}
                            components={{ destacado: <strong /> }}
                          />
                        )}{' '}
                        {absence.over_the_limit.unconverted_days > 0 &&
                          `${t('Hay {{dias}} día(s) sin turno previsto, así que no se han podido contar en horas.', { dias: absence.over_the_limit.unconverted_days })} `}
                        {t(
                          'Se puede aprobar igual —el saldo no cuenta los descansos que fije el convenio ni los de ampliación sectorial—, pero conviene saberlo.',
                        )}
                      </>
                    ) : absence.over_the_limit.period === 'EVENT' ? (
                      <Trans
                        i18nKey="Pide <destacado>{{pedido}}</destacado> y el permiso da {{permiso}}{{extra}}."
                        values={{
                          pedido: fmt(absence.over_the_limit.used),
                          permiso: fmt(absence.over_the_limit.allowance),
                          extra:
                            absence.over_the_limit.travel_extra > 0
                              ? ` ${t('(+{{cuanto}} si hay desplazamiento)', {
                                  cuanto: fmt(absence.over_the_limit.travel_extra),
                                })}`
                              : '',
                        }}
                        components={{ destacado: <strong /> }}
                      />
                    ) : (
                      <Trans
                        i18nKey="Con esto se pasaría del tope: lleva <destacado>{{lleva}}</destacado> de {{tope}} en este periodo."
                        values={{
                          lleva: fmt(absence.over_the_limit.used),
                          tope: fmt(absence.over_the_limit.allowance),
                        }}
                        components={{ destacado: <strong /> }}
                      />
                    )}{' '}
                    {absence.over_the_limit.kind !== 'rest_debt' &&
                      t(
                        'Se puede aprobar igual —el convenio puede dar más de lo que consta en el catálogo—, pero conviene saberlo.',
                      )}
                  </Alert>
                )}

                {/* Vacaciones que puso otro, con menos de dos meses. El aviso
                    llega aquí y no solo a quien las metió, porque si solo lo
                    viera quien las puso bastaría con no leerlo.

                    Tampoco impide: acortar el plazo de acuerdo es corriente y
                    legítimo, y negarse a registrarlo dejaría fuera del sistema
                    unas vacaciones que se van a disfrutar igual. */}
                {absence.short_notice && (
                  <Alert severity="info" variant="outlined" sx={{ mt: 1.5 }}>
                    <Trans
                      i18nKey="Las fechas se pusieron con <destacado>{{plazo}}</destacado> de antelación, y el {{articulo}} pide dos meses. El plazo existe para que dé tiempo a organizarse; se puede aprobar si la persona está de acuerdo."
                      values={{
                        plazo: `${absence.short_notice.days} ${t(plural(absence.short_notice.days, 'día', 'días'))}`,
                        articulo: absence.short_notice.citation,
                      }}
                      components={{ destacado: <strong /> }}
                    />
                  </Alert>
                )}
              </RequestCard>
            ))}
            <ListaRecortada total={absences.data?.count} mostradas={absenceRows.length} />
            <SelectionBar
              selection={absencePick}
              noun={{ singular: alCatalogo('ausencia'), plural: alCatalogo('ausencias') }}
              busy={bulking}
              actions={[
                {
                  label: t('Aprobar'),
                  onClick: () =>
                    decideMany(
                      shownAbsences.filter((row) => absencePick.isSelected(row)),
                      approveAbsence,
                      { done: t('aprobadas') },
                    ).then(absencePick.clear),
                },
                {
                  // Rechazar en bloque abre el mismo cuadro de motivo que
                  // rechazar una: el «no» que se lee es el mismo, y sin motivo
                  // no se distingue de un despiste.
                  label: t('Rechazar'),
                  variant: 'text',
                  color: 'inherit',
                  onClick: () =>
                    setRejecting({
                      action: rejectAbsence,
                      rows: shownAbsences.filter((row) => absencePick.isSelected(row)),
                      needsNote: false,
                      onDone: absencePick.clear,
                    }),
                },
              ]}
            />
          </Stack>
        ))}

      {tab === 1 &&
        (corrections.isLoading ? (
          <Loading />
        ) : shownCorrections.length === 0 ? (
          <Empty>
            {filtering
              ? t('Ninguna corrección coincide con el filtro.')
              : t('No hay correcciones esperando respuesta.')}
          </Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            {shownCorrections.map((correction) => (
              <RequestCard
                key={correction.id}
                busy={decide.isPending || bulking}
                select={<SelectBox selection={correctionPick} item={correction} />}
                title={correction.employee_name}
                meta={t(KIND_LABELS[correction.kind] ?? correction.kind_display)}
                reason={correction.reason}
                onApprove={() => decide.mutate({ action: approveCorrection, id: correction.id })}
                onReject={() => openReject(rejectCorrection, correction.id, true)}
              >
                <Stack
                  direction="row"
                  sx={{ gap: 1, mt: 1, alignItems: 'center', flexWrap: 'wrap' }}
                >
                  <ChangeOnTheRecord correction={correction} zone={correction.time_zone ?? zone} />
                  <SourceChip source="ADMIN" />
                </Stack>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 1 }}
                >
                  {t(
                    'Si se aprueba, el original no se borra: queda anulado y legible, y el fichaje nuevo se marca como corrección. Se avisará a la persona.',
                  )}
                </Typography>
              </RequestCard>
            ))}
            <Pager
              count={corrections.data?.count}
              page={paginaCorrecciones}
              pageSize={PAGE_SIZE}
              noun={{ singular: alCatalogo('corrección'), plural: alCatalogo('correcciones') }}
              onChange={(pagina) => {
                setPaginaCorrecciones(pagina)
                // La selección se vacía al cambiar de página: las acciones en
                // bloque actúan sobre lo que se ve, y arrastrar marcas de una
                // página que ya no está a la vista es cómo se aprueba algo sin
                // haberlo mirado.
                correctionPick.clear()
              }}
            />
            <SelectionBar
              selection={correctionPick}
              noun={{ singular: alCatalogo('corrección'), plural: alCatalogo('correcciones') }}
              busy={bulking}
              actions={[
                {
                  label: t('Aprobar'),
                  onClick: () =>
                    decideMany(
                      shownCorrections.filter((row) => correctionPick.isSelected(row)),
                      approveCorrection,
                      { done: t('aprobadas') },
                    ).then(correctionPick.clear),
                },
                {
                  label: t('Rechazar'),
                  variant: 'text',
                  color: 'inherit',
                  onClick: () =>
                    setRejecting({
                      action: rejectCorrection,
                      rows: shownCorrections.filter((row) => correctionPick.isSelected(row)),
                      needsNote: true,
                      onDone: correctionPick.clear,
                    }),
                },
              ]}
            />
          </Stack>
        ))}

      {tab === 2 &&
        (waiting.isLoading ? (
          <Loading />
        ) : shownOpen.length === 0 ? (
          <Empty>
            {filtering
              ? t('Ningún cambio coincide con el filtro.')
              : t('Ningún cambio propuesto por la empresa espera respuesta.')}
          </Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            <Alert severity="info" variant="outlined">
              {t(
                'Un cambio que propone la empresa sobre el registro de otra persona necesita su autorización (art. 4.b). Si discrepa o no contesta en el plazo, la empresa puede aplicarlo igualmente: queda marcado como hecho sin acuerdo y su versión viaja al informe de Inspección.',
              )}
            </Alert>

            {shownOpen.map((correction) => (
              <Paper key={correction.id} variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  sx={{ gap: 2, justifyContent: 'space-between' }}
                >
                  <SelectBox
                    selection={openPick}
                    item={correction}
                    label={t('Seleccionar la propuesta de {{quien}}', {
                      quien: correction.employee_name,
                    })}
                  />
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Typography sx={{ fontWeight: 600 }}>{correction.employee_name}</Typography>
                      <StatusChip
                        status={correction.status}
                        label={
                          correction.employee_responded_at
                            ? t('No está de acuerdo')
                            : t('Sin contestar todavía')
                        }
                      />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                      {t(KIND_LABELS[correction.kind] ?? correction.kind_display)}
                      {correction.proposed_timestamp && (
                        <>
                          {' · '}
                          {timeOf(
                            correction.proposed_timestamp,
                            correction.time_zone ?? zone,
                          )} del {dateOf(correction.proposed_timestamp)}
                        </>
                      )}
                    </Typography>

                    <Typography
                      variant="body2"
                      sx={{
                        mt: 1.5,
                        pl: 1.5,
                        borderLeft: 2,
                        borderColor: 'divider',
                        fontStyle: 'italic',
                        maxWidth: '68ch',
                      }}
                    >
                      {correction.reason}
                    </Typography>

                    {correction.employee_dissent && (
                      <Typography variant="body2" sx={{ mt: 1.5, maxWidth: '68ch' }}>
                        <strong>{t('Su versión:')}</strong> {correction.employee_dissent}
                      </Typography>
                    )}

                    {/* Whether the representatives were told, and --- when there
                        are none on record --- that nobody was. Claiming an
                        obligation was met would be worse than admitting the gap. */}
                    {correction.representatives_notice && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', mt: 1 }}
                      >
                        {correction.representatives_notice}
                      </Typography>
                    )}
                  </Box>

                  <Stack sx={{ gap: 1, flexShrink: 0, alignItems: 'flex-start' }}>
                    <Button
                      size="small"
                      variant="outlined"
                      color="secondary"
                      disabled={decide.isPending}
                      onClick={() =>
                        setConfirming({
                          title: t('Aplicar sin acuerdo'),
                          body: correction.employee_name,
                          detail: correction.employee_dissent
                            ? t(
                                'Su versión queda registrada junto al cambio y las dos cosas van al informe de Inspección. Se le avisa.',
                              )
                            : t(
                                'Todavía no ha contestado. El registro dirá que se aplicó sin su conformidad, no que estuviera de acuerdo.',
                              ),
                          verb: t('Aplicar'),
                          run: () =>
                            decide.mutate({ action: applyCorrectionAnyway, id: correction.id }),
                        })
                      }
                    >
                      {t('Aplicar sin acuerdo')}
                    </Button>
                    <Button
                      size="small"
                      color="inherit"
                      disabled={decide.isPending}
                      onClick={() => openReject(rejectCorrection, correction.id, true)}
                    >
                      {t('Retirar la propuesta')}
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            ))}

            {/* Solo «Retirar», y la ausencia de «Aplicar sin acuerdo» aquí es
                deliberada, no un olvido.

                Retirar una propuesta no toca el registro de nadie: lo deja
                como estaba. Aplicar sin acuerdo sí, y es la excepción del
                art. 4.b --- un cambio unilateral sobre el registro de otra
                persona. Veinticinco de esas con un clic convertiría lo
                excepcional en lo cómodo, que es justo lo que la norma quiere
                evitar. Se siguen aplicando de una en una, con su cuadro que
                dice a quién y qué queda registrado.

                Retirar en bloque sí hace falta: una cola de propuestas viejas
                que ya no vienen a cuento se limpia entera. */}
            <Pager
              count={waiting.data?.count}
              page={paginaEspera}
              pageSize={PAGE_SIZE}
              noun={{ singular: alCatalogo('propuesta'), plural: alCatalogo('propuestas') }}
              onChange={(pagina) => {
                setPaginaEspera(pagina)
                openPick.clear()
              }}
            />
            <SelectionBar
              selection={openPick}
              noun={{ singular: alCatalogo('propuesta'), plural: alCatalogo('propuestas') }}
              busy={bulking}
              actions={[
                {
                  label: t('Retirar la propuesta'),
                  variant: 'outlined',
                  color: 'inherit',
                  onClick: () =>
                    setRejecting({
                      action: rejectCorrection,
                      rows: shownOpen.filter((row) => openPick.isSelected(row)),
                      needsNote: true,
                      onDone: openPick.clear,
                    }),
                },
              ]}
            />
          </Stack>
        ))}

      {tab === 3 &&
        (overtime.isLoading ? (
          <Loading />
        ) : shownOvertime.length === 0 ? (
          <Empty>
            {filtering
              ? t('Ninguna hora extra coincide con el filtro.')
              : t('No hay horas extra por resolver.')}
          </Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            <Alert severity="info" variant="outlined">
              {t(
                'El registro capta el tiempo real. Aquí solo dices qué parte es hora extra autorizada y cómo se salda (art. 35.1): pagada, o compensada con descanso dentro de cuatro meses. No se toca ningún fichaje.',
              )}
            </Alert>

            {shownOvertime.map((group) => (
              <OvertimePersonCard
                key={group.employee}
                group={group}
                busy={ruleOvertime.isPending}
                select={
                  <SelectBox
                    selection={overtimePick}
                    item={group}
                    label={t('Seleccionar las horas de {{quien}}', { quien: group.name })}
                  />
                }
                onDecide={(payload) =>
                  ruleOvertime.mutate({ employee: group.employee, ...payload })
                }
              />
            ))}

            {/* Cómo se salda es lo que se decide aquí, y en bloque tiene
                sentido porque suele ser una política de la empresa para todo
                el mes, no un caso a caso.

                Con descanso y pagada por separado, sin un «autorizar y ya»:
                son dos consecuencias distintas del art. 35.1, y las
                compensadas con descanso además **no cuentan** para el tope de
                ochenta horas al año. Un botón único obligaría a elegir un
                valor por defecto, y el que se eligiera sería el que se
                aplicara sin pensar. */}
            <SelectionBar
              selection={overtimePick}
              noun={{ singular: alCatalogo('persona'), plural: alCatalogo('personas') }}
              busy={bulking}
              actions={[
                {
                  label: t('Autorizar con descanso'),
                  onClick: () =>
                    decidirHorasExtra(
                      seleccionadas(shownOvertime, overtimePick),
                      true,
                      'REST',
                    ).then(overtimePick.clear),
                },
                {
                  label: t('Autorizar pagadas'),
                  variant: 'outlined',
                  onClick: () =>
                    decidirHorasExtra(
                      seleccionadas(shownOvertime, overtimePick),
                      true,
                      'PAID',
                    ).then(overtimePick.clear),
                },
                {
                  label: t('No autorizar'),
                  variant: 'text',
                  color: 'inherit',
                  onClick: () =>
                    decidirHorasExtra(seleccionadas(shownOvertime, overtimePick), false).then(
                      overtimePick.clear,
                    ),
                },
              ]}
            />
          </Stack>
        ))}

      {tab === 4 &&
        (recoveries.isLoading ? (
          <Loading />
        ) : recoveryRows.length === 0 ? (
          <Empty>{t('No hay vacaciones pendientes de recuperar.')}</Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            <Alert severity="info" variant="outlined">
              {t(
                'Cuando una baja cae encima de unas vacaciones ya aprobadas, esos días no se han disfrutado y se disfrutan después (art. 38.3 ET). Aquí solo se confirma que vuelven al saldo: la baja y las vacaciones no se tocan.',
              )}
            </Alert>

            {recoveryRows.map((row) => (
              <Paper key={row.id} variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  sx={{ gap: 2, justifyContent: 'space-between', alignItems: { md: 'center' } }}
                >
                  <SelectBox
                    selection={recoveryPick}
                    item={row}
                    label={t('Seleccionar los días de {{quien}}', {
                      quien: row.employee_name,
                    })}
                  />
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 600 }}>{row.employee_name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>
                        {row.days} {row.days === 1 ? t('día') : t('días')}
                      </strong>{' '}
                      del {dayRange(row.first_day, row.last_day)} · {row.because_of}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.expires_on
                        ? t('Se pueden disfrutar hasta el {{fecha}}.', {
                            fecha: dateOf(row.expires_on, { year: 'numeric' }),
                          })
                        : t(
                            'Sin plazo: se disfrutan al terminar la suspensión, aunque acabe el año.',
                          )}
                    </Typography>
                  </Box>
                  <Stack direction="row" sx={{ gap: 1, flexShrink: 0 }}>
                    <Button
                      variant="contained"
                      disabled={ruleRecovery.isPending}
                      onClick={() => ruleRecovery.mutate({ recovery: row.id, accept: true })}
                    >
                      {t('Devolver al saldo')}
                    </Button>
                    <Button
                      color="inherit"
                      disabled={ruleRecovery.isPending}
                      onClick={() => ruleRecovery.mutate({ recovery: row.id, accept: false })}
                    >
                      {t('No procede')}
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            ))}

            {/* Aquí no hay línea roja que cuidar: confirmar una recuperación
                devuelve días al saldo de quien estuvo de baja durante sus
                vacaciones. Es a favor de la persona y no toca ni la baja ni
                las vacaciones, así que hacerlo de veinte en veinte no cambia
                nada salvo el tiempo que se tarda. */}
            <SelectionBar
              selection={recoveryPick}
              noun={{ singular: alCatalogo('recuperación'), plural: alCatalogo('recuperaciones') }}
              busy={bulking}
              actions={[
                {
                  label: t('Devolver al saldo'),
                  onClick: () =>
                    decidirRecuperaciones(seleccionadas(recoveryRows, recoveryPick), true).then(
                      recoveryPick.clear,
                    ),
                },
                {
                  label: t('No procede'),
                  variant: 'text',
                  color: 'inherit',
                  onClick: () =>
                    decidirRecuperaciones(seleccionadas(recoveryRows, recoveryPick), false).then(
                      recoveryPick.clear,
                    ),
                },
              ]}
            />
          </Stack>
        ))}

      {tab === 5 && <AdaptationQueue rows={adaptationRows} loading={adaptations.isLoading} />}

      <ConfirmDialog
        request={confirming}
        busy={decide.isPending}
        onClose={() => setConfirming(null)}
      />

      <RejectDialog
        open={Boolean(rejecting)}
        needsNote={rejecting?.needsNote}
        count={rejecting?.rows?.length ?? 1}
        busy={decide.isPending || bulking}
        onClose={() => setRejecting(null)}
        onConfirm={(note) => {
          if (rejecting.rows) {
            const { rows, action, onDone } = rejecting
            setRejecting(null)
            decideMany(rows, (id) => action(id, note), { done: t('rechazadas') }).then(onDone)
            return
          }
          decide.mutate({ action: rejecting.action, id: rejecting.id, note })
        }}
      />
    </>
  )
}
