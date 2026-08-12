import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import VisibilityIcon from '@mui/icons-material/Visibility'

import { getAuditTrail } from '../../services/api.js'
import { Empty, Loading, PageHeader } from '../../components/common.jsx'
import { dateOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

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
                {String(value[0])}
              </Box>{' '}
              → <strong>{String(value[1])}</strong>
            </>
          ) : (
            String(value)
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

  const { data, isLoading } = useQuery({
    queryKey: ['audit', action],
    queryFn: () => getAuditTrail(action ? { action } : {}),
  })

  const rows = data ?? []

  return (
    <>
      <PageHeader
        title="Registro de actividad"
        subtitle={
          isAdmin
            ? 'Qué se ha hecho y quién lo hizo. No se puede modificar ni borrar: la base de datos lo impide, también para la administración.'
            : 'Quién ha consultado tu registro y qué se ha cambiado sobre ti. Nadie puede borrar estas entradas.'
        }
      />

      <TextField
        select
        size="small"
        label="Qué mostrar"
        value={action}
        onChange={(event) => setAction(event.target.value)}
        sx={{ minWidth: 300, mb: 2 }}
      >
        {GROUPS.map((group) => (
          <MenuItem key={group.value} value={group.value}>
            {group.label}
          </MenuItem>
        ))}
      </TextField>

      {isLoading ? (
        <Loading rows={6} />
      ) : rows.length === 0 ? (
        <Empty>No hay entradas que mostrar.</Empty>
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

      {rows.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          Consultar tu propio registro no deja entrada: es un derecho, y anotarlo enterraría lo
          que sí importa. {dateOf(new Date().toISOString())}
        </Typography>
      )}
    </>
  )
}
