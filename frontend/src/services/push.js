/** Avisos en el navegador: registrar este dispositivo, y dejar de estarlo.
 *
 *  Web Push es un estándar del navegador, no un servicio contratado: el
 *  servidor firma el aviso con su propia clave y lo entrega en la dirección que
 *  el navegador dio. Aquí solo está el lado del cliente de ese trato.
 *
 *  Todo es por dispositivo, no por persona: alguien puede querer el aviso en el
 *  móvil y no en el portátil de la oficina, y son dos suscripciones distintas.
 *  El interruptor de «Recordatorios» dice si quiere que le avisen; esto dice
 *  *por dónde*.
 */

import { getPushKey, subscribePush, unsubscribePush } from './api.js'

/** Si el navegador puede hacer esto. Safari en iOS solo desde la aplicación
 *  añadida a la pantalla de inicio, y ningún navegador lo permite sin HTTPS
 *  (localhost aparte), así que hay que preguntar antes de ofrecerlo. */
export const pushSupported = () =>
  'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

/** El estado real, leído del navegador y no de lo que creamos recordar:
 *  `denied`, `unsupported`, `on` u `off`. */
export async function pushState() {
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const registration = await navigator.serviceWorker.getRegistration('/sw.js')
  const subscription = await registration?.pushManager.getSubscription()
  return subscription ? 'on' : 'off'
}

/** Registra este navegador. Devuelve el estado resultante.
 *
 *  El permiso se pide aquí, dentro del gesto de encender el interruptor, y
 *  nunca al cargar la página: un navegador que pregunta nada más entrar se
 *  responde con «bloquear» y ya no hay vuelta atrás.
 */
export async function enablePush() {
  if (!pushSupported()) return 'unsupported'

  const { enabled, public_key: publicKey } = await getPushKey()
  if (!enabled || !publicKey) return 'unconfigured'

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off'

  const registration = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready

  const subscription = await registration.pushManager.subscribe({
    // Obligatorio en Chrome: no admite suscripciones que puedan recibir avisos
    // sin contenido, y con razón --- un aviso sin contenido es un aviso que el
    // servicio del navegador puede usar para saber que algo pasó.
    userVisibleOnly: true,
    applicationServerKey: fromBase64Url(publicKey),
  })

  const raw = subscription.toJSON()
  await subscribePush({
    endpoint: raw.endpoint,
    p256dh: raw.keys.p256dh,
    auth: raw.keys.auth,
    device_label: deviceLabel(),
  })
  return 'on'
}

/** Da de baja este navegador, en el navegador y en el servidor.
 *
 *  Los dos lados: cancelar solo en el servidor deja al navegador creyendo que
 *  sigue suscrito y no vuelve a pedir permiso; cancelar solo en el navegador
 *  deja una fila muerta que el servidor descubre cuando ya ha fallado un envío.
 */
export async function disablePush() {
  if (!pushSupported()) return 'unsupported'
  const registration = await navigator.serviceWorker.getRegistration('/sw.js')
  const subscription = await registration?.pushManager.getSubscription()
  if (subscription) {
    await unsubscribePush(subscription.endpoint).catch(() => {})
    await subscription.unsubscribe()
  }
  return 'off'
}

/** Cómo se llama este dispositivo en la lista de la persona. Del user agent y
 *  a grandes rasgos: sirve para distinguir «el móvil» del «portátil», no para
 *  identificar a nadie. */
function deviceLabel() {
  const ua = navigator.userAgent
  const system = /Android/i.test(ua)
    ? 'Android'
    : /iPhone|iPad/i.test(ua)
      ? 'iOS'
      : /Windows/i.test(ua)
        ? 'Windows'
        : /Mac/i.test(ua)
          ? 'Mac'
          : /Linux/i.test(ua)
            ? 'Linux'
            : ''
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Chrome\//.test(ua)
      ? 'Chrome'
      : /Firefox\//.test(ua)
        ? 'Firefox'
        : /Safari\//.test(ua)
          ? 'Safari'
          : ''
  return [browser, system].filter(Boolean).join(' · ')
}

/** La clave pública viaja en base64url sin relleno; `subscribe` quiere bytes. */
function fromBase64Url(value) {
  const padded = (value + '='.repeat((4 - (value.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const raw = atob(padded)
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}
