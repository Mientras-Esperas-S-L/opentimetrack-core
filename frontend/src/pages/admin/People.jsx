import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import SearchIcon from '@mui/icons-material/Search'

import {
  createEmployee,
  deactivateEmployee,
  getDepartments,
  getEmployees,
  getWorkplaces,
  inviteEmployee,
  PAGE_SIZE,
  reactivateEmployee,
  updateEmployee,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pager,
} from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'
import { useDebounced } from '../../hooks/useDebounced.js'

const ROLES = [
  { value: 'EMPLOYEE', label: 'Persona trabajadora' },
  { value: 'MANAGER', label: 'Responsable' },
  { value: 'ADMIN', label: 'Administración' },
]

const roleLabel = (value) => ROLES.find((r) => r.value === value)?.label ?? value

/** How the working day is agreed. Three axes, and they are not the same axis.
 *
 *  The form used to have one switch called "jornada parcial", which could not
 *  say twenty-five hours, could not tell a reduced day under art. 37.6 from
 *  part-time work --- the first keeps the right to overtime and the second does
 *  not --- and had no way at all to record somebody with no agreed figure. It
 *  also sent two fields the server stopped accepting, so the regime silently
 *  never got saved.
 */
const REGIMES = [
  { value: 'FULL_TIME', label: 'Jornada completa', hint: 'La de la empresa.' },
  {
    value: 'PART_TIME',
    label: 'Jornada parcial',
    hint: 'Sin horas extraordinarias (art. 12.4.c ET). Las de más son complementarias.',
  },
  {
    value: 'REDUCED',
    label: 'Jornada reducida',
    hint: 'Art. 37.6 ET: guarda legal o cuidados. No es parcial, conserva las horas extra.',
  },
  { value: 'TRAINING', label: 'Contrato formativo', hint: 'Art. 11 ET.' },
  {
    value: 'VARIABLE',
    label: 'Sin cifra pactada',
    hint: 'Horas sueltas, llamamiento. Solo se le aplica el máximo legal.',
  },
]

const PERIODS = [
  { value: 'WEEK', label: 'a la semana' },
  { value: 'MONTH', label: 'al mes' },
  { value: 'YEAR', label: 'al año' },
]

const NIGHT_STATUS = [
  { value: 'AUTO', label: 'Según el cuadrante' },
  { value: 'YES', label: 'Sí' },
  { value: 'NO', label: 'No' },
]

/** Whether the regime has a figure to go with it, which decides three fields. */
const takesHours = (regime) => regime !== 'VARIABLE'
const needsHours = (regime) => regime === 'PART_TIME' || regime === 'TRAINING'

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  employee_id: '',
  role: 'EMPLOYEE',
  department: '',
  workplace: '',
  annual_leave_days: '',
  // Art. 3.b and 3.e of the pending decree, plus the two fields the domain
  // logic reads and nothing could fill: without a date of birth no
  // under-eighteen protection is ever applied, and with nobody marked as a
  // representative the art. 4.b notice can never reach anyone.
  date_of_birth: '',
  regime: 'FULL_TIME',
  contracted_hours: '',
  contracted_period: 'WEEK',
  contract_start: '',
  contract_end: '',
  seasonal: false,
  contracted_schedule: '',
  night_worker: 'AUTO',
  rotating_shifts: false,
  voluntary_night_shift: false,
  default_work_mode: 'ONSITE',
  is_worker_representative: false,
  wants_punch_reminders: true,
}

const fromPerson = (person) => ({
  first_name: person.first_name ?? '',
  last_name: person.last_name ?? '',
  email: person.email ?? '',
  employee_id: person.employee_id ?? '',
  role: person.role ?? 'EMPLOYEE',
  department: person.department ?? '',
  workplace: person.workplace ?? '',
  annual_leave_days: person.annual_leave_days ?? '',
  date_of_birth: person.date_of_birth ?? '',
  regime: person.regime || 'FULL_TIME',
  contracted_hours: person.contracted_hours ?? '',
  contracted_period: person.contracted_period || 'WEEK',
  contract_start: person.contract_start ?? '',
  contract_end: person.contract_end ?? '',
  seasonal: Boolean(person.seasonal),
  contracted_schedule: person.contracted_schedule ?? '',
  night_worker: person.night_worker || 'AUTO',
  rotating_shifts: Boolean(person.rotating_shifts),
  voluntary_night_shift: Boolean(person.voluntary_night_shift),
  default_work_mode: person.default_work_mode || 'ONSITE',
  is_worker_representative: Boolean(person.is_worker_representative),
  wants_punch_reminders: person.wants_punch_reminders !== false,
})

function PersonDialog({ open, person, departments, workplaces, onClose, onSave, saving, error }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [loaded, setLoaded] = useState(null)

  // Fills the form when a different person is opened, without an effect.
  if (open && loaded !== (person?.id ?? 'new')) {
    setLoaded(person?.id ?? 'new')
    setForm(person ? fromPerson(person) : EMPTY_FORM)
  }
  if (!open && loaded !== null) setLoaded(null)

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSave({
      ...form,
      department: form.department || null,
      workplace: form.workplace || null,
      annual_leave_days: form.annual_leave_days === '' ? null : Number(form.annual_leave_days),
      date_of_birth: form.date_of_birth || null,
      contract_start: form.contract_start || null,
      contract_end: form.contract_end || null,
      contracted_schedule: form.contracted_schedule.trim(),
      // Null rather than empty, and always null on a regime that has no agreed
      // figure: the server refuses hours on that one, and sending '' would fail
      // a validation about a field the form never showed.
      contracted_hours:
        takesHours(form.regime) && form.contracted_hours !== ''
          ? Number(form.contracted_hours)
          : null,
    })
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>{person ? 'Editar persona' : 'Dar de alta'}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                autoFocus
                required
                fullWidth
                label="Nombre"
                value={form.first_name}
                onChange={set('first_name')}
              />
              <TextField
                required
                fullWidth
                label="Apellidos"
                value={form.last_name}
                onChange={set('last_name')}
              />
            </Stack>
            <TextField
              required
              fullWidth
              type="email"
              label="Correo"
              value={form.email}
              onChange={set('email')}
              helperText="Con él inicia sesión. Único dentro de la empresa."
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                label="Número de empleado"
                value={form.employee_id}
                onChange={set('employee_id')}
                helperText="Su identificador en vuestros sistemas."
              />
              <TextField select fullWidth label="Perfil" value={form.role} onChange={set('role')}>
                {ROLES.map((role) => (
                  <MenuItem key={role.value} value={role.value}>
                    {role.label}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                select
                fullWidth
                label="Departamento"
                value={form.department}
                onChange={set('department')}
              >
                <MenuItem value="">Sin asignar</MenuItem>
                {departments.map((department) => (
                  <MenuItem key={department.id} value={department.id}>
                    {department.name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                fullWidth
                type="number"
                label="Días de vacaciones"
                value={form.annual_leave_days}
                onChange={set('annual_leave_days')}
                helperText="Vacío = los de la empresa."
              />
            </Stack>

            {/* El centro no es el departamento: uno dice con quién trabaja y el
                otro dónde. Del centro salen los festivos locales, la zona
                horaria de su jornada y el sitio donde una inspección pediría su
                registro. */}
            <TextField
              select
              fullWidth
              label="Centro de trabajo"
              value={form.workplace}
              onChange={set('workplace')}
              helperText={
                workplaces.length === 0
                  ? 'Todavía no hay centros. Se crean en Centros.'
                  : 'Decide sus festivos locales y la zona horaria de su jornada.'
              }
            >
              <MenuItem value="">Sin asignar</MenuItem>
              {workplaces.map((place) => (
                <MenuItem key={place.id} value={place.id}>
                  {place.name}
                  {place.municipality ? ` · ${place.municipality}` : ''}
                  {place.time_zone ? ` · ${place.time_zone}` : ''}
                </MenuItem>
              ))}
            </TextField>

            <Divider textAlign="left" sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Contrato
              </Typography>
            </Divider>

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                type="date"
                label="Fecha de nacimiento"
                value={form.date_of_birth}
                onChange={set('date_of_birth')}
                slotProps={{ inputLabel: { shrink: true } }}
                // Not a nicety: this is the only thing that turns the
                // under-eighteen protections on. Empty means they are not being
                // applied, and somebody should know that rather than assume.
                helperText="Solo para aplicar las protecciones de menores de 18. Sin ella no se aplican."
              />
              <TextField
                select
                fullWidth
                label="Modalidad habitual"
                value={form.default_work_mode}
                onChange={set('default_work_mode')}
                helperText="Cada fichaje puede registrar la otra."
              >
                <MenuItem value="ONSITE">Presencial</MenuItem>
                <MenuItem value="REMOTE">A distancia</MenuItem>
              </TextField>
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                select
                fullWidth
                label="Régimen de jornada"
                value={form.regime}
                onChange={(event) =>
                  setForm({
                    ...form,
                    regime: event.target.value,
                    // Cleared here rather than refused later: the server does
                    // not accept a figure on a regime that has none.
                    contracted_hours: takesHours(event.target.value)
                      ? form.contracted_hours
                      : '',
                  })
                }
                helperText={REGIMES.find((r) => r.value === form.regime)?.hint}
              >
                {REGIMES.map((regime) => (
                  <MenuItem key={regime.value} value={regime.value}>
                    {regime.label}
                  </MenuItem>
                ))}
              </TextField>
              {takesHours(form.regime) && (
                <Stack direction="row" sx={{ gap: 1, width: '100%' }}>
                  <TextField
                    required={needsHours(form.regime)}
                    fullWidth
                    type="number"
                    label="Horas contratadas"
                    value={form.contracted_hours}
                    onChange={set('contracted_hours')}
                    slotProps={{ htmlInput: { min: 0.5, step: 0.5 } }}
                    helperText={
                      needsHours(form.regime)
                        ? 'Art. 3.b: obligatorias en este régimen.'
                        : 'Vacío = la jornada de la empresa.'
                    }
                  />
                  <TextField
                    select
                    label="Período"
                    value={form.contracted_period}
                    onChange={set('contracted_period')}
                    sx={{ minWidth: 130 }}
                  >
                    {PERIODS.map((period) => (
                      <MenuItem key={period.value} value={period.value}>
                        {period.label}
                      </MenuItem>
                    ))}
                  </TextField>
                </Stack>
              )}
            </Stack>

            <TextField
              fullWidth
              label="Horario contratado"
              placeholder="L-V 09:00-17:00"
              value={form.contracted_schedule}
              onChange={set('contracted_schedule')}
              helperText="Va en el informe de Inspección: es contenido obligatorio del registro."
            />

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                type="date"
                label="Inicio del contrato"
                value={form.contract_start}
                onChange={set('contract_start')}
                slotProps={{ inputLabel: { shrink: true } }}
                helperText="Vacío = ya estaba en marcha."
              />
              <TextField
                fullWidth
                type="date"
                label="Fin del contrato"
                value={form.contract_end}
                onChange={set('contract_end')}
                slotProps={{ inputLabel: { shrink: true } }}
                helperText="Vacío = indefinido."
              />
            </Stack>

            <FormControlLabel
              control={
                <Switch
                  checked={form.seasonal}
                  onChange={(event) => setForm({ ...form, seasonal: event.target.checked })}
                />
              }
              label="Fijo discontinuo"
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5 }}>
              Art. 16 ET: el trabajo viene por temporadas. Fuera de ellas no se espera jornada.
            </Typography>

            <Divider textAlign="left" sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Nocturnidad y turnos
              </Typography>
            </Divider>

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                select
                fullWidth
                label="Trabajador nocturno"
                value={form.night_worker}
                onChange={set('night_worker')}
                helperText="Art. 36.1 ET. Es una condición de la persona, no del turno."
              >
                {NIGHT_STATUS.map((status) => (
                  <MenuItem key={status.value} value={status.value}>
                    {status.label}
                  </MenuItem>
                ))}
              </TextField>
              <Stack sx={{ width: '100%', justifyContent: 'center' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={form.rotating_shifts}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          rotating_shifts: event.target.checked,
                          // Volunteering is about the night shift on a rotation.
                          // Off the rotation it means nothing, and leaving it on
                          // would quietly lift the two-week cap.
                          voluntary_night_shift: event.target.checked
                            ? form.voluntary_night_shift
                            : false,
                        })
                      }
                    />
                  }
                  label="Turnos rotativos"
                />
                {form.rotating_shifts && (
                  <FormControlLabel
                    control={
                      <Switch
                        checked={form.voluntary_night_shift}
                        onChange={(event) =>
                          setForm({ ...form, voluntary_night_shift: event.target.checked })
                        }
                      />
                    }
                    label="Se ofreció para las noches"
                  />
                )}
              </Stack>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5 }}>
              Con turnos rotativos, el relevo puede bajar de doce horas de descanso hasta siete
              (art. 19.a RD 1561/1995) y la diferencia se devuelve en cuatro semanas. Sin
              adscripción voluntaria, nadie está más de dos semanas seguidas de noche (art. 36.3
              ET).
            </Typography>

            <Divider sx={{ mt: 1 }} />

            <FormControlLabel
              control={
                <Switch
                  checked={form.is_worker_representative}
                  onChange={(event) =>
                    setForm({ ...form, is_worker_representative: event.target.checked })
                  }
                />
              }
              label="Representante legal de las personas trabajadoras"
            />

            <FormControlLabel
              control={
                <Switch
                  checked={form.wants_punch_reminders}
                  onChange={(event) =>
                    setForm({ ...form, wants_punch_reminders: event.target.checked })
                  }
                />
              }
              label="Recordatorios de fichaje"
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5 }}>
              Aviso si empieza el turno y no ha fichado, o si deja la jornada abierta. Empuja al
              fichaje real, nunca lo registra. Cada persona puede desactivarlo en su perfil.
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5 }}>
              Se le informa cuando alguien discrepa de un cambio en su registro (art. 4.b) y puede
              consultar el registro de la empresa (art. 6.2).
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            Guardar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** The row's actions: the common one visible, the rest behind the menu.
 *
 *  Three text buttons side by side wrapped onto two lines on a laptop and made
 *  every row taller than the name it was about. Editing is what somebody comes
 *  here to do; sending an access link and deactivating are occasional, and
 *  putting them a click away also stops "Dar de baja" sitting under the cursor
 *  next to "Editar".
 */
function RowActions({ person, busy, onEdit, onInvite, onReactivate, onDeactivate }) {
  const [anchor, setAnchor] = useState(null)
  const close = () => setAnchor(null)
  const pick = (run) => () => {
    close()
    run()
  }

  return (
    <Stack direction="row" sx={{ gap: 0.5, justifyContent: 'flex-end', alignItems: 'center' }}>
      {person.is_active ? (
        <Button size="small" onClick={onEdit}>
          Editar
        </Button>
      ) : (
        <Button size="small" onClick={onReactivate}>
          Volver a dar de alta
        </Button>
      )}

      <IconButton
        size="small"
        aria-label={`Más acciones para ${person.first_name} ${person.last_name}`.trim()}
        onClick={(event) => setAnchor(event.currentTarget)}
      >
        <MoreVertIcon fontSize="small" />
      </IconButton>

      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        {!person.is_active && <MenuItem onClick={pick(onEdit)}>Editar</MenuItem>}
        {/* Their account exists but they may never have had a way into it: the
            link expires, and accounts created before invitations existed never
            got one. Pointless for a federated account, whose credentials belong
            to the identity provider. */}
        {person.is_active && !person.is_federated && (
          <MenuItem onClick={pick(onInvite)} disabled={busy}>
            Enviar enlace de acceso
          </MenuItem>
        )}
        {person.is_active && <MenuItem onClick={pick(onDeactivate)}>Dar de baja</MenuItem>}
      </Menu>
    </Stack>
  )
}

export default function People() {
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [editing, setEditing] = useState(undefined) // undefined = closed, null = new
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(null) // address the last link went to
  const [confirming, setConfirming] = useState(null)
  const [page, setPage] = useState(1)

  // The box updates on every keystroke --- it has to, or typing feels broken ---
  // but the request waits for a pause.
  const asked = useDebounced(search)

  const { data, isLoading } = useQuery({
    queryKey: ['employees', { asked, showInactive, page }],
    queryFn: () =>
      getEmployees({
        search: asked || undefined,
        ...(showInactive ? {} : { is_active: true }),
        page,
      }),
    placeholderData: (previous) => previous,
  })

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
  })
  const { data: workplaces = [] } = useQuery({
    queryKey: ['workplaces'],
    queryFn: () => getWorkplaces(),
  })

  const save = useMutation({
    mutationFn: (payload) =>
      editing ? updateEmployee(editing.id, payload) : createEmployee(payload),
    onSuccess: () => {
      setEditing(undefined)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: setError,
  })

  const deactivate = useMutation({
    mutationFn: deactivateEmployee,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
    onError: setError,
  })

  const reactivate = useMutation({
    mutationFn: reactivateEmployee,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
    onError: setError,
  })

  const invite = useMutation({
    mutationFn: inviteEmployee,
    onSuccess: (data) => setSent(data.sent_to),
    onError: setError,
  })

  const rows = data?.rows ?? []

  return (
    <>
      <PageHeader
        title="Personas"
        subtitle="Quien está de alta puede fichar. Dar de baja no borra nada: sus registros se conservan."
        action={
          isAdmin && (
            <Button
              variant="contained"
              startIcon={<PersonAddIcon />}
              onClick={() => setEditing(null)}
            >
              Dar de alta
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {sent && (
        <Alert severity="success" onClose={() => setSent(null)} sx={{ mb: 2 }}>
          Enlace enviado a <strong>{sent}</strong>. Caduca en 24 horas.
        </Alert>
      )}

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{ gap: 2, mb: 2, alignItems: { sm: 'center' } }}
      >
        <TextField
          size="small"
          placeholder="Buscar por nombre, correo o número"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
          sx={{ flexGrow: 1, maxWidth: 380 }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={showInactive}
              onChange={(event) => {
                setShowInactive(event.target.checked)
                setPage(1)
              }}
            />
          }
          label="Ver también las bajas"
        />
      </Stack>

      {isLoading ? (
        <Loading rows={5} />
      ) : rows.length === 0 ? (
        <Empty>
          {search ? 'Nadie coincide con esa búsqueda.' : 'Todavía no hay nadie dado de alta.'}
        </Empty>
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nombre</TableCell>
                <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>Correo</TableCell>
                <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Nº</TableCell>
                <TableCell>Perfil</TableCell>
                {isAdmin && <TableCell align="right">Acciones</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((person) => (
                <TableRow key={person.id} hover sx={{ opacity: person.is_active ? 1 : 0.55 }}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {`${person.first_name} ${person.last_name}`.trim() || person.email}
                    </Typography>
                    {!person.is_active && (
                      <Chip size="small" label="De baja" sx={{ mt: 0.5, height: 20 }} />
                    )}
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                    <Typography variant="body2" color="text.secondary">
                      {person.email}
                    </Typography>
                  </TableCell>
                  <TableCell
                    sx={{
                      display: { xs: 'none', sm: 'table-cell' },
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {person.employee_id || '—'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={roleLabel(person.role)}
                      color={person.role === 'EMPLOYEE' ? 'default' : 'primary'}
                    />
                  </TableCell>
                  {/* Only administrators may write here. A manager reaches this
                      page --- the guard lets them --- so without this they would
                      see buttons that always answer 403. */}
                  {isAdmin && (
                    <TableCell align="right">
                      <RowActions
                        person={person}
                        busy={invite.isPending}
                        onEdit={() => setEditing(person)}
                        onInvite={() => invite.mutate(person.id)}
                        onReactivate={() => reactivate.mutate(person.id)}
                        onDeactivate={() =>
                          setConfirming({
                            title: 'Dar de baja',
                            body:
                              `${person.first_name} ${person.last_name}`.trim() || person.email,
                            detail:
                              'Deja de poder fichar y de entrar. Sus registros se conservan y puede volver a darse de alta cuando haga falta.',
                            verb: 'Dar de baja',
                            run: () => deactivate.mutate(person.id),
                          })
                        }
                      />
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Pager
        count={data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        noun="personas"
      />

      <PersonDialog
        open={editing !== undefined}
        person={editing}
        departments={departments}
        workplaces={workplaces}
        saving={save.isPending}
        error={error}
        onClose={() => {
          setEditing(undefined)
          setError(null)
        }}
        onSave={save.mutate}
      />

      <ConfirmDialog
        request={confirming}
        busy={deactivate.isPending}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
