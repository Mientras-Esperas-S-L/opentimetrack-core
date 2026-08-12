import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'

import {
  createShiftPattern,
  deleteShiftPattern,
  getShiftPatterns,
  updateShiftPattern,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
} from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

const PALETTE = ['#1b5e4a', '#b0533a', '#2e5f8a', '#7a4b8f', '#8a6d2e', '#4a4a4a']

/** Minutes of a span, treating an end before the start as crossing midnight ---
 *  a night shift, not a mistake. Mirrors the server so the preview matches what
 *  gets saved. */
function spanMinutes(start, end) {
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const diff = eh * 60 + em - (sh * 60 + sm)
  return diff > 0 ? diff : diff + 1440
}

const hhmm = (minutes) => `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`

function PatternDialog({ open, pattern, onClose, onSave, saving, error }) {
  const [form, setForm] = useState(null)
  const [loaded, setLoaded] = useState(null)

  if (open && loaded !== (pattern?.id ?? 'new')) {
    setLoaded(pattern?.id ?? 'new')
    setForm({
      name: pattern?.name ?? '',
      colour: pattern?.colour ?? PALETTE[0],
      segments: pattern?.segments ?? [{ start: '08:00', end: '16:00' }],
    })
  }
  if (!open && loaded !== null) setLoaded(null)
  if (!form) return null

  const setSpan = (index, field) => (event) => {
    const segments = form.segments.map((span, i) =>
      i === index ? { ...span, [field]: event.target.value } : span,
    )
    setForm({ ...form, segments })
  }

  const total = form.segments.reduce((sum, s) => sum + spanMinutes(s.start, s.end), 0)
  const crossesMidnight = form.segments.some((s) => s.end <= s.start)

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSave(form)
        }}
      >
        <DialogTitle>{pattern ? 'Editar turno' : 'Nuevo turno'}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              autoFocus
              required
              fullWidth
              label="Nombre"
              placeholder="Mañana, Noche, Partida…"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />

            <Box>
              <Typography variant="caption" color="text.secondary">
                Tramos horarios
              </Typography>
              <Stack sx={{ gap: 1, mt: 0.5 }}>
                {form.segments.map((span, index) => (
                  <Stack key={index} direction="row" sx={{ gap: 1, alignItems: 'center' }}>
                    <TextField
                      size="small"
                      type="time"
                      label="Desde"
                      value={span.start}
                      onChange={setSpan(index, 'start')}
                      slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <TextField
                      size="small"
                      type="time"
                      label="Hasta"
                      value={span.end}
                      onChange={setSpan(index, 'end')}
                      slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ minWidth: 52 }}>
                      {hhmm(spanMinutes(span.start, span.end))}
                    </Typography>
                    {form.segments.length > 1 && (
                      <IconButton
                        size="small"
                        aria-label="Quitar tramo"
                        onClick={() =>
                          setForm({
                            ...form,
                            segments: form.segments.filter((_, i) => i !== index),
                          })
                        }
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Stack>
                ))}
              </Stack>
              <Button
                size="small"
                startIcon={<AddIcon />}
                sx={{ mt: 1 }}
                onClick={() =>
                  setForm({
                    ...form,
                    segments: [...form.segments, { start: '15:00', end: '19:00' }],
                  })
                }
              >
                Añadir tramo
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Dos tramos = jornada partida. Total: <strong>{hhmm(total)}</strong>.
                {crossesMidnight && ' Un tramo cruza la medianoche: se cuenta como turno de noche.'}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                Color en el cuadrante
              </Typography>
              <Stack direction="row" sx={{ gap: 1, mt: 0.5 }}>
                {PALETTE.map((colour) => (
                  <Box
                    key={colour}
                    onClick={() => setForm({ ...form, colour })}
                    sx={{
                      width: 30,
                      height: 30,
                      borderRadius: 1,
                      bgcolor: colour,
                      cursor: 'pointer',
                      outline: form.colour === colour ? '2px solid' : 'none',
                      outlineColor: 'text.primary',
                      outlineOffset: 2,
                    }}
                  />
                ))}
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                El color acompaña al nombre; nunca es lo único que identifica un turno.
              </Typography>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            Guardar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default function ShiftPatterns() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'

  const [editing, setEditing] = useState(undefined)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(null)

  const { data: patterns, isLoading } = useQuery({
    queryKey: ['shift-patterns'],
    queryFn: getShiftPatterns,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['shift-patterns'] })

  const save = useMutation({
    mutationFn: (payload) =>
      editing ? updateShiftPattern(editing.id, payload) : createShiftPattern(payload),
    onSuccess: () => {
      setEditing(undefined)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const remove = useMutation({
    mutationFn: deleteShiftPattern,
    onSuccess: refresh,
    onError: setError,
  })

  const rows = patterns ?? []

  return (
    <>
      <PageHeader
        title="Turnos"
        subtitle="Las formas de jornada que se repiten. Cambiar una no reescribe los días ya publicados: el cuadrante guarda las horas con las que se creó."
        action={
          isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing(null)}>
              Nuevo turno
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>Todavía no hay turnos definidos.</Empty>
      ) : (
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
          {rows.map((pattern) => (
            <Paper key={pattern.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" sx={{ gap: 2, alignItems: 'flex-start' }}>
                <Box
                  sx={{
                    width: 8,
                    alignSelf: 'stretch',
                    borderRadius: 1,
                    bgcolor: pattern.colour,
                    flexShrink: 0,
                  }}
                />
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 600 }}>{pattern.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {pattern.segments.map((s) => `${s.start}–${s.end}`).join(' y ')}
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    sx={{ mt: 1 }}
                    label={hhmm(pattern.minutes)}
                  />
                </Box>
                {isAdmin && (
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button size="small" onClick={() => setEditing(pattern)}>
                      Editar
                    </Button>
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() =>
                        setConfirming({
                          title: 'Eliminar turno',
                          body: pattern.name,
                          // SET_NULL, so nothing published disappears: the days
                          // stay and stop naming a shift. Which is exactly the
                          // sort of thing somebody should hear before, not find
                          // out afterwards looking at a blank cuadrante.
                          detail: pattern.shifts_count
                            ? `Hay ${pattern.shifts_count} ${pattern.shifts_count === 1 ? 'día' : 'días'} del cuadrante con este turno. No se borran: dejan de llevar nombre de turno, y sus horas siguen contando.`
                            : 'No está puesto en ningún día del cuadrante. No se puede deshacer.',
                          verb: 'Eliminar',
                          run: () => remove.mutate(pattern.id),
                        })
                      }
                      disabled={remove.isPending}
                    >
                      Eliminar
                    </Button>
                  </Stack>
                )}
              </Stack>
            </Paper>
          ))}
        </Box>
      )}

      <PatternDialog
        open={editing !== undefined}
        pattern={editing}
        saving={save.isPending}
        error={error}
        onClose={() => {
          setEditing(undefined)
          setError(null)
        }}
        onSave={save.mutate}
      />
      <ConfirmDialog
        request={confirming}
        busy={remove.isPending}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
