import { createApp, h } from 'vue'
import Config from './Config.vue'
let store = {}
const host = {
  async getConfig(){ return store },
  async saveConfig(v){ store={...store,...v} },
  async callApi(path){
    if(path==='/status') return {running:false,task:'',scheduled:true,schedule:'0 3 * * *',history:[{time:'2026-08-28 03:16:24',source:'定时',task:'定时媒体维护',ok:true,summary:'剧集季集修复\n检查 182 集，修正 3 集'}]}
    return {ok:true,started:true,message:'已开始'}
  },
  toast:{success:console.log,error:console.warn},
}
createApp({render:()=>h(Config,{pluginId:'emby_toolbox',host})}).mount('#app')
