import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  base: '/api/plugins/email_collection/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_email_collection',
      filename: 'remoteEntry.js',
      exposes: {'./Config': './src/Config.vue'},
      shared: {vue: {singleton: true, requiredVersion: false, generate: false}},
      format: 'esm',
    }),
  ],
  build: {target: 'esnext', minify: true, cssCodeSplit: true},
})
