import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'

import { changePassword } from '../services/api.js'

/** Cambiar la contraseña propia estando dentro.
 *
 *  No existía: solo se podía con el enlace de «He olvidado mi contraseña», que
 *  depende de que el correo salga. Pide la de ahora, para que un ordenador con la
 *  sesión abierta no baste para quedarse con la cuenta.
 *
 *  El padre lo remonta con una `key` en cada apertura, así que nace vacío.
 */
export default function ChangePasswordDialog({ abierto, onClose }) {
  const { t } = useTranslation()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [errores, setErrores] = useState({})
  const [error, setError] = useState(null)
  const [hecho, setHecho] = useState(false)
  const [guardando, setGuardando] = useState(false)

  const noCoinciden = repetida !== '' && repetida !== nueva

  const guardar = async () => {
    setGuardando(true)
    setError(null)
    setErrores({})
    try {
      await changePassword(actual, nueva)
      setHecho(true)
    } catch (fallo) {
      const campos = Object.fromEntries(
        Object.entries(fallo?.details ?? {}).map(([campo, dichos]) => [
          campo,
          [].concat(dichos).join(' '),
        ]),
      )
      setErrores(campos)
      setError(
        Object.keys(campos).length
          ? null
          : fallo?.message || t('No se ha podido cambiar la contraseña.'),
      )
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Dialog open={abierto} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('Cambiar la contraseña')}</DialogTitle>
      <DialogContent>
        {hecho ? (
          <Alert severity="success" sx={{ mt: 1 }}>
            {t('Contraseña cambiada. Las demás sesiones abiertas con tu cuenta se han cerrado.')}
          </Alert>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              type="password"
              autoComplete="current-password"
              label={t('Contraseña actual')}
              value={actual}
              onChange={(e) => setActual(e.target.value)}
              error={Boolean(errores.current_password)}
              helperText={errores.current_password}
            />
            <TextField
              type="password"
              autoComplete="new-password"
              label={t('Contraseña nueva')}
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              error={Boolean(errores.new_password)}
              helperText={
                errores.new_password || t('Al menos 12 caracteres, y que no sea solo números.')
              }
            />
            <TextField
              type="password"
              autoComplete="new-password"
              label={t('Repite la contraseña nueva')}
              value={repetida}
              onChange={(e) => setRepetida(e.target.value)}
              error={noCoinciden}
              helperText={noCoinciden ? t('No coincide con la nueva.') : ' '}
            />
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {hecho ? (
          <Button variant="contained" onClick={onClose}>
            {t('Cerrar')}
          </Button>
        ) : (
          <>
            <Button onClick={onClose} disabled={guardando}>
              {t('Cancelar')}
            </Button>
            <Button
              variant="contained"
              onClick={guardar}
              disabled={guardando || !actual || nueva.length < 12 || nueva !== repetida}
            >
              {guardando ? t('Guardando…') : t('Cambiar')}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  )
}
