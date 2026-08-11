import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  approveAbsence,
  approveCorrection,
  getCorrections,
  getPendingAbsences,
  rejectAbsence,
  rejectCorrection,
} from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader, SourceChip } from '../../components/common.jsx'
import { dateOf, dayRange, timeOf } from '../../components/format.js'
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

  const absences = useQuery({ queryKey: ['absences', 'pending'], queryFn: getPendingAbsences })
  const corrections = useQuery({
    queryKey: ['corrections', 'pending'],
    queryFn: () => getCorrections({ status: 'PENDING' }),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['absences'] })
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
  const correctionRows = corrections.data ?? []

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
                meta={`${absence.type_display} · ${dayRange(absence.start_date, absence.end_date)} · ${absence.days} ${absence.days === 1 ? 'día' : 'días'}`}
                reason={absence.reason}
                onApprove={() => decide.mutate({ action: approveAbsence, id: absence.id })}
                onReject={() => openReject(rejectAbsence, absence.id, false)}
              />
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

      <RejectDialog
        open={Boolean(rejecting)}
        needsNote={rejecting?.needsNote}
        onClose={() => setRejecting(null)}
        onConfirm={(note) => decide.mutate({ action: rejecting.action, id: rejecting.id, note })}
      />
    </>
  )
}
