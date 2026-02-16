import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { alphaTab } from '@coderline/alphatab-vite'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), alphaTab(), basicSsl()],
  optimizeDeps: {
    exclude: ['@coderline/alphatab']
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    https: {}
  }
})
