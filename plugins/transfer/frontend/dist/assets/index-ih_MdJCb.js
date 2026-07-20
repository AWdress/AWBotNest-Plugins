import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-BTNxrj2v.js';

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
  site_audiences: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hddolby: ['on', 'notify', 'lb_in', 'lb_out'],
  site_azusa: ['on', 'notify', 'lb_in', 'lb_out'],
  site_zm: ['on', 'notify', 'lb_in', 'lb_out'],
  site_springsunday: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hdsky: ['on', 'notify', 'lb_in', 'lb_out'],
  site_mocktest: [],
  rank_output: 'image', rank_size: 10, rank_command: '转账排行',
  notify_delay_min: 0, notify_delay_max: 0,
  ssd_click_mode: 'off', owner_notify: false,
};

const mockHost = {
  pluginId: 'transfer',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path === '/sites') return {
      sites: [
        { name: 'audiences', bonus: '爆米花', has_data: true },
        { name: 'hdsky', bonus: '银元', has_data: true },
        { name: 'azusa', bonus: '魔力值', has_data: false },
      ],
    }
    if (path.startsWith('/leaderboard')) return {
      items: [
        { rank: 1, user_name: '大佬A', total: 12000, count: 8 },
        { rank: 2, user_name: '大佬B', total: 8600, count: 5 },
        { rank: 3, user_name: '大佬C', total: 3000, count: 2 },
      ],
    }
    if (path === '/recent') return {
      items: [
        { site: 'audiences', direction: 'in', user_name: '大佬A', amount: 1000, ts: '2026-07-15T20:30:00' },
        { site: 'hdsky', direction: 'out', user_name: '大佬B', amount: 500, ts: '2026-07-15T20:25:00' },
      ],
    }
    if (path === '/reset') return { ok: true }
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
