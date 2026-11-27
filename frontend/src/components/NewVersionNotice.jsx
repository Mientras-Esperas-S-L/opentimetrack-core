/** «Hay una versión nueva»: el aviso de arriba, con su botón de recargar.
 *
 *  Fuera de las rutas, junto a la aplicación entera: sale también en la
 *  pantalla de entrar, que es justo la que se queda abierta días en un móvil.
 *
 *  No se cierra solo ni recarga solo. Quien está pidiendo una ausencia termina
 *  y luego pulsa.
 *
 *  En el APK el botón descarga la versión nueva, que Android pide confirmar
 *  antes de instalarla encima. "Ahora no" lo calla hasta que se vuelva a abrir.
 */

import { useState } from 'react'

import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Snackbar from '@mui/material/Snackbar'

import { useTranslation } from 'react-i18next'

import { useNewVersion } from '../hooks/useNewVersion.js'
import { openInSystemBrowser } from '../services/appLinks.js'

export default function NewVersionNotice() {
  const { t } = useTranslation()
  const available = useNewVersion()
  const [later, setLater] = useState(false)
  const apk = available?.apk

  return (
    <Snackbar
      open={Boolean(available) && !later}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
    >
      <Alert
        severity="info"
        variant="filled"
        action={
          apk ? (
            <>
              <Button color="inherit" size="small" onClick={() => setLater(true)}>
                {t('Ahora no')}
              </Button>
              <Button
                color="inherit"
                size="small"
                onClick={() => openInSystemBrowser(apk).catch(() => {})}
              >
                {t('Descargar')}
              </Button>
            </>
          ) : (
            <Button color="inherit" size="small" onClick={() => window.location.reload()}>
              {t('Actualizar')}
            </Button>
          )
        }
      >
        {t('Hay una versión nueva de la aplicación.')}
      </Alert>
    </Snackbar>
  )
}
