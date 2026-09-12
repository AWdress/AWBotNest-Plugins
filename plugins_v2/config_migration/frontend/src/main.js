import { createApp, h } from 'vue'
import Config from './Config.vue'

const host = {
  async getConfig() { return {} },
  async revealSecret() { return '' },
  async saveConfig() {},
  async callApi() { return {ok: true} },
  toast: {success: console.log, error: console.error},
}
createApp({render: () => h(Config, {pluginId: 'config_migration', host})}).mount('#app')
