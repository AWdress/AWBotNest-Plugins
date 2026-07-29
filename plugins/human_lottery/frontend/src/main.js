import { createApp, h } from 'vue'
import Config from './Config.vue'

let store = {}
const host = {
  async getConfig() { return store },
  async saveConfig(value) { store = { ...value } },
  async callApi(path) {
    if (path === '/activities') return { items: [] }
    if (path === '/history') return { items: [] }
    return { ok: true }
  },
  toast: { success: console.log, error: console.error },
}
createApp({ render: () => h(Config, { pluginId: 'human_lottery', host }) }).mount('#app')
