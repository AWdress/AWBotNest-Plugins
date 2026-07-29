import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'human_lottery',
      filename: 'remoteEntry.js',
      exposes: { './Config': './src/Config.vue' },
      shared: ['vue'],
    }),
  ],
  build: { target: 'esnext', minify: false },
})
