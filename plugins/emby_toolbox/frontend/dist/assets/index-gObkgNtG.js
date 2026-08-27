import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-D65sQCGU.js';

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
let store = {};
const host = {
  async getConfig(){ return store },
  async saveConfig(v){ store={...store,...v}; },
  async callApi(path){
    if(path==='/status') return {running:false,task:'',scheduled:true,schedule:'0 3 * * *',history:[{time:'2026-08-28 03:16:24',source:'定时',task:'定时媒体维护',ok:true,summary:'剧集季集修复\n检查 182 集，修正 3 集'}]}
    return {ok:true,started:true,message:'已开始'}
  },
  toast:{success:console.log,error:console.warn},
};
createApp({render:()=>h(Config,{pluginId:'emby_toolbox',host})}).mount('#app');
