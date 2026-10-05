import { createApp, h } from 'vue'
import Config from './Config.vue'

// 本地开发预览：仅在内存中保存，不连接平台或发送 Telegram 消息。
let store = {}
const mockHost = {
  async getConfig() { return structuredClone(store) },
  async saveConfig(values) { store = JSON.parse(JSON.stringify(values)) },
  async callApi(path) {
    if (path === '/status') return { ocr_available: true, active_count: 0 }
    return { items: [], ok: true }
  },
  toast: { success: console.info, error: console.error },
}
createApp({ render: () => h(Config, { pluginId: 'red_packet_grab', host: mockHost }) }).mount('#app')
