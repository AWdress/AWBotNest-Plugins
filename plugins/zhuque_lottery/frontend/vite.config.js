import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

// 插件前端 = 模块联邦「远程」。平台从 /api/plugins/zhuque_lottery/fe/assets/remoteEntry.js
// 动态 import，取 exposes 的 './Config'。base 用绝对挂载路径避免子 chunk 404
// （详见 auto_subscribe/vite.config.js 注释）。
export default defineConfig({
  base: '/api/plugins/zhuque_lottery/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_zhuque_lottery',
      filename: 'remoteEntry.js',
      exposes: {
        './Config': './src/Config.vue',
      },
      shared: {
        vue: { singleton: true, requiredVersion: false, generate: false },
      },
      format: 'esm',
    }),
  ],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
  },
  server: { port: 5015, cors: true },
})
