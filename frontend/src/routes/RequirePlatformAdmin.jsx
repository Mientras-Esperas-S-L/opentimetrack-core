import { Navigate, Outlet } from 'react-router-dom'

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
  const esAdmin = usePlatformAdmin()

  if (esAdmin === null) return null
  if (!esAdmin) return <Navigate to="/panel" replace />
  return <Outlet />
}
