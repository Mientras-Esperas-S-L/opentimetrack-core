import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Container from '@mui/material/Container'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

import { collectSsoSession } from '../services/api.js'

/** Donde aterriza quien vuelve de su proveedor de identidad.
 *
 *  Antes de esta pantalla, el viaje acababa en la respuesta de la API: quien entraba
 *  con la cuenta de su empresa se quedaba mirando un JSON con sus testigos dentro.
 *  Funcionaba para un integrador y no para una persona.
 *
 *  Lo único que hace es cambiar el vale por la sesión y entrar. No pide nada ni
 *  decide nada: quien decidió si esa persona puede entrar fue su proveedor.
 */
export default function SsoLanding() {
  const { t } = useTranslation()
  // El vale se lee al montar y no dentro del efecto: leer la dirección no es un
  // efecto, y decidir ahí que falta obligaba a cambiar el estado en mitad del
  // render, que es lo que el aviso de React señala.
  const [ticket] = useState(() => new URLSearchParams(window.location.search).get('ticket'))
  const [error, setError] = useState(() =>
    ticket ? null : t('Falta el identificador de la entrada. Vuelve a intentarlo desde la pantalla de acceso.')
  )

  useEffect(() => {
    if (!ticket) return
    collectSsoSession(ticket)
      .then(() => {
        // A la portada y **sin dejar rastro en el historial**: el vale ya está
        // gastado, así que volver atrás llevaría a una pantalla que sólo puede
        // fallar. `replace` la quita de en medio.
        window.location.replace('/')
      })
      .catch((fallo) => setError(fallo.message))
  }, [ticket])

  return (
    <Container maxWidth="xs" sx={{ py: 12 }}>
      {error ? (
        <Stack spacing={2.5}>
          <Alert severity="error" variant="outlined">
            {error}
          </Alert>
          <Button href="/" variant="contained" fullWidth>
            {t('Volver a la pantalla de acceso')}
          </Button>
        </Stack>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <CircularProgress />
          <Typography color="text.secondary">{t('Entrando…')}</Typography>
        </Box>
      )}
    </Container>
  )
}
