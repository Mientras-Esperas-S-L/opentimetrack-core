import { useLocation, useNavigate } from 'react-router-dom'
import BottomNavigation from '@mui/material/BottomNavigation'
import BottomNavigationAction from '@mui/material/BottomNavigationAction'
import Paper from '@mui/material/Paper'

import { NAV_ADMIN, NAV_ME } from './navigation.jsx'

/** Phone navigation.
 *
 *  Only four slots, because five is where the labels start truncating. The
 *  worker's three screens always fit; management collapses to a single entry
 *  that lands on the panel, which is where somebody managing from a phone is
 *  going anyway.
 */
export default function BottomNav({ canManage }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const items = canManage ? [...NAV_ME, NAV_ADMIN[0]] : NAV_ME

  // Anything under /panel keeps the management tab lit, not just its index.
  const current =
    items.findIndex((item) =>
      item.to === '/' ? pathname === '/' : pathname.startsWith(item.to),
    ) ?? 0

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        borderTop: 1,
        borderColor: 'divider',
        zIndex: (t) => t.zIndex.appBar,
        // Keeps the bar clear of the home indicator on a phone.
        pb: 'env(safe-area-inset-bottom)',
      }}
    >
      <BottomNavigation
        showLabels
        value={current === -1 ? 0 : current}
        onChange={(_, index) => navigate(items[index].to)}
        sx={{ bgcolor: 'background.paper' }}
      >
        {items.map((item) => (
          <BottomNavigationAction key={item.to} label={item.label} icon={item.icon} />
        ))}
      </BottomNavigation>
    </Paper>
  )
}
