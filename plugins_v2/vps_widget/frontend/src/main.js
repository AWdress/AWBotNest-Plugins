import { createApp } from 'vue'
import Config from './Config.vue'

const host = window.__AW_PLUGIN_HOST__
if (host) createApp(Config, { host }).mount('#app')
else document.getElementById('app').textContent = '请在 AWBotNest 的 VPS-Widget 配置页打开。'
