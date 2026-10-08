/** Si el servidor tiene ya otra versión de la aplicación que la que está abierta.
 *
 *  Cada build deja su huella en `version.json` y la lleva también dentro del
 *  código (`VITE_BUILD_ID`, ver vite.config.js). Si no coinciden, esta pestaña
 *  se quedó atrás en un despliegue. Pasa mucho en el móvil: la pestaña o la
 *  aplicación instalada sigue abierta días, y nadie recarga.
 *
 *  Se mira cada minuto y al volver a la pantalla, que en el móvil es cuando de
 *  verdad se usa. Con la pantalla oculta no se mira: no hay a quién avisar.
 *
 *  Solo avisa. Recargar por su cuenta podría tirar algo a medio escribir.
 */

import { useEffect, useState } from 'react'

const CURRENT = import.meta.env.VITE_BUILD_ID
const EVERY_MS = 60_000

export function useNewVersion() {
  const [available, setAvailable] = useState(false)

  useEffect(() => {
    // En desarrollo no hay `version.json`, y Vite ya recarga solo.
    if (import.meta.env.DEV || !CURRENT || available) return undefined
    let cancelled = false

    const check = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        // Sin caché: el navegador podría guardarse el fichero un rato y
        // contestar con la versión de antes.
        const response = await fetch('/version.json', { cache: 'no-store' })
        if (!response.ok) return
        const { build } = await response.json()
        if (!cancelled && build && build !== CURRENT) setAvailable(true)
      } catch {
        // Sin red, o un servidor de antes de esto que contesta con la página:
        // se vuelve a mirar en la próxima vuelta.
      }
    }

    check()
    const timer = setInterval(check, EVERY_MS)
    document.addEventListener('visibilitychange', check)
    return () => {
      cancelled = true
      clearInterval(timer)
      document.removeEventListener('visibilitychange', check)
    }
  }, [available])

  return available
}
