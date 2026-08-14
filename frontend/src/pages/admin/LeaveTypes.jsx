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
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { getLeaveTypes, seedLeaveTypes, updateLeaveType } from '../../services/api.js'
import { Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import { FilterBar, SearchField } from '../../components/filters.jsx'
import { useAuth } from '../../hooks/useAuth.js'

const UNIDADES = {
  DAYS_CALENDAR: 'días naturales',
  DAYS_WORKING: 'días laborables',
  HOURS: 'horas',
  WEEKS: 'semanas',
}

const PERIODOS = {
  EVENT: 'cada vez',
  DAY: 'al día',
  WEEK: 'a la semana',
  MONTH: 'al mes',
  YEAR: 'al año',
}

/** Lo que se puede cambiar de un permiso, y lo que no.
 *
 *  Se edita **cuánto da**, no de qué artículo sale. El convenio mejora la
 *  cifra ---quince días de matrimonio pueden ser dieciocho--- y esa es la razón
 *  entera de que el catálogo se copie en vez de leerse del marco legal: si se
 *  leyera vivo, corregir una cifra nuestra reescribiría en silencio algo que
 *  alguien negoció.
 *
 *  El artículo y el código no se tocan. El artículo es de la ley y cambiarlo
 *  mandaría a quien lo lea al sitio equivocado; el código es por donde la
 *  siembra reconoce los suyos, y renombrarlo haría que el original volviera
 *  como duplicado.
 */
function LeaveTypeDialog({ open, kind, onClose, onSave, saving, error }) {
  const [form, setForm] = useState(null)

  if (open && kind && (form === null || form.id !== kind.id)) {
    setForm({
      id: kind.id,
      name: kind.name,
      amount: kind.amount ?? '',
      unit: kind.unit ?? 'DAYS_CALENDAR',
      period: kind.period ?? 'EVENT',
      extra_when_travelling: kind.extra_when_travelling ?? '',
      needs_justification: Boolean(kind.needs_justification),
      note: kind.note ?? '',
      is_active: kind.is_active !== false,
    })
  }
  if (!open && form !== null) setForm(null)

  if (!form) return null

  const set = (campo) => (event) => setForm({ ...form, [campo]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSave({
      id: form.id,
      name: form.name,
      // Vacío significa «sin tope», que es lo que dice «el tiempo
      // indispensable»: mandar 0 sería inventarse un límite de cero.
      amount: form.amount === '' ? null : Number(form.amount),
      unit: form.unit,
      period: form.period,
      extra_when_travelling:
        form.extra_when_travelling === '' ? null : Number(form.extra_when_travelling),
      needs_justification: form.needs_justification,
      note: form.note,
      is_active: form.is_active,
    })
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>{kind.name}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          {kind.basis && (
            <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
              {kind.basis}. Lo que dice la ley es el suelo: el convenio puede dar más, nunca menos.
              El artículo no se cambia aquí.
            </Alert>
          )}
          <Stack sx={{ gap: 2, pt: 0.5 }}>
            <TextField fullWidth label="Nombre" value={form.name} onChange={set('name')} required />

            <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap' }}>
              <TextField
                type="number"
                label="Cuánto da"
                value={form.amount}
                onChange={set('amount')}
                helperText="Vacío: el tiempo indispensable, sin tope."
                sx={{ minWidth: 140 }}
              />
              <TextField
                select
                label="Contado en"
                value={form.unit}
                onChange={set('unit')}
                sx={{ minWidth: 170 }}
              >
                {Object.entries(UNIDADES).map(([valor, texto]) => (
                  <MenuItem key={valor} value={valor}>
                    {texto}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label="Cada"
                value={form.period}
                onChange={set('period')}
                sx={{ minWidth: 150 }}
              >
                {Object.entries(PERIODOS).map(([valor, texto]) => (
                  <MenuItem key={valor} value={valor}>
                    {texto}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            <TextField
              type="number"
              label="Días de más si hay desplazamiento"
              value={form.extra_when_travelling}
              onChange={set('extra_when_travelling')}
              helperText="Se guarda como el extra, no como el total: quien no se desplaza tiene el de arriba."
            />

            <FormControlLabel
              control={
                <Switch
                  checked={form.needs_justification}
                  onChange={(event) =>
                    setForm({ ...form, needs_justification: event.target.checked })
                  }
                />
              }
              label="Pide justificante"
            />

            <TextField
              fullWidth
              multiline
              minRows={2}
              label="Nota"
              value={form.note}
              onChange={set('note')}
              helperText="Se ve al pedirlo. Aquí van las condiciones que el convenio añada."
            />

            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                />
              }
              label="Se puede pedir"
            />
            {!form.is_active && (
              <Typography variant="caption" color="text.secondary">
                Deja de ofrecerse en las solicitudes nuevas. Las que ya existen se siguen leyendo:
                un permiso cuyo motivo deja de renderizarse es un registro que perdió algo.
              </Typography>
            )}
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

/** El catálogo de permisos de la empresa, y cómo lo mejora su convenio.
 *
 *  Existía entero ---el modelo, la siembra por país, el endpoint completo, y
 *  hasta `createLeaveType` y `updateLeaveType` exportados en el cliente--- y no
 *  había pantalla: la mejora que un convenio trae solo se podía aplicar por
 *  API. O sea que la decisión de copiar el catálogo en vez de leerlo del marco,
 *  que se tomó justo para permitir esa mejora, no servía para nada.
 */
export default function LeaveTypes() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)
  const [busca, setBusca] = useState('')
  const [error, setError] = useState(null)

  const esAdmin = session?.user?.role === 'ADMIN'

  const { data: tipos = [], isLoading } = useQuery({
    queryKey: ['leave-types', 'todos'],
    // También los retirados: si no, quien quiera volver a ofrecer uno no lo
    // encuentra por ninguna parte.
    queryFn: () => getLeaveTypes({ is_active: undefined }),
  })

  const guardar = useMutation({
    mutationFn: ({ id, ...cambios }) => updateLeaveType(id, cambios),
    onSuccess: () => {
      setEditando(null)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['leave-types'] })
    },
    onError: setError,
  })

  const cargar = useMutation({
    mutationFn: seedLeaveTypes,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-types'] }),
    onError: setError,
  })

  const aguja = busca.trim().toLowerCase()
  const filas = tipos.filter(
    (tipo) =>
      !aguja ||
      tipo.name.toLowerCase().includes(aguja) ||
      (tipo.basis ?? '').toLowerCase().includes(aguja),
  )

  if (isLoading) {
    return (
      <>
        <PageHeader title="Permisos" />
        <Loading rows={6} />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Permisos"
        subtitle="Lo que la empresa concede, y de qué artículo sale. La ley es el suelo: el convenio puede dar más."
        action={
          esAdmin && (
            <Button variant="outlined" disabled={cargar.isPending} onClick={() => cargar.mutate()}>
              Cargar los que falten
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />
      {cargar.isSuccess && (
        <Alert severity="success" variant="outlined" sx={{ mb: 2 }}>
          {cargar.data?.added
            ? `Añadidos ${cargar.data.added}.`
            : 'No faltaba ninguno: no se ha tocado nada.'}
        </Alert>
      )}

      <FilterBar>
        <SearchField value={busca} onChange={setBusca} placeholder="Buscar por nombre o artículo" />
      </FilterBar>

      {filas.length === 0 ? (
        <Empty>
          {tipos.length === 0
            ? 'Esta empresa no tiene permisos configurados, así que nadie puede pedir ninguno.'
            : 'Ningún permiso coincide con esa búsqueda.'}
        </Empty>
      ) : (
        <Stack component="ul" sx={{ gap: 1.5, listStyle: 'none', m: 0, p: 0 }}>
          {filas.map((tipo) => (
            <Paper
              component="li"
              key={tipo.id}
              variant="outlined"
              sx={{ p: 2, opacity: tipo.is_active === false ? 0.55 : 1 }}
            >
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                sx={{ gap: 2, justifyContent: 'space-between', alignItems: { sm: 'center' } }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 600 }}>{tipo.name}</Typography>
                    {tipo.basis && <Chip size="small" variant="outlined" label={tipo.basis} />}
                    {tipo.is_active === false && (
                      <Chip size="small" color="default" label="Retirado" />
                    )}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {tipo.allowance || 'El tiempo indispensable'}
                    {tipo.needs_justification && ' · pide justificante'}
                    {tipo.paid === false && ' · sin sueldo'}
                  </Typography>
                  {tipo.note && (
                    <Typography variant="caption" color="text.secondary">
                      {tipo.note}
                    </Typography>
                  )}
                </Box>
                {esAdmin && (
                  // Con el nombre del permiso dentro: quien navega con lector de
                  // pantalla oye una lista de botones, y treinta y dos
                  // «Cambiar» seguidos no dicen cuál es cuál. De paso deja de
                  // chocar con el «Cambiar entre claro y oscuro» de la cabecera.
                  <Button
                    size="small"
                    aria-label={`Cambiar ${tipo.name}`}
                    onClick={() => setEditando(tipo)}
                  >
                    Cambiar
                  </Button>
                )}
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      <LeaveTypeDialog
        open={Boolean(editando)}
        kind={editando}
        saving={guardar.isPending}
        error={guardar.error}
        onClose={() => setEditando(null)}
        onSave={guardar.mutate}
      />
    </>
  )
}
