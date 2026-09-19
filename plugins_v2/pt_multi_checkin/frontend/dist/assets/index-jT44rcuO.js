import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-DlO4HoGo.js';

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
    defaults: { selected_sites: ['audiences', 'ourbits', 'piggo', 'hhan', 'tjupt', 'chdbits', 'opencd', 'u2', 'btschool', 'hdsky', 'pterclub', 'zhuque'], custom_sites: [] },
    sites: [
      { key: 'audiences', name: '观众', domain: 'audiences.me', group: '12大站点' },
      { key: 'ourbits', name: '我堡', domain: 'ourbits.club', group: '12大站点' },
      { key: 'piggo', name: '猪猪', domain: 'piggo.me', group: '其他站点' },
      { key: 'hhan', name: '憨憨', domain: 'hhanclub.net', group: '12大站点' },
      { key: 'tjupt', name: '北洋园', domain: 'tjupt.org', group: '其他站点' },
      { key: 'chdbits', name: '彩虹岛', domain: 'ptchdbits.co', group: '12大站点' },
      { key: 'opencd', name: '皇后', domain: 'open.cd', group: '12大站点' },
      { key: 'u2', name: '幼儿园', domain: 'u2.dmhy.org', group: '其他站点' },
      { key: 'btschool', name: '学校', domain: 'pt.btschool.club', group: '其他站点' },
      { key: 'hdsky', name: '天空', domain: 'hdsky.me', group: '12大站点' },
      { key: 'pterclub', name: '猫站', domain: 'pterclub.net', group: '12大站点' },
      { key: 'ttg', name: '听听歌', domain: 'totheglory.im', group: '12大站点' },
      { key: 'hdhome', name: '家园', domain: 'hdhome.org', group: '12大站点' },
      { key: 'hdfans', name: '红豆饭', domain: 'hdfans.org', group: '其他站点' },
      { key: 'zmpt', name: '织梦', domain: 'zmpt.cc', group: '其他站点' },
      { key: 'hdkyl', name: '麒麟', domain: 'hdkyl.in', group: '其他站点' },
      { key: 'cyanbug', name: '大青虫', domain: 'cyanbug.net', group: '其他站点' },
      { key: 'pt52', name: '我爱PT', domain: '52pt.site', group: '其他站点' },
      { key: 'haidan', name: '海胆', domain: 'haidan.video', group: '其他站点' },
      { key: 'hares', name: '白兔', domain: 'club.hares.top', group: '其他站点' },
      { key: 'hdarea', name: '好大', domain: 'hdarea.club', group: '其他站点' },
      { key: 'hdchina', name: '高清中国', domain: 'hdchina.org', group: '其他站点' },
      { key: 'hdcity', name: '高清城市', domain: 'hdcity.city', group: '其他站点' },
      { key: 'hdupt', name: '北邮人', domain: 'pt.hdupt.com', group: '其他站点' },
      { key: 'pttime', name: 'PT时间', domain: 'pttime.org', group: '其他站点' },
      { key: 'yema', name: '野马', domain: 'yemapt.org', group: '其他站点' },
      { key: 'zhuque', name: '朱雀', domain: 'zhuque.in', group: '其他站点' },
    ],
  } : path === '/history' ? { items: [] } : path === '/logs' ? { items: [{ time: '08:10:00', level: 'info', site: '系统', message: '插件已加载，等待签到任务' }] } : {},
  saveConfig: async () => {},
  toast: { success: console.log, warning: console.warn, error: console.error },
};

createApp(Config, { pluginId: 'pt_multi_checkin', host: demoHost }).mount('#app');
