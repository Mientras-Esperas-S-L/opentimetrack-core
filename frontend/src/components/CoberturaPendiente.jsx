import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { getCoverage, reassignShift } from '../services/api.js'
import { ErrorNote, Loading } from './common.jsx'
import { localeDeFechas } from '../i18n/index.js'

const MOTIVO = {
  left_the_company: 'dejó la empresa',
  on_leave: 'de baja',
}

/** Un hueco y quién puede taparlo.
 *
 *  Los candidatos inviables se enseñan **con su motivo** en vez de esconderse.
 *  Sin ellos, quien mira una lista corta no sabe si es que no hay nadie o si el
 *  filtro se ha pasado de listo, y en ese caso lo que hace es no fiarse y
 *  abrir las fichas a mano ---que es exactamente lo que esto viene a evitar---.
 */
function Hueco({ hueco, onCubrir, guardando }) {
  const [quien, setQuien] = useState('')
  const viables = hueco.candidates.filter((c) => c.viable)
  const elegido = hueco.candidates.find((c) => c.employee_id === quien)
  // El día distingue estos huecos entre sí: el mismo turno de la misma persona
  // aparece varias veces, uno por jornada sin cubrir.
  const diaLegible = new Date(`${hueco.day}T00:00:00`).toLocaleDateString(localeDeFechas(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <Paper component="li" variant="outlined" sx={{ p: 2, listStyle: 'none' }}>
      <Stack sx={{ gap: 1.5 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography sx={{ fontWeight: 600 }}>{diaLegible}</Typography>
          <Chip
            size="small"
            variant="outlined"
            label={`${hueco.starts_at}–${hueco.ends_at}`}
            sx={{ fontVariantNumeric: 'tabular-nums' }}
          />
          <Typography variant="body2" color="text.secondary">
            {hueco.employee_label} · {MOTIVO[hueco.reason] ?? hueco.detail}
          </Typography>
        </Stack>

        {hueco.candidates.length === 0 ? (
          <Alert severity="warning" variant="outlined">
            No hay nadie más en la empresa a quien ofrecérselo.
          </Alert>
        ) : (
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            sx={{ gap: 1.5, alignItems: 'flex-start' }}
          >
            <TextField
              select
              size="small"
              label="Quién lo cubre"
              // Igual que el botón: doce desplegables con la misma etiqueta no
              // dicen de cuál son.
              slotProps={{
                htmlInput: {
                  'aria-label': `Quién cubre el ${diaLegible} el turno de ${hueco.starts_at} a ${hueco.ends_at}`,
                },
              }}
              value={quien}
              onChange={(event) => setQuien(event.target.value)}
              sx={{ minWidth: 260 }}
              helperText={
                viables.length
                  ? `${viables.length} puede${viables.length === 1 ? '' : 'n'} sin incumplir nada`
                  : 'Nadie puede sin incumplir algo'
              }
            >
              {hueco.candidates.map((c) => (
                <MenuItem key={c.employee_id} value={c.employee_id} disabled={!c.viable}>
                  {c.label}
                  {!c.viable && ` — ${c.blockers[0]}`}
                  {c.viable && c.warnings.length > 0 && ' ⚠'}
                </MenuItem>
              ))}
            </TextField>

            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              {/* El precio, dicho antes de pulsar y no después. Quien cubre una
                  urgencia a veces acepta el incumplimiento a sabiendas; lo que
                  no puede es enterarse luego. */}
              {elegido?.warnings.map((aviso) => (
                <Alert key={aviso} severity="warning" variant="outlined" sx={{ mb: 1 }}>
                  {aviso}
                </Alert>
              ))}
              {/* Con el hueco dentro del nombre. Este panel pinta un botón por
                  hueco sin cubrir, así que en un cuadrante con doce eran doce
                  «Asignar» que suenan idénticos para quien navega con lector de
                  pantalla --- y aquí cada uno asigna un turno distinto a una
                  persona distinta. */}
              <Button
                variant="contained"
                aria-label={`Asignar el ${diaLegible} el turno de ${hueco.starts_at} a ${hueco.ends_at} que cubre a ${hueco.employee_label}`}
                disabled={!elegido?.viable || guardando}
                onClick={() => onCubrir(hueco, elegido)}
              >
                Asignar
              </Button>
            </Box>
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}

/** Los turnos que nadie va a trabajar, y la forma de resolverlos.
 *
 *  Existe porque avisar no es cubrir. El cuadrante ya decía que alguien se fue
 *  o está de baja, y quien lo leía tenía que salir de ahí, abrir la rejilla y
 *  mirar ficha por ficha quién podía. Aquí las dos preguntas se contestan
 *  juntas y se resuelve en el sitio.
 */
export default function CoberturaPendiente({ from, to }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['coverage', from, to],
    queryFn: () => getCoverage(from, to),
  })

  const cubrir = useMutation({
    mutationFn: ({ hueco, quien }) => reassignShift(hueco.shift_id, quien.employee_id),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['coverage'] })
      queryClient.invalidateQueries({ queryKey: ['roster'] })
      queryClient.invalidateQueries({ queryKey: ['roster-review'] })
    },
    onError: setError,
  })

  if (isLoading) return <Loading rows={2} />

  const huecos = data?.uncovered ?? []
  if (huecos.length === 0) return null

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack sx={{ gap: 1.5 }}>
        <Typography variant="h3" sx={{ fontSize: '1rem' }}>
          Cobertura pendiente ({huecos.length})
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Turnos asignados a quien no los va a trabajar. Mientras sigan así, esa persona saldrá cada
          día como ausencia sin justificar.
        </Typography>

        <ErrorNote error={error} onClose={() => setError(null)} />

        <Stack component="ul" sx={{ gap: 1.5, m: 0, p: 0 }}>
          {huecos.map((hueco) => (
            <Hueco
              key={hueco.shift_id}
              hueco={hueco}
              guardando={cubrir.isPending}
              onCubrir={(h, quien) => cubrir.mutate({ hueco: h, quien })}
            />
          ))}
        </Stack>
      </Stack>
    </Paper>
  )
}
