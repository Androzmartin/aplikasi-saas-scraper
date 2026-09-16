import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors the "@/*" path mapping in tsconfig.json.
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Dev-only: lets the SPA call the API on the same origin.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
