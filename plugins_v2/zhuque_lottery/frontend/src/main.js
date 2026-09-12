// 本地预览入口（npm run dev）：模拟 host 跑 Config.vue。真正运行时由平台注入真实 host。
import { createApp, h } from 'vue'
import Config from './Config.vue'

let store = {
  cookie: '', xcsrf: '', my_name: '我',
  enable_getinfo: true, getinfo_command: 'getinfo',
  enable_prizewheel: true, prizewheel_command: 'prizewheel', prize_tasks: 4,
  enable_betbonus: true, betbonus_command: 'betbonus',
  enable_firegenshin: false, firegenshin_interval: 20,
  enable_raiding: false, fanda_mode: 'off', fanxian: false,
  fanxian_probability: 1, fanxian_blacklist: '', raid_cd_minutes: 5,
  enable_redpocket: false, redpocket_max_retry: 20,
  enable_transform: false, transform_notification: false,
  transform_leaderboard: false, transform_payleaderboard: false,
  enable_ydx: false, ydx_dice_reveal: true, ydx_dice_bet: false,
  ydx_wwd_switch: false, ydx_start_count: 5, ydx_stop_count: 5,
  ydx_start_bouns: 500, ydx_bet_model: 'a',
  enable_card: false, card_command: 'card',
  card_id_1: '1', card_id_2: '2', card_id_3: '3', card_id_4: '4',
  owner_notify: true,
}

const mockHost = {
  pluginId: 'zhuque_lottery',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store) },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts)
    if (path === '/info') return { ok: true, info: { UID: '10086', '用户名': 'AWdress', '等级': 'Nexus Lv7', '灵石': '1234567', '上传': '12.34 TiB', '下载': '1.23 TiB' }, firegenshin_total: 88888, firegenshin_last_date: '2026-07-15' }
    if (path === '/transform') return {
      get_leaderboard: [{ name: '大佬A', total: 500000, count: 5 }, { name: '大佬B', total: 200000, count: 2 }],
      pay_leaderboard: [{ name: '小弟C', total: 100000, count: 3 }],
      get_total: 700000, pay_total: 100000,
      recent: [{ direction: 'get', amount: 100000, user_name: '大佬A', ts: '2026-07-15T20:00:00' }],
    }
    if (path === '/raids') return {
      raiding: { gain: 300000, loss: 50000, count: 12 },
      beraided: { gain: 80000, loss: 120000, count: 8 },
      recent: [{ action: 'raiding', amount: 20000, count: 3, ts: '2026-07-15T20:10:00' }],
    }
    if (path === '/ydx') return { total: 40, big: 22, small: 18, bet_total: 50000, win_total: 62000, recent: [{ die_point: 14, lottery_result: 'Big', bet_side: 'b', bet_amount: 500, win_amount: 950, ts: '2026-07-15T20:20:00' }] }
    if (path === '/clear') return { ok: true }
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
