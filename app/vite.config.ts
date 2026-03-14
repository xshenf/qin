import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { alphaTab } from '@coderline/alphatab-vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  const plugins = [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'qin-logo.svg'],
      manifest: {
        name: 'Qin Guitar',
        short_name: 'Qin',
        description: 'Guitar Practice & Score Viewer',
        theme_color: '#1a1a2e',
        icons: [
          {
            src: 'qin-logo.svg',
            sizes: '192x192',
            type: 'image/svg+xml'
          },
          {
            src: 'qin-logo.svg',
            sizes: '512x512',
            type: 'image/svg+xml'
          }
        ]
      }
    }),
    // basicSsl(),
  ];

  if (command === 'serve') {
    // alphaTab plugin might return an array of plugins, so we spread it if necessary
    // or push it directly if it's a single plugin object.
    const atPlugin = alphaTab();
    if (Array.isArray(atPlugin)) {
      plugins.push(...atPlugin);
    } else {
      plugins.push(atPlugin);
    }
  }

  // 构建配置项
  const buildConfig: any = {
    rollupOptions: {}
  };

  return {
    plugins,
    optimizeDeps: {
      exclude: ['@coderline/alphatab']
    },
    build: buildConfig,
    server: {
      host: '0.0.0.0',
      port: 5175,
      // https: {} // Remove https for now to avoid complexity if not needed, or keep if basicSsl is used
      proxy: {
        '/api': {
          target: 'http://localhost:3000',
          changeOrigin: true,
          // rewrite: (path) => path.replace(/^\/api/, ''), // Keep /api if the backend expects it
        }
      }
    }
  };
})
