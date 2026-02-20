import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { alphaTab } from '@coderline/alphatab-vite'
import basicSsl from '@vitejs/plugin-basic-ssl'
import fs from 'fs'
import path from 'path'

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
        },
        plugins: [
          {
            name: 'remove-fonts-on-build',
            closeBundle() {
              const distDir = path.resolve(__dirname, 'dist');

              ['font', 'soundfont'].forEach((dir) => {
                const target = path.join(distDir, dir);
                if (fs.existsSync(target)) {
                  fs.rmSync(target, { recursive: true, force: true });
                  console.log(`\nRemoved ${dir} from dist/`);
                }
              });
            }
          }
        ]
      }
    },
    server: {
      host: '0.0.0.0',
      port: 5175,
      // https: {} // Remove https for now to avoid complexity if not needed, or keep if basicSsl is used
    }
  };
})
