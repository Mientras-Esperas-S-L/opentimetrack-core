import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { getCompany, updateCompany } from '../../services/api.js'
import { ErrorNote, Loading, PageHeader, Panel } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

/** Spain spans two, and both are in daily use. The rest of the list is there
 *  because the product is not Spain-only, even if the rules currently are. */
const ZONES = [
  'Europe/Madrid',
  'Atlantic/Canary',
  'Europe/Lisbon',
  'Europe/Paris',
  'Europe/London',
  'America/Mexico_City',
  'America/Bogota',
  'America/Argentina/Buenos_Aires',
  'UTC',
]

const LANGUAGES = [
  ['es', 'Español'],
  ['en', 'Inglés'],
  ['ca', 'Catalán'],
  ['gl', 'Gallego'],
  ['eu', 'Euskera'],
  ['fr', 'Francés'],
  ['pt', 'Portugués'],
  ['de', 'Alemán'],
]

const MONTHS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

export default function Settings() {
  const queryClient = useQueryClient()
  const { session, setSession } = useAuth()
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  const { data: company, isLoading } = useQuery({ queryKey: ['company'], queryFn: getCompany })

  // Fill the form once the settings arrive, without an effect.
  if (company && form === null) setForm(company)

  const save = useMutation({
    mutationFn: updateCompany,
    onSuccess: (data) => {
      setError(null)
      setSaved(true)
      setForm(data)
      queryClient.invalidateQueries({ queryKey: ['company'] })
      // The shell shows the company name and every screen formats times in its
      // zone, so the open session has to learn about the change too.
      if (session) setSession({ ...session, tenant: { ...session.tenant, ...data } })
    },
    onError: (failure) => {
      setSaved(false)
      setError(failure)
    },
  })

  if (isLoading || !form) {
    return (
      <>
        <PageHeader title="Ajustes de la empresa" />
        <Loading rows={4} />
      </>
    )
  }

  const set = (field) => (event) => {
    setSaved(false)
    setForm({ ...form, [field]: event.target.value })
  }

  const submit = (event) => {
    event.preventDefault()
    // The server refuses both anyway; dropping them here keeps the request
    // honest about what it is asking to change.
    const editable = { ...form }
    delete editable.id
    delete editable.tax_id
    save.mutate(editable)
  }

  return (
    <form onSubmit={submit}>
      <PageHeader
        title="Ajustes de la empresa"
        subtitle={`${form.name} · ${form.tax_id}`}
        action={
          <Button type="submit" variant="contained" disabled={save.isPending}>
            Guardar cambios
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSaved(false)}>
          Ajustes guardados.
        </Alert>
      )}

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
        <Panel title="Identificación">
          <Stack sx={{ gap: 2 }}>
            <TextField fullWidth label="Razón social" value={form.name} onChange={set('name')} />
            <TextField
              fullWidth
              disabled
              label="CIF/NIF"
              value={form.tax_id}
              helperText="No se puede cambiar: identifica a la empresa en cada informe ya emitido."
            />
          </Stack>
        </Panel>

        <Panel
          title="Zona horaria e idioma"
          hint="Las horas se guardan siempre en UTC. La zona solo decide cómo se muestran."
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              select
              fullWidth
              label="Zona horaria"
              value={form.time_zone}
              onChange={set('time_zone')}
            >
              {ZONES.map((zone) => (
                <MenuItem key={zone} value={zone}>
                  {zone}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              label="Idioma"
              value={form.language}
              onChange={set('language')}
              helperText="Cada persona puede usar otro distinto."
            >
              {LANGUAGES.map(([code, label]) => (
                <MenuItem key={code} value={code}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </Panel>

        <Panel
          title="Vacaciones"
          hint="Estos valores salen del convenio. El sistema no los conoce: los aplica."
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="number"
              label="Días al año"
              value={form.annual_leave_days}
              onChange={set('annual_leave_days')}
              helperText="Días laborables por periodo. El art. 38 ET fija un mínimo de 30 naturales."
            />
            <TextField
              select
              fullWidth
              label="El periodo de cómputo empieza en"
              value={form.leave_year_start_month}
              onChange={set('leave_year_start_month')}
              helperText="Enero = año natural. El convenio puede fijar otro periodo."
            >
              {MONTHS.map((month, index) => (
                <MenuItem key={month} value={index + 1}>
                  {month}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </Panel>

        <Panel title="Conservación de datos">
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="number"
              label="Registro de jornada (años)"
              value={form.record_retention_years}
              onChange={set('record_retention_years')}
              helperText="Mínimo cuatro, por el art. 34.9 ET. Más tiempo necesita su propia justificación."
            />
            <TextField
              fullWidth
              type="number"
              label="Metadatos de seguridad (días)"
              value={form.security_metadata_retention_days}
              onChange={set('security_metadata_retention_days')}
              helperText="IP, dispositivo y agente de usuario. Sirven para detectar anomalías, no para acreditar la jornada."
            />
            <Typography variant="caption" color="text.secondary">
              Borrar los metadatos no toca el fichaje: conserva su hora, su tipo, su origen y su
              huella válida.
            </Typography>
          </Stack>
        </Panel>
      </Box>
    </form>
  )
}
