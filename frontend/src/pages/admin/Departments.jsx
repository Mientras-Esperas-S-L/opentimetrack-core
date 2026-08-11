import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'

import {
  createDepartment,
  deleteDepartment,
  getDepartments,
  updateDepartment,
} from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

function DepartmentDialog({ open, department, onClose, onSave, saving, error }) {
  const [form, setForm] = useState({ name: '', description: '' })
  const [loaded, setLoaded] = useState(null)

  if (open && loaded !== (department?.id ?? 'new')) {
    setLoaded(department?.id ?? 'new')
    setForm({ name: department?.name ?? '', description: department?.description ?? '' })
  }
  if (!open && loaded !== null) setLoaded(null)

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSave(form)
        }}
      >
        <DialogTitle>{department ? 'Editar departamento' : 'Nuevo departamento'}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              autoFocus
              required
              fullWidth
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              fullWidth
              multiline
              minRows={2}
              label="Descripción (opcional)"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
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

export default function Departments() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'

  const [editing, setEditing] = useState(undefined)
  const [error, setError] = useState(null)

  const { data: departments, isLoading } = useQuery({
    queryKey: ['departments'],
    queryFn: () => getDepartments(),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['departments'] })
    queryClient.invalidateQueries({ queryKey: ['employees'] })
  }

  const save = useMutation({
    mutationFn: (payload) =>
      editing ? updateDepartment(editing.id, payload) : createDepartment(payload),
    onSuccess: () => {
      setEditing(undefined)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const remove = useMutation({
    mutationFn: deleteDepartment,
    onSuccess: refresh,
    onError: setError,
  })

  const rows = departments ?? []

  return (
    <>
      <PageHeader
        title="Departamentos"
        subtitle="Agrupan a las personas y sirven para filtrar informes. Una persona puede no tener ninguno."
        action={
          isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing(null)}>
              Nuevo
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>
          Todavía no hay departamentos. {isAdmin ? 'Crea el primero.' : 'Puede crearlos la administración.'}
        </Empty>
      ) : (
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
          {rows.map((department) => (
            <Paper key={department.id} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 600 }}>{department.name}</Typography>
                  {department.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                      {department.description}
                    </Typography>
                  )}
                  <Chip
                    size="small"
                    variant="outlined"
                    sx={{ mt: 1 }}
                    label={
                      department.people_count === 1
                        ? '1 persona'
                        : `${department.people_count} personas`
                    }
                  />
                </Box>

                {isAdmin && (
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button size="small" onClick={() => setEditing(department)}>
                      Editar
                    </Button>
                    {/* Only when empty. Removing one that still has people would
                        leave them unassigned without saying so. */}
                    {department.people_count === 0 && (
                      <Button
                        size="small"
                        color="inherit"
                        onClick={() => remove.mutate(department.id)}
                        disabled={remove.isPending}
                      >
                        Eliminar
                      </Button>
                    )}
                  </Stack>
                )}
              </Stack>
            </Paper>
          ))}
        </Box>
      )}

      <DepartmentDialog
        open={editing !== undefined}
        department={editing}
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
