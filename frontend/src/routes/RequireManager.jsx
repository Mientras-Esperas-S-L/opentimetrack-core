import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth.js'
import { NAV_ADMIN } from './navigation.jsx'

/** Lo que la asesoría puede abrir: lo mismo que su menú, sacado de él para que
 *  no haya dos listas que mantener. */
const DE_LA_ASESORIA = new Set(NAV_ADMIN.filter((item) => item.asesoria).map((item) => item.to))

/** Guards everything under /panel.
 *
 *  The menu already hides these entries, but hiding a link is not a permission:
 *  anybody can type the path. The server refuses too --- that is the check that
 *  actually protects the data --- and this one keeps somebody who typed a URL
 *  from landing on a screen full of failed requests.
 *
 *  La asesoría entraba en todas: el menú solo le ofrecía las suyas, pero con la
 *  dirección escrita abría el Cuadrante o «Por decidir», y cada una se cargaba
 *  con peticiones que el servidor le contesta 403.
 */
export default function RequireManager() {
  const { session } = useAuth()
  const { pathname } = useLocation()
  const role = session?.user?.role

  if (role !== 'MANAGER' && role !== 'ADMIN' && role !== 'ADVISOR') {
    return <Navigate to="/" replace />
  }
  if (role === 'ADVISOR' && !DE_LA_ASESORIA.has(pathname.replace(/\/+$/, ''))) {
    return <Navigate to="/panel" replace />
  }
  return <Outlet />
}
