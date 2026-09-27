import { useEffect, useState } from 'react'
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

import { discoverSso, requestPasswordReset, startSso } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'
import { INSTALLATION_NAME } from '../installation.js'

export default function SignIn() {
  const { t } = useTranslation()
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [taxId, setTaxId] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  // Por qué el proveedor no dejó entrar, si es que se vuelve de él. Se lee **al
  // montar** y no en un efecto que escriba estado: el motivo ya está en la
  // dirección cuando la pantalla aparece, así que es un valor inicial, no algo
  // que pase después.
  //
  // Llega por la dirección porque quien vuelve es un navegador, no una
  // integración: antes acababa mirando el JSON de la API, que no le dice nada a
  // quien solo quería fichar.
  const [rechazoDelProveedor] = useState(() => new URLSearchParams(window.location.search).get('sso_error'))

  useEffect(() => {
    // Se limpia de la barra para que recargar no repita el aviso.
    if (rechazoDelProveedor) window.history.replaceState({}, '', window.location.pathname)
  }, [rechazoDelProveedor])

  // El servidor manda un código; aquí se convierte en una frase que dice qué
  // hacer. `person_not_here` es el caso frecuente y el que más despista: la
  // empresa sí usa este sistema, pero a esa persona no la ha dado de alta nadie,
  // y este proveedor no da de alta por su cuenta, a propósito.
  const porQueNoEntro = {
    person_not_here: t(
      'Tu empresa usa este sistema, pero aquí no consta nadie con esa cuenta. Habla con quien lleve el registro de jornada.'
    ),
    person_inactive: t('Esa cuenta ya no está activa aquí.'),
    company_inactive: t('El acceso de tu empresa está desactivado. Habla con quien lleve el registro de jornada.'),
    provider_refused: t('Tu empresa no ha autorizado la entrada.'),
    provider_unknown: t('El proveedor de identidad de tu empresa ya no está disponible aquí.'),
    issuer_mismatch: t('El proveedor de identidad no es el que esta instalación tiene configurado.'),
    provider_keys_unavailable: t('No se han podido comprobar las claves de tu proveedor de identidad.'),
    provider_unreachable: t('No se ha podido hablar con el proveedor de identidad de tu empresa.'),
    // Se llegó al inicio sin el secreto que ata la entrada a este navegador: un
    // enlace guardado o una pestaña de antes. Basta con volver a pulsar el botón.
    start_from_sign_in: t('Vuelve a pulsar el botón de tu empresa para entrar.'),
  }
  const avisoDeError =
    error ??
    (rechazoDelProveedor
      ? (porQueNoEntro[rechazoDelProveedor] ?? t('No se ha podido completar la entrada. Vuelve a intentarlo.'))
      : null)

  // 'in' | 'recover' | 'sent'. Inline rather than a dialog: the screen has one
  // job and losing it behind a modal for a flow this short is noise.
  const [mode, setMode] = useState('in')

  // Only asked for when the server says the address exists in more than one
  // company. Nobody should have to type a tax number to clock in.
  const [needsCompany, setNeedsCompany] = useState(false)
  // Their company's identity provider, if their address belongs to one. Asked of
  // the server as they type, because the only thing they know is their address:
  // which identity system their employer uses is not their problem.
  const [provider, setProvider] = useState(null)

  useEffect(() => {
    let vivo = true
    // Waits for them to stop typing: one call per address, not per keystroke. And
    // everything happens inside the timer, so nothing is set while rendering.
    const timer = setTimeout(async () => {
      if (mode !== 'in' || !email.includes('@')) {
        if (vivo) setProvider(null)
        return
      }
      try {
        const answer = await discoverSso(email)
        if (vivo) setProvider(answer?.sso ? answer : null)
      } catch {
        // If we cannot ask, the password field is still there and still works.
        if (vivo) setProvider(null)
      }
    }, 500)
    return () => {
      vivo = false
      clearTimeout(timer)
    }
  }, [email, mode])

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
        {INSTALLATION_NAME}
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
              {avisoDeError && (
                <Alert severity="error" variant="outlined">
                  {avisoDeError}
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

              {mode === 'in' && provider && (
                // Their provider signs them in, so there is no password of ours to
                // ask for. The field below disappears rather than sitting there
                // unusable: a box you must not fill in is worse than no box.
                <Stack spacing={1.5}>
                  <Alert severity="info" variant="outlined">
                    {t('Tu empresa usa {{provider}} para identificarte.', {
                      provider: provider.provider,
                    })}
                  </Alert>
                  <Button
                    variant="contained"
                    size="large"
                    fullWidth
                    onClick={() => startSso(provider.slug)}
                  >
                    {t('Entrar con {{provider}}', { provider: provider.provider })}
                  </Button>
                </Stack>
              )}
              {mode === 'in' && !provider && (
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

              {/* Con proveedor no hay nada que enviar aquí: el botón de arriba se
                  lleva la entrada, y este sobraría en la pantalla. */}
              {!(mode === 'in' && provider) && (
                <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
                  {mode === 'in'
                    ? busy
                      ? t('Entrando…')
                      : t('Entrar')
                    : busy
                      ? t('Enviando…')
                      : t('Enviarme un enlace')}
                </Button>
              )}

              {/* Quien entra por su proveedor no tiene contraseña aquí que recuperar:
                  ofrecérsela sería mandarle a un correo que no sirve de nada. */}
              <Box sx={{ textAlign: 'center', display: mode === 'in' && provider ? 'none' : 'block' }}>
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
