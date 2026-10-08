import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth.js'
import { usePlatformAdmin } from '../hooks/usePlatformAdmin.js'

/** Guarda la administración de la instalación.
 *
 *  Mismo razonamiento que `RequireAdmin`, un peldaño más arriba: dar de alta una
 *  empresa no es cosa de quien administra **una**. Esconder el menú no es el
 *  permiso ---lo decide el API, que contesta 403--- pero enseñar una pantalla que
 *  va a fallar entera sí es un error de interfaz.
 *
 *  Mientras no se sabe no se decide: redirigir antes de tiempo echaría a quien sí
 *  puede.
 */
export default function RequirePlatformAdmin() {
  const { session } = useAuth()
  const esAdmin = usePlatformAdmin()

  if (esAdmin === null) return null
  // Sin empresa no hay otro sitio al que mandarla: el Resumen pide empresa y la
  // devuelve aquí, y un «no» por un fallo de red las haría rebotar sin fin. Se
  // queda, y la pantalla dice lo que conteste el servidor.
  if (!esAdmin && session?.tenant) return <Navigate to="/panel" replace />
  return <Outlet />
}
