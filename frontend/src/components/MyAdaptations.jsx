import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import {
  answerScheduleAdaptation,
  createScheduleAdaptation,
  getScheduleAdaptations,
} from '../services/api.js'
import { alCatalogo } from '../i18n/index.js'
import { dateOf } from './format.js'
import { Empty, ErrorNote, Loading } from './common.jsx'

/** Cómo se ve cada estado, y con qué color. */
const COMO_QUEDÓ = {
  PENDING: { texto: alCatalogo('En negociación'), color: 'default' },
  ACCEPTED: { texto: alCatalogo('Aceptada'), color: 'success' },
  ALTERNATIVE: { texto: alCatalogo('Con una alternativa'), color: 'warning' },
  REFUSED: { texto: alCatalogo('Denegada'), color: 'error' },
  WITHDRAWN: { texto: alCatalogo('Retirada'), color: 'default' },
}

/** Las adaptaciones de jornada de quien está mirando (art. 34.8 ET).
 *
 *  Vive en «Mi jornada» y no en «Mis ausencias» a propósito: pedir entrar media
 *  hora más tarde no es faltar un día, y quien lo busca lo busca donde ve su
 *  jornada. Mezclarlo con las ausencias habría sido más fácil de programar y
 *  peor de encontrar.
 *
 *  Se puede pedir siempre, sin condiciones previas: el derecho es de quien
 *  tenga hijos menores de doce años o cuidados a su cargo, y el producto no
 *  sabe ---ni tiene por qué--- si es el caso. Poner una condición aquí sería
 *  decidir sobre la vida de alguien con los datos de una nómina.
 */
export default function MyAdaptations() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)
  const [pidiendo, setPidiendo] = useState(false)
  const [texto, setTexto] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['schedule-adaptations', 'mine'],
    queryFn: () => getScheduleAdaptations(),
  })
  const mías = data?.rows ?? []

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['schedule-adaptations'] })
  }

  const pedir = useMutation({
    mutationFn: () =>
      createScheduleAdaptation({
        // Sin `employee`: el servidor la pone a nombre de quien la pide, que es
        // la única a nombre de quien se puede pedir.
        requested_on: new Date().toISOString().slice(0, 10),
        asked_for: texto.trim(),
      }),
    onSuccess: () => {
      setTexto('')
      setPidiendo(false)
      setError(null)
      refrescar()
    },
    onError: setError,
  })

  const retirar = useMutation({
    mutationFn: (id) => answerScheduleAdaptation(id, { status: 'WITHDRAWN' }),
    onSuccess: refrescar,
    onError: setError,
  })

  return (
    <Box component="section" sx={{ mt: 4 }}>
      <Typography variant="h2" sx={{ fontSize: '1.15rem', mb: 0.5 }}>
        {t('Adaptación de jornada')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t(
          'Art. 34.8 ET: puedes pedir cambiar la duración, la distribución o la forma de trabajar ---incluido a distancia--- para conciliar. La empresa tiene quince días para contestar por escrito.',
        )}
      </Typography>

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={1} />
      ) : mías.length === 0 ? (
        <Empty>{t('No has pedido ninguna adaptación de jornada.')}</Empty>
      ) : (
        <Stack component="ul" sx={{ gap: 1, listStyle: 'none', m: 0, p: 0, mb: 2 }}>
          {mías.map((suya) => {
            const estado = COMO_QUEDÓ[suya.status] ?? COMO_QUEDÓ.PENDING
            return (
              <Paper component="li" key={suya.id} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5, mb: 0.5 }}>
                  <Chip size="small" color={estado.color} label={t(estado.texto)} />
                  <Typography variant="caption" color="text.secondary">
                    {t('Pedida el {{fecha}}', {
                      fecha: dateOf(suya.requested_on, { year: 'numeric' }),
                    })}
                  </Typography>
                  {/* El plazo, solo mientras corre: decirle a quien ya tiene
                      respuesta cuántos días esperó no le sirve de nada. */}
                  {suya.status === 'PENDING' && suya.out_of_time && (
                    <Typography variant="caption" color="error.main">
                      {t('{{dias}} días sin respuesta, y el art. 34.8 da quince', {
                        dias: suya.days_waiting,
                      })}
                    </Typography>
                  )}
                  <Box sx={{ flexGrow: 1 }} />
                  {suya.status === 'PENDING' && (
                    <Button
                      size="small"
                      color="inherit"
                      disabled={retirar.isPending}
                      onClick={() => retirar.mutate(suya.id)}
                    >
                      {t('Retirar')}
                    </Button>
                  )}
                </Stack>
                <Typography variant="body2">{suya.asked_for}</Typography>
                {suya.answer && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {t('Respuesta: {{texto}}', { texto: suya.answer })}
                  </Typography>
                )}
              </Paper>
            )
          })}
        </Stack>
      )}

      {pidiendo ? (
        <Stack sx={{ gap: 1.5, alignItems: 'flex-start' }}>
          <TextField
            fullWidth
            multiline
            minRows={2}
            autoFocus
            label={t('Qué pides')}
            value={texto}
            onChange={(event) => setTexto(event.target.value)}
            helperText={t('Por ejemplo: entrar a las 9:30 y salir media hora más tarde.')}
          />
          <Stack direction="row" sx={{ gap: 1 }}>
            <Button
              variant="contained"
              disabled={!texto.trim() || pedir.isPending}
              onClick={() => pedir.mutate()}
            >
              {t('Pedirla')}
            </Button>
            <Button
              color="inherit"
              onClick={() => {
                setPidiendo(false)
                setTexto('')
              }}
            >
              {t('Cancelar')}
            </Button>
          </Stack>
        </Stack>
      ) : (
        <Button variant="outlined" onClick={() => setPidiendo(true)}>
          {t('Pedir una adaptación')}
        </Button>
      )}
    </Box>
  )
}
