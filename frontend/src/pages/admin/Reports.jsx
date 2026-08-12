import { useState } from 'react'
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

import {
  downloadReport,
  generatePayrollSummaries,
  getDepartments,
} from '../../services/api.js'
import EmployeePicker from '../../components/EmployeePicker.jsx'
import { ErrorNote, PageHeader, Panel } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

const isoDaysAgo = (days) => {
  const day = new Date()
  day.setDate(day.getDate() - days)
  return day.toISOString().slice(0, 10)
}

/** Hands the blob to the browser. Revoking the object URL matters here: these
 *  documents are not small and the tab may stay open all day. */
function save({ blob, filename }) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export default function Reports() {
  const { session } = useAuth()

  // Empty until the list arrives. Seeding it with the current user's id makes
  // MUI warn about an out-of-range value on every render before the query
  // resolves, because at that point the select has no options at all.
  const [employee, setEmployee] = useState('')
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(30))
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10))
  // 'person' | 'company' | a department id. An inspection asks for the
  // workforce, and producing two hundred documents one at a time means it does
  // not get done.
  const [scope, setScope] = useState('person')
  const [error, setError] = useState(null)
  const [payrollDay, setPayrollDay] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const [lastFingerprint, setLastFingerprint] = useState('')

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
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
        title="Informes"
        subtitle="El documento que se entrega a la Inspección. Recoge el registro de una persona en un periodo, con su origen y las correcciones señaladas."
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1.2fr 1fr' } }}>
        <Panel title="Registro de jornada">
          <Stack sx={{ gap: 2 }}>
            <TextField
              select
              fullWidth
              label="De quién"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              helperText={
                scope === 'person'
                  ? 'Un documento.'
                  : 'Un PDF por persona dentro de un zip, o un CSV con todo el mundo.'
              }
            >
              <MenuItem value="person">Una persona</MenuItem>
              <MenuItem value="company">Toda la empresa</MenuItem>
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
                helperText="Escribe para buscar."
              />
            )}

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                type="date"
                label="Desde"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                fullWidth
                type="date"
                label="Hasta"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                error={invalidRange}
                helperText={invalidRange ? 'La fecha final no puede ir antes que la inicial.' : ' '}
              />
            </Stack>

            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<PictureAsPdfIcon />}
                disabled={(scope === 'person' && !employee) || invalidRange || build.isPending}
                onClick={() => build.mutate('pdf')}
              >
                Descargar PDF
              </Button>
              <Button
                variant="outlined"
                startIcon={<TableViewIcon />}
                disabled={(scope === 'person' && !employee) || invalidRange || build.isPending}
                onClick={() => build.mutate('csv')}
              >
                Descargar CSV
              </Button>
            </Stack>

            {lastFingerprint && (
              <Alert severity="success" sx={{ mt: 1 }}>
                <Typography variant="body2">Descargado. Huella del documento:</Typography>
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

        <Panel title="Qué contiene y qué no">
          <Stack sx={{ gap: 1.5 }}>
            <Typography variant="body2">
              Recoge cada evento con su hora, su tipo y <strong>cómo llegó al sistema</strong>. Un
              fichaje que hizo la persona y uno que hizo una aplicación en su nombre son los dos
              válidos, pero no son lo mismo, y quien lee el informe tiene derecho a distinguirlos.
            </Typography>
            <Typography variant="body2">
              Los días con eventos corregidos van señalados, y los fichajes anulados siguen
              apareciendo. Un informe que ocultara las correcciones no serviría de prueba.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              La huella SHA-256 permite comprobar que el documento no se ha alterado después de
              descargarlo. No acredita por sí sola que el registro nunca se tocara: para eso harían
              falta garantías adicionales.
            </Typography>
          </Stack>
        </Panel>

        {/* Art. 6.1: el resumen que acompaña a la nómina. Estaba construido en
            el backend, con su periodo atado al ciclo de pago de la empresa, y
            no había ninguna pantalla desde la que generarlo. */}
        <Panel
          title="Resumen para la nómina"
          hint="Art. 6.1: se entrega junto al recibo de salarios. El periodo lo fija el ciclo de pago de la empresa, no esta pantalla."
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              fullWidth
              type="date"
              label="Un día del periodo"
              value={payrollDay}
              onChange={(event) => setPayrollDay(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText="Cualquier día dentro del periodo que se quiere cerrar."
            />

            <Button
              variant="outlined"
              startIcon={<ReceiptLongIcon />}
              disabled={generate.isPending}
              onClick={() => generate.mutate(payrollDay)}
            >
              Generar los de toda la plantilla
            </Button>

            {generate.data && (
              <Alert severity="success" onClose={() => generate.reset()}>
                {generate.data.generated}{' '}
                {generate.data.generated === 1 ? 'resumen generado' : 'resúmenes generados'} para{' '}
                {generate.data.period.from} → {generate.data.period.to}.
                {generate.data.without_hours.length > 0 && (
                  <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
                    {/* Quién queda fuera es la pregunta que se hace quien cierra
                        la nómina, así que se dice y no se calla. */}
                    Sin horas en el periodo, y por tanto sin resumen:{' '}
                    {generate.data.without_hours.join(', ')}.
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
