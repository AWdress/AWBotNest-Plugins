import { createApp } from 'vue'
import Config from './Config.vue'
const unavailable = async () => { throw new Error('请在 AWBotNest 插件页面打开。') }
createApp(Config, { host: { pluginId: 'immortal', getConfig: unavailable, saveConfig: unavailable, callApi: unavailable } }).mount('#app')
