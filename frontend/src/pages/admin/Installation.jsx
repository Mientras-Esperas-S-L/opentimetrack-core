import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import {
  createCompany,
  getCompanies,
  removeCompanyIdentity,
  saveCompanyIdentity,
} from '../../services/api.js'

/** Administrar la instalación: las empresas que hay y cómo entra su gente.
 *
 *  Existe para no tener que abrir una consola. Hasta ahora, dar de alta una
 *  empresa era una llamada a la API desde dentro del contenedor y configurar su
 *  proveedor de identidad, un `manage.py shell`: cualquiera que instale esto se
 *  encontraba lo mismo.
 *
 *  Es la administración de la **instalación**, no de una empresa: aquí no se ven
 *  sus datos ni se entra en ellos, solo su ficha, cuánta gente tiene y si su
 *  identidad está configurada.
 */
export default function Installation() {
  const { t } = useTranslation()
  const [empresas, setEmpresas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [nueva, setNueva] = useState(null)
  const [identidadDe, setIdentidadDe] = useState(null)
  const [reciénCreada, setReciénCreada] = useState(null)

  // La lista se pide en el efecto y se escribe **dentro de la promesa**: un
  // `setState` síncrono ahí dispara renders en cascada, y el linter lo para.
  // Recargar es subir el contador, que es lo que vuelve a lanzarlo.
  const [vuelta, setVuelta] = useState(0)
  const cargar = useCallback(() => setVuelta((n) => n + 1), [])

  useEffect(() => {
    let vivo = true
    getCompanies()
      .then((datos) => vivo && setEmpresas(datos))
      .catch(() => vivo && setError(t('No he podido leer las empresas de esta instalación.')))
      .finally(() => vivo && setCargando(false))
    return () => {
      vivo = false
    }
  }, [t, vuelta])

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      {/* `gap` y el botón sin encoger, o el botón se monta encima de la línea
          que explica la pantalla: la fila reparte el hueco y el texto de debajo
          es más ancho que el título. */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        gap={2}
        sx={{ mb: 2 }}
      >
        <Box>
          <Typography variant="h5">{t('Instalación')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('Las empresas que viven en este OpenTimeTrack y cómo entra su gente.')}
          </Typography>
        </Box>
        <Button
          variant="contained"
          sx={{ flexShrink: 0 }}
          onClick={() =>
            setNueva({
              company_name: '',
              tax_id: '',
              country: 'ES',
              time_zone: 'Europe/Madrid',
              email: '',
              first_name: '',
              last_name: '',
            })
          }
        >
          {t('Nueva empresa')}
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {reciénCreada && (
        // Una sola vez, como la credencial de aplicación: si esto se pierde, la
        // única salida es restablecer la contraseña de esa persona.
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setReciénCreada(null)}>
          <Typography variant="body2">
            {t('Empresa creada. Apunta ahora la contraseña de quien la administra: no se vuelve a enseñar.')}
          </Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
            {reciénCreada.email} · {reciénCreada.password}
          </Typography>
        </Alert>
      )}

      <Paper variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t('Empresa')}</TableCell>
              <TableCell>{t('CIF')}</TableCell>
              <TableCell align="right">{t('Personas')}</TableCell>
              <TableCell>{t('Cómo entran')}</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {empresas.map((empresa) => (
              <TableRow key={empresa.id}>
                <TableCell>
                  {empresa.name}
                  <Typography variant="caption" color="text.secondary" display="block">
                    {empresa.time_zone}
                  </Typography>
                </TableCell>
                <TableCell>{empresa.tax_id}</TableCell>
                <TableCell align="right">{empresa.people}</TableCell>
                <TableCell>
                  {empresa.identity ? (
                    <Chip
                      size="small"
                      color="primary"
                      variant="outlined"
                      label={empresa.identity.name}
                      title={empresa.identity.domains.join(', ')}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {t('Con contraseña')}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Button size="small" onClick={() => setIdentidadDe(empresa)}>
                    {t('Identidad')}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!cargando && empresas.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary">
                    {t('Todavía no hay ninguna empresa.')}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      <NewCompanyDialog
        key={nueva ? 'nueva' : 'sin-nueva'}
        valores={nueva}
        onClose={() => setNueva(null)}
        onCreada={(datos) => {
          setReciénCreada(datos.administrator)
          setNueva(null)
          cargar()
        }}
      />

      <IdentityDialog
        key={identidadDe?.id ?? 'sin-empresa'}
        empresa={identidadDe}
        onClose={() => setIdentidadDe(null)}
        onGuardada={() => {
          setIdentidadDe(null)
          cargar()
        }}
      />
    </Box>
  )
}

/** El alta: la empresa y quien la va a administrar, de una vez. */
function NewCompanyDialog({ valores, onClose, onCreada }) {
  const { t } = useTranslation()
  // Sin efecto que sincronice con las props: el padre le pone `key`, así que este
  // formulario nace ya con lo suyo cada vez que se abre.
  const [form, setForm] = useState(() => valores ?? {})
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const cambiar = (campo) => (e) => setForm((previo) => ({ ...previo, [campo]: e.target.value }))

  const guardar = async () => {
    setGuardando(true)
    setError(null)
    try {
      onCreada(await createCompany(form))
    } catch (fallo) {
      const datos = fallo?.response?.data ?? {}
      const dicho = datos?.error?.message ?? Object.values(datos).flat().join(' ')
      setError(dicho || t('No se ha podido crear la empresa.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Dialog open={Boolean(valores)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t('Nueva empresa')}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label={t('Nombre fiscal')} value={form.company_name ?? ''} onChange={cambiar('company_name')} />
          <TextField
            label={t('CIF')}
            value={form.tax_id ?? ''}
            onChange={cambiar('tax_id')}
            helperText={t('Es lo que distingue a una empresa de otra: no puede repetirse.')}
          />
          <Stack direction="row" spacing={2}>
            <TextField label={t('País')} value={form.country ?? 'ES'} onChange={cambiar('country')} sx={{ width: 120 }} />
            <TextField
              fullWidth
              label={t('Zona horaria')}
              value={form.time_zone ?? ''}
              onChange={cambiar('time_zone')}
              helperText={t('En la que se mide su jornada. Un centro puede tener otra.')}
            />
          </Stack>
          <Typography variant="subtitle2" sx={{ pt: 1 }}>
            {t('Quien la administra')}
          </Typography>
          <TextField label={t('Correo electrónico')} value={form.email ?? ''} onChange={cambiar('email')} />
          <Stack direction="row" spacing={2}>
            <TextField fullWidth label={t('Nombre')} value={form.first_name ?? ''} onChange={cambiar('first_name')} />
            <TextField fullWidth label={t('Apellidos')} value={form.last_name ?? ''} onChange={cambiar('last_name')} />
          </Stack>
          <Alert severity="info">
            {t('Su contraseña se genera y se enseña una sola vez al crear la empresa.')}
          </Alert>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={guardando}>
          {t('Cancelar')}
        </Button>
        <Button
          variant="contained"
          onClick={guardar}
          disabled={guardando || !form.company_name || !form.tax_id || !form.email}
        >
          {t('Crear')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

/** Cómo entra la gente de esa empresa: con contraseña, o por su proveedor. */
function IdentityDialog({ empresa, onClose, onGuardada }) {
  const { t } = useTranslation()
  // Igual que el de arriba: el padre lo remonta con `key`, así que el estado
  // inicial es el de esta empresa y no hace falta sincronizar nada.
  const [form, setForm] = useState(() => {
    const identidad = empresa?.identity
    return {
      name: identidad?.name ?? '',
      issuer: identidad?.issuer ?? '',
      slug: identidad?.slug ?? '',
      jwks_uri: identidad?.jwks_uri ?? '',
      client_id: identidad?.client_id ?? '',
      client_secret: '',
      may_act_for_people: identidad?.may_act_for_people ?? false,
      is_active: identidad?.is_active ?? true,
      domains: (identidad?.domains ?? []).join('\n'),
      has_secret: identidad?.has_secret ?? false,
    }
  })
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const cambiar = (campo) => (e) =>
    setForm((previo) => ({
      ...previo,
      [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value,
    }))

  const guardar = async () => {
    setGuardando(true)
    setError(null)
    try {
      await saveCompanyIdentity(empresa.id, {
        ...form,
        domains: form.domains.split('\n').map((d) => d.trim()).filter(Boolean),
      })
      onGuardada()
    } catch (fallo) {
      const datos = fallo?.response?.data ?? {}
      const dicho = datos?.error?.message ?? Object.values(datos).flat().join(' ')
      setError(dicho || t('No se ha podido guardar.'))
    } finally {
      setGuardando(false)
    }
  }

  const quitar = async () => {
    setGuardando(true)
    try {
      await removeCompanyIdentity(empresa.id)
      onGuardada()
    } catch {
      setError(t('No se ha podido quitar el proveedor.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Dialog open={Boolean(empresa)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {t('Cómo entra su gente')}
        {empresa ? ` — ${empresa.name}` : ''}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <Alert severity="info">
            {t('Sin proveedor, su gente entra con correo y contraseña de aquí. Con proveedor, entra con el sistema de su empresa.')}
          </Alert>
          <TextField label={t('Nombre del proveedor')} value={form.name ?? ''} onChange={cambiar('name')} />
          <TextField
            label={t('Emisor')}
            value={form.issuer ?? ''}
            onChange={cambiar('issuer')}
            placeholder="https://api.empresa.example/o"
            helperText={t('Exactamente el «iss» de sus testigos.')}
          />
          <TextField
            label={t('Dirección de las claves')}
            value={form.jwks_uri ?? ''}
            onChange={cambiar('jwks_uri')}
            helperText={t('En blanco se le pregunta al proveedor. Ponerlo evita depender de eso.')}
          />
          <Stack direction="row" spacing={2}>
            <TextField fullWidth label={t('Identificador de cliente')} value={form.client_id ?? ''} onChange={cambiar('client_id')} />
            <TextField
              fullWidth
              type="password"
              label={t('Secreto')}
              value={form.client_secret ?? ''}
              onChange={cambiar('client_secret')}
              helperText={form.has_secret ? t('Hay uno guardado. En blanco se deja como está.') : ''}
            />
          </Stack>
          <TextField
            label={t('Dominios de correo')}
            value={form.domains ?? ''}
            onChange={cambiar('domains')}
            multiline
            minRows={2}
            helperText={t('Uno por línea. Nada de dominios personales: mandaría al proveedor a cualquiera que escriba uno.')}
          />
          <FormControlLabel
            control={<Switch checked={Boolean(form.may_act_for_people)} onChange={cambiar('may_act_for_people')} />}
            label={t('Su aplicación puede fichar en nombre de su gente')}
          />
          <FormControlLabel
            control={<Switch checked={Boolean(form.is_active)} onChange={cambiar('is_active')} />}
            label={t('Activo')}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        {empresa?.identity && (
          <Button color="error" onClick={quitar} disabled={guardando}>
            {t('Quitar el proveedor')}
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose} disabled={guardando}>
          {t('Cancelar')}
        </Button>
        <Button variant="contained" onClick={guardar} disabled={guardando || !form.name || !form.issuer}>
          {t('Guardar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
