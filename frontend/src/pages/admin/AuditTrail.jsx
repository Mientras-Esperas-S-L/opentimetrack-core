import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import VisibilityIcon from '@mui/icons-material/Visibility'

import { downloadAuditTrail, getAuditTrail, PAGE_SIZE } from '../../services/api.js'
import { Empty, Loading, PageHeader, Pager } from '../../components/common.jsx'
import { dateOf, firstOfThisMonth, today } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'
import EmployeePicker from '../../components/EmployeePicker.jsx'

/** Entries that are somebody reading, as opposed to somebody changing.
 *
 *  Drawn apart because they answer a different question. A change is expected
 *  and has a form behind it; a read is the one nobody announces, and it is what
 *  a worker comes to this screen to find out about.
 */
const READS = new Set(['RECORD_VIEWED', 'REPORT_EXPORTED', 'DOCUMENT_DOWNLOADED'])

const GROUPS = [
  { value: '', label: 'Todo' },
  { value: 'RECORD_VIEWED', label: 'Lecturas de registros ajenos' },
  { value: 'DOCUMENT_DOWNLOADED', label: 'Descargas de justificantes' },
  { value: 'REPORT_EXPORTED', label: 'Exportaciones de informes' },
  { value: 'ROLE_CHANGED', label: 'Cambios de perfil' },
  { value: 'SETTINGS_CHANGED', label: 'Cambios de ajustes' },
  { value: 'CORRECTION_APPROVED', label: 'Correcciones aprobadas' },
]

function when(iso) {
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Un valor del rastro, escrito para que lo lea una persona.
 *
 *  `String(null)` es «null», y eso es lo que salía en pantalla cuando un campo
 *  estaba vacío: «consulted_on: null → 2024-01-10». Lo destapó la prueba que
 *  vigila `undefined`, `NaN` y `null` en todas las pantallas, a raíz de una
 *  entrada nueva con una fecha opcional --- pero le pasaba a cualquiera, porque
 *  la mitad de los campos del producto se pueden dejar en blanco.
 *
 *  Vacío se escribe con una raya, que es como se escribe vacío en una tabla.
 */
const legible = (valor) => {
  if (valor === null || valor === undefined || valor === '') return '—'
  if (typeof valor === 'boolean') return valor ? 'sí' : 'no'
  return String(valor)
}

/** {campo: [antes, después]} en una línea legible. */
function Changes({ changes }) {
  const entries = Object.entries(changes ?? {})
  if (entries.length === 0) return null

  return (
    <Stack sx={{ mt: 0.5, gap: 0.25 }}>
      {entries.map(([field, value]) => (
        <Typography key={field} variant="caption" color="text.secondary">
          {field}:{' '}
          {Array.isArray(value) && value.length === 2 ? (
            <>
              <Box component="span" sx={{ textDecoration: 'line-through' }}>
                {legible(value[0])}
              </Box>{' '}
              → <strong>{legible(value[1])}</strong>
            </>
          ) : (
            legible(value)
          )}
        </Typography>
      ))}
    </Stack>
  )
}

export default function AuditTrail() {
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'
  const [action, setAction] = useState('')
  //: Quién lo hizo. Solo para la administración: quien mira lo suyo ya sabe de
  //: quién es cada línea, y ofrecerle un filtro de personas sugeriría que
  //: puede mirar las de otros.
  const [actor, setActor] = useState('')

  // A month, not "the most recent fifty". An inspection asks for a period, and
  // before this the screen had no way to express one: it showed one page and
  // said nothing about the rest of the trail.
  const [from, setFrom] = useState(firstOfThisMonth)
  const [to, setTo] = useState(today)
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)

  const narrow = (set) => (value) => {
    set(value)
    setPage(1)
  }

  const { data, isLoading } = useQuery({
    queryKey: ['audit', { action, actor, from, to, page }],
    queryFn: () =>
      getAuditTrail({
        ...(action ? { action } : {}),
        ...(actor ? { actor } : {}),
        date_from: from,
        date_to: to,
        page,
      }),
    placeholderData: (previous) => previous,
  })

  const rows = data?.rows ?? []

  return (
    <>
      <PageHeader
        action={
          isAdmin && (
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              disabled={exporting}
              onClick={async () => {
                setExporting(true)
                try {
                  // Lo que se descarga es lo que se está viendo. Un fichero
                  // más ancho que la pantalla es la forma callada de entregar
                  // de más.
                  await downloadAuditTrail({
                    ...(action ? { action } : {}),
                    ...(actor ? { actor } : {}),
                    date_from: from,
                    date_to: to,
                  })
                } finally {
                  setExporting(false)
                }
              }}
            >
              Descargar
            </Button>
          )
        }
        title="Registro de actividad"
        subtitle={
          isAdmin
            ? 'Qué se ha hecho y quién lo hizo. No se puede modificar ni borrar: la base de datos lo impide, también para la administración.'
            : 'Quién ha consultado tu registro y qué se ha cambiado sobre ti. Nadie puede borrar estas entradas.'
        }
      />

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{ gap: 2, mb: 2, alignItems: { sm: 'flex-start' }, flexWrap: 'wrap' }}
      >
        <TextField
          select
          size="small"
          label="Qué mostrar"
          value={action}
          onChange={(event) => narrow(setAction)(event.target.value)}
          sx={{ minWidth: 300 }}
        >
          {GROUPS.map((group) => (
            <MenuItem key={group.value} value={group.value}>
              {group.label}
            </MenuItem>
          ))}
        </TextField>
        {isAdmin && (
          <EmployeePicker
            size="small"
            label="Quién"
            value={actor}
            onChange={(id) => narrow(setActor)(id)}
            everyoneLabel="Cualquiera"
            sx={{ minWidth: 240 }}
          />
        )}
        <TextField
          size="small"
          type="date"
          label="Desde"
          value={from}
          onChange={(event) => narrow(setFrom)(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Hasta"
          value={to}
          onChange={(event) => narrow(setTo)(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          error={to < from}
          helperText={to < from ? 'Va antes que la inicial.' : ' '}
        />
      </Stack>

      {isLoading ? (
        <Loading rows={6} />
      ) : rows.length === 0 ? (
        <Empty>No hay entradas en ese periodo.</Empty>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {rows.map((entry) => {
            const isRead = READS.has(entry.action)
            return (
              <Paper
                key={entry.id}
                variant="outlined"
                sx={{
                  p: 1.5,
                  // Una lectura lleva marca al margen: es la que nadie anuncia.
                  borderLeft: 3,
                  borderLeftColor: isRead ? 'secondary.main' : 'divider',
                }}
              >
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  sx={{ gap: 1.5, justifyContent: 'space-between' }}
                >
                  <Box sx={{ minWidth: 0 }}>
                    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      {isRead && <VisibilityIcon sx={{ fontSize: 15, color: 'secondary.main' }} />}
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {entry.action_display}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {entry.actor_label || 'sistema'}
                      {entry.target_label && ` · sobre ${entry.target_label}`}
                    </Typography>
                    {entry.note && (
                      <Typography variant="caption" sx={{ fontStyle: 'italic' }}>
                        {entry.note}
                      </Typography>
                    )}
                    <Changes changes={entry.changes} />
                  </Box>

                  <Stack sx={{ alignItems: { sm: 'flex-end' }, flexShrink: 0 }}>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {when(entry.at)}
                    </Typography>
                    {entry.ip_address && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={entry.ip_address}
                        sx={{ height: 18, fontSize: '0.62rem', mt: 0.5 }}
                      />
                    )}
                  </Stack>
                </Stack>
              </Paper>
            )
          })}
        </Stack>
      )}

      <Pager
        count={data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        noun="entradas"
      />

      {rows.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          Consultar tu propio registro no deja entrada: es un derecho, y anotarlo enterraría lo que
          sí importa. {dateOf(new Date().toISOString())}
        </Typography>
      )}
    </>
  )
}
