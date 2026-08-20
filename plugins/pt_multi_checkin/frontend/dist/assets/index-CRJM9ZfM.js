import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-Bh7mJeHC.js';

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

const {createApp} = await importShared('vue');

const demoHost = {
  getConfig: async () => ({}),
  callApi: async path => path === '/meta' ? {
    defaults: { selected_sites: ['audiences', 'ourbits', 'piggo', 'hhan', 'tjupt', 'hdsky', 'opencd'] },
    sites: [
      { key: 'audiences', name: 'Audiences', domain: 'audiences.me', group: 'NexusPHP' },
      { key: 'ourbits', name: 'OurBits', domain: 'ourbits.club', group: 'NexusPHP' },
      { key: 'piggo', name: 'PigGo', domain: 'piggo.me', group: 'NexusPHP' },
      { key: 'hhan', name: 'HHanClub', domain: 'hhanclub.net', group: 'NexusPHP' },
      { key: 'tjupt', name: 'TJUPT', domain: 'tjupt.org', group: '交互验证' },
      { key: 'hdsky', name: '天空', domain: 'hdsky.me', group: '交互验证' },
      { key: 'opencd', name: 'OpenCD', domain: 'open.cd', group: '交互验证' },
      { key: 'pterclub', name: 'PTerClub', domain: 'pterclub.net', group: '专用适配' },
      { key: 'zhuque', name: '朱雀', domain: 'zhuque.in', group: '专用适配' },
    ],
  } : path === '/history' ? { items: [] } : {},
  saveConfig: async () => {},
  toast: { success: console.log, warning: console.warn, error: console.error },
};
createApp(Config, { pluginId: 'pt_multi_checkin', host: demoHost }).mount('#app');
