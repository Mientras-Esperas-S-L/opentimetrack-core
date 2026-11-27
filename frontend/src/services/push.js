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

import {
  getPushKey,
  registerAppDevice,
  subscribePush,
  unregisterAppDevice,
  unsubscribePush,
} from './api.js'
import i18next from '../i18n/index.js'
import { isNativeApp } from '../native.js'

/** Si el navegador puede hacer esto. Safari en iOS solo desde la aplicación
 *  añadida a la pantalla de inicio, y ningún navegador lo permite sin HTTPS
 *  (localhost aparte), así que hay que preguntar antes de ofrecerlo. */
export const pushSupported = () =>
  isNativeApp ||
  ('serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window)

/** El estado real, leído del navegador y no de lo que creamos recordar:
 *  `denied`, `unsupported`, `on` u `off`. */
export async function pushState() {
  if (isNativeApp) return appPushState()
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
  if (isNativeApp) return enableAppPush()
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
  if (isNativeApp) return disableAppPush()
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

// ------------------------------------------------- la aplicación de Android
//
// Dentro del APK no hay Web Push: la vista web de Android no lo tiene. Avisa
// Firebase Cloud Messaging, a través del plugin de Capacitor. Mismo trato que en
// el navegador: el permiso se pide al encender el interruptor y nunca al
// entrar, y la baja se hace en los dos lados.
//
// El plugin se carga solo dentro del APK, con import(): en la web no pinta nada.

const APP_TOKEN = 'ott.appPushToken'

const savedToken = () => {
  try {
    return localStorage.getItem(APP_TOKEN)
  } catch {
    return null
  }
}

const saveToken = (token) => {
  try {
    if (token) localStorage.setItem(APP_TOKEN, token)
    else localStorage.removeItem(APP_TOKEN)
  } catch {
    // Sin almacenamiento el interruptor saldrá apagado; el servidor sí lo sabe.
  }
}

// Devuelve el módulo y no el plugin: el plugin de Capacitor es un proxy que
// responde a cualquier método, también a `then`, así que devolverlo desde una
// función asíncrona hace que `await` lo tome por una promesa y falle con
// «PushNotifications.then() is not implemented».
const pluginModule = () => import('@capacitor/push-notifications')

/** El canal por el que llegan los recordatorios de fichar: suena, vibra y cae
 *  sobre lo que haya en pantalla, que es lo que hace falta para que un aviso en
 *  el bolsillo se note. El servidor lo nombra igual (`URGENT_CHANNEL` en
 *  backend/apps/notifications/fcm.py). Crearlo dos veces no hace nada, y la
 *  importancia, una vez creado, ya solo la cambia la persona en los ajustes del
 *  móvil: eso es de Android, y está bien que sea así. */
async function ensureReminderChannel(PushNotifications) {
  await PushNotifications.createChannel({
    id: 'recordatorios',
    name: i18next.t('Recordatorios de fichar'),
    description: i18next.t(
      'Cuando empieza tu turno y no has fichado, o se queda la jornada abierta.',
    ),
    // 4 es IMPORTANCE_HIGH de Android: el mínimo para que el aviso caiga encima.
    importance: 4,
    visibility: 1,
    vibration: true,
  })
}

async function appPushState() {
  const { app_enabled: enabled } = await getPushKey()
  if (!enabled) return 'unconfigured'
  const { PushNotifications } = await pluginModule()
  const { receive } = await PushNotifications.checkPermissions()
  if (receive === 'denied') return 'denied'
  return receive === 'granted' && savedToken() ? 'on' : 'off'
}

/** El token que Firebase da a esta instalación. Llega por un evento, no como
 *  respuesta de `register()`, así que se espera al evento, con un límite: sin
 *  servicios de Google en el móvil no llega nunca. */
async function firebaseToken(PushNotifications) {
  const handles = []
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('FCM: no token')), 20000)
      Promise.all([
        PushNotifications.addListener('registration', ({ value }) => {
          clearTimeout(timer)
          resolve(value)
        }),
        PushNotifications.addListener('registrationError', (error) => {
          clearTimeout(timer)
          reject(new Error(error?.error || 'FCM: registration failed'))
        }),
      ])
        .then((added) => {
          handles.push(...added)
          return PushNotifications.register()
        })
        .catch((error) => {
          clearTimeout(timer)
          reject(error)
        })
    })
  } finally {
    handles.forEach((handle) => handle.remove())
  }
}

async function enableAppPush() {
  const { app_enabled: enabled } = await getPushKey()
  if (!enabled) return 'unconfigured'

  const { PushNotifications } = await pluginModule()
  let { receive } = await PushNotifications.checkPermissions()
  if (receive !== 'granted' && receive !== 'denied') {
    receive = (await PushNotifications.requestPermissions()).receive
  }
  if (receive !== 'granted') return receive === 'denied' ? 'denied' : 'off'

  const token = await firebaseToken(PushNotifications)
  await registerAppDevice({ token, device_label: 'Android' })
  saveToken(token)
  return 'on'
}

async function disableAppPush() {
  await forgetThisPhone()
  return 'off'
}

/** Deja de avisar en este móvil a quien tiene la sesión abierta. Se llama
 *  también al cerrar sesión: el móvil puede ser compartido, y los avisos de una
 *  persona no deben seguir llegando a un aparato que ya no usa. */
export async function forgetThisPhone() {
  if (!isNativeApp) return
  const token = savedToken()
  if (!token) return
  await unregisterAppDevice(token).catch(() => {})
  saveToken(null)
  const { PushNotifications } = await pluginModule()
  await PushNotifications.unregister().catch(() => {})
}

/** Al pulsar un aviso, la aplicación abre la pantalla que dice el aviso. Se
 *  cambia la dirección sin recargar: React Router escucha `popstate`. */
export async function listenToAppNotifications() {
  if (!isNativeApp) return
  const { PushNotifications } = await pluginModule()
  await ensureReminderChannel(PushNotifications).catch(() => {})
  await PushNotifications.addListener('pushNotificationActionPerformed', ({ notification }) => {
    const url = notification?.data?.url
    // Solo rutas propias: un aviso no debe poder sacar la aplicación a otra web.
    if (typeof url === 'string' && url.startsWith('/') && !url.startsWith('//')) {
      window.history.pushState({}, '', url)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }
  })
}
