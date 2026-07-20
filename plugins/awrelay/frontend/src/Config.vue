<template>
  <div class="awrelay-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'status' }" @click="tab = 'status'">📊 运行状态</button>
      <button :class="{ active: tab === 'topics' }" @click="tab = 'topics'">💬 话题列表</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <div class="section">
          <h3>基本设置</h3>
          <label class="row switch"><input v-model="cfg.enabled" type="checkbox" /><span>启用 AWRelay</span></label>
          <label class="row"><span>话题群组 ID</span><input v-model="cfg.group_id" class="inp" placeholder="负数，如 -1001234567890" /></label>
          <label class="row"><span>管理员用户 ID</span><input v-model="cfg.admin_ids" class="inp" placeholder="留空允许群内成员，多个 ID 用逗号分隔" /></label>
        </div>

        <div class="section">
          <h3>人机验证</h3>
          <label class="row switch"><input v-model="cfg.captcha_enabled" type="checkbox" /><span>启用人机验证</span></label>
          <p v-if="cfg.captcha_enabled" class="muted">插件会为每位待验证用户随机生成一道简单算术题。</p>
        </div>

        <div class="section">
          <h3>广告过滤</h3>
          <label class="row switch"><input v-model="cfg.spam_enabled" type="checkbox" /><span>启用广告过滤</span></label>
          <label class="row" v-if="cfg.spam_enabled"><span>关键词</span><textarea v-model="cfg.spam_keywords" class="inp" rows="3" placeholder="多个关键词用逗号分隔"></textarea></label>
        </div>

        <div class="section">
          <h3>限流设置</h3>
          <label class="row"><span>时间窗口(秒)</span><input v-model.number="cfg.rate_limit_window" type="number" class="inp" min="1" /></label>
          <label class="row"><span>窗口内最大消息数</span><input v-model.number="cfg.rate_limit_count" type="number" class="inp" min="1" /></label>
        </div>

        <div class="section">
          <h3>其他</h3>
          <label class="row"><span>媒体组聚合延迟(秒)</span><input v-model.number="cfg.media_group_delay" type="number" class="inp" min="0" step="0.1" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else-if="tab === 'status'" class="status">
        <div class="card">
          <h3>服务状态</h3>
          <div class="kv"><span>Bot 状态</span><b :class="status.bot_running ? 'ok' : 'err'">{{ status.bot_status || '未运行' }}</b></div>
          <div class="kv"><span>话题群组</span><b>{{ status.group_title || '-' }}</b></div>
          <div class="kv"><span>活跃用户数</span><b>{{ status.active_users || 0 }}</b></div>
          <div class="kv"><span>总话题数</span><b>{{ status.total_topics || 0 }}</b></div>
          <div class="kv"><span>黑名单用户</span><b>{{ status.banned_users || 0 }}</b></div>
        </div>
      </div>

      <div v-else class="topics">
        <div class="toolbar">
          <button @click="loadTopics" class="btn-sm">刷新</button>
          <span class="muted">共 {{ topics.length }} 个话题</span>
        </div>
        <table class="tbl">
          <thead><tr><th>用户名</th><th>用户 ID</th><th>话题 ID</th><th>最后活跃</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in topics" :key="i">
              <td><b>{{ t.name }}</b></td>
              <td class="muted">{{ t.user_id }}</td>
              <td class="muted">{{ t.topic_id }}</td>
              <td class="muted">{{ t.last_active }}</td>
              <td><span :class="'status-' + t.status">{{ t.status }}</span></td>
              <td><button class="btn-sm" @click="toggleBan(t)">{{ t.status === '已封禁' ? '解除' : '拉黑' }}</button></td>
            </tr>
            <tr v-if="!topics.length"><td colspan="6" class="empty">暂无话题</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})
const cfg = ref({
  enabled: false, group_id: '', admin_ids: '',
  captcha_enabled: true,
  spam_enabled: true, spam_keywords: 'USDT,博彩,兼职,t.me/,http://,https://',
  rate_limit_window: 10, rate_limit_count: 5,
  media_group_delay: 2.0,
})
const tab = ref('settings')
const saving = ref(false)
const status = ref({})
const topics = ref([])

let timer
onMounted(async () => {
  try {
    Object.assign(cfg.value, await props.host.getConfig() || {})
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  }
  await Promise.all([loadStatus(), loadTopics()])
  timer = setInterval(loadStatus, 10000)
})
onUnmounted(() => clearInterval(timer))

async function save() {
  saving.value = true
  try {
    await props.host.saveConfig({ ...cfg.value })
    props.host.toast.success('配置已保存')
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function loadStatus() {
  try {
    const r = await props.host.callApi('/status')
    status.value = r
  } catch (e) { props.host.toast.error('读取状态失败：' + (e.message || e)) }
}

async function loadTopics() {
  try {
    const r = await props.host.callApi('/topics')
    topics.value = r.topics || []
  } catch (e) { props.host.toast.error('读取话题失败：' + (e.message || e)) }
}

async function toggleBan(topic) {
  const banned = topic.status !== '已封禁'
  try {
    const result = await props.host.callApi('/ban', { method: 'POST', body: { user_id: topic.user_id, banned } })
    if (!result?.ok) throw new Error(result?.message || '后端未确认操作成功')
    topic.status = banned ? '已封禁' : '正常'
    await loadStatus()
    props.host.toast.success(banned ? '已拉黑用户' : '已解除黑名单')
  } catch (e) { props.host.toast.error('操作失败：' + (e.message || e)) }
}
</script>

<style scoped>
.awrelay-config { display: flex; flex-direction: column; gap: 16px; }
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
.inp, textarea.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
textarea.inp { resize: vertical; font-family: inherit; }
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
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); color: var(--text-secondary, #b9c0cc); font-size: 12px; font-weight: normal; }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); font-size: 13px; color: var(--text-primary, #e8edf5); }
.tbl td.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl td.empty { text-align: center; color: var(--text-muted, #7a8291); padding: 40px; }
.status-正常 { color: #4ade80; }
.status-已封禁 { color: #ff4a4a; }
</style>
