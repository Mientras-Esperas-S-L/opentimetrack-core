/** Si hay otra versión de la aplicación que la que está abierta.
 *
 *  En la web: cada build deja su huella en `version.json` y la lleva también
 *  dentro del código (`VITE_BUILD_ID`, ver vite.config.js). Si no coinciden, esta
 *  pestaña se quedó atrás en un despliegue. Pasa mucho en el móvil: la pestaña o
 *  la aplicación instalada sigue abierta días, y nadie recarga. Se arregla
 *  recargando.
 *
 *  En el APK, la web va dentro y un despliegue no la cambia: lo que se mira es
 *  si hay un APK más nuevo publicado (ver src/apkVersion.js). Se arregla
 *  instalándolo.
 *
 *  Se mira al abrir, al volver a la pantalla y, en la web, cada minuto. Con la
 *  pantalla oculta no se mira: no hay a quién avisar.
 *
 *  Solo avisa. Recargar o instalar por su cuenta podría tirar algo a medio
 *  escribir. Devuelve null, o `{ apk }` con la dirección del APK nuevo (en la
 *  web, `apk` es null).
 */

import { useEffect, useState } from 'react'

import { newerThan, publishedApk } from '../apkVersion.js'
import { isNativeApp } from '../native.js'

const CURRENT = import.meta.env.VITE_BUILD_ID
const APK_CURRENT = import.meta.env.VITE_APK_VERSION
const APK_VERSION_URL = import.meta.env.VITE_APK_VERSION_URL
const EVERY_MS = 60_000

export function useNewVersion() {
  const [available, setAvailable] = useState(null)

  useEffect(() => {
    if (!isNativeApp || !APK_VERSION_URL || available) return undefined
    let cancelled = false

    const check = async () => {
      if (document.visibilityState !== 'visible') return
      const published = await publishedApk(APK_VERSION_URL)
      if (!cancelled && published && newerThan(APK_CURRENT, published.version)) {
        setAvailable({ apk: published.apk })
      }
    }

    check()
    document.addEventListener('visibilitychange', check)
    window.addEventListener('online', check)
    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', check)
      window.removeEventListener('online', check)
    }
  }, [available])

  useEffect(() => {
    // En desarrollo no hay `version.json`, y Vite ya recarga solo.
    if (import.meta.env.DEV || isNativeApp || !CURRENT || available) return undefined
    let cancelled = false

    const check = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        // Sin caché: el navegador podría guardarse el fichero un rato y
        // contestar con la versión de antes.
        const response = await fetch('/version.json', { cache: 'no-store' })
        if (!response.ok) return
        const { build } = await response.json()
        if (!cancelled && build && build !== CURRENT) setAvailable({ apk: null })
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
