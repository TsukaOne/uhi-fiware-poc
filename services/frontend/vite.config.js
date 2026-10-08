import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import cesium from 'vite-plugin-cesium'

// CARTO_API_KEY lives in the repository root .env, shared with docker compose.
// It is only read here (Node side), never bundled into the browser code.
const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url))

export default defineConfig(({ mode }) => {
  const { CARTO_API_KEY } = loadEnv(mode, REPO_ROOT, 'CARTO_')

  return {
    plugins: [vue(), cesium()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/prediction': {
          target: 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/prediction/, '')
        },
        // Same role as nginx in production: the key is added here, never in the browser
        '/basemap': {
          target: 'https://a.basemaps.cartocdn.com',
          changeOrigin: true,
          rewrite: (path) => `${path.replace(/^\/basemap/, '/light_all')}?key=${CARTO_API_KEY}`
        },
        // Exported tiles, served by the frontend container (docker-compose.dev.yml)
        '/tiles': {
          target: 'http://localhost:3000',
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets'
    }
  }
})
