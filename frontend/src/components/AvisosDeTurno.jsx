import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

import { getMyShiftNotices, readShiftNotice } from '../services/api.js'
import { queCambio } from './cambiosDeTurno.js'
import { capitalised, dateOf, timeOf } from './format.js'
import { ErrorNote } from './common.jsx'

/** Los cambios de turno que la persona aún no ha visto.
 *
 *  Pedirlos es lo que hace constar que le llegaron, y «Entendido» que los ha
 *  visto: el RD 723/2026 pide a la empresa poder probar las dos cosas cuando
 *  avisa por un canal electrónico. Por eso no se esconden solos ni se marcan
 *  al pasar por encima: lo dice la persona, con un botón.
 */
export default function AvisosDeTurno() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const { data } = useQuery({
    queryKey: ['shift-notices', 'mine'],
    queryFn: getMyShiftNotices,
    refetchInterval: 5 * 60 * 1000,
  })

  const visto = useMutation({
    mutationFn: readShiftNotice,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shift-notices'] }),
  })

  const avisos = data?.rows ?? []
  if (avisos.length === 0) return null

  return (
    <Stack sx={{ gap: 1.5, mb: 2 }}>
      <ErrorNote error={visto.error} onClose={() => visto.reset()} />
      {avisos.map((aviso) => (
        <Alert
          key={aviso.id}
          severity="warning"
          variant="outlined"
          action={
            <Button
              color="inherit"
              size="small"
              disabled={visto.isPending}
              onClick={() => visto.mutate(aviso.id)}
            >
              {t('Entendido')}
            </Button>
          }
        >
          <AlertTitle>{t('Te han cambiado el turno')}</AlertTitle>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {aviso.changes.map((cambio) => (
              <Typography component="li" variant="body2" key={cambio.day}>
                <strong>{capitalised(dateOf(cambio.day, { weekday: 'long' }))}:</strong>{' '}
                {queCambio(cambio, t)}
              </Typography>
            ))}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {aviso.changed_by_name
              ? t('Lo cambió {{quien}} el {{dia}} a las {{hora}}.', {
                  quien: aviso.changed_by_name,
                  dia: dateOf(aviso.created_at),
                  hora: timeOf(aviso.created_at),
                })
              : t('Cambiado el {{dia}} a las {{hora}}.', {
                  dia: dateOf(aviso.created_at),
                  hora: timeOf(aviso.created_at),
                })}{' '}
            {t('Al pulsar «Entendido» queda constancia de que lo has visto.')}
          </Typography>
        </Alert>
      ))}
    </Stack>
  )
}
