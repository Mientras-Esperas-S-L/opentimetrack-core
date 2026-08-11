import { useQuery } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Container from '@mui/material/Container'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'

import { getHealth } from './services/api.js'

const NOMBRES = {
  database: 'Base de datos',
  cache: 'Caché',
}

function Comprobacion({ nombre, ok, detalle }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
      {ok ? (
        <CheckCircleIcon color="success" fontSize="small" />
      ) : (
        <ErrorIcon color="error" fontSize="small" />
      )}
      <Typography sx={{ flexGrow: 1 }}>{NOMBRES[nombre] ?? nombre}</Typography>
      <Typography variant="body2" color="text.secondary">
        {detalle}
      </Typography>
    </Stack>
  )
}

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  })

  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <Typography variant="h1" gutterBottom>
        OpenTimeTrack
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Registro horario conforme al artículo 34.9 del Estatuto de los Trabajadores. La marca
        temporal de cada fichaje la fija el servidor, nunca el cliente.
      </Typography>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack
          direction="row"
          sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2 }}
        >
          <Typography variant="h2">Estado del servicio</Typography>
          {data && (
            <Chip
              size="small"
              color={data.status === 'ok' ? 'success' : 'error'}
              label={data.status === 'ok' ? 'Operativo' : 'Degradado'}
            />
          )}
        </Stack>

        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {error && (
          <Alert severity="error" variant="outlined">
            {error.message}
            {error.code && (
              <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                código: {error.code}
              </Typography>
            )}
          </Alert>
        )}

        {data && (
          <>
            <Stack spacing={1.5} divider={<Divider flexItem />}>
              {Object.entries(data.checks).map(([nombre, check]) => (
                <Comprobacion
                  key={nombre}
                  nombre={nombre}
                  ok={check.ok}
                  detalle={check.detail}
                />
              ))}
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
              Versión {data.version}
            </Typography>
          </>
        )}
      </Paper>

      <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
        Andamiaje inicial. El panel de administración y la pantalla de fichaje llegan en sus fases
        del plan de construcción.
      </Typography>
    </Container>
  )
}
