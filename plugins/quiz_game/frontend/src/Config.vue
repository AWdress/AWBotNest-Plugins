<template>
  <div class="quiz-game-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'history' }" @click="tab = 'history'">📝 答题记录</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <div class="section">
          <h3>群组设置</h3>
          <label class="row"><span>允许的群组</span><input v-model="cfg.valid_groups" class="inp" placeholder="留空=不限制，多个 ID 用逗号分隔" /></label>
        </div>

        <div class="section">
          <h3>出题源</h3>
          <label class="row"><span>出题方式</span><select v-model="cfg.source" class="inp">
            <option value="ai">AI 模型</option>
            <option value="tianapi">天行数据</option>
          </select></label>

          <template v-if="cfg.source === 'ai'">
            <label class="row"><span>API Key</span><input v-model="cfg.ai_api_key" type="password" class="inp" /></label>
            <label class="row"><span>接口地址</span><input v-model="cfg.ai_base_url" class="inp" placeholder="如 https://api.openai.com/v1" /></label>
            <label class="row"><span>模型</span><input v-model="cfg.ai_model" class="inp" placeholder="gpt-4o-mini" /></label>
          </template>

          <template v-if="cfg.source === 'tianapi'">
            <label class="row"><span>天行数据 Key</span><input v-model="cfg.tianapi_key" type="password" class="inp" /></label>
          </template>
        </div>

        <div class="section">
          <h3>奖励设置</h3>
          <label class="row"><span>基础奖励(魔力)</span><input v-model.number="cfg.base_reward" type="number" class="inp" min="1" /></label>
          <label class="row switch"><input v-model="cfg.streak_enabled" type="checkbox" /><span>启用连胜加成</span></label>
          <template v-if="cfg.streak_enabled">
            <label class="row indent"><span>连胜倍率</span><input v-model.number="cfg.streak_multiplier" type="number" class="inp" min="1" step="0.1" /></label>
            <label class="row indent"><span>最大连胜</span><input v-model.number="cfg.max_streak" type="number" class="inp" min="1" /></label>
          </template>
        </div>

        <div class="section">
          <h3>答题规则</h3>
          <label class="row"><span>答题超时(秒)</span><input v-model.number="cfg.timeout" type="number" class="inp" min="10" /></label>
          <label class="row"><span>自动删除延迟(秒)</span><input v-model.number="cfg.auto_delete_delay" type="number" class="inp" min="0" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else class="history">
        <div class="toolbar">
          <button @click="loadHistory" class="btn-sm">刷新</button>
          <span class="muted">最近 {{ history.length }} 条</span>
        </div>
        <table class="tbl">
          <thead><tr><th>时间</th><th>群组</th><th>题目</th><th>答案</th><th>回答者</th><th>奖励</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in history" :key="i">
              <td class="muted">{{ h.time }}</td>
              <td>{{ h.group }}</td>
              <td>{{ h.question }}</td>
              <td><b>{{ h.answer }}</b></td>
              <td>{{ h.player || '-' }}</td>
              <td class="gold">{{ h.reward || 0 }}</td>
            </tr>
            <tr v-if="!history.length"><td colspan="6" class="empty">暂无答题记录</td></tr>
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
  valid_groups: '', source: 'ai',
  ai_api_key: '', ai_base_url: '', ai_model: 'gpt-4o-mini',
  tianapi_key: '',
  base_reward: 500, streak_enabled: true, streak_multiplier: 1.5, max_streak: 5,
  timeout: 60, auto_delete_delay: 30,
})
const tab = ref('settings')
const saving = ref(false)
const history = ref([])

onMounted(() => {
  Object.assign(cfg.value, props.config || {})
  loadHistory()
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

async function loadHistory() {
  try {
    const r = await props.api.get('/history')
    history.value = r.history || []
  } catch {}
}
</script>

<style scoped>
.quiz-game-config { display: flex; flex-direction: column; gap: 16px; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tabs button { background: none; border: none; color: var(--text-secondary, #b9c0cc); padding: 10px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tabs button.active { color: var(--text-primary, #e8edf5); border-bottom-color: var(--primary, #4a9eff); }
.tab-content { padding: 16px 0; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; color: var(--text-primary, #e8edf5); margin-bottom: 12px; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.row > span:first-child { min-width: 130px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { gap: 8px; }
.row.switch span { min-width: auto; }
.row.indent { margin-left: 20px; }
.row.indent > span:first-child { min-width: 110px; }
.inp, select.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
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
</style>
