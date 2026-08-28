import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useMutation, useQuery } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong'
import TableViewIcon from '@mui/icons-material/TableView'

import { downloadReport, generatePayrollSummaries, getDepartments } from '../../services/api.js'
import EmployeePicker from '../../components/EmployeePicker.jsx'
import { ErrorNote, PageHeader, Panel } from '../../components/common.jsx'
import { save } from '../../services/download.js'
import { useAuth } from '../../hooks/useAuth.js'
import { plural, today } from '../../components/format.js'

// En fecha local, no en UTC: con `toISOString()` el periodo por defecto
// empezaba y acababa un día antes durante toda la madrugada, y el informe que
// se entrega a la Inspección salía con un periodo que nadie eligió.
const isoDaysAgo = (days) => {
  const day = new Date()
  day.setDate(day.getDate() - days)
  return day.toLocaleDateString('sv-SE')
}

export default function Reports() {
  const { t } = useTranslation()
  const { session } = useAuth()

  // Empty until the list arrives. Seeding it with the current user's id makes
  // MUI warn about an out-of-range value on every render before the query
  // resolves, because at that point the select has no options at all.
  const [employee, setEmployee] = useState('')
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(30))
  const [dateTo, setDateTo] = useState(today())
  // 'person' | 'company' | a department id. An inspection asks for the
  // workforce, and producing two hundred documents one at a time means it does
  // not get done.
  const [scope, setScope] = useState('person')
  const [error, setError] = useState(null)
  const [payrollDay, setPayrollDay] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const [lastFingerprint, setLastFingerprint] = useState('')

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

  // Defaults to whoever is asking: the record they are most likely to want,
  // and an empty field is a dead end. Taken from the session rather than from a
  // loaded list, which was only ever the first page of the workforce.
  if (!employee && session?.user?.id) setEmployee(session.user.id)

  const generate = useMutation({
    mutationFn: generatePayrollSummaries,
    onError: setError,
  })

  const build = useMutation({
    mutationFn: (format) =>
      downloadReport({
        // One of the three, never a mixture: `scope` and `department` are what
        // the server reads to know it is producing many, and sending an
        // employee alongside would look like a contradiction.
        ...(scope === 'person'
          ? { employee }
          : scope === 'company'
            ? { scope: 'company' }
            : { department: scope }),
        date_from: dateFrom,
        date_to: dateTo,
        format,
      }),
    onSuccess: (result) => {
      setError(null)
      setLastFingerprint(result.fingerprint)
      save(result)
    },
    onError: setError,
  })

  const invalidRange = dateTo < dateFrom

  return (
    <>
      <PageHeader
        title={t('Informes')}
        subtitle={t(
          'El documento que se entrega a la Inspección. Recoge el registro de una persona en un periodo, con su origen y las correcciones señaladas.',
        )}
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1.2fr 1fr' } }}>
        <Panel title={t('Registro de jornada')}>
          <Stack sx={{ gap: 2 }}>
            <TextField
              select
              fullWidth
              label={t('De quién')}
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              helperText={
                scope === 'person'
                  ? t('Un documento.')
                  : t('Un PDF por persona dentro de un zip, o un CSV con todo el mundo.')
              }
            >
              <MenuItem value="person">{t('Una persona')}</MenuItem>
              <MenuItem value="company">{t('Toda la empresa')}</MenuItem>
              {departments.length > 0 && <Divider />}
              {departments.map((department) => (
                <MenuItem key={department.id} value={department.id}>
                  {department.name}
                </MenuItem>
              ))}
            </TextField>

            {scope === 'person' && (
              <EmployeePicker
                value={employee}
                onChange={setEmployee}
                helperText={t('Escribe para buscar.')}
              />
            )}

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                type="date"
                label={t('Desde')}
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                fullWidth
                type="date"
                label={t('Hasta')}
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                error={invalidRange}
                helperText={
                  invalidRange ? t('La fecha final no puede ir antes que la inicial.') : ' '
                }
              />
            </Stack>

            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<PictureAsPdfIcon />}
                disabled={(scope === 'person' && !employee) || invalidRange || build.isPending}
                onClick={() => build.mutate('pdf')}
              >
                {t('Descargar PDF')}
              </Button>
              <Button
                variant="outlined"
                startIcon={<TableViewIcon />}
                disabled={(scope === 'person' && !employee) || invalidRange || build.isPending}
                onClick={() => build.mutate('csv')}
              >
                {t('Descargar CSV')}
              </Button>
            </Stack>

            {lastFingerprint && (
              <Alert severity="success" sx={{ mt: 1 }}>
                <Typography variant="body2">{t('Descargado. Huella del documento:')}</Typography>
                <Typography
                  variant="caption"
                  sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
                >
                  {lastFingerprint}
                </Typography>
              </Alert>
            )}
          </Stack>
        </Panel>

        <Panel title={t('Qué contiene y qué no')}>
          <Stack sx={{ gap: 1.5 }}>
            <Typography variant="body2">
              <Trans
                i18nKey="Recoge cada evento con su hora, su tipo y <destacado>cómo llegó al sistema</destacado>. Un fichaje que hizo la persona y uno que hizo una aplicación en su nombre son los dos válidos, pero no son lo mismo, y quien lee el informe tiene derecho a distinguirlos."
                components={{ destacado: <strong /> }}
              />
            </Typography>
            <Typography variant="body2">
              {t(
                'Los días con eventos corregidos van señalados, y los fichajes anulados siguen apareciendo. Un informe que ocultara las correcciones no serviría de prueba.',
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t(
                'La huella SHA-256 permite comprobar que el documento no se ha alterado después de descargarlo. No acredita por sí sola que el registro nunca se tocara: para eso harían falta garantías adicionales.',
              )}
            </Typography>
          </Stack>
        </Panel>

        {/* Art. 6.1: el resumen que acompaña a la nómina. Estaba construido en
            el backend, con su periodo atado al ciclo de pago de la empresa, y
            no había ninguna pantalla desde la que generarlo. */}
        <Panel
          title={t('Resumen para la nómina')}
          hint={t(
            'Art. 6.1: se entrega junto al recibo de salarios. El periodo lo fija el ciclo de pago de la empresa, no esta pantalla.',
          )}
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="date"
              label={t('Un día del periodo')}
              value={payrollDay}
              onChange={(event) => setPayrollDay(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={t('Cualquier día dentro del periodo que se quiere cerrar.')}
            />

            <Button
              variant="outlined"
              startIcon={<ReceiptLongIcon />}
              disabled={generate.isPending}
              onClick={() => generate.mutate(payrollDay)}
            >
              {t('Generar los de toda la plantilla')}
            </Button>

            {generate.data && (
              <Alert severity="success" onClose={() => generate.reset()}>
                {t('{{cuantos}} para {{desde}} → {{hasta}}.', {
                  cuantos: `${generate.data.generated} ${plural(
                    generate.data.generated,
                    t('resumen generado'),
                    t('resúmenes generados'),
                  )}`,
                  desde: generate.data.period.from,
                  hasta: generate.data.period.to,
                })}
                {generate.data.without_hours.length > 0 && (
                  <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
                    {/* Quién queda fuera es la pregunta que se hace quien cierra
                        la nómina, así que se dice y no se calla. */}
                    {t('Sin horas en el periodo, y por tanto sin resumen: {{quienes}}.', {
                      quienes: generate.data.without_hours.join(', '),
                    })}
                  </Box>
                )}
              </Alert>
            )}
          </Stack>
        </Panel>
      </Box>
    </>
  )
}
