import { createApp, h } from 'vue'
import Config from './Config.vue'

let config = { enabled: true, notify_result: true, notify_cookie_error: true, lottery_count: 10, max_count: 100, interval_seconds: 7, page_delay: 1, max_pages: 200 }
let running = false
let processed = 0
const started = Date.now()

const mockHost = {
  pluginId: 'hhan_lottery',
  async getConfig() { return { ...config } },
  async saveConfig(values) { config = { ...config, ...values } },
  async callApi(path) {
    if (path === '/lottery/status') return { running, completed: processed, target: 10, last_prize: processed ? '憨豆 500' : '', last_result: processed ? '本次抽奖完成：10 次' : '' }
    if (path === '/lottery/run') { running = true; processed = 3; return { ok: true, message: '转盘任务已开始' } }
    if (path === '/lottery/stop') { running = false; return { ok: true, message: '已请求停止' } }
    if (path === '/lottery/cookie/check') return { ok: true, message: 'Cookie 有效；余额 12,500，单次消耗 100' }
    if (path === '/lottery/stats') return { ok: true, text: '累计抽奖：36 次\n累计消耗：3,600 憨豆\n奖品：憨豆 500 × 8' }
    if (path === '/status') {
      if (running) processed = Math.min(12, processed + 2)
      return {
        running, phase: running ? 'processing' : 'completed',
        message: running ? '第 2 页正在处理 4 条' : '全部未读消息已处理',
        current_page: running ? 2 : 3, total_pages: 3, processed,
        started_at: '2026-08-20 14:20:00',
        finished_at: running ? '' : '2026-08-20 14:20:08', stop_requested: false,
      }
    }
    if (path === '/run') { running = true; processed = 0; return { ok: true, message: '任务已开始' } }
    if (path === '/stop') { running = false; return { ok: true, message: '已请求停止' } }
    if (path === '/cookie/check') return { ok: true, message: 'Cookie 有效，当前页识别到 4 条未读消息' }
    if (path === '/history') return { ok: true, items: [
      { time: '2026-08-20 14:12:06', status: 'completed', processed: 12, pages: 3, detail: '全部未读消息已处理' },
      { time: '2026-08-19 21:08:32', status: 'completed', processed: 3, pages: 1, detail: '已进入历史已读区域，任务结束' },
    ] }
    if (path === '/history/clear') return { ok: true, message: '运行记录已清空' }
    return { ok: true }
  },
  toast: {
    success: message => console.log('[success]', message),
    error: message => console.warn('[error]', message),
  },
}

createApp({
  render: () => h(Config, { pluginId: mockHost.pluginId, host: mockHost }),
}).mount('#app')
