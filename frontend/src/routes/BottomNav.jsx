import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import BottomNavigation from '@mui/material/BottomNavigation'
import BottomNavigationAction from '@mui/material/BottomNavigationAction'
import Paper from '@mui/material/Paper'

import { NAV_ADMIN, NAV_ME } from './navigation.jsx'

/** Phone navigation.
 *
 *  Four entries for whoever only clocks in, five for whoever also manages:
 *  management collapses into a single one that lands on the panel, which is where
 *  somebody managing from a phone is going anyway.
 *
 *  **The five have to be told to share the width.** MUI gives each action a minimum
 *  of 80px plus padding, and five of those do not fit in a phone: measured in devel,
 *  the first started at -20 and the last ended at 380 on a 360px screen, and at -40
 *  and 360 on a 320px one. Both ends were cut off, which is the header comment this
 *  file used to carry --- «five is where the labels start truncating» --- describing
 *  a case the code then went and created.
 */
export default function BottomNav({ canManage }) {
  const { t } = useTranslation()
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
          <BottomNavigationAction
            key={item.to}
            label={t(item.label)}
            icon={item.icon}
            //  Sin mínimo: que se repartan lo que hay. Con el mínimo de MUI, cinco
            //  no caben y se salen por los dos lados.
            sx={{ minWidth: 0, px: 0.5 }}
          />
        ))}
      </BottomNavigation>
    </Paper>
  )
}
