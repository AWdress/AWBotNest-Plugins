import { createApp, h } from 'vue'
import Config from './Config.vue'

let store = { enabled: true, ocr_enabled: true, copy_fallback: true }
const mockHost = {
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store) },
  async callApi(path) {
    if (path === '/status') return { ocr_available: true, active_count: 1 }
    if (path === '/history') return { items: [{ ts: Date.now()/1000, group_id: -100123, sender: '测试用户', code: 'A7K9', mode: 'OCR', ok: true }] }
    return { ok: true }
  },
  toast: { success: console.log, error: console.error },
}
createApp({ render: () => h(Config, { pluginId: 'red_packet_grab', host: mockHost }) }).mount('#app')
