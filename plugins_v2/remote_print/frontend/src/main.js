// Local preview is read-only: production receives the authenticated host from
// AWBotNest's RemotePluginConfig component through the ./Config exposure.
import { createApp, h } from 'vue'
import Config from './Config.vue'

const host = {
  async getConfig() { return {} },
  async saveConfig() { throw new Error('本地预览不会保存配置，请在平台配置页保存。') },
  async revealSecret() { throw new Error('本地预览不会读取密钥。') },
  async callApi() { throw new Error('本地预览不会执行工具或打印，请在平台中操作。') },
}

createApp({ render: () => h(Config, { host }) }).mount('#app')
