/* Service worker de OpenTimeTrack.
 *
 * Hace una sola cosa: recibir avisos del navegador y abrir la pantalla que
 * corresponde al pulsarlos. No cachea nada, no intercepta ninguna petición y no
 * guarda estado.
 *
 * Es deliberado, no una fase pendiente. Un service worker que cachea la
 * pantalla de fichar puede acabar enseñando el estado de ayer a quien va a
 * fichar hoy, o aceptando un fichaje sin red y decidiendo por su cuenta con qué
 * hora se registra. Eso son decisiones sobre el registro, y el registro no se
 * decide en el navegador. Cuando haya cola sin cobertura será una funcionalidad
 * diseñada, con su hora declarada y su hora de recepción, no un efecto
 * secundario de haber puesto aquí una caché.
 */

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  // Sin datos no hay nada que enseñar: un aviso vacío en la pantalla de
  // bloqueo solo desconcierta.
  if (!event.data) return

  let message
  try {
    message = event.data.json()
  } catch {
    message = { title: 'OpenTimeTrack', body: event.data.text() }
  }

  event.waitUntil(
    self.registration.showNotification(message.title || 'OpenTimeTrack', {
      body: message.body || '',
      // El mismo asunto reemplaza al anterior en vez de apilar tres tarjetas
      // iguales.
      tag: message.tag || 'opentimetrack',
      renotify: Boolean(message.tag),
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      data: { url: message.url || '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/', self.location.origin).href

  // Si la aplicación ya está abierta, se lleva esa pestaña al frente en vez de
  // abrir una segunda: acabar con cinco pestañas de fichar es la forma más
  // rápida de que alguien fiche dos veces.
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          client.navigate(target)
          return client.focus()
        }
      }
      return self.clients.openWindow(target)
    }),
  )
})
