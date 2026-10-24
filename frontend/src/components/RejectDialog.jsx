import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { ErrorNote } from './common.jsx'

/** El «no», de una en una o de varias a la vez.
 *
 *  Rechazar en bloque pasa por el mismo cuadro que rechazar una, y con el mismo
 *  motivo obligatorio donde lo es: el texto que va a leer la persona no puede
 *  depender de por qué botón se llegó. Y un motivo compartido por varias se
 *  avisa, para que nadie escriba «no procede» pensando en un caso y se lo
 *  mande a cinco.
 */
/** Rechazar lo que alguien pidió, o retirar una propuesta de la empresa.
 *
 *  `retirar`: «Sin acuerdo» usaba este mismo diálogo diciendo «Rechazar la
 *  solicitud» sobre una propuesta propia, y además llamaba a la ruta de
 *  rechazar, que a una propuesta en espera le contesta 409: el botón no
 *  funcionaba nunca.
 */
export default function RejectDialog({
  open,
  onClose,
  onConfirm,
  needsNote,
  count = 1,
  busy,
  error,
  retirar = false,
}) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  const many = count > 1

  // El motivo no se borra al pulsar: si el rechazo falla, se perdía lo escrito.
  // Se vacía al abrir otra vez, porque quien lo monta le cambia la `key`.
  const confirm = () => onConfirm(note)

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {retirar
          ? many
            ? t('Retirar {{cuantas}} propuestas', { cuantas: count })
            : t('Retirar la propuesta')
          : many
            ? t('Rechazar {{cuantas}} solicitudes', { cuantas: count })
            : t('Rechazar la solicitud')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {retirar
            ? t(
                'El registro se queda como estaba y la propuesta consta como retirada. La persona ya no tiene que contestar.',
              )
            : many
              ? t(
                  'El mismo motivo se enviará a todas. Se conservan rechazadas: que alguien lo pidiera y se le dijera que no también es parte del historial.',
                )
              : t(
                  'La solicitud se conserva rechazada: que alguien lo pidiera y se le dijera que no también es parte del historial.',
                )}
        </Typography>
        {/* Dentro, y no solo en la página: el fallo se pintaba detrás del
            diálogo, que se quedaba abierto sin decir nada. */}
        <ErrorNote error={error} />
        <TextField
          autoFocus
          fullWidth
          multiline
          minRows={3}
          label={
            retirar
              ? t('Por qué se retira')
              : needsNote
                ? t('Motivo del rechazo')
                : t('Motivo del rechazo (opcional)')
          }
          placeholder={
            many
              ? t('Lo leerán todas las personas afectadas.')
              : t('Lo leerá la persona que lo solicitó.')
          }
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">
          {t('Volver')}
        </Button>
        <Button
          onClick={confirm}
          variant="contained"
          color="secondary"
          disabled={busy || (needsNote && !note.trim())}
        >
          {retirar
            ? many
              ? t('Retirar las {{cuantas}}', { cuantas: count })
              : t('Retirar')
            : many
              ? t('Rechazar las {{cuantas}}', { cuantas: count })
              : t('Rechazar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
