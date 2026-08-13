import { useMemo, useState } from 'react'
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
  applyCorrectionAnyway,
  approveAbsence,
  approveCorrection,
  decideOvertime,
  getCorrections,
  getPendingAbsences,
  getPendingOvertime,
  rejectAbsence,
  rejectCorrection,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  SourceChip,
  StatusChip,
} from '../../components/common.jsx'
import {
  dateOf,
  dayRange,
  durationOf,
  leaveLabel,
  leaveLength,
  timeOf,
} from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

const KIND_LABELS = {
  ADD: 'Añadir un fichaje que falta',
  MODIFY: 'Cambiar la hora',
  VOID: 'Anular un fichaje',
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
function OvertimePersonCard({ group, busy, onDecide }) {
  const [settlement, setSettlement] = useState('PAID')
  const [showDays, setShowDays] = useState(false)
  const { rows } = group
  const single = rows.length === 1
  const total = rows.reduce((sum, row) => sum + row.minutes, 0)
  const reopened = rows.filter((row) => row.previous).length

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        sx={{ gap: 2, justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600 }}>{group.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {single ? (
              <>
                {dateOf(rows[0].day)} · <strong>{durationOf(rows[0].minutes)}</strong> de más (
                {durationOf(rows[0].worked_minutes)} trabajadas de{' '}
                {durationOf(rows[0].expected_minutes)} previstas)
              </>
            ) : (
              <>
                {rows.length} días · <strong>{durationOf(total)}</strong> de más en total ·{' '}
                {dayRange(rows[0].day, rows[rows.length - 1].day)}
              </>
            )}
          </Typography>
          {reopened > 0 && (
            <Typography variant="caption" color="warning.main">
              {reopened === 1
                ? 'Un día ya resuelto vuelve a revisión: la cifra ha cambiado.'
                : `${reopened} días ya resueltos vuelven a revisión: la cifra ha cambiado.`}
            </Typography>
          )}
        </Box>

        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            select
            size="small"
            label="Se salda"
            value={settlement}
            onChange={(event) => setSettlement(event.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="PAID">Pagada</MenuItem>
            <MenuItem value="REST">Con descanso</MenuItem>
          </TextField>
          <Button
            variant="contained"
            disabled={busy}
            onClick={() =>
              onDecide({ days: rows.map((row) => row.day), authorise: true, settlement })
            }
          >
            {single ? 'Autorizar' : 'Autorizar todo'}
          </Button>
          <Button
            color="inherit"
            disabled={busy}
            onClick={() => onDecide({ days: rows.map((row) => row.day), authorise: false })}
          >
            {single ? 'No autorizar' : 'No autorizar nada'}
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
            {showDays ? 'Ocultar los días' : `Ver los ${rows.length} días`}
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
                    {dateOf(row.day)} · <strong>{durationOf(row.minutes)}</strong> de más (
                    {durationOf(row.worked_minutes)} de {durationOf(row.expected_minutes)}{' '}
                    previstas)
                    {row.previous && (
                      <Typography component="span" variant="caption" color="warning.main">
                        {' '}
                        · resuelto antes con {durationOf(row.previous.minutes)}
                      </Typography>
                    )}
                  </Typography>
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button
                      size="small"
                      disabled={busy}
                      onClick={() => onDecide({ days: [row.day], authorise: true, settlement })}
                    >
                      Autorizar
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
function RequestCard({ title, meta, reason, children, onApprove, onReject, busy }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        sx={{ gap: 2, justifyContent: 'space-between', alignItems: { md: 'flex-start' } }}
      >
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
            Rechazar
          </Button>
          <Button size="small" variant="contained" onClick={onApprove} disabled={busy}>
            Aprobar
          </Button>
        </Stack>
      </Stack>
    </Paper>
  )
}

function RejectDialog({ open, onClose, onConfirm, needsNote }) {
  const [note, setNote] = useState('')

  const confirm = () => {
    onConfirm(note)
    setNote('')
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Rechazar la solicitud</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          La solicitud se conserva rechazada: que alguien lo pidiera y se le dijera que no también
          es parte del historial.
        </Typography>
        <TextField
          autoFocus
          fullWidth
          multiline
          minRows={3}
          label={needsNote ? 'Motivo del rechazo' : 'Motivo del rechazo (opcional)'}
          placeholder="Lo leerá la persona que lo solicitó."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">
          Volver
        </Button>
        <Button onClick={confirm} variant="contained" color="secondary">
          Rechazar
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default function Decisions() {
  const { session } = useAuth()
  const zone = session?.tenant?.time_zone
  const queryClient = useQueryClient()

  const [tab, setTab] = useState(0)
  const [error, setError] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [confirming, setConfirming] = useState(null)

  const absences = useQuery({ queryKey: ['absences', 'pending'], queryFn: getPendingAbsences })
  const corrections = useQuery({
    queryKey: ['corrections', 'pending'],
    queryFn: () => getCorrections({ status: 'PENDING' }),
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
    queryKey: ['corrections', 'awaiting'],
    queryFn: () => getCorrections({ status: 'AWAITING_EMPLOYEE' }),
  })

  // Horas extra pendientes de autorizar. La cola por excepción del tiempo: días
  // que se pasaron de lo previsto y que nadie ha resuelto.
  const overtime = useQuery({ queryKey: ['overtime', 'pending'], queryFn: getPendingOvertime })

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
    onError: setError,
  })

  const ruleOvertime = useMutation({
    mutationFn: decideOvertime,
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['overtime'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: setError,
  })

  const openReject = (action, id, needsNote) => setRejecting({ action, id, needsNote })

  const absenceRows = absences.data ?? []
  const correctionRows = corrections.data?.rows ?? []
  // Those who have answered first: the company can act on them now, whereas
  // the silent ones are still inside their window to reply.
  const overtimeRows = overtime.data ?? []
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

  return (
    <>
      <PageHeader
        title="Por decidir"
        subtitle="Solicitudes esperando respuesta. Toda decisión queda registrada con su autor y su momento."
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      <Tabs value={tab} onChange={(_, next) => setTab(next)} sx={{ mb: 2 }}>
        <Tab
          label={
            <Badge badgeContent={absenceRows.length} color="secondary" sx={{ pr: 1.5 }}>
              Ausencias
            </Badge>
          }
        />
        <Tab
          label={
            <Badge badgeContent={correctionRows.length} color="secondary" sx={{ pr: 1.5 }}>
              Fichajes
            </Badge>
          }
        />
        <Tab
          label={
            <Badge badgeContent={openRows.length} color="secondary" sx={{ pr: 1.5 }}>
              Sin acuerdo
            </Badge>
          }
        />
        <Tab
          label={
            <Badge badgeContent={overtimeRows.length} color="secondary" sx={{ pr: 1.5 }}>
              Horas extra
            </Badge>
          }
        />
      </Tabs>

      {tab === 0 &&
        (absences.isLoading ? (
          <Loading />
        ) : absenceRows.length === 0 ? (
          <Empty>No hay ausencias esperando respuesta.</Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            {absenceRows.map((absence) => (
              <RequestCard
                key={absence.id}
                busy={decide.isPending}
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
                    {absence.over_the_limit.period === 'EVENT' ? (
                      <>
                        Pide <strong>{fmt(absence.over_the_limit.used)}</strong> y el permiso da{' '}
                        {fmt(absence.over_the_limit.allowance)}
                        {absence.over_the_limit.travel_extra > 0 &&
                          ` (+${fmt(absence.over_the_limit.travel_extra)} si hay desplazamiento)`}
                        .
                      </>
                    ) : (
                      <>
                        Con esto se pasaría del tope: lleva{' '}
                        <strong>{fmt(absence.over_the_limit.used)}</strong> de{' '}
                        {fmt(absence.over_the_limit.allowance)} en este periodo.
                      </>
                    )}{' '}
                    Se puede aprobar igual —el convenio puede dar más de lo que consta en el
                    catálogo—, pero conviene saberlo.
                  </Alert>
                )}
              </RequestCard>
            ))}
          </Stack>
        ))}

      {tab === 1 &&
        (corrections.isLoading ? (
          <Loading />
        ) : correctionRows.length === 0 ? (
          <Empty>No hay correcciones esperando respuesta.</Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            {correctionRows.map((correction) => (
              <RequestCard
                key={correction.id}
                busy={decide.isPending}
                title={correction.employee_name}
                meta={KIND_LABELS[correction.kind] ?? correction.kind_display}
                reason={correction.reason}
                onApprove={() => decide.mutate({ action: approveCorrection, id: correction.id })}
                onReject={() => openReject(rejectCorrection, correction.id, true)}
              >
                <Stack
                  direction="row"
                  sx={{ gap: 1, mt: 1, alignItems: 'center', flexWrap: 'wrap' }}
                >
                  {correction.proposed_timestamp && (
                    <Typography variant="body2">
                      Hora propuesta:{' '}
                      <Box
                        component="span"
                        sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}
                      >
                        {timeOf(correction.proposed_timestamp, zone)}
                      </Box>{' '}
                      del {dateOf(correction.proposed_timestamp)}
                    </Typography>
                  )}
                  <SourceChip source="ADMIN" />
                </Stack>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 1 }}
                >
                  Si se aprueba, el original no se borra: queda anulado y legible, y el fichaje
                  nuevo se marca como corrección. Se avisará a la persona.
                </Typography>
              </RequestCard>
            ))}
          </Stack>
        ))}

      {tab === 2 &&
        (waiting.isLoading ? (
          <Loading />
        ) : openRows.length === 0 ? (
          <Empty>Ningún cambio propuesto por la empresa espera respuesta.</Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            <Alert severity="info" variant="outlined">
              Un cambio que propone la empresa sobre el registro de otra persona necesita su
              autorización (art. 4.b). Si discrepa o no contesta en el plazo, la empresa puede
              aplicarlo igualmente: queda marcado como hecho sin acuerdo y su versión viaja al
              informe de Inspección.
            </Alert>

            {openRows.map((correction) => (
              <Paper key={correction.id} variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  sx={{ gap: 2, justifyContent: 'space-between' }}
                >
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Typography sx={{ fontWeight: 600 }}>{correction.employee_name}</Typography>
                      <StatusChip
                        status={correction.status}
                        label={
                          correction.employee_responded_at
                            ? 'No está de acuerdo'
                            : 'Sin contestar todavía'
                        }
                      />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                      {KIND_LABELS[correction.kind] ?? correction.kind_display}
                      {correction.proposed_timestamp && (
                        <>
                          {' · '}
                          {timeOf(correction.proposed_timestamp, zone)} del{' '}
                          {dateOf(correction.proposed_timestamp)}
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
                        <strong>Su versión:</strong> {correction.employee_dissent}
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
                          title: 'Aplicar sin acuerdo',
                          body: correction.employee_name,
                          detail: correction.employee_dissent
                            ? 'Su versión queda registrada junto al cambio y las dos cosas van al informe de Inspección. Se le avisa.'
                            : 'Todavía no ha contestado. El registro dirá que se aplicó sin su conformidad, no que estuviera de acuerdo.',
                          verb: 'Aplicar',
                          run: () =>
                            decide.mutate({ action: applyCorrectionAnyway, id: correction.id }),
                        })
                      }
                    >
                      Aplicar sin acuerdo
                    </Button>
                    <Button
                      size="small"
                      color="inherit"
                      disabled={decide.isPending}
                      onClick={() => openReject(rejectCorrection, correction.id, true)}
                    >
                      Retirar la propuesta
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            ))}
          </Stack>
        ))}

      {tab === 3 &&
        (overtime.isLoading ? (
          <Loading />
        ) : overtimeRows.length === 0 ? (
          <Empty>No hay horas extra por resolver.</Empty>
        ) : (
          <Stack sx={{ gap: 1.5 }}>
            <Alert severity="info" variant="outlined">
              El registro capta el tiempo real. Aquí solo dices qué parte es hora extra autorizada y
              cómo se salda (art. 35.1): pagada, o compensada con descanso dentro de cuatro meses.
              No se toca ningún fichaje.
            </Alert>

            {overtimeGroups.map((group) => (
              <OvertimePersonCard
                key={group.employee}
                group={group}
                busy={ruleOvertime.isPending}
                onDecide={(payload) =>
                  ruleOvertime.mutate({ employee: group.employee, ...payload })
                }
              />
            ))}
          </Stack>
        ))}

      <ConfirmDialog
        request={confirming}
        busy={decide.isPending}
        onClose={() => setConfirming(null)}
      />

      <RejectDialog
        open={Boolean(rejecting)}
        needsNote={rejecting?.needsNote}
        onClose={() => setRejecting(null)}
        onConfirm={(note) => decide.mutate({ action: rejecting.action, id: rejecting.id, note })}
      />
    </>
  )
}
