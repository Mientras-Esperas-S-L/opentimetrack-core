import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import AppBar from '@mui/material/AppBar'
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
import Stack from '@mui/material/Stack'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'

import LogoutIcon from '@mui/icons-material/Logout'
import MenuIcon from '@mui/icons-material/Menu'

import ThemeToggle from '../components/ThemeToggle.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { NAV_ADMIN, NAV_ME } from './navigation.jsx'
import BottomNav from './BottomNav.jsx'

const DRAWER_WIDTH = 232

/** Initials, for the avatar. Two letters read better than one at this size. */
function initialsOf(user) {
  const first = user?.first_name?.[0] ?? ''
  const last = user?.last_name?.[0] ?? ''
  return (first + last).toUpperCase() || user?.email?.[0]?.toUpperCase() || '?'
}

function NavSection({ title, items, onNavigate }) {
  const { t } = useTranslation()

  return (
    <List
      dense
      subheader={
        <ListSubheader
          sx={{
            bgcolor: 'transparent',
            fontSize: '0.7rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            lineHeight: 2.4,
          }}
        >
          {title}
        </ListSubheader>
      }
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
  const { session, signOut } = useAuth()
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))
  const location = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)

  const user = session?.user
  const company = session?.tenant
  const canManage = user?.role === 'MANAGER' || user?.role === 'ADMIN'
  // Alguna entrada de gestión es solo de administración. Ocultar un enlace no
  // es un permiso ---el API decide--- pero enseñar uno que va a contestar 403 sí
  // es un error de interfaz.
  const management = NAV_ADMIN.filter((item) => !item.adminOnly || user?.role === 'ADMIN')

  // `alCerrar` es lo que `NavSection` esperaba en su `onNavigate` desde el
  // principio y nadie le pasaba: en un cajón que se superpone, elegir una
  // pantalla tiene que cerrarlo. En el permanente no hay nada que cerrar.
  const menu = (alCerrar) => (
    <Box sx={{ overflowY: 'auto', pb: 2 }}>
      <NavSection title={t('Mi trabajo')} items={NAV_ME} onNavigate={alCerrar} />
      {canManage && (
        <>
          <Divider sx={{ my: 1, mx: 2 }} />
          <NavSection title={t('Gestión')} items={management} onNavigate={alCerrar} />
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
          {!isDesktop && canManage && (
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
              {/* El nombre del producto no se traduce: es un nombre propio. */}
              {isDesktop ? t(currentLabel) : 'OpenTimeTrack'}
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
              user?.role === 'ADMIN'
                ? t('Administración')
                : canManage
                  ? t('Responsable')
                  : t('Persona trabajadora')
            }
            sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
          />
          <ThemeToggle />
          <Tooltip title={user ? `${user.first_name} ${user.last_name}`.trim() : ''}>
            <Avatar sx={{ width: 34, height: 34, bgcolor: 'primary.main', fontSize: '0.85rem' }}>
              {initialsOf(user)}
            </Avatar>
          </Tooltip>
          <Tooltip title={t('Cerrar sesión')}>
            <IconButton onClick={signOut} edge="end" aria-label={t('Cerrar sesión')}>
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
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
          <Toolbar />
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
          <Toolbar />
          {navigation}
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          px: { xs: 2, md: 4 },
          pt: { xs: 10, md: 12 },
          // Room for the bottom bar on a phone, so the last row is reachable.
          pb: { xs: 12, md: 5 },
        }}
      >
        <Outlet />
      </Box>

      {!isDesktop && <BottomNav canManage={canManage} />}
    </Box>
  )
}
