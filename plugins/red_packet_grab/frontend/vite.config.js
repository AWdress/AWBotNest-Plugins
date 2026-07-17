import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'red_packet_grab_config',
      filename: 'remoteEntry.js',
      exposes: { './Config': './src/Config.vue' },
      shared: ['vue'],
    }),
  ],
  build: {
    target: 'esnext',
    minify: true,
    cssCodeSplit: false,
  },
})
