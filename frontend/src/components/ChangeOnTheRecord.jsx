/** Qué cambia exactamente en el registro: de qué, a qué.
 *
 *  Lo que faltaba para que el consentimiento del art. 4.b signifique algo. Una
 *  propuesta de **anular** un fichaje no lleva hora nueva ---por diseño, no hay
 *  ninguna--- así que la pantalla de quien tiene que autorizarla decía «Anular
 *  un fichaje · Pedida el 12 de agosto» y ponía dos botones debajo. Se le pedía
 *  consentir un cambio sin decirle cuál. En un cambio de hora enseñaba la hora
 *  nueva y nunca la que sustituye, que es la mitad de la información.
 *
 *  La pantalla de quien propone el cambio sí lo enseñaba. La de quien tiene que
 *  aceptarlo, no, que es exactamente al revés de como debería estar.
 */

import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import ArrowRightAltIcon from '@mui/icons-material/ArrowRightAlt'

import { dateOf, timeOf } from './format.js'

const TIPO = { IN: 'Entrada', OUT: 'Salida' }

/** «Salida de las 17:00 del 12 ago», o un guion si no hay tal fichaje. */
function Sello({ punch, tipo, hora, zone }) {
  const cuando = punch?.timestamp ?? hora
  const clase = TIPO[punch?.punch_type ?? tipo] ?? ''

  if (!cuando) return <Box component="span">—</Box>

  return (
    <Box component="span" sx={{ fontVariantNumeric: 'tabular-nums' }}>
      {clase && `${clase} `}
      <strong>{timeOf(cuando, zone)}</strong> del {dateOf(cuando)}
    </Box>
  )
}

export default function ChangeOnTheRecord({ correction, zone }) {
  const {
    kind,
    target_detail: actual,
    proposed_timestamp: propuesta,
    proposed_type: tipo,
  } = correction

  // Un `null` en la propuesta es la anulación: el fichaje deja de contar. Se
  // dice con palabras y no con un hueco, porque un hueco se lee como un fallo
  // de la pantalla y no como el cambio que es.
  const anula = kind === 'VOID'

  return (
    <Stack
      direction="row"
      sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.75 }}
      aria-label="Qué cambia en el registro"
    >
      <Typography variant="body2" color="text.secondary">
        {actual ? (
          <Sello punch={actual} zone={zone} />
        ) : (
          <Box component="span" sx={{ fontStyle: 'italic' }}>
            no hay fichaje
          </Box>
        )}
      </Typography>

      <ArrowRightAltIcon fontSize="small" sx={{ color: 'text.disabled' }} />

      <Typography variant="body2" color={anula ? 'secondary.main' : 'text.primary'}>
        {anula ? 'queda anulado' : <Sello tipo={tipo} hora={propuesta} zone={zone} />}
      </Typography>
    </Stack>
  )
}
