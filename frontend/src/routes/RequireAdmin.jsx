import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth.js'

/** Guards what only administration may open, inside /panel.
 *
 *  Same reasoning as RequireManager, one rung up. Authorising an application
 *  hands out a key to the whole company's records, so the API refuses it to a
 *  manager with a 403 --- and until 14/08/2026 nothing on this side agreed:
 *  `adminOnly` in navigation.jsx hid the menu entry and stopped there, so a
 *  manager who typed the path got the screen, every request failed, and the
 *  empty state told them there were no applications. There were; they just
 *  could not see them.
 */
export default function RequireAdmin() {
  const { session } = useAuth()

  if (session?.user?.role !== 'ADMIN') {
    return <Navigate to="/panel" replace />
  }
  return <Outlet />
}
