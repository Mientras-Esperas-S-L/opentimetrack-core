import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

/** The small pieces every screen needs, so they look the same on all of them. */

export function PageHeader({ title, subtitle, action }) {
  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      sx={{ alignItems: { sm: 'flex-end' }, justifyContent: 'space-between', gap: 2, mb: 3 }}
    >
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h1" sx={{ fontSize: { xs: '1.5rem', md: '1.9rem' } }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: '62ch' }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {action}
    </Stack>
  )
}

export function Panel({ title, hint, action, children, sx }) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 }, ...sx }}>
      {(title || action) && (
        <Stack
          direction="row"
          sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 2, mb: hint ? 0.5 : 2 }}
        >
          <Typography variant="h2" sx={{ fontSize: '1rem' }}>
            {title}
          </Typography>
          {action}
        </Stack>
      )}
      {hint && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          {hint}
        </Typography>
      )}
      {children}
    </Paper>
  )
}

/** Shown instead of a spinner where the shape of the content is known: the page
 *  does not jump when the data lands. */
export function Loading({ rows = 3 }) {
  return (
    <Stack spacing={1}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} variant="rounded" height={44} />
      ))}
    </Stack>
  )
}

export function Spinner() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
      <CircularProgress />
    </Box>
  )
}

/** An empty screen is an invitation to act, not a shrug. */
export function Empty({ children }) {
  return (
    <Box sx={{ py: 5, textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">
        {children}
      </Typography>
    </Box>
  )
}

export function ErrorNote({ error, onClose }) {
  if (!error) return null
  return (
    <Alert severity="error" onClose={onClose} sx={{ mb: 2 }}>
      {error.message ?? String(error)}
    </Alert>
  )
}

const STATUS_LOOKS = {
  PENDING: { label: 'Pendiente', color: 'warning', variant: 'filled' },
  APPROVED: { label: 'Aprobada', color: 'success', variant: 'outlined' },
  REJECTED: { label: 'Rechazada', color: 'default', variant: 'outlined' },
}

/** State reads at a glance: pending is the only one filled, because it is the
 *  only one that asks somebody to do something. */
export function StatusChip({ status, label }) {
  const look = STATUS_LOOKS[status] ?? { label: status, color: 'default', variant: 'outlined' }
  return <Chip size="small" label={label ?? look.label} color={look.color} variant={look.variant} />
}

const SOURCE_LABELS = {
  WEB: 'Web',
  MOBILE: 'Móvil',
  APPLICATION: 'App externa',
  DELEGATED: 'En su nombre',
  TERMINAL: 'Terminal',
  ADMIN: 'Corrección',
  IMPORT: 'Importado',
}

/** How the record got here. Not decoration: an event somebody else produced is
 *  not the same as one the person made, and the inspection report says so too.
 *  The two that were not made by the person are the ones that stand out. */
export function SourceChip({ source }) {
  const flagged = source === 'DELEGATED' || source === 'ADMIN'
  return (
    <Chip
      size="small"
      variant="outlined"
      label={SOURCE_LABELS[source] ?? source}
      color={flagged ? 'secondary' : 'default'}
      sx={{ fontSize: '0.7rem', height: 22 }}
    />
  )
}
