<script setup>
import { ref } from 'vue'
import LotteryPanel from './LotteryPanel.vue'
import ReadPanel from './ReadPanel.vue'
import BonusPanel from './BonusPanel.vue'
import ActivityPanel from './ActivityPanel.vue'
import CookiePanel from './CookiePanel.vue'

defineProps({ pluginId: { type: String, required: true }, host: { type: Object, required: true } })
const tab = ref('bonus')
</script>

<template>
  <div class="plugin-shell">
    <nav class="tabs" aria-label="插件功能">
      <button :class="{ active: tab === 'bonus' }" @click="tab = 'bonus'">赠豆</button>
      <button :class="{ active: tab === 'activity' }" @click="tab = 'activity'">抢红包/抽奖</button>
      <button :class="{ active: tab === 'lottery' }" @click="tab = 'lottery'">幸运转盘</button>
      <button :class="{ active: tab === 'read' }" @click="tab = 'read'">消息管理</button>
      <button :class="{ active: tab === 'auth' }" @click="tab = 'auth'">登录设置</button>
    </nav>
    <BonusPanel v-if="tab === 'bonus'" :plugin-id="pluginId" :host="host" />
    <ActivityPanel v-else-if="tab === 'activity'" :plugin-id="pluginId" :host="host" />
    <LotteryPanel v-else-if="tab === 'lottery'" :plugin-id="pluginId" :host="host" />
    <ReadPanel v-else-if="tab === 'read'" :plugin-id="pluginId" :host="host" />
    <CookiePanel v-else :plugin-id="pluginId" :host="host" />
  </div>
</template>

<style scoped>
.plugin-shell { color: #dce7f5; }
.tabs { display: flex; gap: 6px; width: fit-content; max-width: 100%; overflow-x: auto; box-sizing: border-box; padding: 5px; margin: 0 0 18px; border: 1px solid #25364c; border-radius: 12px; background: #101a29; scrollbar-color: #38506c #101a29; }
.tabs button { flex: 0 0 auto; min-height: 38px; padding: 0 18px; border: 0; border-radius: 8px; color: #9badc2; background: transparent; font: inherit; font-weight: 650; white-space: nowrap; cursor: pointer; transition: .18s ease; }
.tabs button:hover { color: #dce7f5; background: #172438; }
.tabs button.active { color: #fff; background: #287de7; box-shadow: 0 5px 14px #0b68d64d; }
@media (max-width: 560px) { .tabs { width: 100%; } .tabs button { padding: 0 13px; } }
</style>
