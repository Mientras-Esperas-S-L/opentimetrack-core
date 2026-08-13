import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Pagination from '@mui/material/Pagination'
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

/** El error, con el motivo concreto y no solo el titular.
 *
 *  Un error de validación llega con la forma `{code, message, details}`, y el
 *  `message` de esos es siempre el mismo: «Los datos enviados no son válidos».
 *  Lo que dice **qué** pasa está en `details`, por campo, y hasta el 13/08/2026
 *  no se enseñaba: el servidor contestaba «Hugo Bermejo no tiene perfil de
 *  responsable, así que ponerle al mando no le daría nada» y la pantalla decía
 *  «datos no válidos». Quien lo veía no tenía forma de saber qué corregir.
 */
export function ErrorNote({ error, onClose }) {
  if (!error) return null

  // `details` es `{campo: [motivos]}`, y a veces el motivo es un objeto anidado
  // (un serializador dentro de otro). Se aplana a líneas legibles.
  const reasons = Object.values(error.details ?? {})
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .map((reason) => (typeof reason === 'string' ? reason : JSON.stringify(reason)))
    .filter(Boolean)

  return (
    <Alert severity="error" onClose={onClose} sx={{ mb: 2 }}>
      {error.message ?? String(error)}
      {reasons.length > 0 && (
        <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </Box>
      )}
    </Alert>
  )
}

/** Which slice of a list is on screen, and how big the list actually is.
 *
 *  The count is the point, not the arrows. Every one of these screens used to
 *  render the first fifty rows and stop, with nothing saying more existed ---
 *  under headings like "el registro tal y como está guardado". Somebody
 *  checking whether a punch was recorded would have concluded it was not.
 *
 *  So the total shows even on a single page: "12 registros" is a statement that
 *  there are twelve, which is what makes the fuller lists trustworthy.
 */
export function Pager({ count, page, pageSize, onChange, noun = 'registros' }) {
  if (!count) return null

  const pages = Math.ceil(count / pageSize)
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, count)

  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      sx={{ gap: 1, mt: 2, alignItems: 'center', justifyContent: 'space-between' }}
    >
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {pages > 1 ? `${first}–${last} de ${count} ${noun}` : `${count} ${noun}`}
      </Typography>
      {pages > 1 && (
        <Pagination
          size="small"
          count={pages}
          page={page}
          onChange={(_, next) => onChange(next)}
          shape="rounded"
        />
      )}
    </Stack>
  )
}

/** Asks before something that is hard or impossible to undo.
 *
 *  Every destructive action in the panel used to happen on the first click.
 *  Most of them are recoverable, but two are not --- emptying a month of the
 *  roster and deleting a department --- and a product where a misclick can wipe
 *  a month has to say so before it does it, not after.
 *
 *  `detail` is where the consequence goes, in the caller's own words: what a
 *  person needs is not "are you sure" but "this leaves three people without a
 *  department".
 *
 *  Driven by an object rather than a boolean so a page with several of these
 *  needs one piece of state: `{ title, body, detail, verb, run }`, or null.
 */
export function ConfirmDialog({ request, onClose, busy }) {
  const open = Boolean(request)
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{request?.title}</DialogTitle>
      <DialogContent>
        {request?.body && <Typography sx={{ fontWeight: 600 }}>{request.body}</Typography>}
        {request?.detail && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {request.detail}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit" autoFocus>
          Cancelar
        </Button>
        <Button
          variant="contained"
          color="secondary"
          disabled={busy}
          onClick={() => {
            request.run()
            onClose()
          }}
        >
          {request?.verb ?? 'Continuar'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

const STATUS_LOOKS = {
  PENDING: { label: 'Pendiente', color: 'warning', variant: 'filled' },
  APPROVED: { label: 'Aprobada', color: 'success', variant: 'outlined' },
  REJECTED: { label: 'Rechazada', color: 'default', variant: 'outlined' },
  // Art. 4.b. AWAITING_EMPLOYEE is the only one of the two still open: it
  // covers both "has not answered" and "answered saying no", because either
  // way the change has not been applied and somebody has to move.
  //
  // DISPUTED is not a pending state despite the name --- it means the company
  // went ahead without agreement and the person's version is recorded beside
  // it. Outlined, because it is over; secondary, because a reader of the
  // record has to be able to tell it from one both parties accepted.
  AWAITING_EMPLOYEE: { label: 'Esperando tu respuesta', color: 'warning', variant: 'filled' },
  DISPUTED: { label: 'Aplicada sin acuerdo', color: 'secondary', variant: 'outlined' },
}

/** State reads at a glance: the ones that ask somebody to do something are
 *  filled, the ones that are over are outlined. */
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
