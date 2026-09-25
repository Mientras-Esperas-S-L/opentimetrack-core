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
  text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

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

export default defineConfig(({ mode }) => {
  const name = installationName({ ...loadEnv(mode, process.cwd(), ''), ...process.env })
  return {
    plugins: [react(), withInstallationName(name)],
    define: { 'import.meta.env.VITE_INSTALLATION_NAME': JSON.stringify(name) },
    server: {
      port: 3000,
      host: true,
      // El contenedor necesita sondeo para ver los cambios del volumen montado.
      watch: { usePolling: true },
    },
    preview: { port: 3000, host: true },
  }
})
