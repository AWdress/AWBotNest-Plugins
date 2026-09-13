import { createApp, h } from 'vue'
import Config from './Config.vue'
const host = { async getConfig(){ return {} }, async saveConfig(){}, async revealSecret(){ return [] }, async callApi(){ return {ok:true,message:'签到完成'} }, toast:{success:console.log,error:console.error} }
createApp({render:()=>h(Config,{pluginId:'bilibili_signin',host})}).mount('#app')
