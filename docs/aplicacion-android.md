# La aplicación de Android

La misma web, empaquetada en un APK con Capacitor. No hay una segunda aplicación
que mantener: lo que cambia dentro del APK está en `frontend/src/native.js` y en
los pocos sitios que lo consultan.

## Construir

```bash
cd frontend
VITE_API_URL=https://ott.example.com/api npm run android   # o en .env.android.local
cd android
./gradlew assembleDebug                                     # de pruebas
OTT_ANDROID_FIRMA=/ruta/firma.properties ./gradlew assembleRelease
```

Hace falta el JDK 21 y el SDK de Android. Para los avisos, además, el
`google-services.json` del proyecto de Firebase en `frontend/android/app/` (ver
[avisos-navegador.md](avisos-navegador.md)).

## Firma de publicación

El APK de pruebas va firmado con la clave de depuración de cada máquina: vale
para probar, pero cada máquina firma distinto y un móvil no acepta encima una
versión firmada por otra. El de publicación se firma siempre con la misma clave.

La clave **no está en el repositorio**. `OTT_ANDROID_FIRMA` apunta a un fichero de
propiedades que vive fuera:

```properties
storeFile=/ruta/ott-publicacion.jks
storePassword=...
keyAlias=ott
keyPassword=...
```

Sin él, `assembleRelease` sale sin firmar y Android no lo instala.

Lo que conviene saber:

- **Si se pierde la clave, no hay actualizaciones.** Un móvil solo acepta una
  versión nueva firmada con la misma clave que la que tiene instalada; con otra,
  hay que desinstalar y volver a instalar. Necesita una copia de seguridad fuera
  de la máquina que compila.
- **Pasar del APK de pruebas al de publicación** obliga a desinstalar el de
  pruebas: las firmas no coinciden.
- **Cada versión sube `versionCode`** en `frontend/android/app/build.gradle`.
  Android no instala encima una versión con el mismo número o uno menor.

## Entrar con el proveedor de la empresa (SSO)

Google y Microsoft no dejan entrar desde una vista web, así que en el APK la
entrada se abre en el navegador del sistema. Al acabar, el servidor devuelve el
vale por el esquema propio de la aplicación (`SSO_APP_URL`, por defecto
`com.greencitycontrol.ott://sso`), que la aplicación tiene registrado en su
`AndroidManifest.xml`. El vale se canjea dentro de la aplicación, con el secreto
que guardó al empezar: otra aplicación que se hiciera con el enlace no podría
usarlo.

Si se cambia el `appId`, hay que cambiar a la vez `SSO_APP_URL`, el esquema del
manifiesto y `APP_SSO_RETURN` en `frontend/src/services/appLinks.js`.

## Descargas

La vista web de Android no descarga. Los PDF y CSV se escriben en la caché de la
aplicación y se ofrecen con el menú de compartir del móvil, desde donde se abren
con el visor, se guardan en Archivos o se mandan.

## Avisos

La primera vez que alguien entra en la aplicación se le ofrecen los avisos, una
sola vez. Quien diga que no tiene el interruptor de "Mi jornada". Al cerrar sesión
se olvida la oferta, para la siguiente persona del mismo móvil.
