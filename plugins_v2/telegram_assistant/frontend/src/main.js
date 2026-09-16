import { createApp, h } from 'vue'
import Config from './Config.vue'

let config = {}
const host = {
  async getConfig() { return config },
  async saveConfig(values) { config = structuredClone(values) },
  async callApi() { return {ok: true, message: '已开始回查历史消息'} },
  toast: {success: console.log, error: console.error},
}

createApp({render: () => h(Config, {pluginId: 'telegram_assistant', host})}).mount('#app')
