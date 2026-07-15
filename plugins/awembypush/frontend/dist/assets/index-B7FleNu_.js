import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-Zs4xaHOy.js';

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

// 本地预览入口（npm run dev）：模拟 host 跑 Config.vue。真正运行时由平台注入真实 host。
const {createApp,h} = await importShared('vue');

let store = {
  enable_tmdb: true, tmdb_api_key: '', tmdb_api_domain: 'api.themoviedb.org',
  tmdb_image_domain: 'image.tmdb.org', emby_server_url: '',
  dedup_window: 60, episode_cache_timeout: 30,
  enable_watch_link: false, watch_link_type: 'server', link_redirect_prefix: '',
  tg_bot_token: '', tg_chat_id: '', tg_api_host: '',
  wx_corp_id: '', wx_corp_secret: '', wx_agent_id: '', wx_user_id: '@all',
  wx_msg_type: 'news_notice', wx_proxy_url: '', wx_no_proxy: true,
  bark_server: 'https://api.day.app', bark_keys: '',
  enable_custom_template: false, tg_template: '', wx_title_template: '',
  wx_body_template: '', bark_title_template: '', bark_body_template: '',
};

const mockHost = {
  pluginId: 'awembypush',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path === '/recent') return {
      items: [
        { time: '07-15 20:30', item_name: '沙丘2', item_type: 'MOV', episode_text: '', channels: 'Telegram / Bark', image_url: '' },
        { time: '07-15 19:10', item_name: '某剧', item_type: 'TV', episode_text: '第1季：第3集', channels: 'Telegram', image_url: '' },
      ],
    }
    if (path === '/test') return { ok: true, message: '已向 Telegram / Bark 发送测试通知' }
    if (path === '/clear') return { ok: true }
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
