import { createApp } from 'vue'
import Config from './Config.vue'

const demoHost = {
  getConfig: async () => ({}),
  callApi: async path => path === '/meta' ? {
    defaults: { selected_sites: ['audiences', 'ourbits', 'piggo', 'hhan', 'tjupt', 'hdsky', 'opencd'] },
    sites: [
      { key: 'audiences', name: 'Audiences', domain: 'audiences.me', group: 'NexusPHP' },
      { key: 'ourbits', name: 'OurBits', domain: 'ourbits.club', group: 'NexusPHP' },
      { key: 'piggo', name: 'PigGo', domain: 'piggo.me', group: 'NexusPHP' },
      { key: 'hhan', name: 'HHanClub', domain: 'hhanclub.net', group: 'NexusPHP' },
      { key: 'tjupt', name: 'TJUPT', domain: 'tjupt.org', group: '交互验证' },
      { key: 'hdsky', name: '天空', domain: 'hdsky.me', group: '交互验证' },
      { key: 'opencd', name: 'OpenCD', domain: 'open.cd', group: '交互验证' },
      { key: 'pterclub', name: 'PTerClub', domain: 'pterclub.net', group: '专用适配' },
      { key: 'zhuque', name: '朱雀', domain: 'zhuque.in', group: '专用适配' },
    ],
  } : path === '/history' ? { items: [] } : {},
  saveConfig: async () => {},
  toast: { success: console.log, warning: console.warn, error: console.error },
}
createApp(Config, { pluginId: 'pt_multi_checkin', host: demoHost }).mount('#app')
