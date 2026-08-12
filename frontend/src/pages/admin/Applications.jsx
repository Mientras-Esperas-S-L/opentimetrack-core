import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import KeyIcon from '@mui/icons-material/Key'

import {
  authoriseApplication,
  getApplicationScopes,
  getApplications,
  issueCredential,
  revokeApplication,
  revokeCredential,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
} from '../../components/common.jsx'
import { dateOf } from '../../components/format.js'

/** Shown once, right after issuing. There is no second chance and the box says
 *  so before somebody closes it. */
function TokenDialog({ token, onClose }) {
  const [copied, setCopied] = useState(false)

  return (
    <Dialog open={Boolean(token)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Copia el token ahora</DialogTitle>
      <DialogContent>
        <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
          Es la única vez que se muestra. Se guarda cifrado, así que no se puede
          recuperar: si lo pierdes, hay que emitir otro.
        </Alert>
        <Paper
          variant="outlined"
          sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden' }}
        >
          <Typography
            sx={{ fontFamily: 'monospace', fontSize: '0.85rem', wordBreak: 'break-all', flexGrow: 1 }}
          >
            {token}
          </Typography>
          <IconButton
            size="small"
            aria-label="Copiar el token"
            onClick={() => {
              navigator.clipboard?.writeText(token)
              setCopied(true)
            }}
          >
            <ContentCopyIcon fontSize="small" />
          </IconButton>
        </Paper>
        {copied && (
          <Typography variant="caption" color="success.main" sx={{ display: 'block', mt: 1 }}>
            Copiado al portapapeles.
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Va en la cabecera <code>Authorization: Bearer …</code> de cada petición.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={onClose}>
          Ya lo tengo
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function ApplicationDialog({ open, scopes, onClose, onSave, saving, error }) {
  const [form, setForm] = useState({ name: '', description: '', scopes: [] })

  const toggle = (value) =>
    setForm({
      ...form,
      scopes: form.scopes.includes(value)
        ? form.scopes.filter((s) => s !== value)
        : [...form.scopes, value],
    })

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSave(form)
        }}
      >
        <DialogTitle>Autorizar una aplicación</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Un terminal en la entrada, un lector NFC, una tableta en obra. Lo que
            registre irá marcado como hecho en nombre de la persona, no por ella:
            son pruebas distintas y quien lea el registro tiene derecho a
            distinguirlas.
          </Typography>
          <Stack sx={{ gap: 2, pt: 0.5 }}>
            <TextField
              autoFocus
              required
              fullWidth
              label="Nombre"
              placeholder="Terminal de la nave"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              helperText="Aparece en cada fichaje que registre."
            />
            <TextField
              fullWidth
              multiline
              minRows={2}
              label="Para qué es"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />

            <Box>
              <Typography variant="caption" color="text.secondary">
                Qué puede hacer
              </Typography>
              {/* One by one, never in bulk. An application with everything is
                  a key to the whole company, and the list is short enough that
                  ticking three boxes is not a hardship. */}
              <Stack sx={{ mt: 0.5 }}>
                {scopes.map((scope) => (
                  <FormControlLabel
                    key={scope.value}
                    control={
                      <Checkbox
                        size="small"
                        checked={form.scopes.includes(scope.value)}
                        onChange={() => toggle(scope.value)}
                      />
                    }
                    label={<Typography variant="body2">{scope.label}</Typography>}
                  />
                ))}
              </Stack>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={saving || !form.name.trim() || form.scopes.length === 0}
          >
            Autorizar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default function Applications() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [token, setToken] = useState(null)
  const [confirming, setConfirming] = useState(null)
  const [error, setError] = useState(null)

  const { data: applications, isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => getApplications(),
  })
  const { data: scopes = [] } = useQuery({
    queryKey: ['application-scopes'],
    // From the server: a list copied into the frontend goes stale the first
    // time somebody adds a scope, and then a real permission cannot be granted.
    queryFn: getApplicationScopes,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['applications'] })

  const authorise = useMutation({
    mutationFn: authoriseApplication,
    onSuccess: () => {
      setCreating(false)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const issue = useMutation({
    mutationFn: issueCredential,
    onSuccess: (data) => {
      setToken(data.token)
      refresh()
    },
    onError: setError,
  })

  const revoke = useMutation({
    mutationFn: ({ application, credential }) =>
      credential ? revokeCredential(application, credential) : revokeApplication(application),
    onSuccess: refresh,
    onError: setError,
  })

  const labelFor = (value) => scopes.find((s) => s.value === value)?.label ?? value
  const rows = applications?.rows ?? []

  return (
    <>
      <PageHeader
        title="Aplicaciones"
        subtitle="Terminales, lectores y sistemas que fichan en nombre de alguien. Cada uno con sus permisos y su propia llave, revocable sin tocar la cuenta de nadie."
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>
            Autorizar
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>
          Todavía no hay ninguna. Se autoriza una cuando un terminal o un lector tiene que fichar
          por la gente que no puede hacerlo con su propia sesión.
        </Empty>
      ) : (
        <Stack sx={{ gap: 2 }}>
          {rows.map((application) => (
            <Paper
              key={application.id}
              variant="outlined"
              sx={{ p: 2, opacity: application.is_active ? 1 : 0.55 }}
            >
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                sx={{ gap: 2, justifyContent: 'space-between' }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 600 }}>{application.name}</Typography>
                    {!application.is_active && <Chip size="small" label="Revocada" />}
                  </Stack>
                  {application.description && (
                    <Typography variant="body2" color="text.secondary">
                      {application.description}
                    </Typography>
                  )}
                  <Stack direction="row" sx={{ gap: 0.5, mt: 1, flexWrap: 'wrap' }}>
                    {application.scopes.map((scope) => (
                      <Chip key={scope} size="small" variant="outlined" label={labelFor(scope)} />
                    ))}
                  </Stack>
                </Box>

                {application.is_active && (
                  <Stack sx={{ gap: 1, flexShrink: 0, alignItems: 'flex-start' }}>
                    <Button
                      size="small"
                      startIcon={<KeyIcon />}
                      disabled={issue.isPending}
                      onClick={() => issue.mutate(application.id)}
                    >
                      Emitir token
                    </Button>
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() =>
                        setConfirming({
                          title: 'Revocar la aplicación',
                          body: application.name,
                          detail:
                            'Deja de funcionar de inmediato, con todos sus tokens. No se borra: lo que registró sigue siendo suyo, y quitarla dejaría esos fichajes sin autor.',
                          verb: 'Revocar',
                          run: () => revoke.mutate({ application: application.id }),
                        })
                      }
                    >
                      Revocar
                    </Button>
                  </Stack>
                )}
              </Stack>

              {application.credentials.length > 0 && (
                <Stack sx={{ gap: 0.5, mt: 2, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                  {application.credentials.map((credential) => (
                    <Stack
                      key={credential.id}
                      direction="row"
                      sx={{ gap: 2, alignItems: 'center', justifyContent: 'space-between' }}
                    >
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        …{credential.token_hint}
                        {credential.label && (
                          <Box component="span" sx={{ fontFamily: 'body1.fontFamily', ml: 1 }}>
                            {credential.label}
                          </Box>
                        )}
                      </Typography>
                      <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          {credential.last_used_at
                            ? `Usado el ${dateOf(credential.last_used_at)}`
                            : 'Sin usar'}
                        </Typography>
                        {credential.is_valid ? (
                          <Button
                            size="small"
                            color="inherit"
                            onClick={() =>
                              setConfirming({
                                title: 'Revocar el token',
                                body: `…${credential.token_hint}`,
                                detail:
                                  'Deja de valer de inmediato. Los demás tokens de esta aplicación siguen funcionando, que es lo que permite cambiarlos sin cortar el servicio.',
                                verb: 'Revocar',
                                run: () =>
                                  revoke.mutate({
                                    application: application.id,
                                    credential: credential.id,
                                  }),
                              })
                            }
                          >
                            Revocar
                          </Button>
                        ) : (
                          <Chip size="small" label="Revocado" sx={{ height: 20 }} />
                        )}
                      </Stack>
                    </Stack>
                  ))}
                </Stack>
              )}
            </Paper>
          ))}
        </Stack>
      )}

      <ApplicationDialog
        open={creating}
        scopes={scopes}
        saving={authorise.isPending}
        error={error}
        onClose={() => {
          setCreating(false)
          setError(null)
        }}
        onSave={authorise.mutate}
      />

      <TokenDialog token={token} onClose={() => setToken(null)} />

      <ConfirmDialog
        request={confirming}
        busy={revoke.isPending}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
