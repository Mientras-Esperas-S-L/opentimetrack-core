/** «Instalar la aplicación»: un icono en la barra superior y, en el móvil,
 *  una opción del menú de la cuenta.
 *
 *  En el móvil va al menú porque en la barra no cabe: un icono más dejaba el
 *  nombre de la instalación en «Open…».
 *
 *  Solo aparece cuando sirve: si el navegador ofrece instalarla, o en un
 *  iPhone, donde hay que hacerlo a mano. Dentro de la aplicación ya instalada
 *  no sale, y en Chrome tampoco cuando ya está instalada: el navegador deja de
 *  ofrecerla.
 *
 *  En el iPhone importa más de lo que parece: allí los avisos de fichaje solo
 *  llegan con la aplicación en la pantalla de inicio.
 */

import { useSyncExternalStore } from 'react'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import InstallMobileIcon from '@mui/icons-material/InstallMobile'
import IosShareIcon from '@mui/icons-material/IosShare'

import { useTranslation } from 'react-i18next'

import {
  closeHowTo,
  howToShown,
  installMode,
  markInstalled,
  startInstall,
  subscribeInstall,
} from '../services/install.js'

const useInstallMode = () => useSyncExternalStore(subscribeInstall, installMode)

/** El icono de la barra, de `sm` para arriba, y las instrucciones del iPhone,
 *  que viven aquí porque este componente no se desmonta nunca. */
export default function InstallButton() {
  const { t } = useTranslation()
  const mode = useInstallMode()
  const howToOpen = useSyncExternalStore(subscribeInstall, howToShown)

  return (
    <>
      {mode && (
        <Tooltip title={t('Instalar la aplicación')}>
          <IconButton
            onClick={startInstall}
            aria-label={t('Instalar la aplicación')}
            sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
          >
            <InstallMobileIcon />
          </IconButton>
        </Tooltip>
      )}

      <Dialog open={howToOpen} onClose={closeHowTo} maxWidth="xs">
        <DialogTitle>{t('Instalar en el iPhone')}</DialogTitle>
        <DialogContent>
          <Typography component="ol" sx={{ pl: 2.5, m: 0, '& li': { mb: 1 } }}>
            <li>
              {t('Pulsa el botón de compartir')}{' '}
              <IosShareIcon fontSize="small" sx={{ verticalAlign: 'text-bottom' }} />
            </li>
            <li>{t('Elige «Añadir a pantalla de inicio».')}</li>
            <li>{t('Pulsa «Añadir».')}</li>
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            {t('En el iPhone, los avisos de fichaje solo llegan con la aplicación instalada.')}
          </Typography>
        </DialogContent>
        <DialogActions>
          {/* Safari no puede saber si ya está instalada: lo dice la persona. */}
          <Button onClick={markInstalled}>{t('Ya la tengo instalada')}</Button>
          <Button onClick={closeHowTo}>{t('Cerrar')}</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

/** La misma opción dentro del menú de la cuenta, solo en el móvil. `onClick`
 *  cierra el menú. */
export function InstallMenuItem({ onClick }) {
  const { t } = useTranslation()
  const mode = useInstallMode()
  if (!mode) return null
  return (
    <MenuItem
      onClick={() => {
        onClick?.()
        startInstall()
      }}
      sx={{ display: { xs: 'flex', sm: 'none' } }}
    >
      {t('Instalar la aplicación')}
    </MenuItem>
  )
}
