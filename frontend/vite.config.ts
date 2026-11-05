import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, resolve(__dirname, '..'), '')
  const backend = `http://127.0.0.1:${env.APP_PORT || '8002'}`
  return {
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: Number(env.FRONTEND_PORT || 5174),
    strictPort: true,
    host: '127.0.0.1',
    proxy: {
      '/api/v1/ws': {
        target: backend,
        ws: true,
        changeOrigin: true
      },
      '/api': {
        target: backend,
        changeOrigin: true
      }
    }
  }
  }
})
