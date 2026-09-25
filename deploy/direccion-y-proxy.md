# La dirección de la instalación y el proxy de delante

Una instalación se describe con **una** dirección: la que la gente escribe en el
navegador. Todo lo demás sale de ella, y producción no arranca si la dirección no
puede funcionar. Antes eran seis ajustes que tenían que coincidir y nadie los
comprobaba. Si se olvidaba uno, el fallo aparecía lejos de su causa: una
invitación que abría `localhost:3000` en el móvil de alguien, o una entrada por el
proveedor de identidad que acababa en una página con las credenciales de sesión en
JSON.

## Lo mínimo

```bash
PUBLIC_URL=https://fichaje.miempresa.example
TRUSTED_PROXIES=1
```

De `PUBLIC_URL` salen:

| Ajuste | Valor que toma | Para qué |
|---|---|---|
| `FRONTEND_URL` | `PUBLIC_URL` | Los enlaces de los correos: invitaciones y contraseña. |
| `API_URL` | `PUBLIC_URL` + `/api` | El enlace de entrega del registro, que es una ruta de la API. |
| `SSO_REDIRECT_URI` | `API_URL` + `/auth/sso/callback/` | La vuelta desde el proveedor de identidad. |
| `SSO_WEB_URL` | `PUBLIC_URL` | A dónde vuelve la persona después de entrar. |
| `ALLOWED_HOSTS` | el host de `PUBLIC_URL` | Los nombres a los que contesta el servidor. |
| `CORS_ALLOWED_ORIGINS` | el origen de `PUBLIC_URL` | Desde dónde acepta llamadas la API. |

Si alguno de esos ajustes se pone a mano, ese valor manda. Las instalaciones que se
montaron antes de `PUBLIC_URL`, con `FRONTEND_URL` y los demás escritos uno a uno,
siguen funcionando igual.

## Lo que producción rechaza al arrancar

- **Sin dirección.** Hace falta `PUBLIC_URL`, o al menos `FRONTEND_URL`.
- **Una dirección sin `https://`.** Por http, las contraseñas y las credenciales
  de sesión viajan en claro. Solo dentro de una red privada:
  `ALLOW_INSECURE_HTTP=true`. Con eso se apagan también la redirección a https,
  HSTS y las cookies seguras, que sin https dejarían la instalación sin poder
  entrar.
- **Una dirección con ruta**, como `https://miempresa.example/fichaje`. Servir la
  instalación bajo un prefijo de ruta no está soportado. Hace falta un nombre de
  host propio, como `https://fichaje.miempresa.example`.
- **Una dirección de la API que no acaba en `/api`**, que es donde está montada.

Las imágenes de producción arrancan con `config.settings.prod` aunque no se diga:
`gunicorn`, `uvicorn` y los *workers* lo toman por defecto. Antes caían en los
ajustes de desarrollo: DEBUG encendido, cualquier host aceptado y el correo escrito
en la consola.

## La API en otro host

Solo si la web y la API no comparten dirección:

```bash
PUBLIC_URL=https://fichaje.miempresa.example
PUBLIC_API_URL=https://api.fichaje.miempresa.example/api
```

El frontal se construye entonces con `VITE_API_URL` apuntando a esa misma dirección.
Si comparten host, que es lo normal, `VITE_API_URL` se deja sin poner: la web llama
a `/api` en su propia dirección y funciona con cualquier nombre.

## Qué registrar en el proveedor de identidad

La vuelta se compara **letra a letra** con la que tenga registrada el proveedor. No
hay que deducirla de la barra del navegador. La instalación la dice:

```bash
curl https://fichaje.miempresa.example/api/instance/
```

```json
{
  "product": "OpenTimeTrack",
  "version": "0.1.0",
  "web_url": "https://fichaje.miempresa.example",
  "api_url": "https://fichaje.miempresa.example/api",
  "sso_callback_url": "https://fichaje.miempresa.example/api/auth/sso/callback/"
}
```

La consola de la instalación la enseña también en «Cómo entra su gente». Y una
aplicación que se integra la lee de ahí, en lugar de construirla.

## El proxy

Hay tres cosas que el proxy tiene que hacer, y `TRUSTED_PROXIES` tiene que decir
cuántos proxies hay:

1. **Conservar el `Host`** que escribió el navegador. Si pone el nombre interno del
   servicio, Django contesta 400 porque ese host no está en `ALLOWED_HOSTS`.
2. **Mandar `X-Forwarded-Proto`**. Sin esa cabecera, Django cree que la petición
   llegó por http y la redirige a https en bucle.
3. **Añadir la dirección de quien llama a `X-Forwarded-For`**. De ahí salen la IP
   que queda en cada fichaje y la que cuentan los límites de intentos de entrada.
   Con `TRUSTED_PROXIES=0` detrás de un proxy, todo el mundo llega con la IP del
   proxy y comparte el mismo límite: cinco contraseñas mal puestas en cualquier
   sitio, y nadie entra durante un minuto. El registro `security` lo avisa. Con un
   número mayor que los proxies reales, cada cual elige la IP que queda en su
   fichaje.

### Caddy

Caddy conserva el `Host`, manda las tres cabeceras y consigue el certificado él
solo. Con Caddy delante, `TRUSTED_PROXIES=1`.

```caddyfile
fichaje.miempresa.example {
    handle /api/* {
        reverse_proxy api:8000
    }
    handle /static/* {
        reverse_proxy api:8000
    }
    handle {
        root * /srv/web
        try_files {path} /index.html
        file_server
    }
}
```

### nginx

```nginx
server {
    listen 443 ssl;
    server_name fichaje.miempresa.example;
    # ssl_certificate y ssl_certificate_key, los de la instalación.

    location ~ ^/(api|static)/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /srv/web;
        try_files $uri /index.html;
    }
}

server {
    listen 80;
    server_name fichaje.miempresa.example;
    return 301 https://$host$request_uri;
}
```

Con un solo nginx, `TRUSTED_PROXIES=1`. Si delante hay además un balanceador que
también añade a `X-Forwarded-For`, son 2. Si el balanceador pasa la conexión tal
cual (TCP, o PROXY protocol con `real_ip_header proxy_protocol` en nginx), no añade
nada y siguen siendo 1.

Las cabeceras que protegen al frontal (CSP y compañía) van en este mismo servidor:
ver [cabeceras.md](cabeceras.md).

## Comprobar que está bien

```bash
# La salud, sin seguir redirecciones: un 301 aquí es un proxy sin X-Forwarded-Proto.
curl -sS -o /dev/null -w '%{http_code}\n' https://fichaje.miempresa.example/api/health/
# Qué va a mandar al proveedor de identidad.
curl -sS https://fichaje.miempresa.example/api/instance/
```
