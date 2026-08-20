import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend container serves the built assets, so the build output is plain
// static files with no dev server assumptions. During local development the
// Vite dev server proxies API calls to the FastAPI process.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
