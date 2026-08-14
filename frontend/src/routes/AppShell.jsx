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
            borderRadius: 1.5,
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

  const user = session?.user
  const company = session?.tenant
  const canManage = user?.role === 'MANAGER' || user?.role === 'ADMIN'
  // Alguna entrada de gestión es solo de administración. Ocultar un enlace no
  // es un permiso ---el API decide--- pero enseñar uno que va a contestar 403 sí
  // es un error de interfaz.
  const management = NAV_ADMIN.filter((item) => !item.adminOnly || user?.role === 'ADMIN')

  const navigation = (
    <Box sx={{ overflowY: 'auto', pb: 2 }}>
      <NavSection title={t('Mi trabajo')} items={NAV_ME} />
      {canManage && (
        <>
          <Divider sx={{ my: 1, mx: 2 }} />
          <NavSection title={t('Gestión')} items={management} />
        </>
      )}
    </Box>
  )

  const currentLabel =
    [...NAV_ME, ...NAV_ADMIN].find(
      (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
    )?.label ?? ''

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
