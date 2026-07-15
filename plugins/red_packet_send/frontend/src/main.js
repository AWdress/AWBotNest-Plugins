// 本地预览入口（npm run dev）：模拟 host 跑 Config.vue。真正运行时由平台注入真实 host。
import { createApp, h } from 'vue'
import Config from './Config.vue'

let store = {
  enabled: true, create_word: '创建红包', status_word: '红包状态', end_word: '结束红包',
  code_length: 4, rotate_code: false,
  max_amount: 0, max_count: 0, activity_timeout_minutes: 30, end_delete_delay: 10,
  transfer_prefix: '+', congrats_text: '恭喜 {name} 抢到 {amount} 魔力！',
  blacklist_ids: '',
}

const mockHost = {
  pluginId: 'red_packet_send',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store) },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts)
    if (path === '/activities') return {
      items: [
        { rp_id: 12, chat_id: -1001234567890, chat_title: '', total_amount: 500, packet_count: 10, remaining_count: 4, remaining_amount: 210, participants: 6, keyword: 'aB7k', status: '进行中', created: '2026-07-15 20:30' },
      ],
    }
    if (path === '/history') return {
      items: [
        { rp_id: 11, chat_id: -1001234567890, total_amount: 300, packet_count: 5, participants: 5, distributed: 300, time: '2026-07-15 19:00' },
      ],
    }
    if (path === '/end') return { ok: true, message: '已结束' }
    return { ok: true }
  },
  toast: {
    success: (m) => console.log('%c[toast.success] ' + m, 'color:#6ee7a8'),
    error: (m) => console.warn('[toast.error] ' + m),
  },
}

createApp({
  render: () => h(Config, { pluginId: mockHost.pluginId, host: mockHost }),
}).mount('#app')
