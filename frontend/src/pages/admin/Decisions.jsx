import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Badge from '@mui/material/Badge'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
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
  getCorrections,
  getPendingAbsences,
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
import { dateOf, dayRange, leaveLabel, leaveLength, timeOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

const KIND_LABELS = {
  ADD: 'Añadir un fichaje que falta',
  MODIFY: 'Cambiar la hora',
  VOID: 'Anular un fichaje',
}

/** One request, with everything needed to decide it visible at once.
 *
 *  Approving is one click; refusing opens a box for the note. That asymmetry is
 *  deliberate: a refusal is what the person will read and ask about, and it
 *  should not be as effortless as a yes.
 */
/** «2,5», no «2.5»: los decimales del aviso se leen en español. */
const fmt = (value) => {
  const n = Number(value ?? 0)
  return (n % 1 === 0 ? n.toString() : n.toFixed(2).replace(/0$/, '')).replace('.', ',')
}

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
          La solicitud se conserva rechazada: que alguien lo pidiera y se le dijera que no
          también es parte del historial.
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

  const openReject = (action, id, needsNote) => setRejecting({ action, id, needsNote })

  const absenceRows = absences.data ?? []
  const correctionRows = corrections.data?.rows ?? []
  // Those who have answered first: the company can act on them now, whereas
  // the silent ones are still inside their window to reply.
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
                        Pide <strong>{fmt(absence.over_the_limit.used)}</strong> y el permiso
                        da {fmt(absence.over_the_limit.allowance)}
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
                <Stack direction="row" sx={{ gap: 1, mt: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                  {correction.proposed_timestamp && (
                    <Typography variant="body2">
                      Hora propuesta:{' '}
                      <Box component="span" sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                        {timeOf(correction.proposed_timestamp, zone)}
                      </Box>{' '}
                      del {dateOf(correction.proposed_timestamp)}
                    </Typography>
                  )}
                  <SourceChip source="ADMIN" />
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
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
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
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
