import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { ErrorNote } from './common.jsx'
import { dateOf, instantFromLocal, timeOf } from './format.js'

/** Un fichaje, escrito como lo reconoce quien lo hizo. */
const nombreDelFichaje = (punch, zone) =>
  `${dateOf(punch.timestamp)} · ${punch.punch_type === 'IN' ? 'entrada' : 'salida'} ${timeOf(punch.timestamp, zone)}`

/** El diálogo de pedir una corrección.
 *
 *  Aparte porque también lo abre la pantalla de fichar, cuando avisa de una
 *  entrada que se quedó sin salida: ahí `initial` lo trae ya puesto en «olvidé
 *  fichar la salida», `contexto` dice de qué jornada, y `desde` impide elegir
 *  una salida anterior a esa entrada. Quien lo monte con `initial` le cambia la
 *  `key` al abrir, para que no arrastre lo escrito la vez anterior.
 */
export default function CorrectionDialog({
  open,
  onClose,
  onSubmit,
  saving,
  error,
  punches = [],
  zone,
  initial,
  contexto,
  desde,
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    kind: 'ADD',
    proposed_type: 'OUT',
    proposed_timestamp: '',
    target: '',
    reason: '',
    ...initial,
  })

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSubmit({
      kind: form.kind,
      proposed_type: form.kind === 'ADD' ? form.proposed_type : undefined,
      // Cuál se corrige. Sin esto el servidor responde «Indica qué fichaje se
      // corrige» y la pantalla no ofrecía dónde indicarlo: la opción de cambiar
      // una hora fallaba **siempre**, con un error que quien lo lee no puede
      // resolver.
      target: form.kind === 'MODIFY' ? form.target : undefined,
      // En la zona de la persona: el navegador puede estar en otra.
      proposed_timestamp: instantFromLocal(form.proposed_timestamp, zone),
      reason: form.reason,
    })
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>{t('Pedir una corrección')}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t(
              'Tu registro no se cambia ahora: se envía la petición y la resuelve un responsable. El fichaje original nunca se borra.',
            )}
          </Typography>
          {contexto && (
            <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
              {contexto}
            </Alert>
          )}
          <Stack sx={{ gap: 2, pt: 0.5 }}>
            <TextField
              select
              label={t('Qué pasó')}
              value={form.kind}
              onChange={set('kind')}
              fullWidth
            >
              <MenuItem value="ADD">{t('Olvidé fichar')}</MenuItem>
              <MenuItem value="MODIFY">{t('La hora registrada no es la real')}</MenuItem>
            </TextField>

            {form.kind === 'ADD' && (
              <TextField
                select
                label={t('Qué falta')}
                value={form.proposed_type}
                onChange={set('proposed_type')}
                fullWidth
              >
                <MenuItem value="IN">{t('La entrada')}</MenuItem>
                <MenuItem value="OUT">{t('La salida')}</MenuItem>
              </TextField>
            )}

            {form.kind === 'MODIFY' &&
              (punches.length === 0 ? (
                <Alert severity="info" variant="outlined">
                  {t(
                    'No hay fichajes en el mes que estás viendo. Cambia de mes para elegir cuál corregir.',
                  )}
                </Alert>
              ) : (
                <TextField
                  select
                  required
                  fullWidth
                  label={t('Cuál')}
                  value={form.target}
                  onChange={set('target')}
                  helperText={t(
                    'El que tiene la hora mal. El original no se borra: queda al lado del cambio.',
                  )}
                >
                  {punches.map((punch) => (
                    <MenuItem key={punch.id} value={punch.id}>
                      {nombreDelFichaje(punch, zone)}
                    </MenuItem>
                  ))}
                </TextField>
              ))}

            <TextField
              required
              fullWidth
              type="datetime-local"
              label={zone ? t('Hora real, en hora de {{zona}}', { zona: zone }) : t('Hora real')}
              value={form.proposed_timestamp}
              onChange={set('proposed_timestamp')}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: desde } }}
              helperText={t('No puede ser una hora futura.')}
            />

            <TextField
              required
              fullWidth
              multiline
              minRows={3}
              label={t('Motivo')}
              placeholder={t('Por ejemplo: me quedé sin batería y no pude fichar la salida.')}
              value={form.reason}
              onChange={set('reason')}
              helperText={t(
                'Obligatorio. Una corrección sin motivo no se distingue de una manipulación.',
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            {t('Cancelar')}
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            {t('Enviar solicitud')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
