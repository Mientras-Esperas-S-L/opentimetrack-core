import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Container from '@mui/material/Container'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { useAuth } from '../hooks/useAuth.js'

export default function SignIn() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [taxId, setTaxId] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

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

  return (
    <Container maxWidth="xs" sx={{ py: 10 }}>
      <Typography variant="h1" gutterBottom>
        OpenTimeTrack
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Sign in to record your working time.
      </Typography>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Box component="form" onSubmit={submit} noValidate>
          <Stack spacing={2.5}>
            {error && (
              <Alert severity="error" variant="outlined">
                {error}
              </Alert>
            )}

            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              autoFocus
              required
              fullWidth
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              fullWidth
            />

            {needsCompany && (
              <TextField
                label="Company tax number"
                value={taxId}
                onChange={(e) => setTaxId(e.target.value)}
                helperText="Only needed when the same address belongs to several companies."
                fullWidth
              />
            )}

            <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </Stack>
        </Box>
      </Paper>
    </Container>
  )
}
