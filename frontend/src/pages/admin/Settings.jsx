import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import FormControlLabel from '@mui/material/FormControlLabel'
import Switch from '@mui/material/Switch'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import {
  getCompany,
  getEmployees,
  getWorkingTimeRules,
  updateCompany,
  updateWorkingTimeRules,
} from '../../services/api.js'
import { ErrorNote, Loading, PageHeader, Panel } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

/** Spain spans two, and both are in daily use. The rest of the list is there
 *  because the product is not Spain-only, even if the rules currently are. */
/** Every zone the browser knows, with the likely ones first.
 *
 *  It used to be a list of nine in a plain Select. The field accepts any IANA
 *  zone, so a company configured through the API with one of the other three
 *  hundred saw the dropdown **blank** --- and saving anything else on this
 *  screen would have quietly changed their zone to whatever they picked to get
 *  rid of the empty box.
 *
 *  `supportedValuesOf` is in every browser this app supports; the fallback is
 *  there so a very old one degrades to the short list rather than to nothing.
 */
const LIKELY = ['Europe/Madrid', 'Atlantic/Canary', 'Europe/Lisbon', 'UTC']

const ZONES = (() => {
  const all = Intl.supportedValuesOf ? Intl.supportedValuesOf('timeZone') : LIKELY
  const rest = all.filter((zone) => !LIKELY.includes(zone))
  return [...LIKELY.filter((zone) => all.includes(zone) || zone === 'UTC'), ...rest]
})()

/** "Europe/Madrid · UTC+02:00", so a choice can be checked at a glance. */
const offsetOf = (zone) => {
  try {
    const parts = new Intl.DateTimeFormat('es-ES', {
      timeZone: zone,
      timeZoneName: 'shortOffset',
    }).formatToParts(new Date())
    return parts.find((part) => part.type === 'timeZoneName')?.value ?? ''
  } catch {
    return ''
  }
}

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

  const [rules, setRules] = useState(null)

  const { data: company, isLoading } = useQuery({ queryKey: ['company'], queryFn: getCompany })
  const representatives = useQuery({
    queryKey: ['employees', 'representatives'],
    queryFn: () => getEmployees({ is_worker_representative: true, is_active: true }),
  })
  const { data: storedRules } = useQuery({
    queryKey: ['working-time-rules'],
    queryFn: getWorkingTimeRules,
  })

  // Fill the forms once the settings arrive, without an effect.
  if (company && form === null) setForm(company)
  if (storedRules && rules === null) setRules(storedRules)

  const saveRules = useMutation({
    mutationFn: updateWorkingTimeRules,
    onSuccess: (data) => {
      setRules(data)
      setSaved(true)
      queryClient.invalidateQueries({ queryKey: ['working-time-rules'] })
      // The roster is measured against these, so its warnings change with them.
      queryClient.invalidateQueries({ queryKey: ['roster-review'] })
    },
    onError: setError,
  })

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
    if (rules) {
      const editableRules = { ...rules }
      delete editableRules.id
      saveRules.mutate(editableRules)
    }
  }

  const setRule = (field) => (event) => {
    setSaved(false)
    setRules({ ...rules, [field]: event.target.value })
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

      {/* Art. 4.b says the workers' representation must be informed when
          somebody disagrees with a change to their record. The system cannot
          know who they are, and with nobody marked the notice reaches nobody
          --- which the correction records honestly, but only after the fact.
          Better said here, once, where it can be fixed. */}
      {representatives.data && representatives.data.count === 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          No hay ninguna persona marcada como representante legal. El art. 4.b obliga a informarla
          cuando alguien discrepa de un cambio en su registro, y sin nadie marcado ese aviso no
          llega a ninguna parte. Se marca en la ficha de cada persona, en <strong>Personas</strong>.
        </Alert>
      )}
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
            <Autocomplete
              fullWidth
              disableClearable
              options={ZONES}
              value={form.time_zone || 'Europe/Madrid'}
              onChange={(_, zone) => {
                setSaved(false)
                setForm({ ...form, time_zone: zone })
              }}
              getOptionLabel={(zone) => zone}
              renderOption={(props, zone) => {
                const { key, ...rest } = props
                return (
                  <li key={key} {...rest}>
                    <Stack
                      direction="row"
                      sx={{ gap: 1, width: '100%', justifyContent: 'space-between' }}
                    >
                      <span>{zone}</span>
                      <Typography variant="caption" color="text.secondary">
                        {offsetOf(zone)}
                      </Typography>
                    </Stack>
                  </li>
                )
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Zona horaria"
                  helperText={`Ahora mismo, ${offsetOf(form.time_zone || 'Europe/Madrid')}.`}
                />
              )}
            />
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

        <Panel
          title="Reglas de jornada"
          hint="Con qué se compara el cuadrante. Cada valor lleva el artículo del que sale, y ninguno bloquea: se avisa y decide la empresa."
        >
          {rules ? (
            <Stack sx={{ gap: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Horas semanales"
                  value={rules.weekly_hours}
                  onChange={setRule('weekly_hours')}
                  helperText="Art. 34.1 ET: 40 de promedio. El convenio puede mejorarlo."
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso entre jornadas (h)"
                  value={rules.daily_rest_hours}
                  onChange={setRule('daily_rest_hours')}
                  helperText="Art. 34.3 ET. El RD 1561/1995 lo modifica en algunos sectores."
                />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso semanal (h)"
                  value={rules.weekly_rest_hours}
                  onChange={setRule('weekly_rest_hours')}
                  helperText="Art. 37.1 ET. Acumulable en catorce días."
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Horas extra al año"
                  value={rules.annual_overtime_hours}
                  onChange={setRule('annual_overtime_hours')}
                  helperText="Art. 35.2 ET."
                />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso a partir de (h)"
                  value={rules.break_after_hours}
                  onChange={setRule('break_after_hours')}
                  helperText="Art. 34.4 ET: cuando la jornada continuada excede de seis."
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Minutos de descanso"
                  value={rules.break_minutes}
                  onChange={setRule('break_minutes')}
                />
              </Stack>

              <FormControlLabel
                control={
                  <Switch
                    checked={rules.break_counts_as_work}
                    onChange={(event) =>
                      setRules({ ...rules, break_counts_as_work: event.target.checked })
                    }
                  />
                }
                label="El descanso computa como trabajo efectivo"
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
                Solo si lo dice el convenio o el contrato. Darlo por hecho inflaría las horas.
              </Typography>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="time"
                  label="El trabajo nocturno empieza"
                  value={String(rules.night_starts_at).slice(0, 5)}
                  onChange={setRule('night_starts_at')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  fullWidth
                  type="time"
                  label="y acaba"
                  value={String(rules.night_ends_at).slice(0, 5)}
                  onChange={setRule('night_ends_at')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
                Art. 36.1 ET. Trabajar en esa franja no convierte a nadie en trabajador
                nocturno: esa condición la determina la empresa, y de ella dependen los
                límites.
              </Typography>
            </Stack>
          ) : (
            <Loading rows={3} />
          )}
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
