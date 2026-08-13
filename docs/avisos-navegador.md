# Avisos en el navegador (Web Push)

Los recordatorios de fichaje salen siempre por correo. Además pueden llegar como
aviso del navegador —en el móvil, en el escritorio— sin instalar ninguna
aplicación y sin contratar ningún servicio.

Web Push es un estándar: tu servidor firma el aviso con **su propia clave** y lo
entrega en la dirección que dio el navegador. No hay intermediario que lea el
contenido ni cuenta que abrir en ningún sitio. Por eso funciona igual en un
despliegue propio que en el servicio alojado.

## Ponerlo en marcha

Una vez, al instalar:

```bash
python manage.py vapid_keys
```

Imprime un par de claves. Van al `.env` del despliegue:

```ini
WEBPUSH_PUBLIC_KEY=B...
WEBPUSH_PRIVATE_KEY=N...
WEBPUSH_SUBJECT=mailto:soporte@tu-dominio.example
```

Y ya está. Cada persona decide en «Mi jornada» si quiere recordatorios, y en qué
dispositivos.

## Qué pasa si no las generas

Nada se rompe. La API contesta que el push está apagado, la interfaz **no
enseña** el interruptor —proponer un aviso que no va a llegar es peor que no
proponerlo— y los recordatorios siguen saliendo por correo.

## Detalles que muerden

- **La clave privada es un secreto.** Si cambia, todos los navegadores suscritos
  dejan de recibir avisos y tienen que volver a suscribirse. No es catastrófico:
  el correo sigue funcionando y la gente vuelve a activarlo.
- **Hace falta HTTPS.** Ningún navegador permite suscribirse sin él, salvo en
  `localhost` para desarrollo.
- **En iPhone**, solo si la persona ha añadido la aplicación a su pantalla de
  inicio. Es una limitación de Safari, no de OpenTimeTrack.
- **El permiso es del navegador, no de la cuenta.** Alguien puede tener los
  avisos en el móvil y no en el portátil de la oficina, y son dos suscripciones
  distintas. Si los bloquea en el navegador, la interfaz lo dice y no insiste:
  desbloquearlos se hace en los ajustes del navegador, no aquí.
- **Una dirección muerta se borra sola.** Cuando el servicio del navegador
  responde que ya no existe —desinstalado, permiso revocado, perfil borrado— la
  suscripción se elimina en ese momento.

## Lo que el aviso no es

Un recordatorio empuja a fichar; **nunca ficha**. Puede llegar tarde, no llegar,
o llegar a un móvil apagado, y nada de eso toca el registro: no hay fichaje que
dependa de que un aviso se entregue. Es exactamente por eso que un fallo aquí es
una molestia y no una incidencia legal.
