<template>
  <div class="hdhive-quiz-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'status' }" @click="tab = 'status'">📊 运行状态</button>
      <button :class="{ active: tab === 'history' }" @click="tab = 'history'">📝 答题记录</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <div class="section">
          <h3>基本设置</h3>
          <label class="row switch"><input v-model="cfg.enabled" type="checkbox" /><span>启用自动答题</span></label>
          <label class="row"><span>发包 Bot ID</span><input v-model="cfg.bot_ids" class="inp" placeholder="留空=监听所有 bot，多个用逗号分隔" /></label>
          <label class="row"><span>监听群组 ID</span><input v-model="cfg.chat_ids" class="inp" placeholder="留空=监听所有群，多个用逗号分隔" /></label>
          <label class="row"><span>回复格式</span><select v-model="cfg.reply_format" class="inp">
            <option value="content">选项原文（如：蜜蜂）</option>
            <option value="letter">选项字母（如：A）</option>
            <option value="full">字母+原文（如：A. 蜜蜂）</option>
          </select></label>
          <p class="tip">回复答案的文本形式。判断题固定回复 对/错。</p>
        </div>

        <div class="section">
          <h3>大模型兜底</h3>
          <label class="row switch"><input v-model="cfg.llm_enabled" type="checkbox" /><span>题库未命中时用大模型兜底</span></label>
          <label class="row"><span>API Key</span><input v-model="cfg.llm_api_key" type="password" class="inp" :disabled="!cfg.llm_enabled" /></label>
          <label class="row"><span>接口地址</span><input v-model="cfg.llm_base_url" class="inp" placeholder="如 https://api.openai.com/v1" :disabled="!cfg.llm_enabled" /></label>
          <label class="row"><span>模型</span><input v-model="cfg.llm_model" class="inp" placeholder="gpt-4o-mini" :disabled="!cfg.llm_enabled" /></label>
        </div>

        <div class="section">
          <h3>题库设置</h3>
          <label class="row"><span>题库仓库</span><input v-model="cfg.bank_repo" class="inp" placeholder="GitHub 仓库地址" /></label>
          <label class="row"><span>分支</span><input v-model="cfg.bank_branch" class="inp" placeholder="main" /></label>
          <label class="row"><span>子目录</span><input v-model="cfg.bank_subdir" class="inp" placeholder="questions" /></label>
          <label class="row"><span>同步间隔(小时)</span><input v-model.number="cfg.bank_sync_hours" type="number" class="inp" min="1" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else-if="tab === 'status'" class="status">
        <div class="card">
          <h3>题库状态</h3>
          <div class="kv"><span>题目数量</span><b>{{ status.bank_size || 0 }}</b></div>
          <div class="kv"><span>最后同步</span><b>{{ status.last_sync || '从未同步' }}</b></div>
          <div class="kv"><span>同步状态</span><b :class="status.sync_running ? 'running' : ''">{{ status.sync_status || '空闲' }}</b></div>
        </div>
        <button @click="syncBank" class="btn" :disabled="syncing">{{ syncing ? '同步中...' : '手动同步题库' }}</button>
        <button @click="testLLM" class="btn" :disabled="testing || !cfg.llm_enabled">{{ testing ? '测试中...' : '测试大模型' }}</button>
        <p v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'err'">{{ testResult.message }}</p>
      </div>

      <div v-else class="history">
        <div class="toolbar">
          <button @click="loadHistory" class="btn-sm">刷新</button>
          <span class="muted">最近 {{ history.length }} 条</span>
        </div>
        <table class="tbl">
          <thead><tr><th>时间</th><th>题目</th><th>答案</th><th>来源</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in history" :key="i">
              <td class="muted">{{ h.time }}</td>
              <td>{{ h.question }}</td>
              <td><b>{{ h.answer }}</b></td>
              <td><span :class="'src-' + h.source">{{ h.source === 'bank' ? '题库' : 'LLM' }}</span></td>
            </tr>
            <tr v-if="!history.length"><td colspan="4" class="empty">暂无答题记录</td></tr>
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
  enabled: false, bot_ids: '', chat_ids: '', reply_format: 'content',
  llm_enabled: false, llm_api_key: '', llm_base_url: '', llm_model: 'gpt-4o-mini',
  bank_repo: 'https://github.com/my-name-is-alan/hdhive-red-questions',
  bank_branch: 'main', bank_subdir: 'questions', bank_sync_hours: 12,
})
const tab = ref('settings')
const saving = ref(false)
const status = ref({})
const syncing = ref(false)
const testing = ref(false)
const testResult = ref(null)
const history = ref([])

onMounted(() => {
  Object.assign(cfg.value, props.config || {})
  loadStatus()
  loadHistory()
  setInterval(loadStatus, 5000)
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

async function loadStatus() {
  try {
    const r = await props.api.get('/status')
    status.value = r
  } catch {}
}

async function syncBank() {
  syncing.value = true
  try {
    const r = await props.api.post('/sync')
    alert(r.message || '同步完成')
    loadStatus()
  } catch (e) {
    alert('同步失败：' + e.message)
  } finally {
    syncing.value = false
  }
}

async function testLLM() {
  testing.value = true
  testResult.value = null
  try {
    const r = await props.api.post('/test_llm')
    testResult.value = r
  } catch (e) {
    testResult.value = { ok: false, message: '测试失败：' + e.message }
  } finally {
    testing.value = false
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
.hdhive-quiz-config { display: flex; flex-direction: column; gap: 16px; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tabs button { background: none; border: none; color: var(--text-secondary, #b9c0cc); padding: 10px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tabs button.active { color: var(--text-primary, #e8edf5); border-bottom-color: var(--primary, #4a9eff); }
.tab-content { padding: 16px 0; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; color: var(--text-primary, #e8edf5); margin-bottom: 12px; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.row > span:first-child { min-width: 100px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { gap: 8px; }
.row.switch input { margin: 0; }
.inp, select.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
.inp:disabled { opacity: 0.5; cursor: not-allowed; }
.tip { font-size: 12px; color: var(--text-muted, #7a8291); margin: 4px 0 0 112px; line-height: 1.6; }
.btn, .btn-primary, .btn-sm { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn-primary { background: var(--primary, #4a9eff); color: #fff; }
.btn { background: var(--bg-card, #12141c); color: var(--text-primary, #e8edf5); border: 1px solid var(--border-light, #2a2e3a); margin-right: 8px; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn:disabled, .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.card { background: var(--bg-card, #12141c); padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.card h3 { font-size: 14px; margin-bottom: 12px; }
.kv { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.kv:last-child { border-bottom: none; }
.kv span { color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.kv b { color: var(--text-primary, #e8edf5); font-size: 14px; }
.kv b.running { color: var(--primary, #4a9eff); }
.test-result { margin-top: 12px; padding: 10px; border-radius: 6px; font-size: 13px; }
.test-result.ok { background: rgba(74, 158, 255, 0.1); color: var(--primary, #4a9eff); }
.test-result.err { background: rgba(255, 74, 74, 0.1); color: #ff4a4a; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); color: var(--text-secondary, #b9c0cc); font-size: 12px; font-weight: normal; }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); font-size: 13px; color: var(--text-primary, #e8edf5); }
.tbl td.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl td.empty { text-align: center; color: var(--text-muted, #7a8291); padding: 40px; }
.src-bank { color: var(--primary, #4a9eff); }
.src-llm { color: #ffa500; }
</style>
