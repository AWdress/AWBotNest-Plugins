import { createApp, h } from 'vue'
import Config from './Config.vue'

let config = {}
const host = {
  async getConfig() { return config },
  async saveConfig(values) { config = structuredClone(values) },
  async revealSecret() { return config.mailboxes || [] },
  async callApi(path) {
    if (path === '/status') return {running: false}
    return {ok: true, message: '立即检查完成：邮箱 1/1，发现 0 封，推送 0 封。'}
  },
  toast: {success: console.log, error: console.error},
}
createApp({render: () => h(Config, {pluginId: 'email_collection', host})}).mount('#app')
