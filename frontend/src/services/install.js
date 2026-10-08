/** Instalar la aplicación en el teléfono o en el ordenador.
 *
 *  Chrome, Edge y Samsung Internet la ofrecen por su cuenta, pero escondida en
 *  el menú del navegador, y casi nadie la encuentra. Este módulo guarda la
 *  oferta del navegador para poder hacerla desde un botón propio.
 *
 *  Se carga desde `main.jsx` y no desde el botón: el navegador avisa una sola
 *  vez por carga y muy pronto, a veces antes de que exista la pantalla que
 *  pinta el botón. Si nadie está escuchando en ese momento, la oferta se pierde
 *  hasta la próxima recarga.
 *
 *  Safari no avisa nunca: en el iPhone se instala a mano desde «Compartir». Ahí
 *  el botón no instala, explica cómo hacerlo.
 */

let deferred = null
const listeners = new Set()
const notify = () => listeners.forEach((listener) => listener())

// Las instrucciones del iPhone, abiertas o no. Aquí y no en el componente
// porque se piden desde dos sitios, la barra y el menú de la cuenta, y el menú
// desmonta lo que lleva dentro al cerrarse: un diálogo suyo moriría con él.
let howToOpen = false

export const howToShown = () => howToOpen

export function closeHowTo() {
  howToOpen = false
  notify()
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    // Sin esto el navegador saca además su propia barra de «Instalar», y son
    // dos ofertas de lo mismo en la misma pantalla.
    event.preventDefault()
    deferred = event
    notify()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    notify()
  })
}

/** Si esta pantalla ya es la aplicación instalada: entonces no se ofrece. */
const runningInstalled = () =>
  window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true

/** iPhone o iPad. El iPad se presenta como un Mac, y se le reconoce por la
 *  pantalla táctil. */
const isIOS = () =>
  /iPhone|iPad|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

// Safari no tiene forma de saber si la aplicación ya está en la pantalla de
// inicio: la instalada guarda sus datos aparte. Así que se le pregunta a la
// persona una vez, y su respuesta se recuerda en este navegador.
const SAID_INSTALLED = 'ott.installed'

const saidInstalled = () => {
  try {
    return localStorage.getItem(SAID_INSTALLED) === '1'
  } catch {
    return false
  }
}

/** «Ya la tengo instalada»: el botón deja de salir en este navegador. */
export function markInstalled() {
  try {
    localStorage.setItem(SAID_INSTALLED, '1')
  } catch {
    // Sin almacenamiento (navegación privada) el botón volverá a salir, nada más.
  }
  howToOpen = false
  notify()
}

/** Cómo se puede instalar aquí: `prompt` (lo hace el navegador), `ios` (hay
 *  que explicarlo) o `null` (ya está instalada, o este navegador no sabe). */
export function installMode() {
  if (typeof window === 'undefined' || runningInstalled()) return null
  if (deferred) return 'prompt'
  if (isIOS() && !saidInstalled()) return 'ios'
  return null
}

export function subscribeInstall(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Lo que hace el botón: instalar si el navegador puede, explicarlo si no. */
export function startInstall() {
  if (installMode() === 'prompt') return promptInstall()
  howToOpen = true
  notify()
}

/** Abre la ventana de instalación del navegador. Devuelve `accepted` o
 *  `dismissed`. La oferta solo vale una vez: después, el navegador decide
 *  cuándo vuelve a hacerla. */
async function promptInstall() {
  const event = deferred
  if (!event) return 'dismissed'
  deferred = null
  await event.prompt()
  const { outcome } = await event.userChoice
  notify()
  return outcome
}
