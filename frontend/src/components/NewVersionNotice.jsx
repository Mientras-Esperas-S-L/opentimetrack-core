/** «Hay una versión nueva»: el aviso de arriba, con su botón de recargar.
 *
 *  Fuera de las rutas, junto a la aplicación entera: sale también en la
 *  pantalla de entrar, que es justo la que se queda abierta días en un móvil.
 *
 *  No se cierra solo ni recarga solo. Quien está pidiendo una ausencia termina
 *  y luego pulsa.
 */

import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Snackbar from '@mui/material/Snackbar'

import { useTranslation } from 'react-i18next'

import { useNewVersion } from '../hooks/useNewVersion.js'

export default function NewVersionNotice() {
  const { t } = useTranslation()
  const available = useNewVersion()

  return (
    <Snackbar open={available} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
      <Alert
        severity="info"
        variant="filled"
        action={
          <Button color="inherit" size="small" onClick={() => window.location.reload()}>
            {t('Actualizar')}
          </Button>
        }
      >
        {t('Hay una versión nueva de la aplicación.')}
      </Alert>
    </Snackbar>
  )
}
