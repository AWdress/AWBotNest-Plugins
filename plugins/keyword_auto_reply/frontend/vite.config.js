import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  base: '/api/plugins/keyword_auto_reply/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_keyword_auto_reply',
      filename: 'remoteEntry.js',
      exposes: { './Config': './src/Config.vue' },
      shared: {
        vue: { singleton: true, requiredVersion: false, generate: false },
      },
      format: 'esm',
    }),
  ],
  build: { target: 'esnext', minify: false, cssCodeSplit: true },
  server: { port: 5014, cors: true },
})
