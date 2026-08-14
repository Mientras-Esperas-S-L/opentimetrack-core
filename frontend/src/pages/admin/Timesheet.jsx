import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Chip from '@mui/material/Chip'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import EditNoteIcon from '@mui/icons-material/EditNote'

import { getPunches, PAGE_SIZE, requestCorrection } from '../../services/api.js'
import EmployeePicker from '../../components/EmployeePicker.jsx'
import { PickFilter } from '../../components/filters.jsx'
import { PUNCH_TYPES, SOURCE_OPTIONS } from '../../components/punches.js'
import {
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pager,
  SourceChip,
} from '../../components/common.jsx'
import { firstOfThisMonth, today } from '../../components/format.js'
import { dateOf, timeOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

/** Groups the flat list of events by local day, newest first.
 *
 *  The API returns events; a person reads days. Doing it here rather than
 *  server-side keeps the endpoint honest --- it returns the record as stored ---
 *  and the grouping is presentation.
 */
function byDay(punches, zone) {
  const groups = new Map()
  for (const punch of punches) {
    const day = new Date(punch.timestamp).toLocaleDateString('sv-SE', { timeZone: zone })
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day).push(punch)
  }
  return [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]))
}

/** Filing a correction from the panel.
 *
 *  ADR-0014: a manager may correct without a prior request, but through the
 *  same procedure and the same mandatory reason. Nobody touches a time without
 *  leaving why --- and the record keeps who it concerns and who filed it as two
 *  separate facts.
 */
function CorrectionDialog({
  open,
  employee,
  employeeName,
  punch,
  onClose,
  onSubmit,
  saving,
  error,
}) {
  const [form, setForm] = useState({ kind: 'ADD', proposed_type: 'OUT', when: '', reason: '' })
  const [loaded, setLoaded] = useState(null)

  const key = punch?.id ?? employee ?? 'new'
  if (open && loaded !== key) {
    setLoaded(key)
    setForm({
      kind: punch ? 'MODIFY' : 'ADD',
      proposed_type: punch?.punch_type ?? 'OUT',
      when: '',
      reason: '',
    })
  }
  if (!open && loaded !== null) setLoaded(null)

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })
  // From the punch when there is one, otherwise from whoever is filtered: the
  // list of people no longer lives on this page, so the name comes down as a
  // name rather than being looked up in it.
  const subject = punch?.employee_name ?? employeeName ?? ''

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit({
            employee: punch?.employee ?? employee,
            target: punch?.id,
            kind: form.kind,
            proposed_type: form.kind === 'ADD' ? form.proposed_type : undefined,
            proposed_timestamp: form.when ? new Date(form.when).toISOString() : undefined,
            reason: form.reason,
          })
        }}
      >
        <DialogTitle>Corregir el registro{subject ? ` de ${subject}` : ''}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            La corrección queda registrada con tu nombre, el momento y el motivo. El fichaje
            original no se borra: queda anulado y legible, y se avisará a la persona.
          </Typography>
          <Stack sx={{ gap: 2, pt: 0.5 }}>
            {punch ? (
              <Alert severity="info" variant="outlined">
                Fichaje seleccionado: {punch.punch_type === 'IN' ? 'entrada' : 'salida'} de las{' '}
                {timeOf(punch.timestamp)} del {dateOf(punch.timestamp)}
              </Alert>
            ) : (
              <TextField
                select
                label="Qué falta"
                value={form.proposed_type}
                onChange={set('proposed_type')}
              >
                <MenuItem value="IN">Una entrada</MenuItem>
                <MenuItem value="OUT">Una salida</MenuItem>
              </TextField>
            )}

            {punch && (
              <TextField select label="Qué hacer" value={form.kind} onChange={set('kind')}>
                <MenuItem value="MODIFY">Cambiar la hora</MenuItem>
                <MenuItem value="VOID">Anular el fichaje</MenuItem>
              </TextField>
            )}

            {form.kind !== 'VOID' && (
              <TextField
                required
                fullWidth
                type="datetime-local"
                label="Hora real"
                value={form.when}
                onChange={set('when')}
                slotProps={{ inputLabel: { shrink: true } }}
                helperText="No puede ser una hora futura."
              />
            )}

            <TextField
              required
              fullWidth
              multiline
              minRows={3}
              label="Motivo"
              placeholder="Por ejemplo: el operario avisó de que la tableta estaba sin batería."
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
            Registrar corrección
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default function Timesheet() {
  const { session } = useAuth()
  const zone = session?.tenant?.time_zone
  const queryClient = useQueryClient()

  const [employee, setEmployee] = useState('')
  const [employeeName, setEmployeeName] = useState('')
  const [correcting, setCorrecting] = useState(null) // {punch} | {} = new event
  const [error, setError] = useState(null)

  // A month by default rather than everything. The screen used to ask for the
  // whole history and show whichever fifty rows came back first, with no way to
  // reach the rest: about a day and a half of a small company's punches, under
  // a heading claiming to be the record as stored.
  const [from, setFrom] = useState(firstOfThisMonth)
  const [to, setTo] = useState(today)
  const [page, setPage] = useState(1)
  //: Tipo y origen. El origen era una columna que se enseñaba y no se podía
  //: usar para buscar --- y es justo por lo que alguien entra aquí: «enséñame
  //: los que registró el terminal», «los que hizo una aplicación en su
  //: nombre». Esas dos son las que la Inspección mira primero.
  const [kind, setKind] = useState('')
  const [source, setSource] = useState('')

  const filters = {
    employee: employee || undefined,
    punch_type: kind || undefined,
    source: source || undefined,
    date_from: from,
    date_to: to,
  }

  const { data, isLoading } = useQuery({
    queryKey: ['punches', { ...filters, page }],
    queryFn: () => getPunches({ ...filters, page, ordering: '-timestamp' }),
    placeholderData: (previous) => previous,
  })

  // Any change to what is being asked for starts at the first page again:
  // staying on page 4 of a narrower range shows an empty screen that looks like
  // "there is nothing here".
  const rephrase = (set) => (value) => {
    set(value)
    setPage(1)
  }

  const correct = useMutation({
    mutationFn: requestCorrection,
    onSuccess: () => {
      setCorrecting(null)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['punches'] })
      queryClient.invalidateQueries({ queryKey: ['corrections'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: setError,
  })

  const days = byDay(data?.rows ?? [], zone)

  return (
    <>
      <PageHeader
        title="Fichajes"
        subtitle="El registro tal y como está guardado. Un fichaje anulado sigue siendo legible: no se borra nada."
        action={
          employee && (
            <Button
              variant="outlined"
              startIcon={<EditNoteIcon />}
              onClick={() => setCorrecting({})}
            >
              Corregir
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{ gap: 2, mb: 2, alignItems: { sm: 'flex-start' } }}
      >
        <EmployeePicker
          size="small"
          value={employee}
          onChange={(id, person) => {
            rephrase(setEmployee)(id)
            setEmployeeName(
              person && !person.__everyone
                ? `${person.first_name} ${person.last_name}`.trim() || person.email
                : '',
            )
          }}
          everyoneLabel="Toda la empresa"
          sx={{ minWidth: 260 }}
        />
        <TextField
          size="small"
          type="date"
          label="Desde"
          value={from}
          onChange={(event) => rephrase(setFrom)(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Hasta"
          value={to}
          onChange={(event) => rephrase(setTo)(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          error={to < from}
          helperText={to < from ? 'Va antes que la inicial.' : ' '}
        />
        <PickFilter
          label="Tipo"
          value={kind}
          onChange={rephrase(setKind)}
          options={PUNCH_TYPES}
          all="Todos"
          width={140}
        />
        <PickFilter
          label="Origen"
          value={source}
          onChange={rephrase(setSource)}
          options={SOURCE_OPTIONS}
          all="Todos"
          width={170}
        />
      </Stack>

      {isLoading ? (
        <Loading rows={6} />
      ) : days.length === 0 ? (
        <Empty>No hay fichajes en ese periodo.</Empty>
      ) : (
        <Stack sx={{ gap: 2 }}>
          {days.map(([day, events]) => (
            <Box key={day}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  display: 'block',
                  mb: 0.75,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {dateOf(day, { weekday: 'long', year: 'numeric' })}
              </Typography>

              <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 92 }}>Hora</TableCell>
                      <TableCell sx={{ width: 110 }}>Tipo</TableCell>
                      {!employee && <TableCell>Persona</TableCell>}
                      <TableCell align="right">Origen</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {events.map((punch) => (
                      <TableRow
                        key={punch.id}
                        hover
                        sx={{
                          // A voided event stays in the list, struck through:
                          // hiding it would misrepresent the record.
                          ...(punch.is_active === false && {
                            opacity: 0.5,
                            textDecoration: 'line-through',
                          }),
                        }}
                      >
                        <TableCell sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                          {timeOf(punch.timestamp, zone)}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant={punch.punch_type === 'IN' ? 'filled' : 'outlined'}
                            color={punch.punch_type === 'IN' ? 'success' : 'default'}
                            icon={
                              punch.punch_type === 'IN' ? (
                                <ArrowDownwardIcon sx={{ fontSize: 14 }} />
                              ) : (
                                <ArrowUpwardIcon sx={{ fontSize: 14 }} />
                              )
                            }
                            label={punch.punch_type === 'IN' ? 'Entrada' : 'Salida'}
                            sx={{ height: 22, fontSize: '0.72rem' }}
                          />
                        </TableCell>
                        {!employee && (
                          <TableCell>
                            <Typography variant="body2">{punch.employee_name ?? '—'}</Typography>
                          </TableCell>
                        )}
                        <TableCell align="right">
                          <Stack
                            direction="row"
                            sx={{ gap: 1, justifyContent: 'flex-end', alignItems: 'center' }}
                          >
                            <SourceChip source={punch.source} />
                            {punch.is_active !== false && (
                              <Button
                                size="small"
                                sx={{ minWidth: 0, px: 1 }}
                                // Cuál. Cuarenta y siete botones «Corregir»
                                // seguidos no dicen de qué fichaje son, y quien
                                // navega con lector de pantalla oye eso.
                                aria-label={`Corregir el fichaje de ${punch.employee_name} de las ${timeOf(punch.timestamp, zone)}`}
                                onClick={() => setCorrecting({ punch })}
                              >
                                Corregir
                              </Button>
                            )}
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          ))}
        </Stack>
      )}

      <Pager
        count={data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        noun="fichajes"
      />

      <CorrectionDialog
        open={correcting !== null}
        punch={correcting?.punch}
        employee={employee}
        employeeName={employeeName}
        saving={correct.isPending}
        error={error}
        onClose={() => {
          setCorrecting(null)
          setError(null)
        }}
        onSubmit={correct.mutate}
      />
    </>
  )
}
