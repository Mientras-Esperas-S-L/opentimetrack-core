import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Container from '@mui/material/Container'
import Link from '@mui/material/Link'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { requestPasswordReset } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'

export default function SignIn() {
  const { t } = useTranslation()
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [taxId, setTaxId] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  // 'in' | 'recover' | 'sent'. Inline rather than a dialog: the screen has one
  // job and losing it behind a modal for a flow this short is noise.
  const [mode, setMode] = useState('in')

  // Only asked for when the server says the address exists in more than one
  // company. Nobody should have to type a tax number to clock in.
  const [needsCompany, setNeedsCompany] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn({ email, password, ...(taxId ? { tax_id: taxId } : {}) })
    } catch (failure) {
      setError(failure.message)
      if (!needsCompany) setNeedsCompany(true)
    } finally {
      setBusy(false)
    }
  }

  const recover = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await requestPasswordReset(email)
      setMode('sent')
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Container maxWidth="xs" sx={{ py: 10 }}>
      <Typography variant="h1" gutterBottom>
        OpenTimeTrack
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        {mode === 'in'
          ? t('Entra para registrar tu jornada.')
          : t('Recupera el acceso a tu cuenta.')}
      </Typography>

      <Paper variant="outlined" sx={{ p: 3 }}>
        {mode === 'sent' ? (
          <Stack spacing={2.5}>
            {/* Deliberately says the same thing whether the address exists or
                not. Confirming that it does would turn this box into a way of
                finding out who works where. */}
            <Alert severity="success" variant="outlined">
              {t(
                'Si esa dirección tiene cuenta, le hemos enviado un enlace para elegir contraseña. Caduca en 24 horas.',
              )}
            </Alert>
            <Typography variant="body2" color="text.secondary">
              {t('Revisa también la carpeta de correo no deseado.')}
            </Typography>
            <Button
              onClick={() => {
                setMode('in')
                setPassword('')
              }}
              fullWidth
            >
              {t('Volver')}
            </Button>
          </Stack>
        ) : (
          <Box component="form" onSubmit={mode === 'in' ? submit : recover} noValidate>
            <Stack spacing={2.5}>
              {error && (
                <Alert severity="error" variant="outlined">
                  {error}
                </Alert>
              )}

              <TextField
                label={t('Correo electrónico')}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                fullWidth
              />

              {mode === 'in' && (
                <>
                  <TextField
                    label={t('Contraseña')}
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    fullWidth
                  />

                  {needsCompany && (
                    <TextField
                      label={t('CIF o NIF de la empresa')}
                      value={taxId}
                      onChange={(e) => setTaxId(e.target.value)}
                      helperText={t(
                        'Solo hace falta cuando el mismo correo pertenece a varias empresas.',
                      )}
                      fullWidth
                    />
                  )}
                </>
              )}

              <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
                {mode === 'in'
                  ? busy
                    ? t('Entrando…')
                    : t('Entrar')
                  : busy
                    ? t('Enviando…')
                    : t('Enviarme un enlace')}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Link
                  component="button"
                  type="button"
                  variant="body2"
                  underline="hover"
                  onClick={() => {
                    setMode(mode === 'in' ? 'recover' : 'in')
                    setError(null)
                  }}
                >
                  {mode === 'in'
                    ? t('He olvidado mi contraseña')
                    : t('Volver a entrar con mi contraseña')}
                </Link>
              </Box>
            </Stack>
          </Box>
        )}
      </Paper>
    </Container>
  )
}
