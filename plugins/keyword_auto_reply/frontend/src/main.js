import { createApp } from 'vue'
import Config from './Config.vue'

if (document.querySelector('#app')) {
  const config = { enabled: true, midnight_reset: false, leaderboard_enabled: true, rules_text: [], chat_ids: [], delete_after: 0, blacklist_ids: '', leaderboard_command: '.羊毛榜', leaderboard_size: 10 }
  const host = { getConfig: async () => config, saveConfig: async value => Object.assign(config, value), toast: { success: console.log, error: console.error } }
  createApp(Config, { pluginId: 'keyword_auto_reply', host }).mount('#app')
}
