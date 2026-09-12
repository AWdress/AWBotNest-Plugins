import { createApp, h } from 'vue'
import Config from './Config.vue'

let state = {}
const host = {
  async getConfig() { return state },
  async saveConfig(value) { state = structuredClone(value) },
  async revealSecret(field) { return state[field] ?? '' },
  async callApi(path) {
    if (path === '/status') return {running: false}
    return {ok: true, message: '已开始 NodeSeek 签到'}
  },
  toast: {success: console.log, error: console.error},
}
createApp({render: () => h(Config, {pluginId: 'nodeseek_signin', host})}).mount('#app')
