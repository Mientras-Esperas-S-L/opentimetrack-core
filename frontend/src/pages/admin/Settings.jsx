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
  getLeaveTypes,
  getRecordArrangement,
  getWorkingTimeRules,
  seedLeaveTypes,
  updateCompany,
  updateRecordArrangement,
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

/** Los que de verdad existen.
 *
 *  Estaban los ocho de `LANGUAGES` de Django y solo hay catálogo de castellano.
 *  Elegir «Catalán» dejaba el producto en castellano sin decir nada: ni un
 *  aviso, ni un error, ni media palabra en catalán. Ofrecer un idioma y
 *  contestar en otro es peor que no ofrecerlo --- quien lo elige se queda
 *  pensando que algo no funciona, y no hay nada que arreglar.
 *
 *  El inglés sí: los mensajes se escriben en inglés y el catálogo los traduce,
 *  así que quien lo elige recibe el original.
 *
 *  Cuando haya un catálogo más, esta lista crece con él y no antes.
 */
const LANGUAGES = [
  ['es', 'Español'],
  ['ca', 'Català'],
  ['gl', 'Galego'],
  ['eu', 'Euskara'],
  ['en', 'Inglés'],
]

const MONTHS = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
]

/** Cómo se llama cada ajuste en la pantalla.
 *
 *  Para poder decir **qué** se ha cambiado antes de guardar. Con diecinueve
 *  campos y un solo botón, quien vuelve a esta pantalla después de un rato no
 *  sabe si tocó algo ni qué, y el único remedio era recargar y perderlo.
 *
 *  Escrito aparte y no leído de los `label` porque un rótulo puede ser «y
 *  acaba», que fuera de su fila no dice nada.
 */
const NOMBRES = {
  name: 'Razón social',
  language: 'Idioma',
  time_zone: 'Zona horaria',
  managers_see_everyone: 'Los responsables ven toda la empresa',
  basis: 'Con qué amparo se organizó el registro',
  reference: 'Cuál (convenio o acuerdo)',
  in_force_since: 'En vigor desde',
  consulted_on: 'Consulta a la representación',
  annual_leave_days: 'Días de vacaciones al año',
  annual_leave_in_working_days: 'Contar en días laborables',
  leave_year_start_month: 'Mes en que empieza el periodo',
  weekly_hours: 'Horas semanales',
  daily_rest_hours: 'Descanso entre jornadas',
  weekly_rest_hours: 'Descanso semanal',
  annual_overtime_hours: 'Horas extra al año',
  entry_tolerance_minutes: 'Margen de entrada',
  exit_tolerance_minutes: 'Margen de salida',
  break_after_hours: 'Descanso a partir de',
  break_minutes: 'Minutos de descanso',
  break_counts_as_work: 'El descanso computa como trabajo',
  night_starts_at: 'El trabajo nocturno empieza',
  night_ends_at: 'El trabajo nocturno acaba',
  record_retention_years: 'Conservación del registro',
  security_metadata_retention_days: 'Conservación de metadatos',
}

/** Lo que se ha tocado y no se ha guardado todavía.
 *
 *  Compara lo escrito con lo que trajo el servidor, campo a campo. Los valores
 *  se comparan como texto a propósito: un número que viene como 40 y se teclea
 *  como «40» son el mismo ajuste, y decir que ha cambiado sería peor que
 *  callarse.
 */
function cambiosPendientes(editado, guardado) {
  if (!editado || !guardado) return []
  return Object.keys(NOMBRES)
    .filter((campo) => campo in editado && campo in guardado)
    .filter((campo) => String(editado[campo] ?? '') !== String(guardado[campo] ?? ''))
    .map((campo) => ({
      campo,
      nombre: NOMBRES[campo],
      antes: String(guardado[campo] ?? '—'),
      ahora: String(editado[campo] ?? '—'),
    }))
}

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

  // Cuántos permisos tiene la empresa. Sin número no se sabe si el catálogo
  // está o falta, y faltaba en toda empresa recién dada de alta.
  const { data: leaveTypes } = useQuery({
    queryKey: ['leave-types'],
    queryFn: () => getLeaveTypes(),
  })
  const permisos = leaveTypes?.length

  const cargar = useMutation({
    mutationFn: seedLeaveTypes,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-types'] }),
  })

  // Cómo se organizó el registro de jornada. Art. 34.9, párrafo segundo: es lo
  // primero que pide una inspección después de los propios registros, porque
  // decide si el sistema tiene amparo.
  const { data: amparo } = useQuery({
    queryKey: ['record-arrangement'],
    queryFn: getRecordArrangement,
  })
  const [organizacion, setOrganizacion] = useState(null)
  if (amparo && organizacion === null) setOrganizacion(amparo)

  const guardarAmparo = useMutation({
    mutationFn: updateRecordArrangement,
    onSuccess: (data) => {
      setOrganizacion(data)
      queryClient.invalidateQueries({ queryKey: ['record-arrangement'] })
    },
  })
  const campoAmparo = (campo) => (event) =>
    setOrganizacion({ ...organizacion, [campo]: event.target.value })

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
      // Only the figures. The rest of the payload is what the server tells us
      // about the applicable law --- the country, its citations, the floors for
      // minors --- and sending it back would be asking to change the law.
      const { id, country, framework, citations, minors, ...figures } = rules
      ;(void id, country, framework, citations, minors)
      saveRules.mutate(figures)
    }
    // El tercero. La pantalla ya guardaba dos sitios con un solo botón, y meter
    // aquí el suyo evita dos botones que empiezan por «Guardar» en la misma
    // página --- ambiguo para quien lo lee, y para la prueba que los buscaba.
    if (organizacion) {
      guardarAmparo.mutate({
        basis: organizacion.basis ?? '',
        reference: organizacion.reference ?? '',
        in_force_since: organizacion.in_force_since || null,
        consulted_on: organizacion.basis === 'EMPLOYER' ? organizacion.consulted_on || null : null,
      })
    }
  }

  /** The article and the note for a field, as the server gave them.
   *
   *  These used to be written here by hand --- six of them --- which meant they
   *  could not be translated, could not vary by country, and were free to drift
   *  from the backend without anybody noticing. Now the screen renders what it
   *  is told, and a company elsewhere is told its own law.
   */
  // Lo tocado en las dos mitades de la pantalla: los datos de la empresa y las
  // reglas de jornada. Se guardan con el mismo botón, así que se cuentan juntas.
  const cambios = [
    ...cambiosPendientes(form, company),
    ...cambiosPendientes(rules, storedRules),
    ...cambiosPendientes(organizacion, amparo),
  ]

  const cite = (field) => {
    const c = rules?.citations?.[field]
    if (!c) return ' '
    return [c.basis, c.note].filter(Boolean).join('. ')
  }

  /** Si el valor escrito se sale del límite que fija el artículo.
   *
   *  Devuelve la frase del aviso, o `null` si no hay nada que decir. El número
   *  no está aquí: lo manda el marco legal del país junto a la cita, porque
   *  escribir «12» en esta pantalla sería enseñarle la cifra española a una
   *  empresa de fuera.
   *
   *  Avisa, no impide. El descanso entre jornadas es el caso claro: el
   *  RD 1561/1995 lo baja de verdad en sectores concretos, así que un producto
   *  que se negara estaría equivocado para esas empresas. Lo que no puede
   *  hacer es callarse ---que es lo que hacía--- porque entonces la misma cifra
   *  se revisa al llegar por convenio y pasa muda si se teclea a mano.
   */
  const outsideTheLaw = (field) => {
    const c = rules?.citations?.[field]
    const raw = rules?.[field]
    // Un campo vacío no es salirse de nada: quien borra para reescribir pasa
    // por aquí, y `Number('')` es cero --- que sí está por debajo de todo.
    if (!c || raw === '' || raw == null) return null

    const value = Number(raw)
    if (Number.isNaN(value)) return null

    if (c.floor != null && value < c.floor) {
      return `Por debajo del mínimo de ${c.floor} que fija el ${c.basis}. Se guarda igual, pero debería ampararlo el convenio o una norma sectorial.`
    }
    if (c.ceiling != null && value > c.ceiling) {
      return `Por encima del máximo de ${c.ceiling} que fija el ${c.basis}. Se guarda igual, pero debería ampararlo el convenio.`
    }
    return null
  }

  /** Las propiedades del campo que lleva límite legal, cita incluida. */
  const legalField = (field) => {
    const warning = outsideTheLaw(field)
    return {
      color: warning ? 'warning' : undefined,
      focused: warning ? true : undefined,
      helperText: warning ?? cite(field),
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
          <Button
            type="submit"
            variant="contained"
            // Desactivado cuando no hay nada que guardar: un botón que se puede
            // pulsar promete que hará algo.
            disabled={save.isPending || cambios.length === 0}
          >
            {cambios.length === 0
              ? 'Guardar cambios'
              : `Guardar ${cambios.length} ${cambios.length === 1 ? 'cambio' : 'cambios'}`}
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {/* Qué se ha tocado, antes de guardarlo. Son diecinueve campos repartidos
          en cuatro bloques con un solo botón al final: quien vuelve después de
          un rato no sabe si cambió algo, y la única forma de averiguarlo era
          recargar --- perdiéndolo. */}
      {cambios.length > 0 && (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            Sin guardar
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {cambios.map((cambio) => (
              <li key={cambio.campo}>
                <Typography variant="body2" component="span">
                  {cambio.nombre}: <s>{cambio.antes}</s> → <strong>{cambio.ahora}</strong>
                </Typography>
              </li>
            ))}
          </Box>
        </Alert>
      )}

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
              {/* Si una empresa se quedó con uno de los que se han retirado, su
                  valor sigue en la lista: un `select` con un valor que no está
                  entre sus opciones se pinta vacío y avisa por consola, y de
                  paso le borraría el ajuste al primer guardado. */}
              {form.language && !LANGUAGES.some(([code]) => code === form.language) && (
                <MenuItem value={form.language}>
                  {form.language} (ya no disponible; responde en español)
                </MenuItem>
              )}
            </TextField>
          </Stack>
        </Panel>

        <Panel
          title="Quién ve a quién"
          hint="Un responsable lee y resuelve por su gente. Administración ve toda la empresa."
        >
          <Stack sx={{ gap: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(form.managers_see_whole_company)}
                  onChange={(event) =>
                    setForm({ ...form, managers_see_whole_company: event.target.checked })
                  }
                />
              }
              label="Los responsables ven toda la empresa"
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
              {form.managers_see_whole_company
                ? 'Cualquier responsable lee el registro y las ausencias de toda la plantilla, lleve el departamento que lleve.'
                : 'Cada responsable lee solo los departamentos que lleva. Se asigna en Departamentos.'}
            </Typography>

            {/* La una concesión de este diseño, dicha en voz alta: acotar por
                departamento no empieza a aplicar hasta que alguien lleva uno,
                porque si no una empresa recién creada tendría un responsable
                que no ve a nadie. */}
            {!form.managers_see_whole_company &&
              company?.managers_without_department?.length > 0 && (
                <Alert severity="warning" variant="outlined">
                  {company.managers_without_department.length === 1
                    ? `${company.managers_without_department[0].name} no lleva ningún departamento, así que ve a toda la empresa.`
                    : `${company.managers_without_department.length} responsables no llevan ningún departamento, así que ven a toda la empresa: ${company.managers_without_department.map((m) => m.name).join(', ')}.`}
                </Alert>
              )}
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
              label={`Días al año, ${form.leave_days_are_working_days ? 'laborables' : 'naturales'}`}
              value={form.annual_leave_days}
              onChange={set('annual_leave_days')}
              helperText={cite('annual_leave_days')}
            />
            {/* Treinta y veintidós son el mismo mínimo legal en dos unidades
                distintas. Cuál de las dos era la cifra de arriba lo decía solo
                un texto de ayuda, mientras el saldo descontaba la otra: una
                quincena costaba catorce días de veintidós. */}
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(form.leave_days_are_working_days)}
                  onChange={(event) =>
                    setForm({ ...form, leave_days_are_working_days: event.target.checked })
                  }
                />
              }
              label="Contar en días laborables"
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
              {form.leave_days_are_working_days
                ? 'Solo se descuentan los días que la persona tenía que trabajar, según su cuadrante. Una quincena cuesta diez.'
                : 'Se descuentan todos los días entre las dos fechas, fines de semana incluidos. La cifra de arriba debe ser la de días naturales del convenio.'}
              {' Los festivos todavía no se descuentan: el sistema aún no los conoce.'}
            </Typography>
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
                  {...legalField('weekly_hours')}
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso entre jornadas (h)"
                  value={rules.daily_rest_hours}
                  onChange={setRule('daily_rest_hours')}
                  {...legalField('daily_rest_hours')}
                />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso semanal (h)"
                  value={rules.weekly_rest_hours}
                  onChange={setRule('weekly_rest_hours')}
                  {...legalField('weekly_rest_hours')}
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Horas extra al año"
                  value={rules.annual_overtime_hours}
                  onChange={setRule('annual_overtime_hours')}
                  {...legalField('annual_overtime_hours')}
                />
              </Stack>

              {/* Márgenes de flexibilidad. Convierten un retraso pequeño en
                  variación, no en incidencia. No ocultan horas extra: la extra
                  es tiempo por encima de lo previsto MÁS el margen, y sigue
                  saliendo. Es la diferencia con el redondeo tramposo. */}
              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Margen de entrada (min)"
                  value={rules.entry_tolerance_minutes}
                  onChange={setRule('entry_tolerance_minutes')}
                  slotProps={{ htmlInput: { min: 0, step: 5 } }}
                  helperText="Fichar dentro de este margen del inicio cuenta como puntual. 0 = estricto."
                />
                <TextField
                  fullWidth
                  type="number"
                  label="Margen de salida (min)"
                  value={rules.exit_tolerance_minutes}
                  onChange={setRule('exit_tolerance_minutes')}
                  slotProps={{ htmlInput: { min: 0, step: 5 } }}
                  helperText="Irse dentro de este margen del fin no es salir antes."
                />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Descanso a partir de (h)"
                  value={rules.break_after_hours}
                  onChange={setRule('break_after_hours')}
                  helperText={cite('break_after_hours')}
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
                {cite('break_counts_as_work')}
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
                {cite('night_starts_at')}
              </Typography>
            </Stack>
          ) : (
            <Loading rows={3} />
          )}
        </Panel>

        {/* El catálogo de permisos.
            No se edita aquí ---cada permiso tiene su cifra, su unidad y su
            periodo, y eso es una pantalla propia--- pero sí se dice cuántos hay
            y se puede traer el del país. Existe por un fallo: una empresa
            recién dada de alta se quedaba con cero, el desplegable de «Qué
            pides» salía vacío, y el endpoint que lo arregla no lo llamaba
            ninguna pantalla. */}
        {/* Art. 34.9, párrafo segundo: «se organizará y documentará este
            registro de jornada». El producto registraba la jornada y no había
            dónde escribir con qué amparo se organizó ese registro.

            Se guarda la constancia, no el acta: que exista un documento, de qué
            fecha y con qué referencia es el hecho comprobable. El acta la
            custodia la empresa con sus otros papeles. */}
        <Panel title="Cómo se organizó el registro">
          <Stack sx={{ gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              El art. 34.9 ET pide dos cosas: llevar el registro y documentar cómo se organizó. Esto
              es lo segundo, y es lo primero que se pide en una inspección.
            </Typography>

            {organizacion?.missing_consultation && (
              <Alert severity="warning" variant="outlined">
                Por decisión de la empresa hace falta consulta previa a la representación de los
                trabajadores, y no consta su fecha. Es el único de los tres caminos que la exige: un
                convenio o un acuerdo ya son la negociación.
              </Alert>
            )}

            <TextField
              select
              fullWidth
              label="Con qué amparo"
              value={organizacion?.basis ?? ''}
              onChange={campoAmparo('basis')}
              helperText="Art. 34.9 ET. Vacío significa que todavía no se ha declarado."
            >
              <MenuItem value="">Sin declarar</MenuItem>
              <MenuItem value="COLLECTIVE">Convenio colectivo</MenuItem>
              <MenuItem value="COMPANY">Acuerdo de empresa</MenuItem>
              <MenuItem value="EMPLOYER">
                Decisión de la empresa, previa consulta a la representación
              </MenuItem>
            </TextField>

            <TextField
              fullWidth
              label="Cuál"
              value={organizacion?.reference ?? ''}
              onChange={campoAmparo('reference')}
              helperText="«Convenio del metal de Sevilla, art. 22», «acuerdo de 3 de marzo con el comité». Sin esto no hay contra qué comprobarlo."
            />

            <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap' }}>
              <TextField
                type="date"
                label="En vigor desde"
                slotProps={{ inputLabel: { shrink: true } }}
                value={organizacion?.in_force_since ?? ''}
                onChange={campoAmparo('in_force_since')}
                helperText="No es la fecha de hoy: un sistema en marcha desde 2023 rige desde 2023."
              />
              {organizacion?.basis === 'EMPLOYER' && (
                <TextField
                  type="date"
                  label="Consulta a la representación"
                  slotProps={{ inputLabel: { shrink: true } }}
                  value={organizacion?.consulted_on ?? ''}
                  onChange={campoAmparo('consulted_on')}
                />
              )}
            </Stack>

            <ErrorNote error={guardarAmparo.error} />
          </Stack>
        </Panel>

        <Panel title="Permisos y ausencias">
          <Stack sx={{ gap: 1.5 }}>
            <Typography variant="body2">
              {permisos === undefined
                ? 'Contando…'
                : permisos === 0
                  ? 'No hay ningún permiso configurado, así que nadie puede pedir ninguno.'
                  : `${permisos} permisos configurados.`}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Cargar el catálogo añade los que falten del país y no toca los que ya están: lo que tu
              convenio mejore se queda como lo tengas.
            </Typography>
            {cargar.isSuccess && (
              <Alert severity="success" variant="outlined">
                {cargar.data?.added
                  ? `Añadidos ${cargar.data.added}.`
                  : 'No faltaba ninguno: no se ha tocado nada.'}
              </Alert>
            )}
            <ErrorNote error={cargar.error} />
            <Box>
              <Button
                variant="outlined"
                disabled={cargar.isPending}
                onClick={() => cargar.mutate()}
              >
                Cargar el catálogo del país
              </Button>
            </Box>
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
              helperText={cite('record_retention_years')}
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
