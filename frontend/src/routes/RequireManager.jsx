import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth.js'

/** Guards everything under /panel.
 *
 *  The menu already hides these entries, but hiding a link is not a permission:
 *  anybody can type the path. The server refuses too --- that is the check that
 *  actually protects the data --- and this one keeps somebody who typed a URL
 *  from landing on a screen full of failed requests.
 */
export default function RequireManager() {
  const { session } = useAuth()
  const role = session?.user?.role

  if (role !== 'MANAGER' && role !== 'ADMIN') {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
