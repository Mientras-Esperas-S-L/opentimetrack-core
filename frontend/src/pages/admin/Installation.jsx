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
import MenuItem from '@mui/material/MenuItem'
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
  addPlatformAdmin,
  authoriseApplicationOfCompany,
  createCompany,
  updateCompanyOfInstallation,
  deactivatePlatformAdmin,
  getPlatformAdmins,
  sendPlatformAdminLink,
  updatePlatformAdmin,
  getCompanyAdmins,
  getPlatformAudit,
  sendCompanyAdminLink,
  PAGE_SIZE,
  resetPlatformAdminPassword,
  getApplicationsOfCompany,
  getCompanies,
  getInstance,
  issueCredentialOfCompany,
  removeCompanyIdentity,
  revokeCredentialOfCompany,
  saveCompanyIdentity,
  withdrawApplicationOfCompany,
} from '../../services/api.js'
import { Pager } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'
import { alCatalogo, localeDeFechas } from '../../i18n/index.js'

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
  const [credencialesDe, setCredencialesDe] = useState(null)
  const [fichaDe, setFichaDe] = useState(null)
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
      {/* Por `sx` y no como props sueltas: MUI dejó de aceptar las props del
          sistema, así que `justifyContent` y `gap` escritos así no llegaban al
          CSS --medido, `justify-content: normal`-- y el botón se montaba encima
          de la línea que explica la pantalla. */}
      {/* Apilada en el móvil. Compartiendo fila, el título y su explicación se
          quedaban en una columna de ciento cuarenta píxeles: «Quién administra esta
          instalación» salía en cuatro líneas de una palabra. */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{
          alignItems: { xs: 'stretch', sm: 'center' },
          justifyContent: 'space-between',
          gap: 2,
          mb: 2,
        }}
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
            {t(
              'Empresa creada. Apunta ahora la contraseña de quien la administra: no se vuelve a enseñar.',
            )}
          </Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
            {reciénCreada.email} · {reciénCreada.password}
          </Typography>
          {/* Y qué viene después, que es la pregunta que deja esta pantalla:
              desde aquí no se entra en ninguna empresa, así que lo demás se
              hace con la cuenta que se acaba de crear. */}
          <Typography variant="body2" sx={{ mt: 1 }}>
            {t(
              'Lo que falta se hace entrando con esa cuenta: su gente, sus centros y la credencial con la que otra aplicación habla con esta empresa.',
            )}
          </Typography>
        </Alert>
      )}

      {/* La tabla se desliza dentro de su caja en vez de estirar la página.
          Medido en devel a 360 px: con siete columnas, el navegador del móvil se
          rendía y usaba un viewport de **978 px**, o sea que enseñaba la pantalla
          entera a un tercio de su tamaño ---título incluido, que salía en una
          columna de palabra por línea---. Así el documento se queda en 360 y lo
          único que se arrastra es la tabla. */}
      <Paper variant="outlined" sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth: 820 }}>
          <TableHead>
            <TableRow>
              <TableCell>{t('Empresa')}</TableCell>
              <TableCell align="right">{t('Personas')}</TableCell>
              <TableCell>{t('Cómo entran')}</TableCell>
              <TableCell>{t('Actividad')}</TableCell>
              <TableCell>{t('Qué le falta')}</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {empresas.map((empresa) => (
              <TableRow key={empresa.id}>
                <TableCell>
                  {empresa.name}
                  {!empresa.is_active && (
                    <Chip
                      size="small"
                      color="error"
                      variant="outlined"
                      label={t('Desactivada')}
                      sx={{ ml: 1 }}
                    />
                  )}
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {/* Aquí y no en su columna: 106 px que, a 1280, dejaban los
                        botones fuera. */}
                    {empresa.tax_id} · {empresa.time_zone}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  {/* Las activas: una baja no ficha, y contarla hacía parecer viva a
                      una empresa que ya no tiene a nadie dentro. */}
                  {empresa.status?.active_people ?? empresa.people}
                  {empresa.status && empresa.status.active_people !== empresa.people && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {t('de {{total}}', { total: empresa.people })}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  {empresa.identity ? (
                    <>
                      <Chip
                        size="small"
                        color="primary"
                        variant="outlined"
                        label={empresa.identity.name}
                        title={empresa.identity.domains.join(', ')}
                      />
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', mt: 0.5 }}
                      >
                        {empresa.status?.last_identity_sign_in_day
                          ? t('Último acceso con ella: {{dia}}', {
                              dia: diaCorto(empresa.status.last_identity_sign_in_day),
                            })
                          : empresa.status?.identity_people
                            ? t('{{n}} persona(s) han entrado con ella', {
                                n: empresa.status.identity_people,
                              })
                            : t('Nadie ha entrado todavía con ella')}
                      </Typography>
                    </>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {t('Con contraseña')}
                    </Typography>
                  )}
                </TableCell>
                {/* «Con qué se conectan» vivía en su columna; ahora va aquí, con el
                    día en que cada aplicación habló. Con ocho columnas, a 1280 px la
                    de los botones quedaba cortada y esta salía palabra a palabra. */}
                <TableCell sx={{ minWidth: 190 }}>
                  <Actividad estado={empresa.status} />
                </TableCell>
                <TableCell>
                  <LeFalta
                    empresa={empresa}
                    onIdentidad={() => setIdentidadDe(empresa)}
                    onCredencial={() => setCredencialesDe(empresa)}
                  />
                </TableCell>
                <TableCell align="right">
                  {/* Uno debajo de otro: en fila, los tres ocupaban la anchura de dos
                      columnas. */}
                  <Stack sx={{ alignItems: 'flex-end' }}>
                    <Button size="small" onClick={() => setFichaDe(empresa)}>
                      {t('Ficha')}
                    </Button>
                    <Button size="small" onClick={() => setCredencialesDe(empresa)}>
                      {t('Credenciales')}
                    </Button>
                    <Button size="small" onClick={() => setIdentidadDe(empresa)}>
                      {t('Identidad')}
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!cargando && empresas.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
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

      <PlatformAdmins onCambio={cargar} />

      <PlatformAudit vuelta={vuelta} />

      <CredentialsDialog
        key={credencialesDe?.id ?? 'sin-credenciales'}
        empresa={credencialesDe}
        onClose={() => setCredencialesDe(null)}
        onCambio={cargar}
      />

      <CompanyDialog
        key={fichaDe?.id ?? 'sin-ficha'}
        empresa={fichaDe}
        onClose={() => setFichaDe(null)}
        onGuardada={() => {
          setFichaDe(null)
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
      setError(motivo(fallo) || t('No se ha podido crear la empresa.'))
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
          <TextField
            label={t('Nombre fiscal')}
            value={form.company_name ?? ''}
            onChange={cambiar('company_name')}
          />
          <TextField
            label={t('CIF')}
            value={form.tax_id ?? ''}
            onChange={cambiar('tax_id')}
            helperText={t('Es lo que distingue a una empresa de otra: no puede repetirse.')}
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label={t('País')}
              value={form.country ?? 'ES'}
              onChange={cambiar('country')}
              sx={{ width: 120 }}
            />
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
          <TextField
            label={t('Correo electrónico')}
            value={form.email ?? ''}
            onChange={cambiar('email')}
          />
          <Stack direction="row" spacing={2}>
            <TextField
              fullWidth
              label={t('Nombre')}
              value={form.first_name ?? ''}
              onChange={cambiar('first_name')}
            />
            <TextField
              fullWidth
              label={t('Apellidos')}
              value={form.last_name ?? ''}
              onChange={cambiar('last_name')}
            />
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
  // La vuelta que hay que registrar en el proveedor, tal como esta instalación la
  // va a mandar. Se compara letra a letra, y deducirla de la barra del navegador
  // falla con la API en otro host o detrás de un proxy.
  const [vuelta, setVuelta] = useState('')
  useEffect(() => {
    let vigente = true
    getInstance()
      .then((instalacion) => vigente && setVuelta(instalacion.sso_callback_url ?? ''))
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])

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
        domains: form.domains
          .split('\n')
          .map((d) => d.trim())
          .filter(Boolean),
      })
      onGuardada()
    } catch (fallo) {
      setError(motivo(fallo) || t('No se ha podido guardar.'))
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
            {t(
              'Sin proveedor, su gente entra con correo y contraseña de aquí. Con proveedor, entra con el sistema de su empresa.',
            )}
          </Alert>
          {vuelta && (
            <TextField
              label={t('Dirección de vuelta para registrar en el proveedor')}
              value={vuelta}
              slotProps={{ input: { readOnly: true } }}
              helperText={t('Cópiala tal cual: el proveedor la compara letra a letra.')}
            />
          )}
          <TextField
            label={t('Nombre del proveedor')}
            value={form.name ?? ''}
            onChange={cambiar('name')}
          />
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
            <TextField
              fullWidth
              label={t('Identificador de cliente')}
              value={form.client_id ?? ''}
              onChange={cambiar('client_id')}
            />
            <TextField
              fullWidth
              type="password"
              label={t('Secreto')}
              value={form.client_secret ?? ''}
              onChange={cambiar('client_secret')}
              helperText={
                form.has_secret ? t('Hay uno guardado. En blanco se deja como está.') : ''
              }
            />
          </Stack>
          <TextField
            label={t('Dominios de correo')}
            value={form.domains ?? ''}
            onChange={cambiar('domains')}
            multiline
            minRows={2}
            helperText={t(
              'Uno por línea. Nada de dominios personales: mandaría al proveedor a cualquiera que escriba uno.',
            )}
          />
          <FormControlLabel
            control={
              <Switch
                checked={Boolean(form.may_act_for_people)}
                onChange={cambiar('may_act_for_people')}
              />
            }
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
        <Button
          variant="contained"
          onClick={guardar}
          disabled={guardando || !form.name || !form.issuer}
        >
          {t('Guardar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

/** Las aplicaciones de una empresa, desde fuera de ella.
 *
 *  Es lo que enchufa una aplicación externa: sin esta credencial, el alta se
 *  queda en una empresa vacía. Vivía solo dentro de la empresa, así que darla de alta obligaba
 *  a salir de aquí, entrar con la cuenta de su administrador y volver.
 *
 *  **El testigo se enseña una vez.** Se guarda cifrado de un solo sentido, así que
 *  no hay forma de volver a verlo: si se pierde, se emite otro. La pantalla lo dice
 *  en vez de dejar que se descubra.
 */
function CredentialsDialog({ empresa, onClose, onCambio }) {
  const { t } = useTranslation()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [trabajando, setTrabajando] = useState(false)
  const [testigo, setTestigo] = useState(null)
  const [vuelta, setVuelta] = useState(0)
  const [nombreNueva, setNombreNueva] = useState('')

  useEffect(() => {
    if (!empresa) return undefined
    let vivo = true
    getApplicationsOfCompany(empresa.id)
      .then((d) => vivo && setDatos(d))
      .catch(() => vivo && setError(t('No he podido leer sus aplicaciones.')))
    return () => {
      vivo = false
    }
  }, [empresa, t, vuelta])

  const recargar = () => {
    setVuelta((n) => n + 1)
    onCambio?.()
  }

  const hacer = async (accion) => {
    setError(null)
    setTrabajando(true)
    try {
      await accion()
      recargar()
    } catch (fallo) {
      setError(motivo(fallo) || t('No ha salido bien.'))
    } finally {
      setTrabajando(false)
    }
  }

  const aplicaciones = datos?.applications ?? []

  return (
    <Dialog open={Boolean(empresa)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {t('Credenciales de {{empresa}}', { empresa: empresa?.name ?? '' })}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}

          {testigo && (
            <Alert severity="success" onClose={() => setTestigo(null)}>
              <Typography variant="body2">{t('Cópiala ahora: no se vuelve a enseñar.')}</Typography>
              <Typography
                variant="body2"
                sx={{ fontFamily: 'monospace', mt: 0.5, wordBreak: 'break-all' }}
              >
                {testigo}
              </Typography>
            </Alert>
          )}

          {aplicaciones.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              {t(
                'Esta empresa no tiene ninguna aplicación autorizada. Sin credencial, ninguna aplicación puede hablar con ella.',
              )}
            </Typography>
          )}

          {aplicaciones.map((app) => (
            <Paper key={app.id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack
                direction="row"
                sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}
              >
                <Box>
                  <Typography variant="body2">
                    {app.name}
                    {!app.is_active && ` · ${t('retirada')}`}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t('{{cuantos}} permiso(s)', { cuantos: app.scopes.length })}
                  </Typography>
                </Box>
                {app.is_active && (
                  <Box>
                    <Button
                      size="small"
                      disabled={trabajando}
                      onClick={() =>
                        hacer(async () => {
                          const nueva = await issueCredentialOfCompany(empresa.id, app.id)
                          setTestigo(nueva.token)
                        })
                      }
                    >
                      {t('Emitir otra')}
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      disabled={trabajando}
                      onClick={() => hacer(() => withdrawApplicationOfCompany(empresa.id, app.id))}
                    >
                      {t('Retirar')}
                    </Button>
                  </Box>
                )}
              </Stack>

              {app.credentials.map((c) => (
                <Stack
                  key={c.id}
                  direction="row"
                  sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 1 }}
                >
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    …{c.token_hint}
                    {c.label ? ` · ${c.label}` : ''}
                    {!c.is_valid && ` · ${t('revocada')}`}
                  </Typography>
                  {c.is_valid && (
                    <Button
                      size="small"
                      color="error"
                      disabled={trabajando}
                      onClick={() =>
                        hacer(() => revokeCredentialOfCompany(empresa.id, app.id, c.id))
                      }
                    >
                      {t('Revocar')}
                    </Button>
                  )}
                </Stack>
              ))}
            </Paper>
          ))}

          {/* El nombre lo pone quien autoriza: es el que sale en el registro de
              cada fichaje que haga esa aplicación. Antes venía escrito aquí, con el
              de un producto concreto, en un programa que usa cualquiera. */}
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            sx={{ gap: 1, alignItems: { sm: 'flex-start' } }}
          >
            <TextField
              size="small"
              fullWidth
              label={t('Nombre de la aplicación')}
              value={nombreNueva}
              onChange={(e) => setNombreNueva(e.target.value)}
              helperText={t('El que saldrá en cada fichaje que haga.')}
            />
            <Button
              variant="contained"
              sx={{ flexShrink: 0 }}
              disabled={trabajando || !nombreNueva.trim()}
              onClick={() =>
                hacer(async () => {
                  const creada = await authoriseApplicationOfCompany(empresa.id, {
                    name: nombreNueva.trim(),
                  })
                  setTestigo(creada.token)
                  setNombreNueva('')
                })
              }
            >
              {t('Autorizar')}
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {t(
              'Autorizar concede de una vez los diez permisos de una integración completa: altas de personas, fichaje en su nombre, ausencias, cuadrante, calendario y disponibilidad. La credencial que sale es la que se pega en la aplicación.',
            )}
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('Cerrar')}</Button>
      </DialogActions>
    </Dialog>
  )
}

/** Quién puede administrar esta instalación.
 *
 *  La primera cuenta se crea en el contenedor y no hay forma de evitarlo: no hay
 *  sesión con la que autorizar su alta. Pero que la segunda siguiera pidiendo un
 *  shell dejaba la instalación con **una sola persona** capaz de operarla, y sin
 *  relevo en cuanto esa persona se va.
 */
function PlatformAdmins({ onCambio }) {
  const { t } = useTranslation()
  const { session } = useAuth()
  const [editando, setEditando] = useState(null)
  const [enviadoA, setEnviadoA] = useState(null)
  const [cuentas, setCuentas] = useState([])
  const [error, setError] = useState(null)
  const [trabajando, setTrabajando] = useState(false)
  const [reciénDicha, setReciénDicha] = useState(null)
  const [nueva, setNueva] = useState(null)
  const [vuelta, setVuelta] = useState(0)

  useEffect(() => {
    let vivo = true
    getPlatformAdmins()
      .then((d) => vivo && setCuentas(d))
      .catch(() => vivo && setError(t('No he podido leer quién administra esta instalación.')))
    return () => {
      vivo = false
    }
  }, [t, vuelta])

  const hacer = async (accion) => {
    setError(null)
    setTrabajando(true)
    try {
      await accion()
      setVuelta((n) => n + 1)
      onCambio?.()
    } catch (fallo) {
      setError(motivo(fallo) || t('No ha salido bien.'))
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <Box sx={{ mt: 4 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{
          alignItems: { xs: 'stretch', sm: 'center' },
          justifyContent: 'space-between',
          gap: 2,
          mb: 2,
        }}
      >
        <Box>
          <Typography variant="h6">{t('Quién administra esta instalación')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('Estas cuentas no pertenecen a ninguna empresa y no ven los datos de ninguna.')}
          </Typography>
        </Box>
        <Button
          sx={{ flexShrink: 0 }}
          onClick={() => setNueva({ email: '', first_name: '', last_name: '' })}
        >
          {t('Añadir cuenta')}
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {enviadoA && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setEnviadoA(null)}>
          {t('Enlace enviado a {{correo}}.', { correo: enviadoA })}
        </Alert>
      )}

      {reciénDicha && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setReciénDicha(null)}>
          <Typography variant="body2">{t('Cópiala ahora: no se vuelve a enseñar.')}</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
            {reciénDicha.email} · {reciénDicha.password}
          </Typography>
        </Alert>
      )}

      {/* Filas apiladas y no una tabla: a 360 px, el nombre quedaba en una columna
          de una palabra y los cuatro botones en torre. Así el nombre ocupa el ancho
          y las acciones van debajo, en las líneas que hagan falta. */}
      <Paper variant="outlined">
        <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}>
          {cuentas.map((cuenta) => (
            <Stack
              key={cuenta.id}
              direction={{ xs: 'column', sm: 'row' }}
              sx={{
                px: 2,
                py: 1,
                gap: 0.5,
                alignItems: { sm: 'center' },
                justifyContent: 'space-between',
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2">
                  {cuenta.first_name} {cuenta.last_name}
                  {cuenta.id === session?.user?.id && ` (${t('tú')})`}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', overflowWrap: 'anywhere' }}
                >
                  {cuenta.email}
                  {!cuenta.is_active && ` · ${t('desactivada')}`}
                </Typography>
              </Box>
              <Stack
                direction="row"
                sx={{
                  flexWrap: 'wrap',
                  justifyContent: { xs: 'flex-start', sm: 'flex-end' },
                  columnGap: 0.5,
                }}
              >
                <Button size="small" disabled={trabajando} onClick={() => setEditando(cuenta)}>
                  {t('Editar')}
                </Button>
                {cuenta.is_active && (
                  <Button
                    size="small"
                    disabled={trabajando}
                    onClick={() =>
                      hacer(async () => {
                        const { sent_to: a } = await sendPlatformAdminLink(cuenta.id)
                        setEnviadoA(a)
                      })
                    }
                  >
                    {t('Mandar enlace')}
                  </Button>
                )}
                <Button
                  size="small"
                  disabled={trabajando}
                  onClick={() =>
                    hacer(async () => {
                      const dicha = await resetPlatformAdminPassword(cuenta.id)
                      setReciénDicha(dicha)
                    })
                  }
                >
                  {t('Nueva contraseña')}
                </Button>
                {/* La propia no: el servidor no deja desactivarse a uno mismo, y
                    un botón que siempre contesta que no es un error de pantalla. */}
                {cuenta.id === session?.user?.id ? null : cuenta.is_active ? (
                  <Button
                    size="small"
                    color="error"
                    disabled={trabajando}
                    onClick={() => hacer(() => deactivatePlatformAdmin(cuenta.id))}
                  >
                    {t('Desactivar')}
                  </Button>
                ) : (
                  <Button
                    size="small"
                    disabled={trabajando}
                    onClick={() => hacer(() => updatePlatformAdmin(cuenta.id, { is_active: true }))}
                  >
                    {t('Reactivar')}
                  </Button>
                )}
              </Stack>
            </Stack>
          ))}
        </Stack>
      </Paper>

      <EditAdminDialog
        key={editando?.id ?? 'sin-edicion'}
        cuenta={editando}
        onClose={() => setEditando(null)}
        onGuardada={() => {
          setEditando(null)
          setVuelta((n) => n + 1)
          onCambio?.()
        }}
      />

      <NewAdminDialog
        key={nueva ? 'nueva-cuenta' : 'sin-cuenta'}
        valores={nueva}
        onClose={() => setNueva(null)}
        onCreada={(dicha) => {
          setReciénDicha(dicha)
          setNueva(null)
          setVuelta((n) => n + 1)
          onCambio?.()
        }}
      />
    </Box>
  )
}

function NewAdminDialog({ valores, onClose, onCreada }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() => valores ?? {})
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const cambiar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))

  const guardar = async () => {
    setError(null)
    setGuardando(true)
    try {
      onCreada(await addPlatformAdmin(form))
    } catch (fallo) {
      setError(motivo(fallo) || t('No se ha podido crear la cuenta.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Dialog open={Boolean(valores)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('Añadir cuenta')}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label={t('Correo electrónico')}
            value={form.email ?? ''}
            onChange={cambiar('email')}
          />
          <TextField
            label={t('Nombre')}
            value={form.first_name ?? ''}
            onChange={cambiar('first_name')}
          />
          <TextField
            label={t('Apellidos')}
            value={form.last_name ?? ''}
            onChange={cambiar('last_name')}
          />
          <Typography variant="caption" color="text.secondary">
            {t('Su contraseña se genera y se enseña una sola vez.')}
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('Cancelar')}</Button>
        <Button variant="contained" onClick={guardar} disabled={guardando}>
          {t('Crear')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

/** Lo que le falta a una empresa para estar enchufada, y por dónde se arregla.
 *
 *  El «¿y ahora qué?» de quien acaba de dar un alta: la empresa existe, y averiguar
 *  qué queda obligaba a abrir tres diálogos uno por uno. Quién decide qué falta es
 *  el servidor ---viene en `missing`---, porque es una regla del producto y el
 *  asistente de alta de cualquier integrador tiene que contestar con la misma.
 */
function LeFalta({ empresa, onIdentidad, onCredencial }) {
  const { t } = useTranslation()
  const huecos = empresa.missing ?? []

  if (huecos.length === 0) {
    return <Chip size="small" color="success" variant="outlined" label={t('Lista')} />
  }

  // Lo que se puede arreglar desde aquí lleva su botón; lo que no ---que entre su
  // gente--- se dice y ya, porque llega sola cuando la da de alta la aplicación.
  const comoSeArregla = {
    identity: { texto: t('Cómo entran'), accion: onIdentidad },
    application: { texto: t('Credencial'), accion: onCredencial },
    people: { texto: t('Su gente'), accion: null },
  }

  return (
    <Stack direction="row" sx={{ gap: 0.5, flexWrap: 'wrap' }}>
      {huecos.map((hueco) => {
        const como = comoSeArregla[hueco]
        if (!como) return null
        return (
          <Chip
            key={hueco}
            size="small"
            color="warning"
            variant="outlined"
            label={como.texto}
            onClick={como.accion ?? undefined}
            title={
              como.accion
                ? t('Pulsa para arreglarlo')
                : t('Su gente llega sola cuando la da de alta la aplicación integrada.')
            }
          />
        )
      })}
    </Stack>
  )
}

/** Lo que han hecho las cuentas de la instalación.
 *
 *  Una lista y no una tabla: a 360 px una tabla de cuatro columnas obliga a
 *  arrastrar para leer quién lo hizo, y aquí cada entrada se lee de una vez.
 *
 *  `vuelta` la sube la pantalla cada vez que algo cambia, para que lo recién hecho
 *  aparezca arriba sin recargar.
 */
function PlatformAudit({ vuelta }) {
  const { t } = useTranslation()
  const [pagina, setPagina] = useState(1)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivo = true
    getPlatformAudit({ page: pagina })
      .then((d) => vivo && setDatos(d))
      .catch(() => vivo && setError(t('No he podido leer el registro de la instalación.')))
    return () => {
      vivo = false
    }
  }, [t, pagina, vuelta])

  const cuando = (iso) =>
    new Date(iso).toLocaleString(localeDeFechas(), {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })

  return (
    <Box sx={{ mt: 4 }}>
      <Typography variant="h6">{t('Registro')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t(
          'Lo que han hecho las cuentas de esta instalación. No se puede cambiar ni borrar. Lo que toca a una empresa también queda en el registro de esa empresa.',
        )}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {datos && datos.rows.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          {t('Todavía no hay nada anotado.')}
        </Typography>
      )}

      {datos && datos.rows.length > 0 && (
        <Paper variant="outlined">
          <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}>
            {datos.rows.map((entrada) => (
              <Box key={entrada.id} sx={{ px: 2, py: 1.25 }}>
                <Typography variant="body2">
                  <strong>{entrada.action_label}</strong>
                  {entrada.target_label && ` · ${entrada.target_label}`}
                  {entrada.company_label &&
                    entrada.company_label !== entrada.target_label &&
                    ` · ${entrada.company_label}`}
                </Typography>
                <Typography variant="caption" color="text.secondary" component="div">
                  {cuando(entrada.at)} · {entrada.actor || t('sistema')}
                  {entrada.note && ` · ${entrada.note}`}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Paper>
      )}

      <Pager
        count={datos?.count ?? 0}
        page={pagina}
        pageSize={PAGE_SIZE}
        onChange={setPagina}
        noun={{ singular: alCatalogo('entrada'), plural: alCatalogo('entradas') }}
      />
    </Box>
  )
}

/** Lo que dice el servidor cuando rechaza, en una frase.
 *
 *  **El error ya llega normalizado** por el interceptor de `api.js`: `{code,
 *  message, details, status}`, sin `response`. Esta pantalla lo leía como un
 *  error de axios crudo ---`fallo.response.data`--- y no encontraba nada, así que
 *  todo rechazo acababa en el genérico: «No se ha podido crear la cuenta» donde el
 *  servidor decía que ese correo ya existía. Medido en devel el 23/09/2026.
 *
 *  El mensaje general de validación no dice qué campo; si hay detalle, se añade.
 */
function motivo(fallo) {
  const campos = Object.values(fallo?.details ?? {}).flat()
  return [fallo?.message, ...campos].filter(Boolean).join(' ')
}

/** Lo que dice el servidor cuando rechaza, campo a campo.
 *
 *  El mensaje general es «Los datos enviados no son válidos», que no dice cuál. El
 *  detalle sí, y es lo que se enseña al lado de cada casilla.
 */
function porCampo(fallo) {
  const detalles = fallo?.details ?? {}
  return Object.fromEntries(
    Object.entries(detalles).map(([campo, dichos]) => [campo, [].concat(dichos).join(' ')]),
  )
}

/** La ficha de una empresa: cambiarla, desactivarla o volver a activarla.
 *
 *  Desactivar está aquí dentro y no en la fila de la lista: es lo único de esta
 *  pantalla que deja a una empresa entera sin entrar, y un botón al alcance del
 *  dedo en una tabla que se arrastra en el móvil es un accidente esperando.
 */
function CompanyDialog({ empresa, onClose, onGuardada }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() =>
    empresa
      ? {
          name: empresa.name,
          tax_id: empresa.tax_id,
          country: empresa.country,
          time_zone: empresa.time_zone,
          language: empresa.language,
        }
      : {},
  )
  const [confirmacion, setConfirmacion] = useState('')
  const [errores, setErrores] = useState({})
  const [error, setError] = useState(null)
  const [trabajando, setTrabajando] = useState(false)

  const cambiar = (campo) => (e) => setForm((previo) => ({ ...previo, [campo]: e.target.value }))

  const enviar = async (cuerpo) => {
    setTrabajando(true)
    setError(null)
    setErrores({})
    try {
      await updateCompanyOfInstallation(empresa.id, cuerpo)
      onGuardada()
    } catch (fallo) {
      const campos = porCampo(fallo)
      setErrores(campos)
      setError(Object.keys(campos).length ? null : motivo(fallo) || t('No ha salido bien.'))
    } finally {
      setTrabajando(false)
    }
  }

  if (!empresa) return null
  const cambiaElCif = form.tax_id?.trim().toUpperCase() !== empresa.tax_id

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t('Ficha de {{empresa}}', { empresa: empresa.name })}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label={t('Nombre fiscal')}
            value={form.name ?? ''}
            onChange={cambiar('name')}
            error={Boolean(errores.name)}
            helperText={errores.name}
          />
          <TextField
            label={t('CIF')}
            value={form.tax_id ?? ''}
            onChange={cambiar('tax_id')}
            error={Boolean(errores.tax_id)}
            helperText={errores.tax_id}
          />
          {cambiaElCif && (
            <Alert severity="warning">
              {t(
                'Quien entre escribiendo el CIF de la empresa tendrá que usar el nuevo. Las aplicaciones conectadas siguen funcionando: hablan con la empresa por su credencial, no por el CIF.',
              )}
            </Alert>
          )}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label={t('País')}
              value={form.country ?? ''}
              onChange={cambiar('country')}
              error={Boolean(errores.country)}
              helperText={errores.country}
              sx={{ width: { sm: 120 } }}
            />
            <TextField
              fullWidth
              label={t('Zona horaria')}
              value={form.time_zone ?? ''}
              onChange={cambiar('time_zone')}
              error={Boolean(errores.time_zone)}
              helperText={errores.time_zone}
            />
          </Stack>
          <TextField
            select
            label={t('Idioma')}
            value={form.language ?? 'es'}
            onChange={cambiar('language')}
          >
            <MenuItem value="es">{t('Castellano')}</MenuItem>
            <MenuItem value="ca">{t('Catalán')}</MenuItem>
            <MenuItem value="gl">{t('Gallego')}</MenuItem>
            <MenuItem value="en">{t('Inglés')}</MenuItem>
          </TextField>

          <CompanyAdmins empresa={empresa} />

          <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 2 }}>
            {empresa.is_active ? (
              <>
                <Typography variant="subtitle2">{t('Desactivar la empresa')}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  {t(
                    'Nadie de dentro podrá entrar, tampoco quien ya tenga la sesión abierta, y sus aplicaciones dejarán de poder fichar en su nombre. No se borra nada: su registro se guarda y se puede volver a activar tal como estaba.',
                  )}
                </Typography>
                <TextField
                  fullWidth
                  size="small"
                  label={t('Escribe «{{nombre}}» para confirmar', { nombre: empresa.name })}
                  value={confirmacion}
                  onChange={(e) => setConfirmacion(e.target.value)}
                  error={Boolean(errores.confirm)}
                  helperText={errores.confirm}
                />
                <Button
                  color="error"
                  variant="outlined"
                  sx={{ mt: 1.5 }}
                  disabled={trabajando || confirmacion.trim() !== empresa.name}
                  onClick={() => enviar({ is_active: false, confirm: confirmacion })}
                >
                  {t('Desactivar')}
                </Button>
              </>
            ) : (
              <>
                <Typography variant="subtitle2">{t('Empresa desactivada')}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  {t('Al reactivarla, su gente y sus aplicaciones vuelven a entrar como antes.')}
                </Typography>
                <Button
                  variant="outlined"
                  disabled={trabajando}
                  onClick={() => enviar({ is_active: true })}
                >
                  {t('Reactivar')}
                </Button>
              </>
            )}
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={trabajando}>
          {t('Cancelar')}
        </Button>
        <Button
          variant="contained"
          disabled={trabajando || !form.name || !form.tax_id}
          onClick={() => enviar(form)}
        >
          {trabajando ? t('Guardando…') : t('Guardar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

/** Quién administra la empresa, y el enlace para que pongan contraseña.
 *
 *  Es la llamada de soporte más habitual: «el responsable no puede entrar». El
 *  enlace va a **su** correo; aquí no se ve. Si se viera, quien administra la
 *  instalación podría entrar como esa persona en los datos de su empresa.
 */
function CompanyAdmins({ empresa }) {
  const { t } = useTranslation()
  const [quienes, setQuienes] = useState(null)
  const [error, setError] = useState(null)
  const [enviado, setEnviado] = useState(null)
  const [enviando, setEnviando] = useState(null)

  useEffect(() => {
    let vivo = true
    getCompanyAdmins(empresa.id)
      .then((d) => vivo && setQuienes(d))
      .catch(() => vivo && setError(t('No he podido leer quién administra esta empresa.')))
    return () => {
      vivo = false
    }
  }, [empresa.id, t])

  const mandar = async (persona) => {
    setError(null)
    setEnviado(null)
    setEnviando(persona.id)
    try {
      const { sent_to: a } = await sendCompanyAdminLink(empresa.id, persona.id)
      setEnviado(a)
    } catch (fallo) {
      setError(motivo(fallo) || t('No se ha podido mandar el enlace.'))
    } finally {
      setEnviando(null)
    }
  }

  const ultimoAcceso = (persona) =>
    persona.last_login
      ? t('Último acceso: {{cuando}}', {
          cuando: new Date(persona.last_login).toLocaleString(localeDeFechas(), {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
          }),
        })
      : // «Nunca» no se puede afirmar: la fecha solo se anota desde el 23/09/2026.
        t('No consta ningún acceso')

  return (
    <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 2 }}>
      <Typography variant="subtitle2">{t('Quién la administra')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t(
          'Si alguien no puede entrar, mándale un enlace para poner contraseña. Le llega a su correo; aquí no se ve.',
        )}
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}
      {enviado && (
        <Alert severity="success" sx={{ mb: 1 }} onClose={() => setEnviado(null)}>
          {t('Enlace enviado a {{correo}}.', { correo: enviado })}
        </Alert>
      )}
      {quienes === null && !error && (
        <Typography variant="body2" color="text.secondary">
          {t('Cargando…')}
        </Typography>
      )}
      <Stack spacing={1}>
        {(quienes ?? []).map((persona) => {
          const porQueNo = persona.federated
            ? t('Entra con la cuenta de su empresa: aquí no tiene contraseña.')
            : !persona.is_active
              ? t('Cuenta desactivada.')
              : !empresa.is_active
                ? t('La empresa está desactivada.')
                : null
          return (
            <Stack
              key={persona.id}
              direction={{ xs: 'column', sm: 'row' }}
              sx={{
                gap: 1,
                alignItems: { xs: 'stretch', sm: 'center' },
                justifyContent: 'space-between',
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                  {[persona.first_name, persona.last_name].filter(Boolean).join(' ') ||
                    persona.email}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', overflowWrap: 'anywhere' }}
                >
                  {persona.email} · {porQueNo ?? ultimoAcceso(persona)}
                </Typography>
              </Box>
              {!porQueNo && (
                <Button
                  size="small"
                  variant="outlined"
                  sx={{ flexShrink: 0 }}
                  disabled={enviando !== null}
                  onClick={() => mandar(persona)}
                >
                  {enviando === persona.id ? t('Enviando…') : t('Mandar enlace')}
                </Button>
              )}
            </Stack>
          )
        })}
        {quienes?.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            {t('Esta empresa no tiene a nadie que la administre.')}
          </Typography>
        )}
      </Stack>
    </Box>
  )
}

/** Un día del servidor (`AAAA-MM-DD`), corto y en el idioma de quien mira.
 *
 *  A mediodía y no a medianoche: `new Date('2026-09-17')` es medianoche **en UTC**,
 *  y en cualquier zona al oeste de Greenwich eso ya es el día anterior.
 */
function diaCorto(dia) {
  return new Date(`${dia}T12:00:00`).toLocaleDateString(localeDeFechas(), {
    day: 'numeric',
    month: 'short',
  })
}

/** Si su gente ficha y si sus aplicaciones hablan. Lo callado se dice con palabras,
 *  no solo con color: el color no se lee en voz alta ni en una pantalla al sol. */
function Actividad({ estado }) {
  const { t } = useTranslation()
  if (!estado) return null
  const linea = (texto, callado) => (
    <Typography
      variant="body2"
      color={callado ? 'warning.main' : 'text.primary'}
      sx={{ fontWeight: callado ? 600 : 400 }}
    >
      {texto}
    </Typography>
  )
  return (
    <Stack spacing={0.5}>
      {estado.last_punch_day
        ? linea(
            estado.punches_quiet
              ? t('Sin fichajes desde el {{dia}}', { dia: diaCorto(estado.last_punch_day) })
              : t('Último fichaje: {{dia}}', { dia: diaCorto(estado.last_punch_day) }),
            estado.punches_quiet,
          )
        : linea(t('Sin fichajes todavía'), false)}
      {estado.applications_detail.length === 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          {t('Sin aplicaciones conectadas')}
        </Typography>
      )}
      {estado.applications_detail.map((app) => (
        <Typography
          key={app.name}
          variant="caption"
          color={app.quiet ? 'warning.main' : 'text.secondary'}
          sx={{ display: 'block', fontWeight: app.quiet ? 600 : 400 }}
        >
          {app.last_used
            ? app.quiet
              ? t('{{app}}: callada desde el {{dia}}', {
                  app: app.name,
                  dia: diaCorto(app.last_used),
                })
              : t('{{app}}: usada el {{dia}}', { app: app.name, dia: diaCorto(app.last_used) })
            : t('{{app}}: sin usar todavía', { app: app.name })}
        </Typography>
      ))}
    </Stack>
  )
}

/** Corregir el nombre o el correo de una cuenta de la instalación.
 *
 *  El correo no se puede poner si ya lo usa otra cuenta, de la instalación o de una
 *  empresa: con dos del mismo correo, esta se quedaría sin forma de entrar. Lo
 *  decide el servidor y aquí se enseña su motivo.
 */
function EditAdminDialog({ cuenta, onClose, onGuardada }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() =>
    cuenta
      ? { first_name: cuenta.first_name, last_name: cuenta.last_name, email: cuenta.email }
      : {},
  )
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const cambiar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))

  if (!cuenta) return null

  const guardar = async () => {
    setError(null)
    setGuardando(true)
    try {
      await updatePlatformAdmin(cuenta.id, form)
      onGuardada()
    } catch (fallo) {
      setError(motivo(fallo) || t('No se ha podido guardar.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('Editar la cuenta')}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label={t('Correo electrónico')}
            value={form.email ?? ''}
            onChange={cambiar('email')}
          />
          <TextField
            label={t('Nombre')}
            value={form.first_name ?? ''}
            onChange={cambiar('first_name')}
          />
          <TextField
            label={t('Apellidos')}
            value={form.last_name ?? ''}
            onChange={cambiar('last_name')}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={guardando}>
          {t('Cancelar')}
        </Button>
        <Button variant="contained" onClick={guardar} disabled={guardando || !form.email}>
          {guardando ? t('Guardando…') : t('Guardar')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
