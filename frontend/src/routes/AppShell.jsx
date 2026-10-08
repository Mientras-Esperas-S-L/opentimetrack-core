import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import AppBar from '@mui/material/AppBar'
import Button from '@mui/material/Button'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import ListSubheader from '@mui/material/ListSubheader'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'

import LogoutIcon from '@mui/icons-material/Logout'
import HelpIcon from '@mui/icons-material/Help'

import ChangePasswordDialog from '../components/ChangePasswordDialog.jsx'
import HelpDrawer from '../components/HelpDrawer.jsx'
import { temaDeAyuda } from '../components/temaDeAyuda.js'
import MenuIcon from '@mui/icons-material/Menu'

import ThemeToggle from '../components/ThemeToggle.jsx'
import { usePlatformAdmin } from '../hooks/usePlatformAdmin.js'
import { useAuth } from '../hooks/useAuth.js'
import { leaveSupport } from '../services/api.js'
import { INSTALLATION_NAME } from '../installation.js'
import { NAV_ADMIN, NAV_PLATFORM, NAV_ME } from './navigation.jsx'
import BottomNav from './BottomNav.jsx'

const DRAWER_WIDTH = 232

/** Initials, for the avatar. Two letters read better than one at this size. */
function initialsOf(user) {
  const first = user?.first_name?.[0] ?? ''
  const last = user?.last_name?.[0] ?? ''
  return (first + last).toUpperCase() || user?.email?.[0]?.toUpperCase() || '?'
}

function Cabecera({ children }) {
  return (
    <ListSubheader
      sx={{
        bgcolor: 'transparent',
        fontSize: '0.7rem',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        lineHeight: 2.4,
      }}
    >
      {children}
    </ListSubheader>
  )
}

function NavSection({ title, items, onNavigate }) {
  const { t } = useTranslation()

  return (
    <List
      dense
      subheader={<Cabecera>{title}</Cabecera>}
    >
      {items.map(({ to, label, icon, end }) => (
        <ListItemButton
          key={to}
          component={NavLink}
          to={to}
          end={end}
          onClick={onNavigate}
          sx={{
            mx: 1,
            // Discreto a propósito. El factor se multiplica por `shape.borderRadius`
            // del tema, que son 10, así que un 1.5 daba 15 px sobre una fila de 40
            // y salía una píldora. Además el redondeo se comía los extremos de la
            // regla de la izquierda, que es justo lo que tiene que verse.
            borderRadius: 0.6,
            // The active item gets a left rule as well as a tint: on a phone in
            // sunlight the tint alone is not always visible.
            '&.active': {
              bgcolor: 'action.selected',
              boxShadow: (t) => `inset 3px 0 0 ${t.palette.primary.main}`,
              '& .MuiListItemText-primary': { fontWeight: 650 },
            },
          }}
        >
          <ListItemIcon sx={{ minWidth: 38 }}>{icon}</ListItemIcon>
          <ListItemText primary={t(label)} />
        </ListItemButton>
      ))}
    </List>
  )
}

export default function AppShell() {
  const { t } = useTranslation()
  const { session, signOut, setSession } = useAuth()
  const navigate = useNavigate()
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))
  const location = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cuentaEn, setCuentaEn] = useState(null)
  const [cambiandoClave, setCambiandoClave] = useState(0)

  const user = session?.user
  const company = session?.tenant
  //: Soporte de la instalación dentro de esta empresa. Se dice arriba y todo el
  //: rato: lo que se haga queda en su registro con ese nombre.
  const esSoporte = Boolean(user?.is_support)
  const salirDeSoporte = async () => {
    const vuelta = await leaveSupport()
    setSession(vuelta)
    navigate(vuelta ? '/panel/instalacion' : '/', { replace: true })
  }
  // Y de una empresa: la cuenta que administra la instalación trae rol de
  // administración y no está en ninguna, así que estas pantallas le contestan
  // 403 una por una. El menú no debe ofrecérselas.
  const canManage = Boolean(company) && (user?.role === 'MANAGER' || user?.role === 'ADMIN')
  // La asesoría laboral lee la gestión sin gestionar, y no ficha: de «Mi
  // trabajo» solo le queda saber quién ha mirado qué.
  const esAsesoria = Boolean(company) && user?.role === 'ADVISOR'
  const verGestion = canManage || esAsesoria
  const mio = esAsesoria ? NAV_ME.filter((item) => item.to === '/actividad') : NAV_ME
  // Alguna entrada de gestión es solo de administración. Ocultar un enlace no
  // es un permiso ---el API decide--- pero enseñar uno que va a contestar 403 sí
  // es un error de interfaz.
  const management = NAV_ADMIN.filter((item) =>
    esAsesoria ? item.asesoria : !item.adminOnly || user?.role === 'ADMIN',
  )
  // Y la instalación, que no es de quien administra una empresa: se pregunta al
  // servidor, porque el superusuario de plataforma es el que no pertenece a
  // ninguna y eso no viaja en la sesión.
  const administraLaInstalacion = usePlatformAdmin()
  //  La ayuda de la pantalla que se está mirando. El tema sale de la ruta, así que
  //  una pantalla nueva no tiene que acordarse de pasar nada: si no hay artículo
  //  para ella, el cajón abre por el índice.
  const [ayudaAbierta, setAyudaAbierta] = useState(false)

  //  Lo que ocupa la barra de arriba, medido. El menú lateral empieza debajo, y
  //  con un `<Toolbar />` de hueco solo dejaba sitio a la fila de los botones:
  //  en soporte el aviso amarillo se comía la parte de arriba del menú, que es
  //  donde va la vuelta a la instalación. El aviso cambia de alto al partirse en
  //  líneas, así que se mide en vez de suponerlo.
  const [altoBarra, setAltoBarra] = useState(null)
  const medirBarra = useCallback((barra) => {
    if (!barra) return undefined
    const observador = new ResizeObserver(() => setAltoBarra(barra.offsetHeight))
    observador.observe(barra)
    return () => observador.disconnect()
  }, [])
  const huecoBarra = altoBarra ? <Box sx={{ height: altoBarra, flexShrink: 0 }} /> : <Toolbar />

  // `alCerrar` es lo que `NavSection` esperaba en su `onNavigate` desde el
  // principio y nadie le pasaba: en un cajón que se superpone, elegir una
  // pantalla tiene que cerrarlo. En el permanente no hay nada que cerrar.
  const menu = (alCerrar) => (
    <Box sx={{ overflowY: 'auto', pb: 2 }}>
      {/* Dentro de una empresa como soporte, la vuelta a la consola solo estaba
          en el aviso de arriba, y no se buscaba ahí: se volvía escribiendo la
          dirección. Va la primera, con el mismo título que tenía antes de
          entrar: debajo de toda la gestión había que bajar para encontrarla. */}
      {esSoporte && (
        <>
          <List dense subheader={<Cabecera>{t('Instalación')}</Cabecera>}>
            <ListItemButton
              onClick={() => {
                alCerrar?.()
                salirDeSoporte()
              }}
              sx={{ mx: 1, borderRadius: 0.6 }}
            >
              <ListItemIcon sx={{ minWidth: 38 }}>{NAV_PLATFORM[0].icon}</ListItemIcon>
              <ListItemText primary={t('Volver a la instalación')} />
            </ListItemButton>
          </List>
          <Divider sx={{ my: 1, mx: 2 }} />
        </>
      )}
      {/* «Mi trabajo» es de quien trabaja en una empresa. La cuenta que
          administra la instalación no está en ninguna, y cada una de estas
          pantallas le contestaría 403: enseñar un enlace que no va a abrirse es
          el mismo error de interfaz que el de abajo, al revés. */}
      {company && <NavSection title={t('Mi trabajo')} items={mio} onNavigate={alCerrar} />}
      {verGestion && (
        <>
          <Divider sx={{ my: 1, mx: 2 }} />
          <NavSection title={t('Gestión')} items={management} onNavigate={alCerrar} />
        </>
      )}
      {administraLaInstalacion && (
        <>
          {/* El divisor solo si hay algo que separar. Para la cuenta que
              administra la instalación no hay secciones encima, y salía una
              raya suelta en lo alto del menú. */}
          {(company || verGestion) && <Divider sx={{ my: 1, mx: 2 }} />}
          <NavSection title={t('Instalación')} items={NAV_PLATFORM} onNavigate={alCerrar} />
        </>
      )}
    </Box>
  )

  const navigation = menu(undefined)
  const navigationConCierre = menu(() => setMenuAbierto(false))

  // La coincidencia más específica, y respetando `end`. Con `find` a secas
  // ganaba siempre «Resumen»: su ruta es `/panel`, que es prefijo de todas las
  // demás, así que la cabecera decía «Resumen» estando en Informes o en el
  // Cuadrante. Es el mismo fallo que `navigation.jsx` documenta y resuelve con
  // `end` para el resaltado del menú --- aquí se ignoraba.
  const currentLabel =
    [...NAV_ME, ...NAV_ADMIN]
      .filter((item) =>
        item.end
          ? location.pathname === item.to
          : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
      )
      .sort((a, b) => b.to.length - a.to.length)[0]?.label ?? ''

  return (
    <Box sx={{ display: 'flex', minHeight: '100dvh', bgcolor: 'background.default' }}>
      <AppBar
        ref={medirBarra}
        position="fixed"
        elevation={0}
        color="inherit"
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          zIndex: (t) => t.zIndex.drawer + 1,
        }}
      >
        <Toolbar sx={{ gap: 2 }}>
          {/* Sin esto, diez de las doce pantallas de gestión no tenían por
              dónde llegarse desde un móvil: la barra lateral solo existe de
              `md` para arriba y la barra de abajo solo lleva al Resumen. Las
              rutas funcionaban si se tecleaban. */}
          {!isDesktop && verGestion && (
            <IconButton
              edge="start"
              onClick={() => setMenuAbierto(true)}
              aria-label={t('Abrir el menú')}
            >
              <MenuIcon />
            </IconButton>
          )}
          <Stack sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography variant="h2" noWrap sx={{ fontSize: '1.05rem' }}>
              {/* El nombre de la instalación no se traduce: es un nombre propio. */}
              {isDesktop ? t(currentLabel) : INSTALLATION_NAME}
            </Typography>
            {company?.name && (
              <Typography variant="caption" color="text.secondary" noWrap>
                {company.name}
              </Typography>
            )}
          </Stack>

          <Chip
            size="small"
            variant="outlined"
            label={
              esSoporte
                ? t('Soporte')
                : user?.role === 'ADMIN'
                  ? t('Administración')
                  : esAsesoria
                    ? t('Asesoría laboral')
                    : canManage
                      ? t('Responsable')
                      : t('Persona trabajadora')
            }
            sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
          />
          <Tooltip title={t('Ayuda')}>
            <IconButton onClick={() => setAyudaAbierta(true)} aria-label={t('Ayuda')}>
              <HelpIcon />
            </IconButton>
          </Tooltip>
          <ThemeToggle />
          {/* Botón y no solo dibujo: abre la cuenta propia. La etiqueta va aquí y no
              en el Tooltip, que en MUI no deja `aria-label` en el DOM. */}
          <Tooltip title={user ? `${user.first_name} ${user.last_name}`.trim() : ''}>
            <IconButton
              onClick={(e) => setCuentaEn(e.currentTarget)}
              aria-label={t('Tu cuenta')}
              aria-haspopup="menu"
              aria-expanded={Boolean(cuentaEn)}
            >
              <Avatar sx={{ width: 34, height: 34, bgcolor: 'primary.main', fontSize: '0.85rem' }}>
                {initialsOf(user)}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Menu anchorEl={cuentaEn} open={Boolean(cuentaEn)} onClose={() => setCuentaEn(null)}>
            {/* Con quién se está dentro. Sin esto, quien volvía de su proveedor con
                la cuenta de otra persona no tenía dónde verlo. */}
            {user && (
              <Box sx={{ px: 2, pt: 1, pb: 1.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {`${user.first_name ?? ''} ${user.last_name ?? ''}`.trim() || user.email}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {user.email}
                </Typography>
              </Box>
            )}
            {user && <Divider />}
            {/* Quien entra con la cuenta de su empresa no tiene contraseña aquí. */}
            {!user?.is_federated && (
              <MenuItem
                onClick={() => {
                  setCuentaEn(null)
                  setCambiandoClave((n) => n + 1)
                }}
              >
                {t('Cambiar la contraseña')}
              </MenuItem>
            )}
            <MenuItem
              onClick={() => {
                setCuentaEn(null)
                signOut()
              }}
            >
              {t('Cerrar sesión')}
            </MenuItem>
          </Menu>
          <ChangePasswordDialog
            key={cambiandoClave}
            abierto={cambiandoClave > 0}
            onClose={() => setCambiandoClave(0)}
          />
          <Tooltip title={t('Cerrar sesión')}>
            <IconButton onClick={signOut} edge="end" aria-label={t('Cerrar sesión')}>
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
        {esSoporte && (
          <Alert
            severity="warning"
            square
            action={
              <Button color="inherit" size="small" onClick={salirDeSoporte}>
                {t('Salir de soporte')}
              </Button>
            }
          >
            {t(
              'Estás dentro de {{empresa}} como soporte. Lo que hagas queda en su registro de actividad.',
              { empresa: company?.name },
            )}
          </Alert>
        )}
      </AppBar>

      {!isDesktop && (
        <Drawer
          open={menuAbierto}
          onClose={() => setMenuAbierto(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              boxSizing: 'border-box',
              bgcolor: 'background.paper',
              backgroundImage: 'none',
            },
          }}
        >
          {huecoBarra}
          {navigationConCierre}
        </Drawer>
      )}

      {isDesktop && (
        <Drawer
          variant="permanent"
          sx={{
            width: DRAWER_WIDTH,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              boxSizing: 'border-box',
              borderRight: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
              backgroundImage: 'none',
            },
          }}
        >
          {huecoBarra}
          {navigation}
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          px: { xs: 2, md: 4 },
          // Más con el aviso de soporte, que va pegado a la barra de arriba.
          pt: esSoporte ? { xs: 17, md: 18 } : { xs: 10, md: 12 },
          // Room for the bottom bar on a phone, so the last row is reachable.
          pb: { xs: company ? 12 : 4, md: 5 },
        }}
      >
        <Outlet />
      </Box>

      {/* Sin empresa, fuera. Fichar, Mi jornada y Mis ausencias son de quien trabaja
          en una, y a la cuenta de la instalación le contestan 403: en el móvil las
          tenía abajo igual. Lo suyo, Instalación, está en el menú. */}
      {!isDesktop && company && <BottomNav canManage={canManage} esAsesoria={esAsesoria} />}

      {/* El tema sale de la ruta: `/panel/personas` pide `personas`. Así una
          pantalla nueva no tiene que acordarse de nada, y si no hay artículo para
          ella el cajón se abre por el índice y lo dice. */}
      <HelpDrawer
        key={ayudaAbierta ? temaDeAyuda(location.pathname) : 'cerrada'}
        abierto={ayudaAbierta}
        tema={temaDeAyuda(location.pathname)}
        onClose={() => setAyudaAbierta(false)}
      />
    </Box>
  )
}
