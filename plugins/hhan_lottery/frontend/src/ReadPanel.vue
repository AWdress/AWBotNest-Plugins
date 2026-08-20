<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const cfg = reactive({ enabled: true, notify_result: true, page_delay: 1, max_pages: 200 })
const status = ref({
  running: false, phase: 'idle', message: '正在读取状态…', current_page: 0,
  total_pages: 0, processed: 0, started_at: '', finished_at: '', stop_requested: false,
})
const history = ref([])
const loading = ref(true)
const saving = ref(false)
const starting = ref(false)
const deleting = ref(false)
const stopping = ref(false)
const checking = ref(false)
const clearing = ref(false)
let timer = null

const phaseLabel = computed(() => ({
  idle: '待运行', checking: '检查登录', searching: '查找未读', processing: '处理中',
  completed: '已完成', stopped: '已停止', failed: '运行失败',
}[status.value.phase] || '待运行'))

const progress = computed(() => {
  const total = Number(status.value.total_pages || 0)
  const current = Number(status.value.current_page || 0)
  if (!total) return 0
  return Math.max(0, Math.min(100, Math.round(current / total * 100)))
})

const statusTone = computed(() => {
  if (status.value.running) return 'active'
  if (status.value.phase === 'failed') return 'danger'
  if (status.value.phase === 'completed') return 'success'
  return 'neutral'
})

function iconPath(name) {
  const paths = {
    inbox: '<path d="M4 5.5h16v13H4z"/><path d="M4 14h4l2 2h4l2-2h4"/>',
    play: '<path d="m8 5 11 7-11 7z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
    shield: '<path d="M12 3 5.5 5.8v5.1c0 4.3 2.8 7.8 6.5 9.1 3.7-1.3 6.5-4.8 6.5-9.1V5.8z"/><path d="m9 12 2 2 4-4"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.3-2.4L20 9M4 15l2.6 2.4A7 7 0 0 0 17.9 15"/>',
  }
  return paths[name] || ''
}

async function loadStatus() {
  try { status.value = await props.host.callApi('/read/status') }
  catch (error) { /* 轮询失败不打断用户 */ }
}

async function loadHistory() {
  try { history.value = (await props.host.callApi('/read/history')).items || [] }
  catch (error) { props.host.toast.error('读取运行记录失败：' + (error.message || error)) }
}

async function save() {
  saving.value = true
  try {
    cfg.page_delay = Math.max(0.2, Math.min(Number(cfg.page_delay) || 1, 10))
    cfg.max_pages = Math.max(1, Math.min(Number(cfg.max_pages) || 200, 1000))
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('配置已保存')
  } catch (error) {
    props.host.toast.error('保存失败：' + (error.message || error))
  } finally { saving.value = false }
}

async function run() {
  starting.value = true
  try {
    await props.host.saveConfig({ ...cfg })
    const result = await props.host.callApi('/read/run', { method: 'POST', body: {} })
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message)
    await loadStatus()
  } catch (error) {
    props.host.toast.error('启动失败：' + (error.message || error))
  } finally { starting.value = false }
}

async function runDelete() {
  if (!confirm('确定删除 HHanClub 收件箱中的全部消息吗？\n\n已读和未读消息都会被永久删除，此操作无法撤销。')) return
  deleting.value = true
  try {
    await props.host.saveConfig({ ...cfg })
    const result = await props.host.callApi('/read/delete', { method: 'POST', body: {} })
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message)
    await loadStatus()
  } catch (error) {
    props.host.toast.error('启动删除失败：' + (error.message || error))
  } finally { deleting.value = false }
}

async function stop() {
  stopping.value = true
  try {
    const result = await props.host.callApi('/read/stop', { method: 'POST', body: {} })
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message)
    await loadStatus()
  } catch (error) {
    props.host.toast.error('停止失败：' + (error.message || error))
  } finally { stopping.value = false }
}

async function checkCookie() {
  checking.value = true
  try {
    const result = await props.host.callApi('/read/cookie/check')
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message)
  } catch (error) {
    props.host.toast.error('检查失败：' + (error.message || error))
  } finally { checking.value = false }
}

async function clearHistory() {
  if (!confirm('清空最近运行记录？')) return
  clearing.value = true
  try {
    const result = await props.host.callApi('/read/history/clear', { method: 'POST', body: {} })
    history.value = []
    props.host.toast.success(result.message)
  } catch (error) {
    props.host.toast.error('清空失败：' + (error.message || error))
  } finally { clearing.value = false }
}

function historyStatus(item) {
  return ({ completed: '完成', stopped: '停止', failed: '失败' }[item.status] || item.status)
}

function operationLabel(item) { return item.operation === 'delete' ? '删除' : '已读' }

onMounted(async () => {
  try {
    Object.assign(cfg, await props.host.getConfig() || {})
    await Promise.all([loadStatus(), loadHistory()])
  } catch (error) {
    props.host.toast.error('读取插件数据失败：' + (error.message || error))
  } finally { loading.value = false }
  timer = window.setInterval(async () => {
    const wasRunning = status.value.running
    await loadStatus()
    if (wasRunning && !status.value.running) await loadHistory()
  }, 1500)
})

onBeforeUnmount(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="read-panel">
    <div v-if="loading" class="skeleton" aria-label="正在加载">
      <span></span><span></span><span></span>
    </div>

    <template v-else>
      <header class="header">
        <div class="title-wrap">
          <svg class="title-icon" viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('inbox')"></svg>
          <div>
            <h2>消息管理</h2>
            <p>可以将未读消息批量设为已读，或删除收件箱全部消息。</p>
          </div>
        </div>
        <span class="state" :class="statusTone"><i></i>{{ phaseLabel }}</span>
      </header>

      <section class="run-area" aria-labelledby="run-heading">
        <div class="run-copy">
          <span id="run-heading" class="section-label">当前任务</span>
          <strong>{{ status.message }}</strong>
          <span class="meta">
            <template v-if="status.total_pages">第 {{ status.current_page }}/{{ status.total_pages }} 页 · </template>
            已处理 {{ status.processed }} 条
          </span>
        </div>
        <div class="actions">
          <button v-if="!status.running" class="button primary" :disabled="starting || !cfg.enabled" @click="run">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('play')"></svg>
            {{ starting ? '启动中…' : '开始全部已读' }}
          </button>
          <button v-if="!status.running" class="button danger" :disabled="deleting || !cfg.enabled" @click="runDelete">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('trash')"></svg>
            {{ deleting ? '启动中…' : '删除全部消息' }}
          </button>
          <button v-else class="button danger" :disabled="stopping || status.stop_requested" @click="stop">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('stop')"></svg>
            {{ status.stop_requested ? '等待停止…' : stopping ? '提交中…' : '停止任务' }}
          </button>
          <button class="button" :disabled="checking || status.running" @click="checkCookie">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('shield')"></svg>
            {{ checking ? '检查中…' : '检查 Cookie' }}
          </button>
        </div>
        <div class="progress" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
          <span :style="{ transform: `scaleX(${progress / 100})` }"></span>
        </div>
      </section>

      <div class="content-grid">
        <section class="settings" aria-labelledby="settings-heading">
          <div class="section-head">
            <div><h3 id="settings-heading">运行设置</h3><p>开始任务时会先自动保存这些设置。</p></div>
            <button class="button compact" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
          </div>
          <label class="toggle-row">
            <span><b>启用插件</b><small>关闭后不能启动新任务</small></span>
            <input v-model="cfg.enabled" type="checkbox" role="switch" />
          </label>
          <label class="toggle-row">
            <span><b>完成后推送结果</b><small>通过平台通知渠道发送处理汇总</small></span>
            <input v-model="cfg.notify_result" type="checkbox" role="switch" />
          </label>
          <div class="field-grid">
            <label><span>翻页间隔</span><div class="input-unit"><input v-model.number="cfg.page_delay" type="number" min="0.2" max="10" step="0.1" /><em>秒</em></div></label>
            <label><span>最多扫描</span><div class="input-unit"><input v-model.number="cfg.max_pages" type="number" min="1" max="1000" /><em>页</em></div></label>
          </div>
          <p class="notice"><b>全部已读</b>只处理带 <code>icon-unread.svg</code> 标记的消息；<b>删除全部消息</b>会清空当前收件箱中的已读和未读消息，且无法撤销。</p>
        </section>

        <section class="history-area" aria-labelledby="history-heading">
          <div class="section-head">
            <div><h3 id="history-heading">最近运行</h3><p>保留最近 20 次处理结果。</p></div>
            <div class="head-actions">
              <button class="icon-button" title="刷新记录" aria-label="刷新记录" @click="loadHistory">
                <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('refresh')"></svg>
              </button>
              <button class="icon-button danger-text" title="清空记录" aria-label="清空记录" :disabled="clearing || !history.length" @click="clearHistory">
                <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('trash')"></svg>
              </button>
            </div>
          </div>
          <div v-if="!history.length" class="empty">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('inbox')"></svg>
            <b>还没有运行记录</b><span>首次执行后，处理数量和结果会显示在这里。</span>
          </div>
          <div v-else class="history-list">
            <article v-for="(item, index) in history" :key="item.time + index" class="history-item">
              <span class="history-status" :class="item.status">{{ historyStatus(item) }}</span>
              <div><b>{{ operationLabel(item) }} · {{ item.processed }} 条消息</b><span>{{ item.detail }}</span></div>
              <div class="history-meta"><time>{{ item.time }}</time><span>{{ item.pages }} 页</span></div>
            </article>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.read-panel {
  --surface: var(--bg-elevated, #151e2c); --surface-low: var(--bg-card, #0f1825);
  --border: var(--border-light, #29384b); --text: var(--text-primary, #edf3fb);
  --muted: var(--text-secondary, #a9b6c8); --quiet: var(--text-muted, #7f8da1);
  --accent: var(--accent, #4c9aff); --accent-low: var(--accent-dim, #17345a);
  display: flex; flex-direction: column; gap: 18px; color: var(--text); container-type: inline-size;
}
.read-panel * { box-sizing: border-box; }
.header, .title-wrap, .actions, .section-head, .head-actions, .history-meta { display: flex; align-items: center; }
.header { justify-content: space-between; gap: 20px; }
.title-wrap { gap: 12px; min-width: 0; }
.title-icon { width: 28px; height: 28px; flex: 0 0 auto; color: var(--accent); fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
h2, h3, p { margin: 0; }
h2 { font-size: 18px; line-height: 1.25; font-weight: 680; letter-spacing: -0.01em; }
h3 { font-size: 14px; line-height: 1.35; font-weight: 650; }
.title-wrap p, .section-head p { margin-top: 4px; font-size: 12px; color: var(--quiet); line-height: 1.5; }
.state { display: inline-flex; align-items: center; gap: 7px; flex: 0 0 auto; padding: 6px 10px; border-radius: 999px; font-size: 12px; color: var(--muted); background: var(--surface-low); border: 1px solid var(--border); }
.state i { width: 7px; height: 7px; border-radius: 50%; background: var(--quiet); }
.state.active i { background: var(--accent); animation: pulse 1.4s ease-in-out infinite; }
.state.success i { background: #43c98b; }.state.danger i { background: #ef6a70; }
@keyframes pulse { 50% { opacity: .42; transform: scale(.72); } }
.run-area { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 14px 18px; padding: 18px; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; }
.run-copy { display: flex; flex-direction: column; min-width: 0; gap: 5px; }
.section-label { color: var(--accent); font-size: 11px; font-weight: 650; }
.run-copy strong { font-size: 15px; line-height: 1.45; overflow-wrap: anywhere; }
.meta { color: var(--quiet); font-size: 12px; font-variant-numeric: tabular-nums; }
.actions { align-self: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.button, .icon-button { border: 1px solid var(--border); background: var(--surface-low); color: var(--muted); cursor: pointer; transition: border-color .18s ease, color .18s ease, background .18s ease; }
.button { min-height: 38px; padding: 8px 13px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; font-size: 13px; }
.button svg, .icon-button svg, .empty svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.button:hover:not(:disabled), .icon-button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.button:focus-visible, .icon-button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.button.primary { color: #f7fbff; border-color: var(--accent); background: var(--accent); }
.button.primary:hover:not(:disabled) { color: #fff; background: #378bec; }
.button.danger { color: #ffecef; border-color: #b94d58; background: #8e3440; }
.button.compact { min-height: 32px; padding: 5px 11px; }
.button:disabled, .icon-button:disabled { opacity: .48; cursor: not-allowed; }
.progress { grid-column: 1 / -1; height: 4px; overflow: hidden; background: var(--surface-low); border-radius: 999px; }
.progress span { display: block; width: 100%; height: 100%; transform-origin: left center; background: var(--accent); border-radius: inherit; transition: transform .22s ease-out; }
.content-grid { display: grid; grid-template-columns: minmax(250px, .82fr) minmax(320px, 1.18fr); gap: 18px; align-items: start; }
.settings, .history-area { min-width: 0; }
.section-head { justify-content: space-between; gap: 12px; padding-bottom: 11px; border-bottom: 1px solid var(--border); }
.head-actions { gap: 6px; }
.toggle-row { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--border); cursor: pointer; }
.toggle-row span { display: flex; flex-direction: column; gap: 3px; }
.toggle-row b, .field-grid label > span { font-size: 13px; font-weight: 580; }
.toggle-row small { font-size: 11px; color: var(--quiet); }
.toggle-row input { width: 38px; height: 21px; flex: 0 0 auto; accent-color: var(--accent); cursor: pointer; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding-top: 14px; }
.field-grid label { display: flex; flex-direction: column; gap: 7px; }
.input-unit { display: flex; align-items: center; border: 1px solid var(--border); border-radius: 9px; background: var(--surface-low); }
.input-unit:focus-within { border-color: var(--accent); }
.input-unit input { width: 100%; min-width: 0; padding: 9px 10px; border: 0; outline: 0; background: transparent; color: var(--text); font-size: 13px; font-variant-numeric: tabular-nums; }
.input-unit em { padding-right: 10px; color: var(--quiet); font-size: 12px; font-style: normal; }
.notice { margin-top: 14px; color: var(--quiet); font-size: 11px; line-height: 1.65; }
.notice code { color: var(--muted); }
.icon-button { width: 34px; height: 34px; padding: 0; border-radius: 9px; display: grid; place-items: center; }
.danger-text:hover:not(:disabled) { border-color: #ef6a70; color: #ef6a70; }
.history-list { display: flex; flex-direction: column; }
.history-item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 11px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.history-item > div:nth-child(2) { display: flex; flex-direction: column; min-width: 0; gap: 3px; }
.history-item b { font-size: 13px; }.history-item div > span { overflow: hidden; color: var(--quiet); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.history-status { min-width: 36px; font-size: 11px; color: var(--muted); }.history-status.completed { color: #43c98b; }.history-status.failed { color: #ef6a70; }.history-status.stopped { color: #e6ad55; }
.history-meta { flex-direction: column; align-items: flex-end; gap: 3px; color: var(--quiet); font-size: 11px; font-variant-numeric: tabular-nums; }
.empty { min-height: 210px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; text-align: center; color: var(--quiet); }
.empty svg { width: 24px; height: 24px; }.empty b { color: var(--muted); font-size: 13px; }.empty span { max-width: 34ch; font-size: 11px; line-height: 1.55; }
.skeleton { display: grid; gap: 14px; }.skeleton span { display: block; height: 72px; border-radius: 12px; background: var(--surface); opacity: .7; animation: shimmer 1.2s ease-in-out infinite alternate; }.skeleton span:nth-child(2) { height: 118px; }.skeleton span:nth-child(3) { height: 220px; }
@keyframes shimmer { to { opacity: .38; } }
::selection { background: var(--accent); color: #fff; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; } }
@container (max-width: 680px) { .content-grid { grid-template-columns: 1fr; }.run-area { grid-template-columns: 1fr; }.actions { justify-content: flex-start; }.progress { grid-column: 1; } }
@container (max-width: 420px) { .header { align-items: flex-start; }.title-wrap p { display: none; }.field-grid { grid-template-columns: 1fr; }.history-item { grid-template-columns: auto minmax(0, 1fr); }.history-meta { grid-column: 2; flex-direction: row; justify-content: flex-start; }.actions .button { flex: 1 1 auto; } }
</style>
