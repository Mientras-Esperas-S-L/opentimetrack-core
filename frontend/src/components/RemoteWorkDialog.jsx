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

import {
  createRemoteWorkAgreement,
  deleteRemoteWorkAgreement,
  getRemoteWorkAgreements,
} from '../services/api.js'
import { dateOf } from './format.js'
import { Empty, ErrorNote, Loading } from './common.jsx'

/** El acuerdo de trabajo a distancia (Ley 10/2021).
 *
 *  Se ofrece a todo el mundo y no solo a quien ya teletrabaja, al revés que las
 *  temporadas del fijo discontinuo: un acuerdo se firma **antes** de empezar
 *  (art. 5.1), así que exigir que ya conste trabajo a distancia para poder
 *  registrarlo obligaría a incumplir el artículo para poder cumplirlo.
 *
 *  Lo que se guarda aquí no es el acuerdo: es que existe, desde cuándo y qué
 *  parte de la jornada. El contenido mínimo del art. 7 ---medios, gastos,
 *  horario, centro de adscripción, control--- es un documento firmado, y quien
 *  tenga que enseñarlo en una inspección enseña el papel.
 */
export default function RemoteWorkDialog({ person, onClose }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)
  const vacío = { signed_on: '', starts_on: '', ends_on: '', agreed_share: '' }
  const [form, setForm] = useState(vacío)

  const abierto = Boolean(person)
  const { data, isLoading } = useQuery({
    queryKey: ['remote-work-agreements', person?.id],
    queryFn: () => getRemoteWorkAgreements(person.id),
    enabled: abierto,
  })
  // `page()` devuelve {rows, count, hasMore}. Leer `.results` aquí daba una
  // lista siempre vacía con el servidor contestando 200.
  const acuerdos = data?.rows ?? []

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['remote-work-agreements', person?.id] })
    // La revisión del cuadrante avisa de quien pasa del 30 % sin acuerdo, así
    // que registrar uno cambia lo que enseña.
    queryClient.invalidateQueries({ queryKey: ['roster-review'] })
  }

  const añadir = useMutation({
    mutationFn: () =>
      createRemoteWorkAgreement({
        employee: person.id,
        signed_on: form.signed_on,
        starts_on: form.starts_on,
        // Vacío es «sin fecha de fin», que es el acuerdo corriente.
        ends_on: form.ends_on || null,
        agreed_share: form.agreed_share === '' ? null : Number(form.agreed_share),
      }),
    onSuccess: () => {
      setForm(vacío)
      setError(null)
      refrescar()
    },
    onError: setError,
  })

  const quitar = useMutation({
    mutationFn: (id) => deleteRemoteWorkAgreement(id),
    onSuccess: refrescar,
    onError: setError,
  })

  const quien = person ? `${person.first_name} ${person.last_name}`.trim() || person.email : ''
  // El aviso de firma tardía se enseña **antes** de guardar, además de después:
  // decirlo cuando ya está escrito es tarde para quien todavía puede mirar la
  // fecha del papel.
  const firmadoTarde =
    form.signed_on && form.starts_on && form.signed_on > form.starts_on ? true : false

  return (
    <Dialog open={abierto} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t('Trabajo a distancia de {{quien}}', { quien })}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t(
            'La Ley 10/2021 se aplica desde el 30 % de la jornada a distancia en tres meses. A partir de ahí hace falta acuerdo por escrito, y firmado antes de empezar.',
          )}
        </Typography>

        <ErrorNote error={error} onClose={() => setError(null)} />

        {isLoading ? (
          <Loading rows={2} />
        ) : acuerdos.length === 0 ? (
          <Empty>{t('No consta ningún acuerdo de trabajo a distancia.')}</Empty>
        ) : (
          <Stack component="ul" sx={{ gap: 1, listStyle: 'none', m: 0, p: 0, mb: 2 }}>
            {acuerdos.map((acuerdo) => (
              <Paper
                component="li"
                key={acuerdo.id}
                variant="outlined"
                sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}
              >
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="body2">
                    {acuerdo.ends_on
                      ? t('Del {{desde}} al {{hasta}}', {
                          desde: dateOf(acuerdo.starts_on, { year: 'numeric' }),
                          hasta: dateOf(acuerdo.ends_on, { year: 'numeric' }),
                        })
                      : t('Desde el {{desde}}, sin fecha de fin', {
                          desde: dateOf(acuerdo.starts_on, { year: 'numeric' }),
                        })}
                    {acuerdo.agreed_share != null &&
                      ` · ${t('{{cuanto}} % pactado', { cuanto: Number(acuerdo.agreed_share) })}`}
                  </Typography>
                  <Typography
                    variant="caption"
                    color={acuerdo.signed_late ? 'error.main' : 'text.secondary'}
                  >
                    {acuerdo.signed_late
                      ? t('Firmado el {{fecha}}, después de haber empezado (art. 5.1)', {
                          fecha: dateOf(acuerdo.signed_on, { year: 'numeric' }),
                        })
                      : t('Firmado el {{fecha}}', {
                          fecha: dateOf(acuerdo.signed_on, { year: 'numeric' }),
                        })}
                  </Typography>
                </Box>
                <IconButton
                  size="small"
                  aria-label={t('Quitar el acuerdo que empieza el {{desde}}', {
                    desde: dateOf(acuerdo.starts_on, { year: 'numeric' }),
                  })}
                  disabled={quitar.isPending}
                  onClick={() => quitar.mutate(acuerdo.id)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Paper>
            ))}
          </Stack>
        )}

        {firmadoTarde && (
          <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
            {t(
              'La firma es posterior al inicio. El art. 5.1 pide que el acuerdo sea previo: se puede guardar así ---el registro cuenta lo que pasó--- y quedará señalado.',
            )}
          </Alert>
        )}

        <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: 'flex-start' }}>
          <TextField
            required
            size="small"
            type="date"
            label={t('Firmado')}
            value={form.signed_on}
            onChange={(event) => setForm({ ...form, signed_on: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            required
            size="small"
            type="date"
            label={t('Empieza')}
            value={form.starts_on}
            onChange={(event) => setForm({ ...form, starts_on: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label={t('Acaba')}
            value={form.ends_on}
            onChange={(event) => setForm({ ...form, ends_on: event.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
            helperText={t('Vacío si no tiene fin.')}
          />
          <TextField
            size="small"
            type="number"
            label={t('% pactado')}
            value={form.agreed_share}
            onChange={(event) => setForm({ ...form, agreed_share: event.target.value })}
            slotProps={{ htmlInput: { min: 0, max: 100, step: 5 } }}
            sx={{ width: 120 }}
          />
          <Button
            variant="outlined"
            disabled={!form.signed_on || !form.starts_on || añadir.isPending}
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
