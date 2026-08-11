import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Container from '@mui/material/Container'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import LoginIcon from '@mui/icons-material/Login'
import LogoutIcon from '@mui/icons-material/Logout'

import { useAuth } from '../hooks/useAuth.js'
import { clock, getToday } from '../services/api.js'

const pad = (n) => String(n).padStart(2, '0')

function formatDuration(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return `${pad(hours)}:${pad(minutes)}`
}

function formatTime(iso, timeZone) {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })
}

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

export default function Clock() {
  const { session, signOut } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)

  const { data: today, isLoading } = useQuery({
    queryKey: ['today'],
    queryFn: getToday,
    refetchInterval: 60000,
  })

  const punch = useMutation({
    mutationFn: () => clock(`web-${navigator.platform || 'unknown'}`),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['today'] })
    },
    onError: (failure) => setError(failure),
  })

  const working = today?.state === 'WORKING'
  const seconds = useLiveSeconds(today?.worked_seconds ?? 0, working)

  return (
    <Container maxWidth="sm" sx={{ py: 6 }}>
      <Stack
        direction="row"
        sx={{ alignItems: 'flex-start', justifyContent: 'space-between', mb: 4 }}
      >
        <Box>
          <Typography variant="h2">{session.user.full_name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {session.tenant.name}
          </Typography>
        </Box>
        <Button size="small" onClick={signOut}>
          Sign out
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
        {isLoading ? (
          <CircularProgress />
        ) : (
          <>
            <Chip
              label={working ? 'Working' : today?.state === 'OFF' ? 'Day closed' : 'Not started'}
              color={working ? 'success' : 'default'}
              sx={{ mb: 3 }}
            />

            <Typography
              sx={{
                fontSize: '3.5rem',
                fontWeight: 300,
                fontVariantNumeric: 'tabular-nums',
                lineHeight: 1,
                mb: 0.5,
              }}
            >
              {formatDuration(seconds)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
              worked today
            </Typography>

            {error && (
              <Alert severity="warning" variant="outlined" sx={{ mb: 3, textAlign: 'left' }}>
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
              {punch.isPending ? 'Recording…' : working ? 'Clock out' : 'Clock in'}
            </Button>
          </>
        )}
      </Paper>

      {today?.segments?.length > 0 && (
        <Paper variant="outlined" sx={{ p: 3, mt: 3 }}>
          <Typography variant="h2" sx={{ fontSize: '1.1rem', mb: 2 }}>
            Today
          </Typography>
          <Stack spacing={1.5} divider={<Divider flexItem />}>
            {today.segments.map((segment, index) => (
              <Stack
                key={index}
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'center' }}
              >
                <Typography sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {formatTime(segment.in, today.time_zone)}
                  {' → '}
                  {segment.out ? formatTime(segment.out, today.time_zone) : '…'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatDuration(segment.seconds)}
                </Typography>
              </Stack>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Times shown in {today.time_zone}. Recorded by the server.
          </Typography>
        </Paper>
      )}
    </Container>
  )
}
