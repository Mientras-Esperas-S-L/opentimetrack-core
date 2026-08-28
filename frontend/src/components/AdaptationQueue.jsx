import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { answerScheduleAdaptation } from '../services/api.js'
import { alCatalogo } from '../i18n/index.js'
import { dateOf } from './format.js'
import { Empty, ErrorNote, Loading } from './common.jsx'

/** Las tres respuestas del art. 34.8, y cuáles piden motivo. */
const RESPUESTAS = [
  { estado: 'ACCEPTED', texto: alCatalogo('Aceptar'), color: 'success', motiva: false },
  {
    estado: 'ALTERNATIVE',
    texto: alCatalogo('Proponer otra cosa'),
    color: 'warning',
    motiva: true,
  },
  { estado: 'REFUSED', texto: alCatalogo('Denegar'), color: 'error', motiva: true },
]

/** La cola de adaptaciones de jornada por contestar (art. 34.8 ET).
 *
 *  **Las tres respuestas están al mismo nivel**, y no «aceptar» frente a un
 *  menú de excusas: el artículo las pone en pie de igualdad y proponer una
 *  alternativa es el resultado normal de una negociación, no una forma suave de
 *  decir que no.
 *
 *  El motivo se pide **antes** de mandar, no después de que el servidor lo
 *  rechace. El servidor lo rechaza igual ---ahí está la garantía--- pero enterarse
 *  de la obligación por un error es enterarse tarde y mal.
 */
export default function AdaptationQueue({ rows, loading }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)
  //: De qué solicitud se está escribiendo la respuesta, y cuál.
  const [contestando, setContestando] = useState(null)
  const [motivo, setMotivo] = useState('')

  const contestar = useMutation({
    mutationFn: ({ id, estado, answer }) =>
      answerScheduleAdaptation(id, {
        status: estado,
        answered_on: new Date().toISOString().slice(0, 10),
        answer,
      }),
    onSuccess: () => {
      setContestando(null)
      setMotivo('')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['schedule-adaptations'] })
      queryClient.invalidateQueries({ queryKey: ['roster-review'] })
    },
    onError: setError,
  })

  if (loading) return <Loading />
  if (rows.length === 0) return <Empty>{t('No hay adaptaciones de jornada por contestar.')}</Empty>

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Alert severity="info" variant="outlined">
        {t(
          'Art. 34.8 ET: hay quince días para negociar y luego hay que contestar por escrito. Si la respuesta no es un sí ---una alternativa también cuenta--- el artículo pide decir por qué.',
        )}
      </Alert>

      <ErrorNote error={error} onClose={() => setError(null)} />

      {rows.map((row) => {
        const abierta = contestando?.id === row.id
        return (
          <Paper key={row.id} variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ alignItems: 'baseline', gap: 1.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontWeight: 600 }}>{row.employee_name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t('Pedida el {{fecha}}', {
                  fecha: dateOf(row.requested_on, { year: 'numeric' }),
                })}
              </Typography>
              <Typography
                variant="caption"
                color={row.out_of_time ? 'error.main' : 'text.secondary'}
              >
                {row.out_of_time
                  ? t('{{dias}} días esperando, fuera del plazo de quince', {
                      dias: row.days_waiting,
                    })
                  : t('{{dias}} de los quince días', { dias: row.days_waiting })}
              </Typography>
            </Stack>

            <Typography variant="body2" sx={{ mt: 1 }}>
              {row.asked_for}
            </Typography>

            {abierta ? (
              <Stack sx={{ gap: 1.5, mt: 2 }}>
                {contestando.motiva && (
                  <TextField
                    fullWidth
                    multiline
                    minRows={2}
                    autoFocus
                    label={t('Por qué')}
                    value={motivo}
                    onChange={(event) => setMotivo(event.target.value)}
                    helperText={t('El art. 34.8 lo pide por escrito.')}
                  />
                )}
                <Stack direction="row" sx={{ gap: 1 }}>
                  <Button
                    variant="contained"
                    color={contestando.color}
                    disabled={(contestando.motiva && !motivo.trim()) || contestar.isPending}
                    onClick={() =>
                      contestar.mutate({
                        id: row.id,
                        estado: contestando.estado,
                        answer: motivo.trim(),
                      })
                    }
                  >
                    {t('Contestar')}
                  </Button>
                  <Button
                    color="inherit"
                    onClick={() => {
                      setContestando(null)
                      setMotivo('')
                    }}
                  >
                    {t('Cancelar')}
                  </Button>
                </Stack>
              </Stack>
            ) : (
              <Stack direction="row" sx={{ gap: 1, mt: 2, flexWrap: 'wrap' }}>
                {RESPUESTAS.map((cual) => (
                  <Button
                    key={cual.estado}
                    size="small"
                    variant="outlined"
                    color={cual.color}
                    onClick={() => {
                      setContestando({ ...cual, id: row.id })
                      setMotivo('')
                    }}
                  >
                    {t(cual.texto)}
                  </Button>
                ))}
                <Box sx={{ flexGrow: 1 }} />
              </Stack>
            )}
          </Paper>
        )
      })}
    </Stack>
  )
}
