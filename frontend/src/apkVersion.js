/** ¿Hay un APK más nuevo publicado? Solo cuenta dentro de la aplicación.
 *
 *  La web se pone al día con cada despliegue. El APK lleva la web dentro y no se
 *  entera: aquí se pregunta qué versión hay publicada (el `.json` que deja
 *  scripts/publicar-apk.sh) y, si es más nueva, se ofrece descargarla. Sin tienda
 *  no hay instalación silenciosa: Android pide confirmarla.
 *
 *  Las versiones son la fecha y hora de la compilación, `AAAA.MM.DD.HHMM`, así que
 *  una más nueva es una mayor número a número.
 */

export function newerThan(current, published) {
  if (!current || !published) return false
  const a = String(current).split('.').map(Number)
  const b = String(published).split('.').map(Number)
  if ([...a, ...b].some((n) => !Number.isFinite(n))) return false
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const x = a[i] || 0
    const y = b[i] || 0
    if (x !== y) return y > x
  }
  return false
}

/** La versión publicada y la dirección de su APK, o null si no se puede saber
 *  (sin red, sin fichero). El APK viene relativo al `.json`. Solo por HTTPS: es
 *  lo que se va a instalar. */
export async function publishedApk(url, ask = fetch) {
  if (!url) return null
  try {
    const response = await ask(url, { cache: 'no-store' })
    if (!response.ok) return null
    const data = await response.json()
    if (!data?.version || !data?.apk) return null
    const apk = new URL(data.apk, url)
    if (apk.protocol !== 'https:') return null
    return { version: String(data.version), apk: apk.toString() }
  } catch {
    return null
  }
}
