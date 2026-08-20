import { createApp } from 'vue'
import Config from './Config.vue'

const demoHost = {
  getConfig: async () => ({}),
  callApi: async path => path === '/meta' ? { defaults: {}, sites: [] } : path === '/history' ? { items: [] } : {},
  saveConfig: async () => {},
  toast: { success: console.log, warning: console.warn, error: console.error },
}
createApp(Config, { pluginId: 'pt_multi_checkin', host: demoHost }).mount('#app')
