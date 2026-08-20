import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-pBY4un5e.js';

true              &&(function polyfill() {
  const relList = document.createElement("link").relList;
  if (relList && relList.supports && relList.supports("modulepreload")) {
    return;
  }
  for (const link of document.querySelectorAll('link[rel="modulepreload"]')) {
    processPreload(link);
  }
  new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type !== "childList") {
        continue;
      }
      for (const node of mutation.addedNodes) {
        if (node.tagName === "LINK" && node.rel === "modulepreload")
          processPreload(node);
      }
    }
  }).observe(document, { childList: true, subtree: true });
  function getFetchOpts(link) {
    const fetchOpts = {};
    if (link.integrity) fetchOpts.integrity = link.integrity;
    if (link.referrerPolicy) fetchOpts.referrerPolicy = link.referrerPolicy;
    if (link.crossOrigin === "use-credentials")
      fetchOpts.credentials = "include";
    else if (link.crossOrigin === "anonymous") fetchOpts.credentials = "omit";
    else fetchOpts.credentials = "same-origin";
    return fetchOpts;
  }
  function processPreload(link) {
    if (link.ep)
      return;
    link.ep = true;
    const fetchOpts = getFetchOpts(link);
    fetch(link.href, fetchOpts);
  }
}());

const {createApp,h} = await importShared('vue');

let config = { enabled: true, bonus_enabled: true, notify_result: true, notify_cookie_error: true, single_command: '.hh', batch_command: '.hhs', cooldown_seconds: 10, result_delete: 90, lottery_count: 10, max_count: 100, interval_seconds: 7, page_delay: 1, max_pages: 200 };
let running = false;
let processed = 0;

const mockHost = {
  pluginId: 'hhan_lottery',
  async getConfig() { return { ...config } },
  async saveConfig(values) { config = { ...config, ...values }; },
  async callApi(path) {
    if (path === '/lottery/status') return { running, completed: processed, target: 10, last_prize: processed ? '憨豆 500' : '', last_result: processed ? '本次抽奖完成：10 次' : '' }
    if (path === '/bonus/cookie/check') return { ok: true, message: 'Cookie 有效，可以使用赠豆命令' }
    if (path === '/lottery/run') { running = true; processed = 3; return { ok: true, message: '转盘任务已开始' } }
    if (path === '/lottery/stop') { running = false; return { ok: true, message: '已请求停止' } }
    if (path === '/lottery/cookie/check') return { ok: true, message: 'Cookie 有效；余额 12,500，单次消耗 100' }
    if (path === '/lottery/stats') return { ok: true, text: '累计抽奖：36 次\n累计消耗：3,600 憨豆\n奖品：憨豆 500 × 8' }
    if (path === '/read/status') {
      if (running) processed = Math.min(12, processed + 2);
      return {
        running, operation: 'read', phase: running ? 'processing' : 'completed',
        message: running ? '第 2 页正在处理 4 条' : '全部未读消息已处理',
        current_page: running ? 2 : 3, total_pages: 3, processed,
        started_at: '2026-08-20 14:20:00',
        finished_at: running ? '' : '2026-08-20 14:20:08', stop_requested: false,
      }
    }
    if (path === '/read/run') { running = true; processed = 0; return { ok: true, message: '任务已开始' } }
    if (path === '/read/delete') { running = true; processed = 0; return { ok: true, message: '删除任务已开始' } }
    if (path === '/read/stop') { running = false; return { ok: true, message: '已请求停止' } }
    if (path === '/read/cookie/check') return { ok: true, message: 'Cookie 有效，当前页识别到 4 条未读消息' }
    if (path === '/read/history') return { ok: true, items: [
      { time: '2026-08-20 14:12:06', operation: 'delete', status: 'completed', processed: 12, pages: 3, detail: '收件箱消息已全部删除' },
      { time: '2026-08-19 21:08:32', operation: 'read', status: 'completed', processed: 3, pages: 1, detail: '已进入历史已读区域，任务结束' },
    ] }
    if (path === '/read/history/clear') return { ok: true, message: '运行记录已清空' }
    return { ok: true }
  },
  toast: {
    success: message => console.log('[success]', message),
    error: message => console.warn('[error]', message),
  },
};

createApp({
  render: () => h(Config, { pluginId: mockHost.pluginId, host: mockHost }),
}).mount('#app');
