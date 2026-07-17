<template>
  <div class="bomb-game-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'games' }" @click="tab = 'games'">🎮 游戏记录</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <div class="section">
          <h3>群组设置</h3>
          <label class="row"><span>允许的群组</span><input v-model="cfg.valid_groups" class="inp" placeholder="留空=不限制，多个 ID 用逗号分隔" /></label>
          <label class="row"><span>临时停用的群</span><input v-model="cfg.monitor_disabled_groups" class="inp" placeholder="暂时禁止开启的群 ID" /></label>
        </div>

        <div class="section">
          <h3>奖池设置</h3>
          <label class="row"><span>参与费用(魔力)</span><input v-model.number="cfg.entry_fee" type="number" class="inp" min="1" /></label>
          <label class="row"><span>中奖者分成(%)</span><input v-model.number="cfg.pool_ratio" type="number" class="inp" min="10" max="90" /></label>
          <label class="row"><span>参与等待时间(秒)</span><input v-model.number="cfg.wait_time" type="number" class="inp" min="5" /></label>
        </div>

        <div class="section">
          <h3>难度设置</h3>
          <label class="row"><span>初始范围下限</span><input v-model.number="cfg.default_min" type="number" class="inp" /></label>
          <label class="row"><span>初始范围上限</span><input v-model.number="cfg.default_max" type="number" class="inp" /></label>
          <label class="row switch"><input v-model="cfg.enable_range_shrink" type="checkbox" /><span>按距离动态调整范围</span></label>
          <template v-if="cfg.enable_range_shrink">
            <label class="row indent"><span>距离1-5调整</span><input v-model.number="cfg.shrink_1_5" type="number" class="inp" /></label>
            <label class="row indent"><span>距离6-15调整</span><input v-model.number="cfg.shrink_6_15" type="number" class="inp" /></label>
            <label class="row indent"><span>距离16-30调整</span><input v-model.number="cfg.shrink_16_30" type="number" class="inp" /></label>
            <label class="row indent"><span>距离31+调整</span><input v-model.number="cfg.shrink_31plus" type="number" class="inp" /></label>
          </template>
          <label class="row"><span>一发命中概率(‰)</span><input v-model.number="cfg.instant_win_permille" type="number" class="inp" min="0" max="50" /></label>
        </div>

        <div class="section">
          <h3>消息设置</h3>
          <label class="row switch"><input v-model="cfg.auto_delete_enabled" type="checkbox" /><span>自动删除游戏消息</span></label>
          <label class="row" v-if="cfg.auto_delete_enabled"><span>删除延迟(秒)</span><input v-model.number="cfg.auto_delete_delay" type="number" class="inp" min="3" /></label>
          <label class="row" v-if="cfg.auto_delete_enabled"><span>不删除的群</span><input v-model="cfg.no_delete_groups" class="inp" placeholder="群 ID，逗号分隔" /></label>
        </div>

        <div class="section">
          <h3>其他</h3>
          <label class="row switch"><input v-model="cfg.require_transfer_confirm" type="checkbox" /><span>需转账bot确认才算参与</span></label>
          <label class="row" v-if="cfg.require_transfer_confirm"><span>转账bot ID</span><input v-model="cfg.transfer_bot_ids" class="inp" placeholder="多个用逗号分隔" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else class="games">
        <div class="toolbar">
          <button @click="loadGames" class="btn-sm">刷新</button>
          <span class="muted">最近 {{ games.length }} 场</span>
        </div>
        <table class="tbl">
          <thead><tr><th>时间</th><th>群组</th><th>参与人数</th><th>奖池</th><th>中奖者</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="(g, i) in games" :key="i">
              <td class="muted">{{ g.time }}</td>
              <td>{{ g.group_name }}</td>
              <td>{{ g.players }}</td>
              <td class="gold">{{ g.pool }}</td>
              <td>{{ g.winner || '-' }}</td>
              <td><span :class="'status-' + g.status">{{ g.status }}</span></td>
            </tr>
            <tr v-if="!games.length"><td colspan="6" class="empty">暂无游戏记录</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({ api: Object, config: Object })
const cfg = ref({
  valid_groups: '', monitor_disabled_groups: '', entry_fee: 888, pool_ratio: 50, wait_time: 30,
  default_min: 1, default_max: 100, enable_range_shrink: true,
  shrink_1_5: -10, shrink_6_15: -4, shrink_16_30: -2, shrink_31plus: 2, instant_win_permille: 5,
  auto_delete_enabled: true, auto_delete_delay: 30, no_delete_groups: '',
  require_transfer_confirm: false, transfer_bot_ids: '',
})
const tab = ref('settings')
const saving = ref(false)
const games = ref([])

onMounted(() => {
  Object.assign(cfg.value, props.config || {})
  loadGames()
})

async function save() {
  saving.value = true
  try {
    await props.api.post('/update_config', cfg.value)
    saving.value = false
  } catch (e) {
    alert('保存失败：' + e.message)
    saving.value = false
  }
}

async function loadGames() {
  try {
    const r = await props.api.get('/games')
    games.value = r.games || []
  } catch {}
}
</script>

<style scoped>
.bomb-game-config { display: flex; flex-direction: column; gap: 16px; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tabs button { background: none; border: none; color: var(--text-secondary, #b9c0cc); padding: 10px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tabs button.active { color: var(--text-primary, #e8edf5); border-bottom-color: var(--primary, #4a9eff); }
.tab-content { padding: 16px 0; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; color: var(--text-primary, #e8edf5); margin-bottom: 12px; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.row > span:first-child { min-width: 140px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { gap: 8px; }
.row.switch span { min-width: auto; }
.row.indent { margin-left: 20px; }
.row.indent > span:first-child { min-width: 120px; }
.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
.btn, .btn-primary, .btn-sm { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn-primary { background: var(--primary, #4a9eff); color: #fff; }
.btn { background: var(--bg-card, #12141c); color: var(--text-primary, #e8edf5); border: 1px solid var(--border-light, #2a2e3a); margin-right: 8px; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn:disabled, .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); color: var(--text-secondary, #b9c0cc); font-size: 12px; font-weight: normal; }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); font-size: 13px; color: var(--text-primary, #e8edf5); }
.tbl td.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl td.empty { text-align: center; color: var(--text-muted, #7a8291); padding: 40px; }
.tbl td.gold { color: #ffd700; font-weight: bold; }
.status-完成 { color: #4ade80; }
.status-进行中 { color: var(--primary, #4a9eff); }
.status-取消 { color: #ff4a4a; }
</style>
