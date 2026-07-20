import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-D4u6p2-Z.js';

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
  api_key: '', base_url: '', model: 'gpt-3.5-turbo',
  enable_private_chat: true, enable_group_chat: true, group_chat_ids: '',
  system_prompt: '# Role\n你是一个相处了很久的普通网友。',
  max_history: 10,
  enable_proactive: false, proactive_chat_ids: '',
  proactive_min_minutes: 60, proactive_max_minutes: 180,
  enable_explain_command: true, enable_explain_prompt: false,
  explain_prompt: '需要解释的消息内容：{content}',
  white_list_chats: '',
};

const mockHost = {
  pluginId: 'ai',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path === '/test') return { ok: true, message: '连接正常', model: 'gpt-3.5-turbo' }
    if (path === '/histories') return {
      items: [
        { chat_id: 12345678, is_private: true, count: 6, last: '你今天怎么样' },
        { chat_id: -1001234567890, is_private: false, count: 4, last: '哈哈哈' },
      ],
      proactive_next: '2026-07-15 21:30:00',
    }
    if (path === '/history') return {
      chat_id: 12345678,
      messages: [
        { role: 'user', content: '在吗' },
        { role: 'assistant', content: '在的👀' },
        { role: 'user', content: '你今天怎么样' },
        { role: 'assistant', content: '还行，摸鱼中😂' },
      ],
    }
    if (path === '/history/clear') return { ok: true }
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
