import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-CikwRvnI.js';

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

// 本地预览入口（npm run dev）：用「模拟 host」把 Config.vue 跑起来，不启动平台也能调界面。
// 真正运行时由平台注入真实 host。
const {createApp,h} = await importShared('vue');

let store = {
  base_url: 'https://sehuatang.org/', username: '', password: '',
  security_question_id: '0', security_answer: '',
  enable_daily_checkin: true, enable_auto_reply: true, enable_smart_reply: true,
  enable_ai_reply: false, enable_ai_post_filter: true, enable_auto_post: false,
  max_replies_per_day: 3, reply_interval: [60, 120],
  schedule_cron: '', schedule_times: ['03:00', '09:00', '15:00', '21:00'],
  target_forums: ['fid=141'],
  reply_templates: ['谢谢楼主分享！', '感谢分享，收藏了！'],
  ai_api_type: 'openai', ai_api_url: '', ai_api_key: '', ai_model: 'gpt-3.5-turbo',
  proxy: { enabled: false, http_proxy: '', https_proxy: '', use_for_ai: true, use_for_browser: false },
  notify: true,
};

const mockHost = {
  pluginId: 'awpulse',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path === '/status') return {
      running: false, task: '', started_at: '', finished_at: '2026-07-15 03:00:12',
      last_result: '📊 AWPulse · 定时\n今日回复 3，签到 已签到\n本轮结果：完成',
      cookie: { exists: true, valid: true, age_days: 1.2, cookie_count: 12, message: '有效（已保存 1.2 天）' },
      today: { reply_count: 3, post_count: 0, checkin_success: true },
      user_info: { user_group: '中级会员', credits: 1200, money: 88 },
      schedule: '03:00、09:00、15:00、21:00',
    }
    if (path === '/run') return { ok: true, started: true, message: '已在后台开始运行' }
    if (path === '/stop') return { ok: true, message: '已请求停止' }
    if (path === '/stats') return {
      ok: true, today: { reply_count: 3, post_count: 0, checkin_success: true },
      ai: { ai_reply_count: 2, ai_filter_count: 5, ai_error_count: 0 },
      user_info: { user_group: '中级会员', credits: 1200, money: 88, coins: 3, rating: 10 },
      all: {},
    }
    if (path === '/posts') return { ok: true, items: [{ thread_title: '某小说', thread_url: 'https://x/tid=1', file_name: 'a.txt', posted_time: '2026-07-14 21:00' }] }
    if (path === '/replies') return { ok: true, items: [{ thread_title: '某帖', thread_url: 'https://x/tid=2', reply_content: '谢谢分享！', reply_time: '2026-07-15 03:00' }] }
    if (path === '/messages') return { ok: true, total: 1, unread: 1, timestamp: '2026-07-15 03:01', messages: [{ sender: '系统', content: '欢迎回来', time: '刚刚', is_unread: true }] }
    if (path === '/messages/refresh') return { ok: true, count: 1, unread: 1 }
    if (path === '/logs') return { ok: true, lines: ['03:00:01 - INFO - 开始运行(定时)', '03:00:12 - INFO - 自动化任务完成'] }
    if (path === '/cookie/check') return { ok: true, exists: true, valid: true, age_days: 1.2, cookie_count: 12, message: '有效（已保存 1.2 天）' }
    if (path === '/test_ai') return { ok: true, reply: '这内容不错，支持一下！' }
    return { ok: true }
  },
  toast: {
    success: (m) => console.log('%c[toast.success] ' + m, 'color:#6ee7a8'),
    error: (m) => console.warn('[toast.error] ' + m),
  },
};

createApp({
  render: () => h(Config, { pluginId: mockHost.pluginId, host: mockHost }),
}).mount('#app');
