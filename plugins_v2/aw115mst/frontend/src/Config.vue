<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import SwitchField from './SwitchField.vue'

const props = defineProps({pluginId: {type: String, required: true}, host: {type: Object, required: true}})
const MASK = '********'
const DEFAULTS = Object.freeze({
  cookie: '', target_pid: '0', qr_app: 'qandroid',
  input_dir: '待检测', rapid_dir: '可秒传', non_rapid_dir: '待秒传',
  use_copy: true, keep_structure: true, check_only: false,
  delete_after_rapid: false, delete_source_after_rapid: false,
  upload_enabled: false, delete_after_upload: false,
  include_extensions: '', exclude_extensions: '.txt,.log,.tmp,.part,.crdownload,.!qb,.!ut,.download,.aria2,.mp',
  min_size_mb: 0, max_size_gb: 100, hash_chunk_mb: 1, stable_seconds: 5,
  watch_enabled: false, watch_interval_seconds: 5,
  schedule_enabled: false, interval_minutes: 30,
  recheck_enabled: false, max_recheck_times: 10,
  notify: false, request_timeout: 30, telegram_control: false, telegram_admin_ids: '',
})
const TABS = [{key: 'account', label: '账号'}, {key: 'files', label: '文件规则'}, {key: 'tasks', label: '自动任务'}, {key: 'records', label: '运行记录'}]
const STATES = {rapid: '已秒传', pending: '待重检', non_rapid: '待秒传', local_pending: '待完成本地整理', failed: '处理失败', upload_failed: '上传失败', uploaded: '已上传', processed: '已处理', checking: '检测中', moved: '已整理', skipped: '已跳过', done: '已完成', dispatched: '已暂存，待重检', dispatch_pending: '待暂存整理', uploading: '真实上传中', cloud_unknown: '网盘结果待核对', missing: '本地文件缺失'}
const form = reactive({...DEFAULTS})
const activeTab = ref('account')
const loading = ref(true)
const saving = ref(false)
const busy = ref('')
const loadError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const statusError = ref('')
const savedSnapshot = ref('')
const status = ref(null)
const refreshing = ref(false)
const cookieVisible = ref(false)
const cookieReveal = ref('')
const revealing = ref(false)
const loginResult = ref('')
const actionAlert = ref(null)
const qr = reactive({session: '', image: '', state: '', message: '', expiresAt: 0})
const clearConfirmation = ref(false)
let pollTimer = null
let alive = true
let qrPolling = false

const snapshot = () => JSON.stringify(form)
const dirty = computed(() => !loading.value && snapshot() !== savedSnapshot.value)
const locked = computed(() => saving.value || !!busy.value || loading.value || !!loadError.value)
const hasCookie = computed(() => !!String(form.cookie || '').trim())
const cookieDisplay = computed(() => cookieVisible.value && form.cookie === MASK ? cookieReveal.value : form.cookie)
const items = computed(() => Array.isArray(status.value?.items) ? status.value.items : Array.isArray(status.value?.records) ? status.value.records : [])
const qrActive = computed(() => !!qr.session && ['waiting', 'scanned'].includes(qr.state))
const runProgress = computed(() => {
  const value = status.value?.progress
  if (typeof value === 'number') return Math.max(0, Math.min(100, value))
  const current = Number(value?.done ?? value?.current ?? 0)
  const total = Number(value?.total ?? 0)
  return total > 0 ? Math.max(0, Math.min(100, current * 100 / total)) : null
})

function notify(type, message) { props.host.toast?.[type]?.(message) }
function errorMessage(error) { return error?.message || String(error) }
function tabEnabled(key) {
  if (key === 'account') return Boolean(loginResult.value) || qr.state === 'confirmed'
  if (key === 'files') return form.upload_enabled
  if (key === 'tasks') return form.watch_enabled || form.schedule_enabled || form.telegram_control
  return Boolean(status.value?.running)
}

async function focusActionError() {
  await nextTick()
  if (!alive || !actionAlert.value) return
  actionAlert.value.focus({preventScroll: true})
  actionAlert.value.scrollIntoView({block: 'center', behavior: 'auto'})
}

function validate() {
  for (const [field, label] of [['input_dir', '待检测目录'], ['rapid_dir', '可秒传目录'], ['non_rapid_dir', '待秒传目录']]) {
    if (!String(form[field] || '').trim()) return {message: `${label}不能为空`, tab: 'files'}
  }
  if (new Set([form.input_dir, form.rapid_dir, form.non_rapid_dir].map((value) => value.trim().replace(/[\\/]+$/, '').toLowerCase())).size !== 3) {
    return {message: '三个文件目录必须分别设置，不能使用同一目录', tab: 'files'}
  }
  if (!/^\d+$/.test(String(form.target_pid).trim())) return {message: '115 目标目录 ID 必须是非负整数，根目录填 0', tab: 'account'}
  const ranges = {
    min_size_mb: [0, 102400, '最小文件大小', 'files'], max_size_gb: [0, 102400, '最大文件大小', 'files'],
    hash_chunk_mb: [1, 16, '哈希读取分块', 'files'], stable_seconds: [0, 3600, '文件稳定等待', 'files'],
    watch_interval_seconds: [5, 3600, '目录检查间隔', 'tasks'], interval_minutes: [1, 10080, '定时处理间隔', 'tasks'],
    max_recheck_times: [0, 10000, '最大重检次数', 'tasks'], request_timeout: [5, 300, '请求超时', 'account'],
  }
  for (const [field, [min, max, label, tab]] of Object.entries(ranges)) {
    const value = form[field]
    if (value === '' || value === null || !Number.isFinite(Number(value)) || Number(value) < min || Number(value) > max) {
      return {message: `${label}必须在 ${min} 到 ${max} 之间`, tab}
    }
    if (!Number.isInteger(Number(value))) return {message: `${label}必须是整数`, tab}
  }
  if (form.check_only && (form.delete_after_rapid || form.delete_source_after_rapid || form.delete_after_upload)) return {message: '仅检测模式不能同时开启本地删除，请关闭三个删除开关后再保存', tab: 'files'}
  if (Number(form.max_size_gb) > 0 && Number(form.min_size_mb) > Number(form.max_size_gb) * 1024) return {message: '最小文件大小不能大于最大文件大小', tab: 'files'}
  if (form.telegram_control && !/^\s*\d+(?:[\s,，]+\d+)*\s*$/.test(form.telegram_admin_ids)) return {message: '请填写允许控制的 Telegram 用户 ID，多个 ID 用逗号或换行分隔', tab: 'tasks'}
  return null
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const saved = await props.host.getConfig()
    if (!alive) return
    Object.assign(form, DEFAULTS)
    for (const key of Object.keys(DEFAULTS)) if (saved && Object.hasOwn(saved, key) && saved[key] !== null && saved[key] !== undefined) form[key] = saved[key]
    savedSnapshot.value = snapshot()
  } catch (error) {
    if (alive) loadError.value = `读取配置失败：${errorMessage(error)}。请重新读取后再保存。`
  } finally {
    if (alive) loading.value = false
  }
}

async function save({quiet = false} = {}) {
  if (loadError.value || loading.value) return false
  const problem = validate()
  if (problem) {
    actionError.value = problem.message
    activeTab.value = problem.tab
    await focusActionError()
    return false
  }
  saving.value = true
  actionError.value = ''
  try {
    const payload = JSON.parse(JSON.stringify(form))
    for (const key of Object.keys(DEFAULTS)) {
      if (typeof DEFAULTS[key] === 'number') payload[key] = Number(payload[key])
      if (typeof DEFAULTS[key] === 'boolean') payload[key] = Boolean(payload[key])
    }
    for (const key of ['input_dir', 'rapid_dir', 'non_rapid_dir', 'target_pid']) payload[key] = String(payload[key]).trim()
    const result = await props.host.saveConfig(payload)
    if (result?.ok === false) throw new Error(result.message || '平台未能保存配置')
    if (!alive) return false
    Object.assign(form, payload)
    savedSnapshot.value = snapshot()
    if (!quiet) {
      actionMessage.value = '配置已保存并应用'
      notify('success', actionMessage.value)
    }
    return true
  } catch (error) {
    if (alive) {
      actionError.value = `保存失败：${errorMessage(error)}`
      await focusActionError()
    }
    return false
  } finally {
    if (alive) saving.value = false
  }
}

async function refreshStatus() {
  if (refreshing.value || !alive) return
  refreshing.value = true
  try {
    const result = await props.host.callApi('/status')
    if (result?.ok === false) throw new Error(result.message || '状态暂不可用')
    if (alive) { status.value = result || null; statusError.value = '' }
  } catch (error) {
    if (alive) statusError.value = `读取运行状态失败：${errorMessage(error)}`
  } finally {
    if (alive) { refreshing.value = false; schedulePoll() }
  }
}

async function postAction(name, path, body = {}) {
  if (busy.value || saving.value || loading.value) return null
  busy.value = name
  actionError.value = ''
  actionMessage.value = ''
  try {
    // Saving may reload the plugin. Stop must address the existing worker;
    // clean action requests must not recreate it or invalidate a QR session.
    if (path !== '/stop' && dirty.value && !await save({quiet: true})) return null
    const result = await props.host.callApi(path, {method: 'POST', body})
    if (result?.ok === false) throw new Error(result.message || '操作未成功')
    if (!alive) return null
    actionMessage.value = result?.message || '操作已完成'
    await refreshStatus()
    return result
  } catch (error) {
    if (alive) actionError.value = errorMessage(error)
    return null
  } finally {
    if (alive) busy.value = ''
  }
}

async function revealCookie() {
  if (cookieVisible.value) { cookieVisible.value = false; cookieReveal.value = ''; return }
  revealing.value = true
  try {
    if (form.cookie === MASK) cookieReveal.value = await props.host.revealSecret('cookie') || ''
    if (alive) cookieVisible.value = true
  } catch (error) {
    if (alive) actionError.value = `无法显示 Cookie：${errorMessage(error)}`
  } finally { if (alive) revealing.value = false }
}

async function testLogin() {
  const result = await postAction('login', '/login_test')
  if (result) loginResult.value = result.user_name ? `已连接账号：${result.user_name}` : result.message || '115 登录有效'
}

async function startQr() {
  const result = await postAction('qr', '/qr/start', {app: form.qr_app})
  if (!result) return
  if (!result.session || !result.image) { actionError.value = '未取得二维码，请重试生成'; return }
  Object.assign(qr, {session: result.session, image: result.image, state: 'waiting', message: '使用 115 客户端扫描二维码', expiresAt: Date.now() + Number(result.expires_in || 300) * 1000})
  schedulePoll()
}

async function pollQr() {
  if (!qrActive.value || activeTab.value !== 'account' || busy.value || qrPolling) return
  if (Date.now() >= qr.expiresAt) { qr.state = 'expired'; qr.message = '二维码已过期，请重新生成'; return }
  const session = qr.session
  qrPolling = true
  try {
    const result = await props.host.callApi('/qr/poll', {method: 'POST', body: {session}})
    if (result?.ok === false) throw new Error(result.message || '扫码状态检查失败')
    if (!result || !alive || session !== qr.session) return
    qr.state = result.status || 'waiting'
    qr.message = result.message || ({waiting: '等待扫码', scanned: '已扫码，请在手机上确认', confirmed: '登录已确认', expired: '二维码已过期，请重新生成'}[qr.state] || '等待登录确认')
    if (qr.state === 'confirmed') {
      // Preserve unsaved edits to other fields when the server updates its cookie.
      const wasDirty = dirty.value
      const previousSaved = JSON.parse(savedSnapshot.value || '{}')
      const saved = await props.host.getConfig()
      if (!alive) return
      form.cookie = saved?.cookie || MASK
      cookieVisible.value = false
      cookieReveal.value = ''
      previousSaved.cookie = form.cookie
      savedSnapshot.value = wasDirty ? JSON.stringify(previousSaved) : snapshot()
      loginResult.value = '扫码登录成功，Cookie 已由平台保存'
      await refreshStatus()
    }
  } catch (error) {
    if (alive) qr.message = `检查扫码状态失败：${errorMessage(error)}。稍后自动重试。`
  } finally {
    qrPolling = false
  }
}

function schedulePoll() {
  clearTimeout(pollTimer)
  pollTimer = null
  if (!alive || !(status.value?.running || (activeTab.value === 'account' && qrActive.value))) return
  pollTimer = setTimeout(async () => {
    try {
      if (status.value?.running) await refreshStatus()
      if (activeTab.value === 'account' && qrActive.value) await pollQr()
    } catch (error) {
      if (alive) actionError.value = errorMessage(error)
    } finally { schedulePoll() }
  }, 5000)
}

async function run(mode) {
  const result = await postAction(`run-${mode}`, '/run', {mode})
  if (result) { activeTab.value = 'records'; schedulePoll() }
}
async function clearRecords() {
  const result = await postAction('clear', '/clear_records', {confirm: true})
  if (result) clearConfirmation.value = false
}
function formatBytes(value) {
  const bytes = Number(value)
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const unit = Math.min(4, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / 1024 ** unit).toFixed(1)} ${['B', 'KB', 'MB', 'GB', 'TB'][unit]}`
}
function formatTime(value) {
  if (!value) return '—'
  const date = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', {hour12: false})
}
function stateLabel(value) { return STATES[value] || value || '待处理' }
function attentionState(value) { return String(value).includes('fail') || ['cloud_unknown', 'missing'].includes(value) }
function count(key) {
  if (!status.value) return '—'
  const counts = status.value.counts || {}
  if (Object.hasOwn(counts, 'total')) return counts[key] ?? 0
  if (key === 'total') return Object.values(counts).reduce((total, value) => total + (Number(value) || 0), 0)
  if (key === 'pending') return Number(counts.pending || 0) + Number(counts.non_rapid || 0) + Number(counts.local_pending || 0) + Number(counts.dispatched || 0) + Number(counts.dispatch_pending || 0)
  if (key === 'failed') return Number(counts.failed || 0) + Number(counts.upload_failed || 0) + Number(counts.cloud_unknown || 0) + Number(counts.missing || 0)
  if (key === 'rapid') return Number(counts.rapid || 0) + Number(counts.done || 0) + Number(counts.uploaded || 0)
  return 0
}
function tabKeyboard(event, index) {
  const direction = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
  if (!direction && !['Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1 : (index + direction + TABS.length) % TABS.length
  activeTab.value = TABS[next].key
  nextTick(() => document.getElementById(`mst-tab-${activeTab.value}`)?.focus())
}

watch([activeTab, () => status.value?.running, () => qr.state], schedulePoll)
onMounted(async () => { await load(); if (alive && !loadError.value) await refreshStatus() })
onBeforeUnmount(() => { alive = false; clearTimeout(pollTimer); cookieReveal.value = '' })
</script>

<template>
  <main class="mst-shell">
    <header class="page-head">
      <div><h2>AW115MST</h2><p>115 秒传检测与文件整理</p></div>
      <span class="save-state" :class="{changed: dirty}">{{ saving ? '正在保存' : dirty ? '有未保存修改' : loading ? '正在读取' : loadError ? '读取失败' : '配置已同步' }}</span>
    </header>
    <div v-if="loadError" class="alert error" role="alert"><p>{{ loadError }}</p><button class="secondary" type="button" @click="load">重新读取</button></div>
    <p v-if="actionError" ref="actionAlert" class="alert error" role="alert" tabindex="-1">{{ actionError }}</p>
    <p v-else-if="actionMessage" class="alert success" role="status">{{ actionMessage }}</p>
    <p v-if="loading" class="loading" role="status">正在读取配置…</p>

    <div v-else class="workspace">
      <nav class="section-nav" role="tablist" aria-label="AW115MST 配置分组">
        <button v-for="(item, index) in TABS" :id="`mst-tab-${item.key}`" :key="item.key" type="button" role="tab" :aria-selected="activeTab === item.key" :aria-controls="`mst-panel-${item.key}`" :tabindex="activeTab === item.key ? 0 : -1" :class="{active: activeTab === item.key}" @click="activeTab = item.key" @keydown="tabKeyboard($event, index)">
          <span>{{ item.label }}</span><i :class="{on: tabEnabled(item.key)}" aria-hidden="true"></i>
        </button>
      </nav>

      <section :id="`mst-panel-${activeTab}`" class="panel" role="tabpanel" :aria-labelledby="`mst-tab-${activeTab}`">
        <fieldset class="fields" :disabled="locked">
          <template v-if="activeTab === 'account'">
            <div class="panel-head"><h3>115 账号</h3><p>使用 Cookie 或扫码连接账号，服务可独立运行。</p></div>
            <div class="subsection">
              <div class="form-grid">
                <label class="wide"><span>115 Cookie</span><div class="secret-field"><input :value="cookieDisplay" :type="cookieVisible ? 'text' : 'password'" autocomplete="off" spellcheck="false" placeholder="留空使用平台 115 Cookie，或在下方扫码登录" @input="form.cookie = $event.target.value"><button type="button" :aria-label="cookieVisible ? '隐藏 Cookie' : '显示 Cookie'" :aria-pressed="cookieVisible" :disabled="revealing || !hasCookie" @click="revealCookie"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12C4.5 7.5 8 5 12 5s7.5 2.5 10 7c-2.5 4.5-6 7-10 7S4.5 16.5 2 12Z"/><circle cx="12" cy="12" r="3"/><path v-if="!cookieVisible" d="m4 3 16 18"/></svg></button></div><small>留空读取平台保存的 115 Cookie；填写后优先使用本插件配置。默认隐藏，点击眼睛可查看。</small></label>
                <label><span>115 目标目录 ID</span><input v-model.trim="form.target_pid" inputmode="numeric"><small>根目录填 0；子目录可从 115 目录链接中查看 ID。</small></label>
                <label><span>请求超时（秒）</span><input v-model.number="form.request_timeout" type="number" min="5" max="300" step="1"></label>
              </div>
              <div class="action-row"><button class="secondary" type="button" :disabled="!!busy" @click="testLogin">{{ busy === 'login' ? '正在检测…' : '检测登录' }}</button><p v-if="loginResult" class="login-result" role="status">{{ loginResult }}</p></div>
            </div>
            <div class="subsection">
              <div class="section-head"><div><h4>扫码登录</h4><p>使用 115 客户端扫描，并在手机上确认登录。</p></div></div>
              <div class="form-grid qr-controls"><label><span>登录客户端</span><select v-model="form.qr_app"><option value="qandroid">115 管理 Android</option><option value="ios">115 生活 iOS</option><option value="web">115 网页端</option></select></label><button class="secondary" type="button" :disabled="!!busy" @click="startQr">{{ busy === 'qr' ? '正在生成…' : qr.session ? '重新生成二维码' : '生成登录二维码' }}</button></div>
              <div v-if="qr.image" class="qr-area"><img :src="qr.image" alt="115 登录二维码" width="192" height="192"><div><b>{{ qr.state === 'confirmed' ? '登录成功' : qr.state === 'scanned' ? '等待手机确认' : qr.state === 'expired' ? '二维码已过期' : '等待扫码' }}</b><p role="status">{{ qr.message }}</p><small>停留在账号页时每 5 秒检查一次扫码状态。</small></div></div>
            </div>
          </template>

          <template v-else-if="activeTab === 'files'">
            <div class="panel-head"><h3>文件规则</h3><p>目录指向服务运行环境；三个目录需独立设置。</p></div>
            <div class="subsection"><div class="form-grid"><label class="wide"><span>待检测目录</span><input v-model.trim="form.input_dir"></label><label><span>可秒传目录</span><input v-model.trim="form.rapid_dir"></label><label><span>待秒传目录</span><input v-model.trim="form.non_rapid_dir"></label></div><p v-if="status?.roots" class="hint root-note">实际目录：{{ typeof status.roots === 'string' ? status.roots : Object.values(status.roots).join(' · ') }}</p></div>
            <div class="subsection switch-list"><SwitchField v-model="form.use_copy" title="复制整理" hint="启用时保留待检测原件；关闭后按移动方式整理。"/><SwitchField v-model="form.keep_structure" title="保留子目录结构" hint="本地整理和 115 目标目录保留相对目录层级。"/><SwitchField v-model="form.check_only" title="仅检测，不整理本地文件" hint="秒传命中会入 115 网盘；仅检测只不改本地文件。"/></div>
            <div class="subsection">
              <div class="section-head"><h4>筛选与文件稳定</h4></div>
              <div class="form-grid">
                <label class="wide"><span>仅包含扩展名</span><input v-model.trim="form.include_extensions" placeholder="留空表示不限；多个扩展名用逗号分隔"><small>例如 .mkv,.mp4；匹配不区分大小写。</small></label>
                <label class="wide"><span>排除扩展名</span><input v-model.trim="form.exclude_extensions"><small>避免处理日志、临时文件和未完成的下载。</small></label>
                <label><span>最小文件大小（MB）</span><input v-model.number="form.min_size_mb" type="number" min="0" max="102400" step="1"></label>
                <label><span>最大文件大小（GB）</span><input v-model.number="form.max_size_gb" type="number" min="0" max="102400" step="1"><small>0 表示不限大小。</small></label>
                <label><span>哈希读取分块（MB）</span><input v-model.number="form.hash_chunk_mb" type="number" min="1" max="16" step="1"></label>
                <label><span>文件稳定等待（秒）</span><input v-model.number="form.stable_seconds" type="number" min="0" max="3600" step="1"></label>
              </div>
            </div>
            <div class="subsection"><div class="section-head"><h4>成功后的本地处理</h4></div><div class="switch-list"><SwitchField v-model="form.delete_after_rapid" title="秒传确认后删除当前处理文件" hint="直接删除当前处理文件，不生成可秒传目录副本。"/><SwitchField v-model="form.delete_source_after_rapid" title="重检入库确认后删除关联输入源文件" hint="仅处理重检记录关联的输入源文件；内容已变化时保留。"/><SwitchField v-model="form.upload_enabled" title="重检达上限后真实上传" hint="秒传仍未命中时上传完整文件，会产生上传流量。"/><SwitchField v-model="form.delete_after_upload" title="真实上传确认后删除当前处理文件" hint="仅在真实上传已确认成功后执行。"/></div></div>
          </template>

          <template v-else-if="activeTab === 'tasks'">
            <div class="panel-head"><h3>自动任务</h3><p>每项任务独立控制，修改后保存即可应用。</p></div>
            <div class="subsection"><SwitchField v-model="form.watch_enabled" title="目录监控（定期检查新文件）" hint="按间隔扫描新文件，并等待文件稳定后处理。"/><div class="form-grid following"><label><span>目录检查间隔（秒）</span><input v-model.number="form.watch_interval_seconds" type="number" min="5" max="3600" step="1"></label></div></div>
            <div class="subsection"><SwitchField v-model="form.schedule_enabled" title="定时处理" hint="按设定间隔检测待检测目录，可同时处理待秒传重检。"/><div class="form-grid following"><label><span>处理间隔（分钟）</span><input v-model.number="form.interval_minutes" type="number" min="1" max="10080" step="1"></label></div></div>
            <div class="subsection"><SwitchField v-model="form.recheck_enabled" title="重检待秒传文件" hint="自动任务中检查已暂存的文件，确认是否能够秒传。"/><div class="form-grid following"><label><span>最大重检次数</span><input v-model.number="form.max_recheck_times" type="number" min="0" max="10000" step="1"><small>0 表示不限次数，不触发达上限真实上传。</small></label></div></div>
            <div class="subsection switch-list"><SwitchField v-model="form.notify" title="Telegram 结果通知" hint="通过平台已有账号发送，不需要新增 Bot Token。"/><SwitchField v-model="form.telegram_control" title="Telegram 命令控制" hint="只接受下方明确允许的用户发送控制命令。"/><div class="form-grid following"><label class="wide"><span>允许控制的 Telegram 用户 ID</span><textarea v-model.trim="form.telegram_admin_ids" rows="3" placeholder="多个用户 ID 用逗号或换行分隔"></textarea><small>开启命令控制时必填；只允许配置中的用户执行。</small></label></div></div>
          </template>

          <template v-else>
            <div class="panel-head records-heading"><div><h3>运行记录</h3><p>查看当前进度与文件处理结果。</p></div><button class="secondary" type="button" :disabled="refreshing" @click="refreshStatus">{{ refreshing ? '正在刷新…' : '刷新状态' }}</button></div>
            <div class="subsection"><p class="hint">秒传命中会入 115 网盘；仅检测只不改本地文件。启动前会保存当前修改，停止任务不会保存。</p><div class="action-row run-actions"><button class="primary" type="button" :disabled="status?.running || !!busy" @click="run('scan')">{{ busy === 'run-scan' ? '正在启动…' : '检测待检测目录' }}</button><button class="secondary" type="button" :disabled="status?.running || !!busy" @click="run('recheck')">重检待秒传文件</button><button class="secondary" type="button" :disabled="status?.running || !!busy" @click="run('all')">检测并重检</button><button v-if="status?.running" class="secondary danger-text" type="button" :disabled="!!busy" @click="postAction('stop', '/stop')">{{ busy === 'stop' ? '正在停止…' : '停止任务' }}</button></div><p class="hint">Cookie 留空时读取平台已保存的 115 Cookie；无法连接时可到账号页检测登录。</p></div>
            <p v-if="statusError" class="alert error status-error" role="alert">{{ statusError }}</p>
            <div v-if="status" class="subsection runtime-status">
              <div class="status-line"><b>{{ status.running ? '任务运行中' : '当前没有任务运行' }}</b><span v-if="status.running">每 5 秒刷新</span></div>
              <p v-if="status.current" class="current-file">{{ typeof status.current === 'string' ? status.current : status.current.path || status.current.name || '' }}</p>
              <progress v-if="status.running && runProgress !== null" :value="runProgress" max="100" :aria-label="`当前进度 ${Math.round(runProgress)}%`"></progress>
              <dl class="counts"><div><dt>文件记录</dt><dd>{{ count('total') }}</dd></div><div><dt>已完成记录</dt><dd>{{ count('rapid') }}</dd></div><div><dt>待重检</dt><dd>{{ count('pending') }}</dd></div><div><dt>失败 / 待核对</dt><dd>{{ count('failed') }}</dd></div></dl>
              <p v-if="status.last_result?.message" class="hint">{{ status.last_result.message }}</p>
            </div>
            <div class="subsection">
              <div class="section-head"><div><h4>文件记录</h4><p>最多显示最近 100 条记录；统计包含全部记录。</p></div><button class="text-button danger-text" type="button" :disabled="!items.length || status?.running || !!busy" @click="clearConfirmation = true">清空记录</button></div>
              <div v-if="clearConfirmation" class="confirmation"><b>清空文件处理记录？</b><p>文件不会删除。清空后会重新检测、可能重复云端入库。</p><div class="action-row"><button class="secondary" type="button" @click="clearConfirmation = false">取消</button><button class="secondary danger-text" type="button" :disabled="!!busy" @click="clearRecords">{{ busy === 'clear' ? '正在清空…' : '确认清空记录' }}</button></div></div>
              <div v-if="!status && statusError" class="empty"><b>运行记录暂不可用</b><p>请点击刷新状态重新读取。</p></div>
              <div v-else-if="!items.length" class="empty"><b>尚无文件处理记录</b><p>连接账号并执行检测后，结果将显示在这里。</p></div>
              <ul v-else class="record-list">
                <li v-for="(item, index) in items" :key="item.path || index">
                  <div class="record-main"><b class="file-path">{{ item.path || item.name }}</b><span :class="['record-state', {failed: attentionState(item.state)}]">{{ stateLabel(item.state) }}</span></div>
                  <div class="record-meta"><span>{{ formatBytes(item.size) }}</span><span>检查 {{ item.checks ?? 0 }} 次</span><time>{{ formatTime(item.updated) }}</time></div>
                  <p v-if="item.message" class="hint" :class="{'danger-text': attentionState(item.state)}">{{ item.message }}</p>
                </li>
              </ul>
            </div>
          </template>
        </fieldset>
      </section>
    </div>

    <footer v-if="!loading" class="save-bar"><span>{{ loadError ? '配置读取失败，暂不可保存' : dirty ? '修改尚未保存' : '当前配置已保存' }}</span><button class="primary" type="button" :disabled="locked || !dirty" @click="save()">{{ saving ? '正在保存…' : '保存配置' }}</button></footer>
  </main>
</template>

<style scoped>
.mst-shell{--mst-bg:var(--bg-base,var(--bg-primary,#0c141f));--mst-surface:var(--bg-card,#111c2a);--mst-input:var(--bg-elevated,var(--bg-input,#0a1420));--mst-line:var(--border-light,var(--border,#29394e));--mst-text:var(--text-primary,#edf3fb);--mst-muted:var(--text-secondary,var(--text-muted,#9eacbd));--mst-accent:var(--accent,#178bd4);--mst-button:color-mix(in srgb,var(--mst-accent) 82%,#000);--mst-button-hover:color-mix(in srgb,var(--mst-accent) 86%,#000);--mst-danger:var(--danger,#d85060);min-width:0;min-height:620px;padding:22px 22px max(18px,env(safe-area-inset-bottom));color:var(--mst-text);background:var(--mst-bg);font-family:inherit;font-size:14px;line-height:1.5;scrollbar-color:var(--mst-line) var(--mst-bg);accent-color:var(--mst-accent);caret-color:var(--mst-accent)}
.mst-shell *{box-sizing:border-box}.mst-shell ::selection{color:#fff;background:var(--mst-accent)}h2,h3,h4,p{margin:0}h2{font-size:22px;line-height:1.25}h3{font-size:19px;line-height:1.3}h4{font-size:15px}button,input,textarea,select{font:inherit}.page-head{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 2px 18px;border-bottom:1px solid var(--mst-line)}.page-head p,.panel-head p,.section-head p{margin-top:4px;color:var(--mst-muted);font-size:12px}.save-state{flex:0 0 auto;padding:6px 10px;border:1px solid var(--mst-line);border-radius:999px;color:var(--mst-muted);font-size:12px}.save-state.changed{color:var(--mst-accent);border-color:var(--mst-accent)}.workspace{display:grid;grid-template-columns:188px minmax(0,1fr);gap:20px;margin-top:20px}.section-nav{display:flex;flex-direction:column;gap:6px;align-self:start;position:sticky;top:16px}.section-nav button{display:grid;grid-template-columns:1fr 8px;align-items:center;gap:12px;width:100%;min-height:44px;padding:0 12px;border:1px solid transparent;border-radius:8px;color:var(--mst-muted);background:transparent;text-align:left;cursor:pointer}.section-nav button:hover{color:var(--mst-text);background:var(--mst-surface)}.section-nav button.active{border-color:var(--mst-accent);color:var(--mst-text);background:color-mix(in srgb,var(--mst-accent) 13%,var(--mst-bg))}.section-nav i{width:7px;height:7px;border-radius:50%;background:var(--mst-line)}.section-nav i.on{background:var(--mst-accent)}.panel{min-width:0;border:1px solid var(--mst-line);border-radius:8px;background:var(--mst-surface);overflow:hidden}.fields{margin:0;padding:0;border:0;min-width:0}.panel-head{padding:20px 22px;border-bottom:1px solid var(--mst-line)}.subsection{padding:20px 22px}.subsection+.subsection{border-top:1px solid var(--mst-line)}.section-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:14px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.form-grid label{min-width:0}.form-grid label>span{display:block;margin-bottom:6px;color:var(--mst-muted);font-size:12px}.form-grid small,.hint{display:block;margin-top:6px;color:var(--mst-muted);font-size:12px;line-height:1.6;overflow-wrap:anywhere}.wide{grid-column:1/-1}input:not([type=checkbox]),textarea,select{width:100%;min-height:42px;padding:9px 11px;border:1px solid var(--mst-line);border-radius:7px;color:var(--mst-text);background:var(--mst-input);outline:none}input:not([type=checkbox]),select{height:42px}textarea{resize:vertical;line-height:1.6}input::placeholder,textarea::placeholder{color:var(--mst-muted);opacity:1}.secret-field{position:relative}.secret-field input{padding-inline-end:46px}.secret-field button{position:absolute;inset-inline-end:4px;top:4px;display:grid;place-items:center;width:34px;height:34px;padding:0;border:0;border-radius:6px;color:var(--mst-muted);background:transparent;cursor:pointer}.secret-field button:hover{color:var(--mst-accent)}.secret-field svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round}.secondary,.primary{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:9px 14px;border:1px solid var(--mst-line);border-radius:8px;color:var(--mst-text);background:var(--mst-input);font-weight:650;cursor:pointer}.secondary:hover:not(:disabled){border-color:var(--mst-accent)}.primary{min-width:112px;border-color:var(--mst-button);color:#fff;background:var(--mst-button)}.primary:hover:not(:disabled){border-color:var(--mst-button-hover);background:var(--mst-button-hover)}button:disabled{opacity:.5;cursor:not-allowed}.action-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:16px}.login-result{color:var(--mst-accent);font-size:13px}.qr-controls{align-items:end}.qr-controls>button{justify-self:start}.qr-area{display:flex;align-items:center;gap:22px;margin-top:20px}.qr-area img{display:block;flex:0 0 192px;max-width:100%;object-fit:contain;border:8px solid #fff;border-radius:8px;background:#fff}.qr-area b{font-size:15px}.qr-area p{margin-top:6px;color:var(--mst-muted);font-size:13px}.qr-area small{display:block;margin-top:10px;color:var(--mst-muted);font-size:12px}.switch-list{display:grid;gap:12px}.following{margin-top:16px}.alert{margin-top:16px;padding:12px 14px;border:1px solid var(--mst-line);border-radius:8px;overflow-wrap:anywhere;font-size:13px}.alert.error{border-color:var(--mst-danger);color:var(--mst-danger);background:color-mix(in srgb,var(--mst-danger) 5%,var(--mst-bg))}.alert.success{border-color:var(--mst-accent);color:var(--mst-text);background:color-mix(in srgb,var(--mst-accent) 8%,var(--mst-bg))}.alert>button{margin-top:10px}.loading{padding:56px 20px;color:var(--mst-muted);text-align:center}.records-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.run-actions{gap:9px}.danger-text{color:var(--mst-danger)}.status-error{margin:0 22px 16px}.status-line{display:flex;align-items:center;justify-content:space-between;gap:12px}.status-line span{color:var(--mst-muted);font-size:12px}.current-file{margin-top:10px;color:var(--mst-muted);overflow-wrap:anywhere}progress{display:block;width:100%;height:7px;margin-top:12px;accent-color:var(--mst-accent)}.counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:16px 0 0}.counts dt{color:var(--mst-muted);font-size:12px}.counts dd{margin:3px 0 0;font-size:16px;font-weight:650;font-variant-numeric:tabular-nums}.text-button{min-height:36px;padding:6px 0;border:0;background:transparent;font-size:12px;cursor:pointer}.confirmation{padding:14px;margin-bottom:14px;border:1px solid var(--mst-danger);border-radius:8px}.confirmation p{margin-top:5px;color:var(--mst-muted);font-size:13px}.confirmation .action-row{margin-top:12px}.empty{padding:28px 12px;border:1px dashed var(--mst-line);border-radius:8px;text-align:center}.empty b{font-size:13px}.empty p{margin-top:6px;color:var(--mst-muted);font-size:12px}.record-list{margin:0;padding:0;list-style:none}.record-list li{padding:14px 0;border-top:1px solid var(--mst-line)}.record-list li:first-child{border-top:0;padding-top:0}.record-main{display:flex;justify-content:space-between;align-items:start;gap:16px}.file-path{min-width:0;font-size:13px;font-weight:550;overflow-wrap:anywhere}.record-state{flex:0 0 auto;color:var(--mst-accent);font-size:12px}.record-state.failed,.record-error{color:var(--mst-danger)}.record-meta{display:flex;flex-wrap:wrap;gap:5px 16px;margin-top:6px;color:var(--mst-muted);font-size:12px;font-variant-numeric:tabular-nums}.record-error{margin-top:8px;font-size:12px;overflow-wrap:anywhere}.save-bar{position:sticky;z-index:3;bottom:0;display:flex;align-items:center;justify-content:flex-end;gap:16px;margin-top:18px;padding:12px 0 max(4px,env(safe-area-inset-bottom));border-top:1px solid var(--mst-line);background:var(--mst-bg)}.save-bar>span{color:var(--mst-muted);font-size:12px}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:2px solid var(--mst-accent);outline-offset:2px}
@media(max-width:900px){.workspace{grid-template-columns:1fr}.section-nav{position:static;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}.section-nav button{gap:6px;padding-inline:9px;text-align:center;grid-template-columns:1fr}.section-nav i{display:none}}
@media(max-width:620px){.mst-shell{min-height:0;padding:16px 12px max(14px,env(safe-area-inset-bottom))}.page-head{align-items:flex-start;gap:12px}.save-state{max-width:120px;text-align:center}.workspace{gap:14px;margin-top:14px}.section-nav button{font-size:12px;white-space:nowrap}.panel-head,.subsection{padding-inline:14px}.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}.qr-area{align-items:flex-start;flex-direction:column;gap:14px}.qr-controls>button{width:100%}.records-heading{align-items:flex-start}.records-heading .secondary{padding-inline:10px;font-size:12px}.counts{grid-template-columns:repeat(2,minmax(0,1fr))}.status-line{align-items:flex-start}.status-error{margin-inline:14px}.record-main{gap:10px}.save-bar{justify-content:space-between}.save-bar .primary{min-width:124px}.run-actions>.primary,.run-actions>.secondary{flex:1 1 140px}}
@media(pointer:coarse){button,input:not([type=checkbox]),select{min-height:44px}.secret-field button{top:0;height:44px}}
@media(forced-colors:active){.panel,input,textarea,select,button,.confirmation{border:1px solid CanvasText}.section-nav button.active{outline:1px solid Highlight}.section-nav i.on{background:Highlight}}
</style>
