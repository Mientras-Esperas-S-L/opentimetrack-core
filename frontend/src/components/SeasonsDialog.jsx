import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import DeleteIcon from '@mui/icons-material/Delete'

import { createActivityPeriod, deleteActivityPeriod, getActivityPeriods } from '../services/api.js'
import { dateOf } from './format.js'
import { Empty, ErrorNote, Loading } from './common.jsx'

/** Cuándo se llama a trabajar a quien tiene contrato fijo discontinuo.
 *
 *  Aparte del formulario de la persona a propósito. Ese ya es largo, guarda de
 *  una vez con un `PATCH`, y esto es otra cosa: una lista que crece con cada
 *  campaña y que se toca en momentos distintos ---la ficha se rellena al
 *  contratar; la temporada, cada año---.
 *
 *  Solo se ofrece a quien está marcado como fijo discontinuo. Sin esa marca, un
 *  periodo de actividad no hace nada: el servidor lo rechaza y hace bien, pero
 *  ofrecerlo aquí sería invitar a escribir un dato que no sirve.
 */
export default function SeasonsDialog({ person, onClose }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)
  const [form, setForm] = useState({ start_date: '', end_date: '', called_on: '' })

  const abierto = Boolean(person)
  const { data, isLoading } = useQuery({
    queryKey: ['activity-periods', person?.id],
    queryFn: () => getActivityPeriods(person.id),
    enabled: abierto,
  })
  // `page()` devuelve {rows, count, hasMore}: leer `.results` aquí daba una
  // lista siempre vacía con el servidor contestando 200, que es el peor de los
  // fallos ---todo parece bien y no hay nada---.
  const temporadas = data?.rows ?? []

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['activity-periods', person?.id] })
    // El cuadrante avisa de los turnos que caen fuera de temporada, así que
    // cambiarla cambia lo que enseña.
    queryClient.invalidateQueries({ queryKey: ['roster-review'] })
    queryClient.invalidateQueries({ queryKey: ['coverage'] })
  }

  const añadir = useMutation({
    mutationFn: () =>
      createActivityPeriod({
        employee: person.id,
        start_date: form.start_date,
        // Vacío es «sigue abierta», no una fecha que haya que inventarse.
        end_date: form.end_date || null,
        called_on: form.called_on || null,
      }),
    onSuccess: () => {
      setForm({ start_date: '', end_date: '', called_on: '' })
      setError(null)
      refrescar()
    },
    onError: setError,
  })

  const quitar = useMutation({
    mutationFn: (id) => deleteActivityPeriod(id),
    onSuccess: refrescar,
    onError: setError,
  })

  const quien = person ? `${person.first_name} ${person.last_name}`.trim() || person.email : ''

  return (
    <Dialog open={abierto} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t('Temporadas de {{quien}}', { quien })}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t(
            'Art. 16 ET: el trabajo viene en periodos de actividad. Fuera de ellos no se espera jornada, y el cuadrante avisa si se asigna un turno.',
          )}
        </Typography>

        <ErrorNote error={error} onClose={() => setError(null)} />

        {isLoading ? (
          <Loading rows={2} />
        ) : temporadas.length === 0 ? (
          <Empty>{t('Todavía no hay ninguna temporada declarada.')}</Empty>
        ) : (
          <Stack component="ul" sx={{ gap: 1, listStyle: 'none', m: 0, p: 0, mb: 2 }}>
            {temporadas.map((temporada) => (
              <Paper
                component="li"
                key={temporada.id}
                variant="outlined"
                sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}
              >
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="body2">
                    {temporada.end_date
                      ? t('Del {{desde}} al {{hasta}}', {
                          desde: dateOf(temporada.start_date, { year: 'numeric' }),
                          hasta: dateOf(temporada.end_date, { year: 'numeric' }),
                        })
                      : t('Desde el {{desde}}, sin cerrar', {
                          desde: dateOf(temporada.start_date, { year: 'numeric' }),
                        })}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {temporada.called_on
                      ? t('Llamamiento del {{fecha}}', {
                          fecha: dateOf(temporada.called_on, { year: 'numeric' }),
                        })
                      : t('Sin fecha de llamamiento')}
                  </Typography>
                </Box>
                <IconButton
                  size="small"
                  aria-label={t('Quitar la temporada que empieza el {{desde}}', {
                    desde: dateOf(temporada.start_date, { year: 'numeric' }),
                  })}
                  disabled={quitar.isPending}
                  onClick={() => quitar.mutate(temporada.id)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Paper>
            ))}
          </Stack>
        )}

        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          {t(
            'El llamamiento va antes de que empiece la temporada: el art. 16.3 lo pide por escrito y con antelación, y la fecha es lo que la acredita.',
          )}
        </Alert>

        <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: 'flex-start' }}>
          <TextField
            required
            size="small"
            type="date"
            label={t('Empieza')}
            value={form.start_date}
            onChange={(event) => setForm({ ...form, start_date: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label={t('Acaba')}
            value={form.end_date}
            onChange={(event) => setForm({ ...form, end_date: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
            helperText={t('Vacío mientras siga abierta.')}
          />
          <TextField
            size="small"
            type="date"
            label={t('Llamamiento')}
            value={form.called_on}
            onChange={(event) => setForm({ ...form, called_on: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <Button
            variant="outlined"
            disabled={!form.start_date || añadir.isPending}
            onClick={() => añadir.mutate()}
            sx={{ mt: 0.25 }}
          >
            {t('Añadir')}
          </Button>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('Cerrar')}</Button>
      </DialogActions>
    </Dialog>
  )
}
