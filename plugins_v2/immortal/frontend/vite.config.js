import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import fs from 'node:fs'
import path from 'node:path'
const cleanVueAssets = {
  name: 'clean-immortal-shell-artifacts',
  buildStart() {
    const directory = path.resolve(import.meta.dirname, 'dist/assets')
    if (!fs.existsSync(directory)) return
    for (const name of fs.readdirSync(directory)) {
      const target = path.resolve(directory, name)
      if (path.dirname(target) === directory && /^(?:__federation_.*|index-[\w-]+|remoteEntry)\.(?:js|css)$/.test(name) && fs.statSync(target).isFile()) fs.unlinkSync(target)
    }
  },
}
export default defineConfig({
  base: '/api/plugins/immortal/fe/',
  plugins: [cleanVueAssets, vue(), federation({ name: 'awbotnest_immortal', filename: 'remoteEntry.js', exposes: { './Config': './src/Config.vue' }, shared: { vue: { singleton: true, requiredVersion: false, generate: false } } })],
  build: { target: 'esnext', emptyOutDir: false, cssCodeSplit: true },
})
