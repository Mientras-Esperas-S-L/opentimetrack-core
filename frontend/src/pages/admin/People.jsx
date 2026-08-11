import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import InputAdornment from '@mui/material/InputAdornment'
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
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import SearchIcon from '@mui/icons-material/Search'

import {
  createEmployee,
  deactivateEmployee,
  getDepartments,
  getEmployees,
  updateEmployee,
} from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'

const ROLES = [
  { value: 'EMPLOYEE', label: 'Persona trabajadora' },
  { value: 'MANAGER', label: 'Responsable' },
  { value: 'ADMIN', label: 'Administración' },
]

const roleLabel = (value) => ROLES.find((r) => r.value === value)?.label ?? value

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  employee_id: '',
  role: 'EMPLOYEE',
  department: '',
  annual_leave_days: '',
}

function PersonDialog({ open, person, departments, onClose, onSave, saving, error }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [loaded, setLoaded] = useState(null)

  // Fills the form when a different person is opened, without an effect.
  if (open && loaded !== (person?.id ?? 'new')) {
    setLoaded(person?.id ?? 'new')
    setForm(
      person
        ? {
            first_name: person.first_name ?? '',
            last_name: person.last_name ?? '',
            email: person.email ?? '',
            employee_id: person.employee_id ?? '',
            role: person.role ?? 'EMPLOYEE',
            department: person.department ?? '',
            annual_leave_days: person.annual_leave_days ?? '',
          }
        : EMPTY_FORM,
    )
  }
  if (!open && loaded !== null) setLoaded(null)

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSave({
      ...form,
      department: form.department || null,
      annual_leave_days: form.annual_leave_days === '' ? null : Number(form.annual_leave_days),
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

export default function People() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [editing, setEditing] = useState(undefined) // undefined = closed, null = new
  const [error, setError] = useState(null)

  const { data: people, isLoading } = useQuery({
    queryKey: ['employees', { search, showInactive }],
    queryFn: () =>
      getEmployees({
        search: search || undefined,
        ...(showInactive ? {} : { is_active: true }),
      }),
  })

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
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

  const rows = people ?? []

  return (
    <>
      <PageHeader
        title="Personas"
        subtitle="Quien está de alta puede fichar. Dar de baja no borra nada: sus registros se conservan."
        action={
          <Button variant="contained" startIcon={<PersonAddIcon />} onClick={() => setEditing(null)}>
            Dar de alta
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{ gap: 2, mb: 2, alignItems: { sm: 'center' } }}
      >
        <TextField
          size="small"
          placeholder="Buscar por nombre, correo o número"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
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
              onChange={(event) => setShowInactive(event.target.checked)}
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
                <TableCell align="right">Acciones</TableCell>
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
                  <TableCell align="right">
                    <Stack direction="row" sx={{ gap: 0.5, justifyContent: 'flex-end' }}>
                      <Button size="small" onClick={() => setEditing(person)}>
                        Editar
                      </Button>
                      {person.is_active && (
                        <Button
                          size="small"
                          color="inherit"
                          onClick={() => deactivate.mutate(person.id)}
                        >
                          Dar de baja
                        </Button>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <PersonDialog
        open={editing !== undefined}
        person={editing}
        departments={departments}
        saving={save.isPending}
        error={error}
        onClose={() => {
          setEditing(undefined)
          setError(null)
        }}
        onSave={save.mutate}
      />
    </>
  )
}
