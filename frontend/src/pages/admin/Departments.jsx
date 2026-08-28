import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { plural } from '../../components/format.js'
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
import { ConfirmDialog, Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import EmployeePicker from '../../components/EmployeePicker.jsx'
import { useAuth } from '../../hooks/useAuth.js'

function DepartmentDialog({ open, department, onClose, onSave, saving, error }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({ name: '', description: '', managers: [], members: [] })
  const [loaded, setLoaded] = useState(null)

  if (open && loaded !== (department?.id ?? 'new')) {
    setLoaded(department?.id ?? 'new')
    setForm({
      name: department?.name ?? '',
      description: department?.description ?? '',
      managers: department?.managers ?? [],
      members: department?.members ?? [],
    })
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
        <DialogTitle>{department ? t('Editar departamento') : t('Nuevo departamento')}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              autoFocus
              required
              fullWidth
              label={t('Nombre')}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              fullWidth
              multiline
              minRows={2}
              label={t('Descripción (opcional)')}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            {/* Quién responde por él, que es lo que decide quién puede leer el
                registro de quién. No es «el responsable que está aquí dentro»:
                alguien de oficina puede llevar perfectamente la brigada de
                jardinería, y leerlo de la pertenencia le daría los registros de
                oficina en vez de los que le tocan. */}
            <EmployeePicker
              multiple
              onlyManagers
              label={t('Quién lo lleva')}
              value={form.managers}
              onChange={(ids) => setForm({ ...form, managers: ids })}
              // Los nombres que ya tenemos, para las fichas de quien no esté en
              // la primera página de la lista. `manager_names` viene en el
              // mismo orden que `managers`: el serializador construye los dos
              // recorriendo la misma relación.
              knownNames={Object.fromEntries(
                (department?.managers ?? []).map((id, index) => [
                  id,
                  department?.manager_names?.[index] ?? '',
                ]),
              )}
              helperText={t(
                'Responsables que pueden leer y resolver por su gente. Sin nadie aquí, todos los responsables de la empresa ven a todo el mundo.',
              )}
            />

            {/* Quién está dentro. Antes esto no se podía hacer aquí: los
                miembros se asignaban desde la ficha de cada persona, así que
                componer un departamento de quince eran quince diálogos --- en
                la pantalla que se llama «Departamentos».

                Es una lista completa, no un «añadir»: quien se quite de aquí
                se queda sin departamento, que es un estado normal. Y cada
                cambio se apunta persona a persona en el registro, porque
                cambiar de departamento decide quién puede leer el registro de
                quién. */}
            <EmployeePicker
              multiple
              label={t('Quién está dentro')}
              value={form.members}
              onChange={(ids) => setForm({ ...form, members: ids })}
              knownNames={Object.fromEntries(
                (department?.members ?? []).map((id, index) => [
                  id,
                  department?.member_names?.[index] ?? '',
                ]),
              )}
              helperText={t(
                'Las personas del departamento. Quitar a alguien de aquí lo deja sin departamento, no lo da de baja.',
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            {t('Cancelar')}
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            {t('Guardar')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default function Departments() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'

  const [editing, setEditing] = useState(undefined)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(null)

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
        title={t('Departamentos')}
        subtitle={t(
          'Agrupan a las personas y sirven para filtrar informes. Una persona puede no tener ninguno.',
        )}
        action={
          isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing(null)}>
              {t('Nuevo')}
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>
          {t('Todavía no hay departamentos.')}{' '}
          {isAdmin ? t('Crea el primero.') : t('Puede crearlos la administración.')}
        </Empty>
      ) : (
        <Box
          component="ul"
          sx={{
            display: 'grid',
            gap: 1.5,
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            listStyle: 'none',
            m: 0,
            p: 0,
          }}
        >
          {rows.map((department) => (
            <Paper component="li" key={department.id} variant="outlined" sx={{ p: 2 }}>
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
                    label={`${department.people_count} ${plural(
                      department.people_count,
                      t('persona'),
                      t('personas'),
                    )}`}
                  />
                  {department.manager_names?.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      {t('Lo lleva {{quienes}}', {
                        quienes: department.manager_names.join(', '),
                      })}
                    </Typography>
                  )}
                </Box>

                {isAdmin && (
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button
                      size="small"
                      aria-label={t('Editar {{cual}}', { cual: department.name })}
                      onClick={() => setEditing(department)}
                    >
                      {t('Editar')}
                    </Button>
                    {/* Vacío de gente **y** sin nadie al mando.

                        `people_count` cuenta quién está dentro, y eso no es lo
                        único que cuelga: quien responde del departamento es la
                        otra población. Ofreciendo el botón solo por lo primero,
                        la pantalla proponía un borrado que el servidor rechaza
                        ---409 `department_has_managers`--- y lo hacía con un
                        texto que prometía que no afectaba a nadie.

                        Retirar el departamento de quien lo dirige la deja «al
                        mando de nada», y eso **amplía** lo que puede leer a
                        toda la empresa. Por eso se mueve primero a los
                        responsables, y por eso aquí no se ofrece. */}
                    {department.people_count === 0 && (department.managers ?? []).length === 0 && (
                      <Button
                        size="small"
                        color="inherit"
                        // Cuál. Siete departamentos seguidos daban siete botones
                        // «Eliminar» que sonaban igual con lector de pantalla.
                        aria-label={t('Eliminar el departamento {{cual}}', {
                          cual: department.name,
                        })}
                        onClick={() =>
                          setConfirming({
                            title: t('Eliminar departamento'),
                            body: department.name,
                            detail: t(
                              'No tiene a nadie asignado ni nadie que responda de él, así que no afecta a ninguna persona. No se puede deshacer.',
                            ),
                            verb: t('Eliminar'),
                            run: () => remove.mutate(department.id),
                          })
                        }
                        disabled={remove.isPending}
                      >
                        {t('Eliminar')}
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
      <ConfirmDialog
        request={confirming}
        busy={remove.isPending}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
