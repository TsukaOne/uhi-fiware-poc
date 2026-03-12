import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
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
      '/orion': {
        target: 'http://localhost:1026',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/orion/, '')
      },
      '/geoserver': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})


