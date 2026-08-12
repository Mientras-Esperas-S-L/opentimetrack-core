import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import LinearProgress from '@mui/material/LinearProgress'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { setPasswordFromLink } from '../services/api.js'
import { ErrorNote } from '../components/common.jsx'
import { useAuth } from '../hooks/useAuth.js'

const MINIMUM = 12

/** Where the link in the email lands.
 *
 *  It has to render without a session, which is why the router mounts this
 *  route outside the sign-in check. Before this page existed the link fell
 *  through to the catch-all and redirected to the clock, so an invited person
 *  arrived at a sign-in screen with no way to get a password at all.
 */
export default function SetPassword() {
  const { uid, token } = useParams()
  const { setSession } = useAuth()
  const navigate = useNavigate()

  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState(null)

  const submit = useMutation({
    mutationFn: () => setPasswordFromLink({ uid, token, password }),
    onSuccess: (data) => {
      // Straight in. Asking somebody to type the password they chose four
      // seconds ago is a test, not a safeguard.
      setSession({ user: data.user, tenant: data.tenant })

      // And off this URL. The route is public, so it keeps matching after the
      // session exists: without this the person ends up signed in and still
      // looking at the form, and pressing the button again tells them the link
      // has already been used --- which is true, and reads like a failure.
      navigate('/', { replace: true })
    },
    onError: setError,
  })

  const tooShort = password.length > 0 && password.length < MINIMUM
  const mismatch = repeat.length > 0 && repeat !== password
  const ready = password.length >= MINIMUM && repeat === password

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        p: 2,
      }}
    >
      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, width: '100%', maxWidth: 440 }}>
        <Typography variant="h6" sx={{ mb: 0.5 }}>
          Elige tu contraseña
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Con ella entrarás a partir de ahora. El enlace sirve una sola vez.
        </Typography>

        <ErrorNote error={error} onClose={() => setError(null)} />

        <form
          onSubmit={(event) => {
            event.preventDefault()
            setError(null)
            submit.mutate()
          }}
        >
          <Stack sx={{ gap: 2 }}>
            <TextField
              autoFocus
              required
              fullWidth
              type="password"
              label="Contraseña"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={tooShort}
              helperText={
                tooShort
                  ? `Faltan ${MINIMUM - password.length} caracteres.`
                  : `Al menos ${MINIMUM} caracteres.`
              }
            />
            <TextField
              required
              fullWidth
              type="password"
              label="Repítela"
              autoComplete="new-password"
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
              error={mismatch}
              helperText={mismatch ? 'No coincide con la anterior.' : ' '}
            />

            {submit.isPending && <LinearProgress />}

            <Button type="submit" variant="contained" size="large" disabled={!ready || submit.isPending}>
              Guardar y entrar
            </Button>
          </Stack>
        </form>

        <Alert severity="info" variant="outlined" sx={{ mt: 3 }}>
          Si el enlace ha caducado o ya lo has usado, pide otro desde{' '}
          <strong>He olvidado mi contraseña</strong> en la pantalla de acceso.
        </Alert>
      </Paper>
    </Box>
  )
}
