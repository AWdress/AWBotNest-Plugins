import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

// 插件前端 = 模块联邦「远程」。平台从 /api/plugins/ai/fe/assets/remoteEntry.js
// 动态 import，取 exposes 的 './Config' 挂进配置弹窗。vue 声明 shared+generate:false，
// 复用平台那份 Vue，不重复打包。base 用绝对挂载路径，避免子 chunk 相对 remoteEntry
// 解析多出一层 assets/ 导致 404（详见 auto_subscribe/vite.config.js 注释）。
export default defineConfig({
  base: '/api/plugins/ai/fe/',
  plugins: [
    vue(),
    federation({
      name: 'awbotnest_ai',
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
  server: { port: 5011, cors: true },
})
