/** La vuelta del SSO a la aplicación de Android.
 *
 *  Dentro del APK la entrada por el proveedor no puede hacerse en la vista web:
 *  Google y Microsoft no dejan entrar desde una. Se abre en el navegador del
 *  sistema (una pestaña personalizada, que la persona ve como parte de la
 *  aplicación) y el servidor, al acabar, devuelve el vale por el esquema propio
 *  de la aplicación (`SSO_APP_URL` en el backend). Aquí se recoge.
 *
 *  El secreto que ata la entrada a quien la empezó se quedó en el almacenamiento
 *  de la aplicación, no en el navegador: por eso el vale se canjea aquí y no
 *  allí, y por eso otra aplicación que se hiciera con el enlace no podría
 *  canjearlo.
 */

import { isNativeApp } from '../native.js'

// El `appId` de capacitor.config.json, y lo que el backend tiene en SSO_APP_URL.
export const APP_SSO_RETURN = 'com.greencitycontrol.ott://sso'

/** La dirección de entrada de la pestaña del navegador, marcada como de la app. */
export const forTheApp = (startUrl) => `${startUrl}&app=android`

/** Abre la entrada en el navegador del sistema. */
export async function openInSystemBrowser(url) {
  const { Browser } = await import('@capacitor/browser')
  await Browser.open({ url })
}

/** Lo que hay que hacer con un enlace que abre la aplicación: a qué pantalla ir,
 *  o nada si no es la vuelta del SSO. Aparte, para poder probarlo sin móvil. */
export function whereTo(url) {
  if (typeof url !== 'string' || !url.startsWith(`${APP_SSO_RETURN}?`)) return null
  const params = new URLSearchParams(url.slice(APP_SSO_RETURN.length + 1))
  const ticket = params.get('ticket')
  if (ticket) return `/entrando?ticket=${encodeURIComponent(ticket)}`
  const error = params.get('sso_error')
  if (error) return `/?sso_error=${encodeURIComponent(error)}`
  return null
}

export async function listenToAppLinks() {
  if (!isNativeApp) return
  const { App } = await import('@capacitor/app')
  await App.addListener('appUrlOpen', async ({ url }) => {
    const target = whereTo(url)
    if (!target) return
    const { Browser } = await import('@capacitor/browser')
    await Browser.close().catch(() => {})
    // Recarga dentro de la aplicación: la pantalla de entrada y la de recogida
    // leen la dirección al montarse, y así da igual en cuál estuviera.
    window.location.assign(target)
  })
}
