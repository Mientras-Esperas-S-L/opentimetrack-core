import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
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
import { capitalised, plural } from '../../components/format.js'
import { avisoDeAlcance } from './avisoDeAlcance.js'
import { useAuth } from '../../hooks/useAuth.js'
import { alCatalogo, IDIOMAS_QUE_SE_OFRECEN, localeDeFechas } from '../../i18n/index.js'

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
    const parts = new Intl.DateTimeFormat(localeDeFechas(), {
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
 *  Cuando haya un catálogo más, esa lista crece con él y no antes. Vive en
 *  `i18n/index.js` porque la ficha de cada persona ofrece la misma.
 */

/** Los doce meses, en el idioma de quien mira.
 *
 *  Estaban escritos a mano en castellano, así que el desplegable del periodo de
 *  cómputo decía «enero» dentro de una pantalla en catalán. Salen del navegador
 *  igual que el resto de fechas, y así no hay una lista más que traducir. */
const meses = () =>
  Array.from({ length: 12 }, (_, i) =>
    new Date(2000, i, 1).toLocaleDateString(localeDeFechas(), { month: 'long' }),
  )

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
  name: alCatalogo('Razón social'),
  language: alCatalogo('Idioma'),
  time_zone: alCatalogo('Zona horaria'),
  managers_see_everyone: alCatalogo('Los responsables ven toda la empresa'),
  basis: alCatalogo('Con qué amparo se organizó el registro'),
  reference: alCatalogo('Cuál (convenio o acuerdo)'),
  in_force_since: alCatalogo('En vigor desde'),
  consulted_on: alCatalogo('Consulta a la representación'),
  annual_leave_days: alCatalogo('Días de vacaciones al año'),
  annual_leave_in_working_days: alCatalogo('Contar en días laborables'),
  leave_year_start_month: alCatalogo('Mes en que empieza el periodo'),
  weekly_hours: alCatalogo('Horas semanales'),
  daily_rest_hours: alCatalogo('Descanso entre jornadas'),
  weekly_rest_hours: alCatalogo('Descanso semanal'),
  annual_overtime_hours: alCatalogo('Horas extra al año'),
  entry_tolerance_minutes: alCatalogo('Margen de entrada'),
  exit_tolerance_minutes: alCatalogo('Margen de salida'),
  max_open_hours: alCatalogo('Jornada abierta como mucho'),
  break_after_hours: alCatalogo('Descanso a partir de'),
  break_minutes: alCatalogo('Minutos de descanso'),
  break_counts_as_work: alCatalogo('El descanso computa como trabajo'),
  night_starts_at: alCatalogo('El trabajo nocturno empieza'),
  night_ends_at: alCatalogo('El trabajo nocturno acaba'),
  record_retention_years: alCatalogo('Conservación del registro'),
  security_metadata_retention_days: alCatalogo('Conservación de metadatos'),
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
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { session, setSession } = useAuth()
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  const [rules, setRules] = useState(null)
  // Desde cuándo aplica un cambio en cómo se cuenta el tiempo. Empieza hoy
  // porque es lo más frecuente, pero se puede mover: un convenio se firma en
  // marzo y entra en enero más veces de las que uno cree.
  const [desdeCuando, setDesdeCuando] = useState(() => new Date().toLocaleDateString('sv-SE'))

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
        <PageHeader title={t('Ajustes de la empresa')} />
        <Loading rows={4} />
      </>
    )
  }

  const set = (field) => (event) => {
    setSaved(false)
    setForm({ ...form, [field]: event.target.value })
  }

  // Las dos que deciden **qué dice el registro**, no si cumple. Cambiarlas exige
  // decir desde cuándo, porque si no reescriben periodos ya cerrados: marcar que
  // la pausa cuenta llevaba un abril terminado de 7:00 a 8:00 h.
  const DEL_COMPUTO = ['break_counts_as_work', 'max_open_hours']
  const cambiaElComputo =
    rules && storedRules && DEL_COMPUTO.some((campo) => rules[campo] !== storedRules[campo])

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
      // Y con la fecha desde la que aplica, si se ha tocado una de las dos del
      // cómputo. El servidor la exige, y hace bien: el sistema no puede saber
      // desde cuándo rige un convenio.
      saveRules.mutate(cambiaElComputo ? { ...figures, effective_from: desdeCuando } : figures)
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
      return t(
        'Por debajo del mínimo de {{limite}} que fija el {{articulo}}. Se guarda igual, pero debería ampararlo el convenio o una norma sectorial.',
        { limite: c.floor, articulo: c.basis },
      )
    }
    if (c.ceiling != null && value > c.ceiling) {
      return t(
        'Por encima del máximo de {{limite}} que fija el {{articulo}}. Se guarda igual, pero debería ampararlo el convenio.',
        { limite: c.ceiling, articulo: c.basis },
      )
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
        title={t('Ajustes de la empresa')}
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
              ? t('Guardar cambios')
              : t('Guardar {{cuantos}} {{unidad}}', {
                  cuantos: cambios.length,
                  unidad: plural(cambios.length, t('cambio'), t('cambios')),
                })}
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
            {t('Sin guardar')}
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
          <Trans
            i18nKey="No hay ninguna persona marcada como representante legal. El art. 4.b obliga a informarla cuando alguien discrepa de un cambio en su registro, y sin nadie marcado ese aviso no llega a ninguna parte. Se marca en la ficha de cada persona, en <donde>{{pantalla}}</donde>."
            values={{ pantalla: t('Personas') }}
            components={{ donde: <strong /> }}
          />
        </Alert>
      )}
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSaved(false)}>
          {t('Ajustes guardados.')}
        </Alert>
      )}

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
        <Panel title={t('Identificación')}>
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              label={t('Razón social')}
              value={form.name}
              onChange={set('name')}
            />
            <TextField
              fullWidth
              disabled
              label={t('CIF/NIF')}
              value={form.tax_id}
              helperText={t(
                'No se puede cambiar: identifica a la empresa en cada informe ya emitido.',
              )}
            />
          </Stack>
        </Panel>

        <Panel
          title={t('Zona horaria e idioma')}
          hint={t('Las horas se guardan siempre en UTC. La zona solo decide cómo se muestran.')}
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
                  label={t('Zona horaria')}
                  helperText={t('Ahora mismo, {{desfase}}.', {
                    desfase: offsetOf(form.time_zone || 'Europe/Madrid'),
                  })}
                />
              )}
            />
            <TextField
              select
              fullWidth
              label={t('Idioma')}
              value={form.language}
              onChange={set('language')}
              helperText={t('Cada persona puede usar otro distinto.')}
            >
              {IDIOMAS_QUE_SE_OFRECEN.map(([code, label]) => (
                <MenuItem key={code} value={code}>
                  {label}
                </MenuItem>
              ))}
              {/* Si una empresa se quedó con uno de los que se han retirado, su
                  valor sigue en la lista: un `select` con un valor que no está
                  entre sus opciones se pinta vacío y avisa por consola, y de
                  paso le borraría el ajuste al primer guardado. */}
              {form.language &&
                !IDIOMAS_QUE_SE_OFRECEN.some(([code]) => code === form.language) && (
                  <MenuItem value={form.language}>
                    {t('{{codigo}} (ya no disponible; responde en español)', {
                      codigo: form.language,
                    })}
                  </MenuItem>
                )}
            </TextField>
          </Stack>
        </Panel>

        <Panel
          title={t('Quién ve a quién')}
          hint={t('Un responsable lee y resuelve por su gente. Administración ve toda la empresa.')}
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
              label={t('Los responsables ven toda la empresa')}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
              {form.managers_see_whole_company
                ? t(
                    'Cualquier responsable lee el registro y las ausencias de toda la plantilla, lleve el departamento que lleve.',
                  )
                : t(
                    'Cada responsable lee solo los departamentos que lleva. Se asigna en Departamentos.',
                  )}
            </Typography>

            {/* La una concesión de este diseño, dicha en voz alta: acotar por
                departamento no empieza a aplicar hasta que alguien lleva uno,
                porque si no una empresa recién creada tendría un responsable
                que no ve a nadie.

                Pasado ese momento el aviso sigue haciendo falta, pero dice lo
                contrario: quien no lleva ninguno no ve a nadie, y eso le pasa
                justo a quien acaba de ceder su departamento. Cuál de los dos es
                lo dice el servidor. */}
            {!form.managers_see_whole_company &&
              (() => {
                const aviso = avisoDeAlcance(
                  company?.managers_without_department,
                  company?.department_scoping_in_use,
                )
                return (
                  aviso && (
                    <Alert severity={aviso.severity} variant="outlined">
                      {aviso.text}
                    </Alert>
                  )
                )
              })()}
          </Stack>
        </Panel>

        <Panel
          title={t('Vacaciones')}
          hint={t('Estos valores salen del convenio. El sistema no los conoce: los aplica.')}
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="number"
              label={t('Días al año, {{unidad}}', {
                unidad: form.leave_days_are_working_days ? t('laborables') : t('naturales'),
              })}
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
              label={t('Contar en días laborables')}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
              {form.leave_days_are_working_days
                ? t(
                    'Solo se descuentan los días que la persona tenía que trabajar, según su cuadrante. Una quincena cuesta diez.',
                  )
                : t(
                    'Se descuentan todos los días entre las dos fechas, fines de semana incluidos. La cifra de arriba debe ser la de días naturales del convenio.',
                  )}{' '}
              {t('Los festivos todavía no se descuentan: el sistema aún no los conoce.')}
            </Typography>
            <TextField
              select
              fullWidth
              label={t('El periodo de cómputo empieza en')}
              value={form.leave_year_start_month}
              onChange={set('leave_year_start_month')}
              helperText={t('Enero = año natural. El convenio puede fijar otro periodo.')}
            >
              {meses().map((mes, indice) => (
                <MenuItem key={mes} value={indice + 1}>
                  {capitalised(mes)}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </Panel>

        <Panel
          title={t('Reglas de jornada')}
          hint={t(
            'Con qué se compara el cuadrante. Cada valor lleva el artículo del que sale, y ninguno bloquea: se avisa y decide la empresa.',
          )}
        >
          {rules ? (
            <Stack sx={{ gap: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label={t('Horas semanales')}
                  value={rules.weekly_hours}
                  onChange={setRule('weekly_hours')}
                  {...legalField('weekly_hours')}
                />
                <TextField
                  fullWidth
                  type="number"
                  label={t('Descanso entre jornadas (h)')}
                  value={rules.daily_rest_hours}
                  onChange={setRule('daily_rest_hours')}
                  {...legalField('daily_rest_hours')}
                />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label={t('Descanso semanal (h)')}
                  value={rules.weekly_rest_hours}
                  onChange={setRule('weekly_rest_hours')}
                  {...legalField('weekly_rest_hours')}
                />
                <TextField
                  fullWidth
                  type="number"
                  label={t('Horas extra al año')}
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
                  label={t('Margen de entrada (min)')}
                  value={rules.entry_tolerance_minutes}
                  onChange={setRule('entry_tolerance_minutes')}
                  slotProps={{ htmlInput: { min: 0, step: 5 } }}
                  helperText={t(
                    'Fichar dentro de este margen del inicio cuenta como puntual. 0 = estricto.',
                  )}
                />
                <TextField
                  fullWidth
                  type="number"
                  label={t('Margen de salida (min)')}
                  value={rules.exit_tolerance_minutes}
                  onChange={setRule('exit_tolerance_minutes')}
                  slotProps={{ htmlInput: { min: 0, step: 5 } }}
                  helperText={t('Irse dentro de este margen del fin no es salir antes.')}
                />
              </Stack>

              {/* La frontera entre «cerró tarde» y «se olvidó de fichar». No la
                  fija ningún artículo, y por eso la pone cada empresa: con
                  guardias de veinticuatro horas ---bomberos, residencias,
                  vigilancia--- dieciséis parte la guardia por la mitad y el
                  registro de esa noche sale mal. */}
              <TextField
                fullWidth
                type="number"
                label={t('Una jornada puede seguir abierta (h)')}
                value={rules.max_open_hours}
                onChange={setRule('max_open_hours')}
                slotProps={{ htmlInput: { min: 1, step: 1 } }}
                helperText={t(
                  'Pasado este rato, una jornada sin cerrar se lee como un olvido de fichar y no como un turno en marcha. Súbelo si hay guardias de 24 h; cuanto más alto, más tarda en detectarse un olvido.',
                )}
              />

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="number"
                  label={t('Descanso a partir de (h)')}
                  value={rules.break_after_hours}
                  onChange={setRule('break_after_hours')}
                  helperText={cite('break_after_hours')}
                />
                <TextField
                  fullWidth
                  type="number"
                  label={t('Minutos de descanso')}
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
                label={t('El descanso computa como trabajo efectivo')}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
                {cite('break_counts_as_work')}
              </Typography>

              {/* Aparece solo cuando se toca una de las dos que deciden qué dice
                  el registro. Sin fecha, el cambio alcanzaría a periodos ya
                  cerrados y entregados ---medido: marcar que la pausa cuenta
                  llevaba un abril terminado de 7:00 a 8:00 h--- y el servidor lo
                  rechaza. La fecha la pone quien cambia la regla porque sale del
                  convenio, y eso no lo puede saber el sistema. */}
              {cambiaElComputo && (
                <Alert severity="info" variant="outlined">
                  <Stack sx={{ gap: 1.5 }}>
                    <span>
                      {t(
                        'Estás cambiando cómo se cuenta el tiempo trabajado. Los días anteriores a la fecha que indiques se siguen contando como hasta ahora.',
                      )}
                    </span>
                    <TextField
                      type="date"
                      label={t('Se aplica desde *')}
                      value={desdeCuando}
                      onChange={(event) => {
                        setSaved(false)
                        setDesdeCuando(event.target.value)
                      }}
                      slotProps={{ inputLabel: { shrink: true } }}
                      sx={{ maxWidth: 260 }}
                      helperText={t('El día en que entra en vigor el acuerdo, no el de hoy.')}
                    />
                  </Stack>
                </Alert>
              )}

              <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                <TextField
                  fullWidth
                  type="time"
                  label={t('El trabajo nocturno empieza')}
                  value={String(rules.night_starts_at).slice(0, 5)}
                  onChange={setRule('night_starts_at')}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  fullWidth
                  type="time"
                  label={t('y acaba')}
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
        <Panel title={t('Cómo se organizó el registro')}>
          <Stack sx={{ gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {t(
                'El art. 34.9 ET pide dos cosas: llevar el registro y documentar cómo se organizó. Esto es lo segundo, y es lo primero que se pide en una inspección.',
              )}
            </Typography>

            {organizacion?.missing_consultation && (
              <Alert severity="warning" variant="outlined">
                {t(
                  'Por decisión de la empresa hace falta consulta previa a la representación de los trabajadores, y no consta su fecha. Es el único de los tres caminos que la exige: un convenio o un acuerdo ya son la negociación.',
                )}
              </Alert>
            )}

            <TextField
              select
              fullWidth
              label={t('Con qué amparo')}
              value={organizacion?.basis ?? ''}
              onChange={campoAmparo('basis')}
              helperText={t('Art. 34.9 ET. Vacío significa que todavía no se ha declarado.')}
            >
              <MenuItem value="">{t('Sin declarar')}</MenuItem>
              <MenuItem value="COLLECTIVE">{t('Convenio colectivo')}</MenuItem>
              <MenuItem value="COMPANY">{t('Acuerdo de empresa')}</MenuItem>
              <MenuItem value="EMPLOYER">
                {t('Decisión de la empresa, previa consulta a la representación')}
              </MenuItem>
            </TextField>

            <TextField
              fullWidth
              label={t('Cuál')}
              value={organizacion?.reference ?? ''}
              onChange={campoAmparo('reference')}
              helperText={t(
                '«Convenio del metal de Sevilla, art. 22», «acuerdo de 3 de marzo con el comité». Sin esto no hay contra qué comprobarlo.',
              )}
            />

            <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap' }}>
              <TextField
                type="date"
                label={t('En vigor desde')}
                slotProps={{ inputLabel: { shrink: true } }}
                value={organizacion?.in_force_since ?? ''}
                onChange={campoAmparo('in_force_since')}
                helperText={t(
                  'No es la fecha de hoy: un sistema en marcha desde 2023 rige desde 2023.',
                )}
              />
              {organizacion?.basis === 'EMPLOYER' && (
                <TextField
                  type="date"
                  label={t('Consulta a la representación')}
                  slotProps={{ inputLabel: { shrink: true } }}
                  value={organizacion?.consulted_on ?? ''}
                  onChange={campoAmparo('consulted_on')}
                />
              )}
            </Stack>

            <ErrorNote error={guardarAmparo.error} />
          </Stack>
        </Panel>

        <Panel title={t('Permisos y ausencias')}>
          <Stack sx={{ gap: 1.5 }}>
            <Typography variant="body2">
              {permisos === undefined
                ? t('Contando…')
                : permisos === 0
                  ? t('No hay ningún permiso configurado, así que nadie puede pedir ninguno.')
                  : `${permisos} ${plural(permisos, t('permiso configurado'), t('permisos configurados'))}.`}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t(
                'Cargar el catálogo añade los que falten del país y no toca los que ya están: lo que tu convenio mejore se queda como lo tengas.',
              )}
            </Typography>
            {cargar.isSuccess && (
              <Alert severity="success" variant="outlined">
                {cargar.data?.added
                  ? t('Añadidos {{cuantos}}.', { cuantos: cargar.data.added })
                  : t('No faltaba ninguno: no se ha tocado nada.')}
              </Alert>
            )}
            <ErrorNote error={cargar.error} />
            <Box>
              <Button
                variant="outlined"
                disabled={cargar.isPending}
                onClick={() => cargar.mutate()}
              >
                {t('Cargar el catálogo del país')}
              </Button>
            </Box>
          </Stack>
        </Panel>

        <Panel title={t('Conservación de datos')}>
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="number"
              label={t('Registro de jornada (años)')}
              value={form.record_retention_years}
              onChange={set('record_retention_years')}
              helperText={cite('record_retention_years')}
            />
            <TextField
              fullWidth
              type="number"
              label={t('Metadatos de seguridad (días)')}
              value={form.security_metadata_retention_days}
              onChange={set('security_metadata_retention_days')}
              helperText={t(
                'IP, dispositivo y agente de usuario. Sirven para detectar anomalías, no para acreditar la jornada.',
              )}
            />
            <Typography variant="caption" color="text.secondary">
              {t(
                'Borrar los metadatos no toca el fichaje: conserva su hora, su tipo, su origen y su huella válida.',
              )}
            </Typography>
          </Stack>
        </Panel>
      </Box>
    </form>
  )
}
