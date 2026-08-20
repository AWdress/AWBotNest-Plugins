import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  base: '/api/plugins/hhan_read/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_hhan_read',
      filename: 'remoteEntry.js',
      exposes: { './Config': './src/Config.vue' },
      shared: {
        vue: { singleton: true, requiredVersion: false, generate: false },
      },
      format: 'esm',
    }),
  ],
  build: { target: 'esnext', minify: false, cssCodeSplit: true },
  server: { port: 5013, cors: true },
})
