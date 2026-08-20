import { createApp, h } from 'vue'
import Config from './Config.vue'

let config = { enabled: true, notify_result: true, page_delay: 1, max_pages: 200 }
let running = false
let processed = 0
const started = Date.now()

const mockHost = {
  pluginId: 'hhan_read',
  async getConfig() { return { ...config } },
  async saveConfig(values) { config = { ...config, ...values } },
  async callApi(path) {
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
