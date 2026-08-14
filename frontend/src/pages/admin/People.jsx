import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
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

import { FilterBar, SearchField } from '../../components/filters.jsx'

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
import { SelectionBar } from '../../components/selection.jsx'
import { useAuth } from '../../hooks/useAuth.js'
import { useDebounced } from '../../hooks/useDebounced.js'
import { useSelection } from '../../hooks/useSelection.js'

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

/** Los idiomas que de verdad existen.
 *
 *  Cinco, y cada uno con su catálogo. Lo que no está traducido cae al
 *  castellano, no al inglés: `LANGUAGE_CODE` es `es` y Django encadena por ahí.
 *  Por eso un catálogo a medias es utilizable ---catalán donde llega a las
 *  personas, castellano en las etiquetas internas--- y no una mezcla con inglés.
 *
 *  Euskera, francés, portugués y alemán siguen fuera. El euskera llegó a
 *  tener catálogo y se retiró: iba incompleto ---faltaban los párrafos
 *  largos de derecho laboral--- y medio idioma en un producto que explica
 *  obligaciones legales no es medio bueno, es confuso.
 */
const IDIOMAS = [
  ['es', 'Español'],
  ['ca', 'Català'],
  ['gl', 'Galego'],
  ['en', 'Inglés'],
]

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  employee_id: '',
  role: 'EMPLOYEE',
  department: '',
  workplace: '',
  annual_leave_days: '',
  locale: '',
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
  locale: person.locale ?? '',
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
              {/* El idioma de esta persona. Los ajustes de la empresa decían
                  «cada persona puede usar otro distinto» y no había dónde
                  elegirlo: el campo existía en el modelo y en la API, y ninguna
                  pantalla lo ofrecía. En esto se nota, además, fuera de la
                  pantalla: los recordatorios y los avisos por correo salen en el
                  idioma de quien los recibe. */}
              <TextField
                select
                fullWidth
                label="Idioma"
                value={form.locale ?? ''}
                onChange={set('locale')}
                helperText="Vacío = el de la empresa."
              >
                <MenuItem value="">El de la empresa</MenuItem>
                {IDIOMAS.map(([codigo, nombre]) => (
                  <MenuItem key={codigo} value={codigo}>
                    {nombre}
                  </MenuItem>
                ))}
              </TextField>
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
                    contracted_hours: takesHours(event.target.value) ? form.contracted_hours : '',
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
  // Una sola vez: se usa en cuatro rótulos accesibles de esta fila y estaba
  // escrito a mano en tres sitios distintos.
  const quien = `${person.first_name} ${person.last_name}`.trim() || person.email
  const [anchor, setAnchor] = useState(null)
  const close = () => setAnchor(null)
  const pick = (run) => () => {
    close()
    run()
  }

  return (
    <Stack direction="row" sx={{ gap: 0.5, justifyContent: 'flex-end', alignItems: 'center' }}>
      {person.is_active ? (
        // Con el nombre dentro del rótulo accesible: una lista de diecinueve
        // botones «Editar» no le dice a nadie cuál es cuál, y quien navega con
        // lector de pantalla oye exactamente eso.
        <Button size="small" aria-label={`Editar ${quien}`} onClick={onEdit}>
          Editar
        </Button>
      ) : (
        <Button size="small" aria-label={`Volver a dar de alta a ${quien}`} onClick={onReactivate}>
          Volver a dar de alta
        </Button>
      )}

      <IconButton
        size="small"
        aria-label={`Más acciones para ${quien}`}
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
  // Turnos que la última baja ha dejado sin nadie. Se enseña aquí y no solo en
  // el cuadrante porque quien acaba de dar la baja es quien tiene que ir a
  // rehacerlo, y si se entera tres días después ya son tres días de ausencias
  // sin justificar.
  const [colgando, setColgando] = useState(0)
  const [page, setPage] = useState(1)
  const [dept, setDept] = useState('')
  const [place, setPlace] = useState('')
  const [role, setRole] = useState('')
  const [enCurso, setEnCurso] = useState(null)
  //: A dónde se está moviendo lo marcado: `{ que: 'department' | 'workplace',
  //: ancla }`. Un menú y no un desplegable dentro de la barra, porque la barra
  //: flota abajo y un desplegable ahí abre su lista fuera de la pantalla.
  const [moviendo, setMoviendo] = useState(null)

  // The box updates on every keystroke --- it has to, or typing feels broken ---
  // but the request waits for a pause.
  const asked = useDebounced(search)

  const { data, isLoading } = useQuery({
    queryKey: ['employees', { asked, showInactive, page, dept, place, role }],
    queryFn: () =>
      getEmployees({
        search: asked || undefined,
        ...(showInactive ? {} : { is_active: true }),
        // «ninguno» no es un identificador: es la pregunta «¿quién está sin
        // departamento?», que con `?department=` vacío no se puede formular
        // porque un parámetro vacío es igual que no mandarlo.
        ...(dept === 'ninguno' ? { no_department: true } : dept ? { department: dept } : {}),
        ...(place ? { workplace: place } : {}),
        ...(role ? { role } : {}),
        page,
      }),
    placeholderData: (previous) => previous,
  })

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    // Envuelta, no pasada pelada: React Query llama a `queryFn` con su propio
    // contexto ---`{ client, queryKey, signal }`--- y `getDepartments` toma ese
    // objeto como parámetros de consulta. La petición salía siendo
    // `/departments/?client=[object Object]&queryKey[]=departments&signal=...`.
    //
    // Hoy no rompe nada porque DRF ignora lo que no conoce, y por eso llevaba
    // ahí sin que nadie lo viera. Rompería el día que exista un filtro que se
    // llame como una de esas tres claves.
    queryFn: () => getDepartments(),
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
    onSuccess: (respuesta) => {
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      // El cuadrante también: sus turnos futuros acaban de quedarse sin nadie.
      queryClient.invalidateQueries({ queryKey: ['coverage'] })
      setColgando(respuesta?.future_shifts || 0)
    },
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
  // Solo quien está de alta: las tres acciones de la barra no le aplican a
  // quien ya está de baja, y una casilla que no hace nada es peor que ninguna.
  const visibles = rows.filter((person) => person.is_active)
  // El mismo mecanismo que «Por decidir». Empecé escribiendo uno a medida aquí
  // y era el mismo: poda lo que desaparece de la lista al leer, y «todo» es lo
  // que se está viendo, no lo que hay en la empresa.
  const pick = useSelection(visibles)
  const marcadasAqui = visibles.filter((person) => pick.isSelected(person))

  /** Aplica el mismo cambio a cada persona marcada, una petición por persona.
   *
   *  Una a una y no un endpoint de lote, a propósito. El camino individual ya
   *  comprueba permisos y **deja su apunte en el registro con nombre y
   *  apellidos**, y cambiar de departamento decide quién puede leer el
   *  registro de quién: una reorganización de veinte personas no puede
   *  aparecer como un solo apunte sin nombres. Un endpoint de lote tendría que
   *  reproducir las dos cosas, y sería otro sitio donde equivocarse.
   *
   *  El precio es que puede fallar a medias, así que se cuenta y se dice: «12
   *  de 15», y las tres que no, con su motivo.
   */
  const enLote = async (etiqueta, cambio) => {
    const gente = marcadasAqui
    setEnCurso({ etiqueta, hechas: 0, total: gente.length })
    const fallos = []

    for (const [indice, person] of gente.entries()) {
      try {
        await updateEmployee(person.id, cambio)
      } catch (fallo) {
        fallos.push(`${person.first_name} ${person.last_name}`.trim() || person.email)
        void fallo
      }
      setEnCurso({ etiqueta, hechas: indice + 1, total: gente.length })
    }

    setEnCurso(null)
    pick.clear()
    queryClient.invalidateQueries({ queryKey: ['employees'] })
    queryClient.invalidateQueries({ queryKey: ['departments'] })
    queryClient.invalidateQueries({ queryKey: ['overview'] })

    if (fallos.length) {
      setError({
        message: `${gente.length - fallos.length} de ${gente.length}. No se pudo con: ${fallos.join(', ')}.`,
      })
    }
  }

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

      {colgando > 0 && (
        <Alert
          severity="warning"
          variant="outlined"
          sx={{ mb: 2 }}
          onClose={() => setColgando(0)}
          action={
            <Button size="small" component={RouterLink} to="/panel/cuadrante">
              Ir al cuadrante
            </Button>
          }
        >
          Le quedaban {colgando} {colgando === 1 ? 'turno asignado' : 'turnos asignados'} después de
          hoy. No se han borrado: hay que ponerles a otra persona, o esos días saldrán como
          ausencia sin justificar.
        </Alert>
      )}

      {sent && (
        <Alert severity="success" onClose={() => setSent(null)} sx={{ mb: 2 }}>
          Enlace enviado a <strong>{sent}</strong>. Caduca en 24 horas.
        </Alert>
      )}

      {/* La compartida, y por la misma razón que el buscador: esta pantalla se
          fabricaba su propia fila y le faltaba el `flexWrap`. Entre 600 y 1000
          px de ancho ---un portátil al 150 % de zoom, una tableta pequeña, media
          ventana--- la fila pasaba a horizontal y se salía 60 px por la derecha,
          con el interruptor de las bajas fuera de la pantalla. */}
      <FilterBar>
        {/* El compartido, no uno propio. Esta pantalla se fabricaba el suyo y
            por eso se quedó fuera cuando el buscador común recibió su nombre
            accesible: se seguía oyendo como «cuadro de texto». De paso hereda
            el botón de vaciar, que aquí tampoco había. */}
        <SearchField
          value={search}
          onChange={(texto) => {
            setSearch(texto)
            setPage(1)
          }}
          placeholder="Buscar por nombre, correo o número"
          width={380}
        />
        {/* Los tres que separan de verdad a la plantilla. «Sin departamento»
            es su propia opción y no un hueco en blanco: es la primera pregunta
            de cualquier reorganización ---quién se ha quedado suelto--- y sin
            ella hay que mirarlo a ojo fila por fila. */}
        <TextField
          select
          size="small"
          label="Departamento"
          value={dept}
          onChange={(event) => {
            setDept(event.target.value)
            setPage(1)
          }}
          sx={{ minWidth: 190 }}
        >
          <MenuItem value="">Todos</MenuItem>
          <MenuItem value="ninguno">Sin departamento</MenuItem>
          {departments.map((department) => (
            <MenuItem key={department.id} value={department.id}>
              {department.name}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          select
          size="small"
          label="Centro"
          value={place}
          onChange={(event) => {
            setPlace(event.target.value)
            setPage(1)
          }}
          sx={{ minWidth: 170 }}
        >
          <MenuItem value="">Todos</MenuItem>
          {workplaces.map((workplace) => (
            <MenuItem key={workplace.id} value={workplace.id}>
              {workplace.name}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          select
          size="small"
          label="Perfil"
          value={role}
          onChange={(event) => {
            setRole(event.target.value)
            setPage(1)
          }}
          sx={{ minWidth: 150 }}
        >
          <MenuItem value="">Todos</MenuItem>
          <MenuItem value="EMPLOYEE">Operario</MenuItem>
          <MenuItem value="MANAGER">Responsable</MenuItem>
          <MenuItem value="ADMIN">Administración</MenuItem>
        </TextField>

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
      </FilterBar>

      {isAdmin && (
        <SelectionBar
          selection={pick}
          noun="personas"
          busy={Boolean(enCurso)}
          actions={[
            {
              label: 'Mover a departamento…',
              onClick: (event) => setMoviendo({ que: 'department', ancla: event.currentTarget }),
            },
            {
              label: 'Cambiar de centro…',
              variant: 'outlined',
              onClick: (event) => setMoviendo({ que: 'workplace', ancla: event.currentTarget }),
            },
            {
              // Lo irreversible pregunta, y la pregunta dice el número.
              // «¿Estás seguro?» no es una pregunta: no dice a cuánta gente
              // afecta.
              label: 'Dar de baja',
              variant: 'text',
              color: 'inherit',
              onClick: () =>
                setConfirming({
                  title:
                    marcadasAqui.length === 1
                      ? 'Dar de baja'
                      : `Dar de baja a ${marcadasAqui.length} personas`,
                  body: marcadasAqui
                    .map((p) => `${p.first_name} ${p.last_name}`.trim() || p.email)
                    .join(', '),
                  detail:
                    'Dejan de poder fichar. No se borra nada: sus registros se conservan los años que diga la empresa, y volver a darles de alta es inmediato.',
                  verb: 'Dar de baja',
                  run: () => enLote('Dando de baja', { is_active: false }),
                }),
            },
          ]}
        />
      )}

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
                {isAdmin && (
                  <TableCell padding="checkbox">
                    {/* «Todas» son las de esta página, no las de la empresa.
                        Un seleccionar-todo que abarcara páginas sin enseñarlas
                        actuaría sobre gente que nadie ha visto. */}
                    <Checkbox
                      size="small"
                      slotProps={{
                        input: { 'aria-label': 'Seleccionar todas las de esta página' },
                      }}
                      checked={pick.allSelected}
                      indeterminate={pick.someSelected}
                      onChange={pick.toggleAll}
                    />
                  </TableCell>
                )}
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
                  {isAdmin && (
                    <TableCell padding="checkbox">
                      {/* Quien ya está de baja no se marca: las tres acciones
                          de la barra no le aplican, y una casilla que no hace
                          nada es peor que ninguna. */}
                      {person.is_active && (
                        <Checkbox
                          size="small"
                          slotProps={{
                            input: {
                              'aria-label': `Seleccionar a ${`${person.first_name} ${person.last_name}`.trim() || person.email}`,
                            },
                          }}
                          checked={pick.isSelected(person)}
                          onChange={() => pick.toggle(person)}
                        />
                      )}
                    </TableCell>
                  )}
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
                            body: `${person.first_name} ${person.last_name}`.trim() || person.email,
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

      {/* Adónde van los marcados. El mismo menú sirve para departamento y
          para centro: lo único que cambia es la lista y qué campo se manda. */}
      <Menu
        anchorEl={moviendo?.ancla ?? null}
        open={Boolean(moviendo)}
        onClose={() => setMoviendo(null)}
      >
        <MenuItem
          onClick={() => {
            enLote('Moviendo', { [moviendo.que]: null })
            setMoviendo(null)
          }}
        >
          {moviendo?.que === 'workplace' ? 'Sin centro' : 'Sin departamento'}
        </MenuItem>
        {(moviendo?.que === 'workplace' ? workplaces : departments).map((destino) => (
          <MenuItem
            key={destino.id}
            onClick={() => {
              enLote('Moviendo', { [moviendo.que]: destino.id })
              setMoviendo(null)
            }}
          >
            {destino.name}
          </MenuItem>
        ))}
      </Menu>

      <ConfirmDialog
        request={confirming}
        busy={deactivate.isPending}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
