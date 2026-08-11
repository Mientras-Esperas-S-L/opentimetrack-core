import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import LoginIcon from '@mui/icons-material/Login'
import LogoutIcon from '@mui/icons-material/Logout'

import { useAuth } from '../hooks/useAuth.js'
import { clock, getToday } from '../services/api.js'
import { hhmm, timeOf } from '../components/format.js'

/** Counts up while a segment is open, so the figure is not stale on screen.
 *
 * The counter resets by comparing during render rather than from inside the
 * effect: adjusting state when a prop changes is the pattern React documents,
 * and it avoids the extra render that setting state in an effect causes.
 */
function useLiveSeconds(baseSeconds, running) {
  const [counter, setCounter] = useState({ from: baseSeconds, ticks: 0 })

  if (counter.from !== baseSeconds) {
    setCounter({ from: baseSeconds, ticks: 0 })
  }

  useEffect(() => {
    if (!running) return undefined
    const timer = setInterval(
      () => setCounter((current) => ({ ...current, ticks: current.ticks + 1 })),
      1000,
    )
    return () => clearInterval(timer)
  }, [running, baseSeconds])

  return running ? baseSeconds + counter.ticks : baseSeconds
}

const STATES = {
  WORKING: { label: 'Trabajando', color: 'success' },
  OFF: { label: 'Jornada cerrada', color: 'default' },
  NOT_STARTED: { label: 'Sin empezar', color: 'default' },
}

export default function Clock() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)

  const { data: today, isLoading } = useQuery({
    queryKey: ['today'],
    queryFn: getToday,
    refetchInterval: 60000,
  })

  const punch = useMutation({
    mutationFn: () => clock(`web-${navigator.userAgentData?.platform ?? navigator.platform ?? 'unknown'}`),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['today'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
      queryClient.invalidateQueries({ queryKey: ['punches'] })
    },
    onError: setError,
  })

  const working = today?.state === 'WORKING'
  const seconds = useLiveSeconds(today?.worked_seconds ?? 0, working)
  const state = STATES[today?.state] ?? STATES.NOT_STARTED

  return (
    <Box sx={{ maxWidth: 560, mx: 'auto' }}>
      <Typography variant="h1" sx={{ fontSize: '1.5rem', mb: 0.5 }}>
        Hola, {session?.user?.first_name || session?.user?.full_name}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {new Date().toLocaleDateString('es-ES', {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
        })}
      </Typography>

      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center' }}>
        {isLoading ? (
          <CircularProgress />
        ) : (
          <>
            <Chip label={state.label} color={state.color} sx={{ mb: 3 }} />

            <Typography
              sx={{
                fontSize: { xs: '3.2rem', sm: '3.8rem' },
                fontWeight: 300,
                fontVariantNumeric: 'tabular-nums',
                lineHeight: 1,
                mb: 0.5,
              }}
            >
              {hhmm(seconds)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
              trabajadas hoy
            </Typography>

            {error && (
              <Alert
                severity="warning"
                variant="outlined"
                sx={{ mb: 3, textAlign: 'left' }}
                onClose={() => setError(null)}
              >
                {error.message}
              </Alert>
            )}

            {/* One tap. The server decides whether it is an entry or an exit. */}
            <Button
              variant="contained"
              color={working ? 'secondary' : 'primary'}
              size="large"
              startIcon={working ? <LogoutIcon /> : <LoginIcon />}
              onClick={() => punch.mutate()}
              disabled={punch.isPending}
              sx={{ py: 2, px: 6, fontSize: '1.15rem', borderRadius: 2 }}
            >
              {punch.isPending ? 'Registrando…' : working ? 'Fichar salida' : 'Fichar entrada'}
            </Button>
          </>
        )}
      </Paper>

      {today?.segments?.length > 0 && (
        <Paper variant="outlined" sx={{ p: 3, mt: 2 }}>
          <Typography variant="h2" sx={{ fontSize: '1rem', mb: 2 }}>
            Hoy
          </Typography>
          <Stack spacing={1.5} divider={<Divider flexItem />}>
            {today.segments.map((segment) => (
              <Stack
                key={segment.in}
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'center' }}
              >
                <Typography sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {timeOf(segment.in, today.time_zone)}
                  {' → '}
                  {segment.out ? timeOf(segment.out, today.time_zone) : '…'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {hhmm(segment.seconds)}
                </Typography>
              </Stack>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Horas de {today.time_zone}. Las pone el servidor, no tu dispositivo.
          </Typography>
        </Paper>
      )}
    </Box>
  )
}
