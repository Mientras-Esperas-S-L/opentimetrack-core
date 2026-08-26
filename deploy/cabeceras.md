# Cabeceras del servidor web

Django pone las suyas: HSTS, `X-Frame-Options`, `nosniff`, referrer policy. Se
comprueban con `manage.py check --deploy` y están en `config/settings/prod.py`.

Lo que Django no puede poner es lo que protege al **frontend**, que es una SPA
servida como ficheros estáticos y no pasa por Django. Esto va donde se sirvan
esos ficheros.

## Por qué importa aquí más que en otros sitios

El token de sesión vive en `localStorage`. Es la elección habitual para una SPA
con API separada, y tiene una consecuencia: **un XSS es apropiación completa de
la sesión**, no solo la ejecución de un script.

Hoy no hay ningún sumidero de XSS en el código —ni un `dangerouslySetInnerHTML`,
ni `innerHTML`, ni `eval`— y React escapa por defecto. Pero eso es una propiedad
del código de hoy: una dependencia comprometida o un descuido futuro bastan. La
CSP es lo que convierte ese descuido en un fallo contenido.

## Content-Security-Policy

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  font-src 'self' data:;
  connect-src 'self' https://API.EJEMPLO.COM https://ALMACEN.EJEMPLO.COM;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  object-src 'none'
```

Tres decisiones que conviene entender antes de tocarlas:

**`style-src` lleva `unsafe-inline`.** Material UI inyecta estilos en tiempo de
ejecución con Emotion. Quitarlo rompe la interfaz entera. Se puede evitar con
nonces si algún día se sirve la SPA desde Django, que no es el caso.

**`connect-src` tiene que nombrar la API.** Va en otro origen —`CORS_ALLOWED_ORIGINS`
existe justo por eso—, así que con `'self'` a secas no se puede llamar a nada.
Sustituir por el dominio real.

**Y también el almacén de objetos, si lo hay.** `STORAGE_BACKEND=s3` es el valor
por defecto en producción, y con él la descarga de un justificante no la sirve la
API: responde un 302 al dominio del almacén, con una URL firmada de vida corta.
El navegador vuelve a evaluar la CSP **sobre el destino de la redirección**, así
que si ese origen no está nombrado, la descarga se bloquea.

Y se bloquea en silencio, que es lo peor: no hay error de la API que enseñar, y
quien lo sufre lee «la aplicación no responde» en vez de «falta un dominio en una
cabecera». Con `STORAGE_BACKEND=filesystem` no hace falta, porque ahí el fichero
lo sirve la propia API.

**`img-src` lleva `data:` y `blob:`.** Las descargas de justificantes e informes
se hacen creando un blob en el cliente.

## El resto

```
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
Referrer-Policy: same-origin
X-Content-Type-Options: nosniff
```

`Permissions-Policy` a vacío en todo: la aplicación no usa ninguna de esas
capacidades. Si algún día se añade fichaje con geolocalización, ese será el
sitio donde habilitarla, y tendrá que ser una decisión y no un descuido.

## Comprobar que están puestas

```
curl -sI https://TU-DOMINIO/ | grep -iE "content-security|permissions|referrer|x-content"
```

Y la que no se ve en las cabeceras: probar que la SPA sigue funcionando. Una
CSP mal puesta no da error visible, simplemente deja de cargar cosas, y la
consola del navegador es donde se ve.
