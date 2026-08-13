/** Las casillas y la barra de acciones de una selección múltiple.
 *
 *  El estado vive en `hooks/useSelection.js` y el ejecutor en
 *  `services/bulk.js`: aquí solo lo que se pinta.
 *
 *  Faltaba en casi todas las pantallas y se notaba: una cola de veinte
 *  solicitudes en la que hay que pulsar cuarenta veces no se gestiona, se
 *  abandona --- y quien la abandona deja gente esperando respuesta.
 *
 *  La barra flota abajo a propósito: la lista sigue entera detrás, sin saltos
 *  ni cabeceras que aparecen y desaparecen moviendo lo que ibas a pulsar.
 */

import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

/** La casilla de una fila. */
export function SelectBox({ selection, item, label }) {
  return (
    <Checkbox
      size="small"
      checked={selection.isSelected(item)}
      onChange={() => selection.toggle(item)}
      slotProps={{ input: { 'aria-label': label ?? 'Seleccionar' } }}
      sx={{ ml: -1 }}
    />
  )
}

/** La casilla de la cabecera: todo, nada, o el guion de «algunas». */
export function SelectAllBox({ selection, count }) {
  return (
    <Checkbox
      size="small"
      checked={selection.allSelected}
      indeterminate={selection.someSelected}
      onChange={selection.toggleAll}
      disabled={count === 0}
      slotProps={{ input: { 'aria-label': 'Seleccionar todo' } }}
    />
  )
}

/** La barra de acciones. Aparece cuando hay algo elegido y no antes.
 *
 *  `actions` son `{label, onClick, variant, color}`. Cada pantalla pone las
 *  suyas: aquí no se sabe qué significa aprobar.
 */
export function SelectionBar({ selection, noun = 'elementos', actions = [], busy }) {
  if (selection.count === 0) return null

  return (
    <Box
      sx={{
        position: 'sticky',
        bottom: 16,
        display: 'flex',
        justifyContent: 'center',
        mt: 2,
        pointerEvents: 'none',
        zIndex: (theme) => theme.zIndex.appBar,
      }}
    >
      <Paper
        elevation={8}
        sx={{
          pointerEvents: 'auto',
          px: 2,
          py: 1.25,
          borderRadius: 999,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          flexWrap: 'wrap',
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {selection.count} {selection.count === 1 ? noun.replace(/s$/, '') : noun}
        </Typography>
        <Button size="small" color="inherit" onClick={selection.clear} disabled={busy}>
          Quitar selección
        </Button>
        <Stack direction="row" sx={{ gap: 1 }}>
          {actions.map((action) => (
            <Button
              key={action.label}
              size="small"
              variant={action.variant ?? 'contained'}
              color={action.color}
              disabled={busy || action.disabled}
              onClick={action.onClick}
            >
              {action.label}
            </Button>
          ))}
        </Stack>
      </Paper>
    </Box>
  )
}
