import { createApp, h } from 'vue'
import Config from './Config.vue'

let config = {}
const host = {
  async getConfig() { return config },
  async saveConfig(values) { config = structuredClone(values) },
  async revealSecret() { return config.accounts || [] },
  async callApi(path) { return path === '/status' ? {running: false, history: []} : {ok: true, message: '已开始签到'} },
  toast: {success: console.log, error: console.error},
}
createApp({render: () => h(Config, {pluginId: 'gptgod_checkin', host})}).mount('#app')
