import { createApp, h } from 'vue'
import Config from './Config.vue'
import './preview.css'

// Standalone development only: no backend, cloud upload or sample run records.
let config = {}
const host = {
  async getConfig() { return structuredClone(config) },
  async saveConfig(values) { config = structuredClone(values) },
  async revealSecret(field) { return config[field] || '' },
  async callApi(path) {
    if (path === '/status') return {ok: false, message: '当前为独立界面预览，运行状态与记录需在 AWBotNest 平台中读取。'}
    return {ok: false, message: '当前为独立界面预览，请在 AWBotNest 平台中执行此操作。'}
  },
  toast: {success: console.log, error: console.error},
}

createApp({render: () => h(Config, {pluginId: 'aw115mst', host})}).mount('#app')
