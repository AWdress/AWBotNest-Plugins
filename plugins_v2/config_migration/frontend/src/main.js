import { createApp } from 'vue'
import Config from './Config.vue'
createApp(Config,{host:{getConfig:async()=>({}),saveConfig:async()=>{},callApi:async()=>({ok:true})}}).mount('#app')
