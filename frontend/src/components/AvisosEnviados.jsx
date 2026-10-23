import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'

import { downloadShiftNotices, getShiftNotices } from '../services/api.js'
import { capitalised, dateOf, timeOf } from './format.js'
import { ErrorNote, Panel } from './common.jsx'
import { queCambio } from './cambiosDeTurno.js'

const cuando = (iso) => `${dateOf(iso)} ${timeOf(iso)}`

/** Los avisos de cambio de turno que se han mandado, y en qué quedó cada uno.
 *
 *  Es la prueba que pide el RD 723/2026 cuando se avisa por un canal
 *  electrónico: cuándo se envió, cuándo llegó a la persona y cuándo lo leyó.
 *  Las horas las pone el servidor y no se pueden cambiar después. La descarga
 *  lleva todos, no solo los de esta pantalla.
 */
export default function AvisosEnviados() {
  const { t } = useTranslation()
  const [error, setError] = useState(null)

  const { data } = useQuery({
    // Bajo `roster`: cada cambio del cuadrante lo refresca, y es justo cuando
    // aparecen avisos nuevos.
    queryKey: ['roster', 'avisos'],
    queryFn: () => getShiftNotices(),
  })

  // Los diez últimos a la vista; el resto, en la descarga.
  const avisos = (data?.rows ?? []).slice(0, 10)
  if (avisos.length === 0) return null

  return (
    <Panel
      title={t('Avisos de cambios de turno')}
      hint={t(
        'A quien le cambia el turno se le avisa por correo, en el navegador y en la aplicación, unos minutos después del último cambio y solo con lo que de verdad cambió. Aquí consta cuándo le llegó y cuándo dijo que lo había visto.',
      )}
      action={
        <Button
          size="small"
          startIcon={<DownloadIcon />}
          onClick={() => downloadShiftNotices().catch(setError)}
        >
          {t('Descargar todos')}
        </Button>
      }
      sx={{ mb: 3 }}
    >
      <ErrorNote error={error} onClose={() => setError(null)} />
      <Stack sx={{ gap: 1 }}>
        {avisos.map((aviso) => (
          <Box
            key={aviso.id}
            sx={{ borderBottom: 1, borderColor: 'divider', pb: 1, '&:last-child': { border: 0 } }}
          >
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              sx={{ justifyContent: 'space-between', gap: 1 }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {aviso.employee_name}
                </Typography>
                {aviso.changes.slice(0, 3).map((cambio) => (
                  <Typography variant="body2" key={cambio.day}>
                    {capitalised(dateOf(cambio.day, { weekday: 'short' }))}: {queCambio(cambio, t)}
                  </Typography>
                ))}
                {aviso.changes.length > 3 && (
                  <Typography variant="body2" color="text.secondary">
                    {t('y {{cuantos}} días más', { cuantos: aviso.changes.length - 3 })}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary">
                  {t('Enviado el {{cuando}}', { cuando: cuando(aviso.created_at) })}
                </Typography>
              </Box>
              <Stack
                direction="row"
                sx={{ gap: 0.5, flexWrap: 'wrap', alignItems: 'flex-start', flexShrink: 0 }}
              >
                {aviso.short_notice && (
                  <Chip
                    size="small"
                    color="warning"
                    label={t('{{dias}} días de preaviso', { dias: aviso.notice_days })}
                  />
                )}
                <Chip
                  size="small"
                  variant="outlined"
                  color={aviso.delivered_at ? 'success' : 'default'}
                  label={
                    aviso.delivered_at
                      ? t('Llegó {{cuando}} · {{donde}}', {
                          cuando: cuando(aviso.delivered_at),
                          donde: aviso.delivered_via,
                        })
                      : t('Aún no ha llegado')
                  }
                />
                <Chip
                  size="small"
                  color={aviso.read_at ? 'success' : 'default'}
                  label={
                    aviso.read_at
                      ? t('Leído {{cuando}}', { cuando: cuando(aviso.read_at) })
                      : t('Sin leer')
                  }
                />
              </Stack>
            </Stack>
          </Box>
        ))}
      </Stack>
    </Panel>
  )
}
