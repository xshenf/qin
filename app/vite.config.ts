import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { alphaTab } from '@coderline/alphatab-vite'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  const plugins = [
    vue(),
    basicSsl(),
    {
      name: 'html-transform',
      apply: 'build' as 'build',
      transformIndexHtml(html: string) {
        return html.replace(
          '</head>',
          `
          <script type="importmap">
            {
              "imports": {
                "vue": "https://unpkg.com/vue@3.5.13/dist/vue.esm-browser.prod.js",
                "@coderline/alphatab": "https://unpkg.com/@coderline/alphatab@1.8.1/dist/alphaTab.mjs"
              }
            }
          </script>
          </head>`
        )
      }
    }
  ];

  if (command === 'serve') {
    // alphaTab plugin might return an array of plugins, so we spread it if necessary
    // or push it directly if it's a single plugin object.
    // However, vite plugins array accepts nested arrays.
    // The previous error suggested `alphaTab()` returns `Plugin<any>[]`.
    const atPlugin = alphaTab();
    if (Array.isArray(atPlugin)) {
      plugins.push(...atPlugin);
    } else {
      plugins.push(atPlugin);
    }
  }

  return {
    plugins,
    optimizeDeps: {
      exclude: ['@coderline/alphatab']
    },
    build: {
      rollupOptions: {
        external: ['vue', '@coderline/alphatab'],
        output: {
          globals: {
            vue: 'Vue',
            '@coderline/alphatab': 'alphaTab'
          }
        }
      }
    },
    server: {
      host: '0.0.0.0',
      port: 5175,
      // https: {} // Remove https for now to avoid complexity if not needed, or keep if basicSsl is used
    }
  };
})
