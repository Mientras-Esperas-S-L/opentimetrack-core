import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // El contenedor necesita sondeo para ver los cambios del volumen montado.
    watch: { usePolling: true },
  },
  preview: { port: 3000, host: true },
})
