import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The mock (web/mock/server.py) listens on 8766; point VITE_BACKEND at http://127.0.0.1:8765 for the real backend.
const backend = process.env.VITE_BACKEND ?? 'http://127.0.0.1:8766'
// The backend only answers its own origin (Host and Origin checks), so the dev proxy presents itself as that origin.
const proxy = Object.fromEntries(
  ['/api', '/shots', '/live', '/ws'].map((path) => [path, { target: backend, changeOrigin: true, ws: path === '/ws', headers: { Origin: backend } }]),
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'] },
})
