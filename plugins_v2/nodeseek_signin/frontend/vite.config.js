import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  base: '/api/plugins/nodeseek_signin/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_nodeseek_signin',
      filename: 'remoteEntry.js',
      exposes: {'./Config': './src/Config.vue'},
      shared: {vue: {singleton: true, requiredVersion: false, generate: false}},
    }),
  ],
  build: {target: 'esnext'},
})
