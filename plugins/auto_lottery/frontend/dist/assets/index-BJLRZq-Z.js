import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-BmrEKuHm.js';

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
  auto_lottery_enabled: false, lottery_bot_id: '6461022460', auto_lottery_username: '',
  auto_lottery_time: '', lottery_target_groups: [], custom_lottery_groups: [],
  lottery_forward_enabled: false, lottery_forward_first_participant: false,
  prize_list: '', universal_prize_match: false, prize_case_sensitive: false,
  trap_enabled: true, trap_case_sensitive: false, trap_enable_prize_pattern_check: true,
  trap_enable_creator_blacklist: true, trap_enable_participant_check: true,
  trap_max_participants: 1, trap_blacklist_creator_ids: '', trap_suspicious_keywords: '脚本,挂机,机器人',
  lottery_wait_enabled: false, lottery_participate_wait_min: 25, lottery_participate_wait_max: 65,
  lottery_thank_wait_min: 10, lottery_thank_wait_max: 45, lottery_heimu_wait_min: 20, lottery_heimu_wait_max: 40,
  lottery_negative_wait_min: 10, lottery_negative_wait_max: 60, group_wait_overrides: '',
  lottery_thank_message: false, thank_texts: '感谢{boss}大佬', username_reply_switch: false,
  transfer_groups: [], lottery_heimu_message: false, heimu_texts: '黑幕',
  lose_reply_switch: false, negative_texts: '怎么可能啊',
  auto_prize_enabled: false, manual_prize_mode: false, prize_send_interval_enabled: true,
  prize_send_interval_min: 2, prize_send_interval_max: 5, prize_send_blacklist: '',
  notify_owner: true, notify_skips: false,
};

const mockHost = {
  pluginId: 'auto_lottery',
  token: 'dev',
  async getConfig() { return { ...store } },
  async saveConfig(values) { store = { ...store, ...values }; console.log('[mock] save', store); },
  async callApi(path, opts = {}) {
    console.log('[mock] callApi', path, opts);
    if (path.startsWith('/dialogs')) return {
      items: [
        { id: -1001234567890, title: '某PT站抽奖群' },
        { id: -1001234567891, title: '另一个抽奖群' },
      ],
    }
    if (path === '/pending') return {
      items: [
        { lottery_id: 'abc12345-def6-7890', winners: 3, chat_title: '某PT站抽奖群', prize: '魔力', time: '2026-07-15 20:00' },
      ],
      count: 1,
    }
    if (path === '/history') return {
      items: [{ lottery_id: 'xyz00000', total: 5, success: 5, failed: 0, time: '2026-07-15 18:00' }],
    }
    if (path === '/send') return { ok: true, message: '发奖完成：成功 3/3' }
    if (path === '/clear') return { ok: true, cleared: 1 }
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
