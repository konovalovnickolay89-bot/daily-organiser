import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local dev only: the Vite server proxies /api to FastAPI on this machine.
// On the house box, FastAPI serves frontend/dist and the API on one origin.
// Leave VITE_API_BASE_URL empty so the client uses that same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
