import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import TableViewIcon from '@mui/icons-material/TableView'

import { downloadReport } from '../../services/api.js'
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
  const [error, setError] = useState(null)
  const [lastFingerprint, setLastFingerprint] = useState('')

  // Defaults to whoever is asking: the record they are most likely to want,
  // and an empty field is a dead end. Taken from the session rather than from a
  // loaded list, which was only ever the first page of the workforce.
  if (!employee && session?.user?.id) setEmployee(session.user.id)

  const build = useMutation({
    mutationFn: (format) =>
      downloadReport({ employee, date_from: dateFrom, date_to: dateTo, format }),
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
            <EmployeePicker
              value={employee}
              onChange={setEmployee}
              helperText="Escribe para buscar."
            />

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
                disabled={!employee || invalidRange || build.isPending}
                onClick={() => build.mutate('pdf')}
              >
                Descargar PDF
              </Button>
              <Button
                variant="outlined"
                startIcon={<TableViewIcon />}
                disabled={!employee || invalidRange || build.isPending}
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
      </Box>
    </>
  )
}
