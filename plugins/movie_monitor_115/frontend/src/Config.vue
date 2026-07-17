<template>
  <div class="movie-monitor-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'status' }" @click="tab = 'status'">📊 运行状态</button>
      <button :class="{ active: tab === 'logs' }" @click="tab = 'logs'">📝 处理记录</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <div class="section">
          <h3>监控范围</h3>
          <label class="row"><span>监控频道/群组</span><input v-model="cfg.monitor_ids" class="inp" placeholder="留空=监控所有会话，多个 ID 用逗号分隔" /></label>
          <div class="fld">
            <span class="lbl">转存类型</span>
            <div class="chips">
              <label class="chip"><input type="checkbox" :checked="mediaTypes.includes('movie')" @change="toggleMedia('movie')" />电影</label>
              <label class="chip"><input type="checkbox" :checked="mediaTypes.includes('tv')" @change="toggleMedia('tv')" />电视剧</label>
            </div>
          </div>
          <label class="row switch"><input v-model="cfg.only_complete_series" type="checkbox" /><span>剧集仅转存完结</span></label>
        </div>

        <div class="section">
          <h3>TMDB 配置</h3>
          <label class="row"><span>API Key</span><input v-model="cfg.tmdb_api_key" type="password" class="inp" placeholder="必填" /></label>
          <label class="row"><span>语言</span><input v-model="cfg.tmdb_language" class="inp" placeholder="zh-CN" /></label>
        </div>

        <div class="section">
          <h3>Emby 配置</h3>
          <label class="row"><span>地址</span><input v-model="cfg.emby_url" class="inp" placeholder="http://emby.local:8096" /></label>
          <label class="row"><span>API Key</span><input v-model="cfg.emby_api_key" type="password" class="inp" /></label>
          <label class="row switch"><input v-model="cfg.skip_emby_check" type="checkbox" /><span>跳过 Emby 查重（直接转发所有链接）</span></label>
        </div>

        <div class="section">
          <h3>转发设置</h3>
          <label class="row"><span>CMS Bot 用户名</span><input v-model="cfg.cms_bot_username" class="inp" placeholder="如 @cmsbot" /></label>
          <label class="row"><span>转发标签</span><input v-model="cfg.forward_label" class="inp" placeholder="115 网盘" /></label>
          <label class="row switch"><input v-model="cfg.forward_to_saved" type="checkbox" /><span>转发到 Saved Messages（自己的收藏）</span></label>
        </div>

        <div class="section">
          <h3>115 网盘配置</h3>
          <label class="row"><span>Cookie</span><input v-model="cfg.pan115_cookie" type="password" class="inp" placeholder="可选，用于获取文件名" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else-if="tab === 'status'" class="status">
        <div class="card">
          <h3>服务状态</h3>
          <div class="kv"><span>TMDB API</span><b :class="status.tmdb_ok ? 'ok' : 'err'">{{ status.tmdb_status || '未测试' }}</b></div>
          <div class="kv"><span>Emby 连接</span><b :class="status.emby_ok ? 'ok' : 'err'">{{ status.emby_status || '未测试' }}</b></div>
          <div class="kv"><span>Emby 库容量</span><b>{{ status.emby_items || 0 }} 项</b></div>
        </div>
        <button @click="testServices" class="btn" :disabled="testing">{{ testing ? '测试中...' : '测试连接' }}</button>
        <p v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'err'">{{ testResult.message }}</p>
      </div>

      <div v-else class="logs">
        <div class="toolbar">
          <button @click="loadLogs" class="btn-sm">刷新</button>
          <span class="muted">最近 {{ logs.length }} 条</span>
        </div>
        <table class="tbl">
          <thead><tr><th>时间</th><th>标题</th><th>TMDB ID</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(log, i) in logs" :key="i">
              <td class="muted">{{ log.time }}</td>
              <td>{{ log.title }}</td>
              <td><span class="tmdb-id">{{ log.tmdb_id || '-' }}</span></td>
              <td><span :class="'action-' + log.action">{{ log.action }}</span></td>
            </tr>
            <tr v-if="!logs.length"><td colspan="4" class="empty">暂无处理记录</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({ api: Object, config: Object })
const cfg = ref({
  monitor_ids: '', media_types: ['movie', 'tv'], only_complete_series: false,
  tmdb_api_key: '', tmdb_language: 'zh-CN',
  emby_url: '', emby_api_key: '', skip_emby_check: false,
  cms_bot_username: '', forward_label: '115 网盘', forward_to_saved: false,
  pan115_cookie: '',
})
const tab = ref('settings')
const saving = ref(false)
const status = ref({})
const testing = ref(false)
const testResult = ref(null)
const logs = ref([])

const mediaTypes = computed({
  get: () => Array.isArray(cfg.value.media_types) ? cfg.value.media_types : [],
  set: (v) => { cfg.value.media_types = v },
})

function toggleMedia(type) {
  const arr = mediaTypes.value
  const i = arr.indexOf(type)
  if (i >= 0) arr.splice(i, 1); else arr.push(type)
}

onMounted(() => {
  Object.assign(cfg.value, props.config || {})
  loadStatus()
  loadLogs()
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

async function testServices() {
  testing.value = true
  testResult.value = null
  try {
    const r = await props.api.post('/test')
    testResult.value = r
    loadStatus()
  } catch (e) {
    testResult.value = { ok: false, message: '测试失败：' + e.message }
  } finally {
    testing.value = false
  }
}

async function loadLogs() {
  try {
    const r = await props.api.get('/logs')
    logs.value = r.logs || []
  } catch {}
}
</script>

<style scoped>
.movie-monitor-config { display: flex; flex-direction: column; gap: 16px; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tabs button { background: none; border: none; color: var(--text-secondary, #b9c0cc); padding: 10px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tabs button.active { color: var(--text-primary, #e8edf5); border-bottom-color: var(--primary, #4a9eff); }
.tab-content { padding: 16px 0; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; color: var(--text-primary, #e8edf5); margin-bottom: 12px; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.row > span:first-child { min-width: 120px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { gap: 8px; }
.row.switch span { min-width: auto; }
.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
.fld { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.lbl { font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-secondary, #b9c0cc); cursor: pointer; padding: 4px 8px; border-radius: 6px; background: var(--bg-card, #12141c); border: 1px solid var(--border-light, #2a2e3a); }
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
.kv b.ok { color: #4ade80; }
.kv b.err { color: #ff4a4a; }
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
.tmdb-id { color: var(--primary, #4a9eff); font-family: monospace; }
.action-转发 { color: #4ade80; }
.action-跳过 { color: #ffa500; }
.action-失败 { color: #ff4a4a; }
</style>
