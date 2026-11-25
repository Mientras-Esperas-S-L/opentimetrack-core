import { randomUUID } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The name people see: OpenTimeTrack unless the installation sets its own, with
// VITE_INSTALLATION_NAME or with the server's own INSTALLATION_NAME, so a build that
// has the server's environment at hand needs nothing else. It reaches the page title,
// the name of the installed app and, through src/installation.js, the screens.
function installationName(env) {
  return (env.VITE_INSTALLATION_NAME || env.INSTALLATION_NAME || '').trim() || 'OpenTimeTrack'
}

const escapeHtml = (text) =>
  text.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  )

// The manifest lives in public/ and is copied as it is; after the build, its name is
// the installation's. Without that, the app installed on a phone would still be
// called OpenTimeTrack whatever the screens say.
function withInstallationName(name) {
  let outDir = 'dist'
  let building = false
  return {
    name: 'installation-name',
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir)
      building = config.command === 'build'
    },
    transformIndexHtml: {
      order: 'pre',
      handler: (html) => html.replaceAll('%INSTALLATION_NAME%', escapeHtml(name)),
    },
    closeBundle() {
      if (!building) return
      const path = resolve(outDir, 'manifest.webmanifest')
      const manifest = JSON.parse(readFileSync(path, 'utf8'))
      manifest.name = name
      writeFileSync(path, `${JSON.stringify(manifest, null, 2)}\n`)
    },
  }
}

// Cada build, una huella: va dentro del código y a `version.json`. Una pestaña
// abierta que lee en `version.json` otra que la suya sabe que se ha quedado atrás
// y lo avisa (src/hooks/useNewVersion.js). Al azar y no del contenido: lo que
// importa es que dos builds no coincidan, no que sean reproducibles.
function buildVersion() {
  const build = randomUUID()
  let outDir = 'dist'
  let building = false
  return {
    name: 'build-version',
    config: () => ({ define: { 'import.meta.env.VITE_BUILD_ID': JSON.stringify(build) } }),
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir)
      building = config.command === 'build'
    },
    closeBundle() {
      if (!building) return
      writeFileSync(resolve(outDir, 'version.json'), `${JSON.stringify({ build })}\n`)
    },
  }
}

// La copia que va dentro del APK (`npm run android`). En el APK no hay proxy
// delante que lleve `/api` al servidor: la dirección de la API tiene que ser
// completa, y es la de una instalación concreta. Sin ella el APK arrancaría y no
// podría entrar nadie, así que mejor no compilarlo.
function androidApiUrl(env) {
  const url = (env.VITE_API_URL || '').trim()
  // `http://localhost:<puerto>/api` solo sirve para probar contra la pila local con
  // `adb reverse`, y solo en la compilación de depuración: la de publicación no deja
  // salir por HTTP sin cifrar (ver android/app/src/debug/AndroidManifest.xml).
  if (!/^(https:\/\/[^/]+|http:\/\/localhost(:\d+)?)\/api\/?$/.test(url)) {
    throw new Error(
      'El APK necesita VITE_API_URL con la API de la instalación, completa y por HTTPS: ' +
        'https://<dominio>/api (por ejemplo, en frontend/.env.android.local).',
    )
  }
  return url.replace(/\/$/, '')
}

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  const name = installationName(env)
  const android = mode === 'android'
  return {
    plugins: [react(), withInstallationName(name), buildVersion()],
    define: {
      'import.meta.env.VITE_INSTALLATION_NAME': JSON.stringify(name),
      'import.meta.env.VITE_NATIVE': JSON.stringify(android ? 'android' : ''),
      ...(android && { 'import.meta.env.VITE_API_URL': JSON.stringify(androidApiUrl(env)) }),
    },
    // Aparte de `dist`, para que compilar el APK no pise la web.
    build: android ? { outDir: 'dist-android' } : {},
    server: {
      port: 3000,
      host: true,
      // El contenedor necesita sondeo para ver los cambios del volumen montado.
      watch: { usePolling: true },
    },
    preview: { port: 3000, host: true },
  }
})
