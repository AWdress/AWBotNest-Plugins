import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-B5_Xy38f.js';

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
  api_url: 'https://nf.example.com/api/openapi', api_key: '',
  schedule: '0 8 * * *', notify: true,
  min_year: 0, min_vote: 0, min_popularity: 0, media_type: 'all',
  douban_enabled: true, douban_ranks: ['movie-hot-gaia', 'tv-hot'],
  netflix_enabled: false, maoyan_enabled: false, mikan_enabled: false,
};

const mockHost = {
  pluginId: 'auto_subscribe',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path === '/test') return { ok: true, quota: { hdhive: 'DEV 1000次/2000积分' } }
    if (path === '/run') return { ok: true, summary: '📥 自动订阅 · 手动\n[豆瓣榜单] 新增订阅2，已订阅3\n✅ 新增订阅：豆瓣榜单·沙丘、豆瓣榜单·某剧' }
    if (path === '/history') return {
      last_run: '2026-07-15 08:00:00',
      stats: { subscribed: 5, in_library: 3, exists: 2, filtered: 4, unrecognized: 1, error: 0 },
      items: [
        { key: 'movie:438631', title: '沙丘', status: 'subscribed', tmdb_id: '438631', source: 'douban', time: '2026-07-15 08:00:01' },
        { key: 'tv:255358:s1', title: '新攻壳机动队', status: 'in_library', tmdb_id: '255358', source: 'mikan', time: '2026-07-15 08:00:02' },
        { key: 'movie:1', title: '某未识别片', status: 'unrecognized', tmdb_id: '', source: 'maoyan', time: '2026-07-15 08:00:03' },
      ],
    }
    if (path === '/history/delete') return { ok: true }
    if (path === '/subscriptions') return {
      items: [
        { tmdb_id: '4556', title: '夜巡', media_type: 'movie', year: '2007', rating: 6.2, total_episodes: 0, local_episodes: 0, sub_status: 'active', is_in_library: false },
        { tmdb_id: '255358', title: '新攻壳机动队', media_type: 'tv', year: '2026', rating: 9.1, total_episodes: 10, local_episodes: 2, sub_status: 'active', is_in_library: false },
      ],
    }
    if (path === '/subscriptions/remove') return { ok: true, message: '已取消订阅' }
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
