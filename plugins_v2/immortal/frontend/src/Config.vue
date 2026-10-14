<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createHostBridge } from './bridge.js'
const props = defineProps({ host: { type: Object, required: true } })
const VERSION = '0.0.1'
const tab = ref('admin')
const tabs = [{ id: 'admin', label: '管理页面' }, { id: 'settings', label: '插件设置' }, { id: 'status', label: '运行状态' }]
const defaults = { auto_tasks: false, allow_downloads: false, notify_results: false, database_url: '' }
const values = ref({ ...defaults })
const baseline = ref('')
const loading = ref(true)
const saving = ref(false)
const loaded = ref(false)
const loadError = ref('')
const notice = ref('')
const failed = ref(false)
const status = ref(null)
const statusError = ref('')
const refreshing = ref(false)
const stopping = ref('')
const frame = ref(null)
const frameReady = ref(false)
const frameError = ref('')
const frameRevision = ref(0)
const session = ref('')
const tabButtons = []
let bridge = null
let connectTimer = null
let mounted = true
const dirty = computed(() => loaded.value && JSON.stringify(values.value) !== baseline.value)
const frameSrc = computed(() => session.value ? `/api/plugins/${encodeURIComponent(props.host.pluginId || 'immortal')}/fe/app/index.html?v=${VERSION}&bridge=${session.value}` : '')
const databaseLabel = computed(() => status.value?.database || (values.value.database_url.trim() ? '外部数据库' : 'SQLite（插件独立文件）'))
const stateLabels = { queued: '等待执行', running: '运行中', stopping: '正在停止', cancelled: '已停止', failed: '失败', success: '已完成', completed: '已完成' }
watch(values, () => { if (!saving.value) notice.value = '' }, { deep: true, flush: 'sync' })
function tabKey(event, index) {
  const next = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key]
  if (next === undefined) return
  event.preventDefault(); tab.value = tabs[next].id; tabButtons[next]?.focus()
}
function resetFrame() {
  bridge?.close(); clearTimeout(connectTimer); frameReady.value = false; frameError.value = ''
  const random = new Uint8Array(24); crypto.getRandomValues(random)
  session.value = Array.from(random, n => n.toString(16).padStart(2, '0')).join('')
  frameRevision.value++
  bridge = createHostBridge({ host: props.host, iframe: () => frame.value, session: session.value, origin: location.origin,
    connected() { frameReady.value = true; clearTimeout(connectTimer) }, error(message) { frameError.value = message } })
  connectTimer = setTimeout(() => { if (mounted && !frameReady.value) frameError.value = '管理页面未连接成功，请确认插件已启用，再重新打开。' }, 20000)
}
async function receive(event) { await bridge?.receive(event) }
async function load() {
  if (saving.value || dirty.value) return
  loading.value = true; loadError.value = ''; loaded.value = false
  try {
    const result = await props.host.getConfig()
    if (!mounted) return
    values.value = { ...defaults, ...result }
    for (const key of ['auto_tasks', 'allow_downloads', 'notify_results']) values.value[key] = result?.[key] === true
    values.value.database_url = typeof result?.database_url === 'string' ? result.database_url : ''
    baseline.value = JSON.stringify(values.value); loaded.value = true
  } catch (error) { if (mounted) loadError.value = `读取配置失败：${error.message || '请重试'}。读取成功前不能保存。` }
  finally { loading.value = false }
  if (loaded.value) { await refresh(); if (mounted) resetFrame() }
}
async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try { const result = await props.host.callApi('/status'); if (mounted) { status.value = result; statusError.value = '' } }
  catch (error) { if (mounted) statusError.value = error.message || '状态读取失败，请确认插件已启用。' }
  finally { refreshing.value = false }
}
async function save() {
  if (!loaded.value || saving.value || !dirty.value) return
  const database = values.value.database_url.trim()
  const unchangedSecret = database === '********' && JSON.parse(baseline.value).database_url === database
  if (database && !unchangedSecret && !/^postgresql(?:\+psycopg2)?:\/\//.test(database)) { notice.value = '数据库地址需使用 postgresql:// 或 postgresql+psycopg2://；留空使用插件独立 SQLite。'; failed.value = true; return }
  saving.value = true; notice.value = ''; failed.value = false
  try {
    await props.host.saveConfig({ ...values.value, database_url: database })
    if (!mounted) return
    values.value.database_url = database; baseline.value = JSON.stringify(values.value)
    notice.value = '配置已保存。管理页将重新连接以应用当前设置。'
    await refresh(); if (mounted) resetFrame()
  } catch (error) { if (mounted) { notice.value = `保存失败：${error.message || '请重试'}。填写内容已保留。`; failed.value = true } }
  finally { saving.value = false }
}
async function stop(job) {
  if (stopping.value || !job.id) return
  stopping.value = job.id
  try { await props.host.callApi('/cancel', { method: 'POST', body: { id: job.id } }); await refresh() }
  catch (error) { statusError.value = error.message || '停止失败，请刷新状态查看。' }
  finally { stopping.value = '' }
}
onMounted(() => { window.addEventListener('message', receive); void load() })
onBeforeUnmount(() => { mounted = false; bridge?.close(); clearTimeout(connectTimer); window.removeEventListener('message', receive) })
</script>

<template>
  <section class="immortal-config">
    <nav class="tabs" role="tablist" aria-label="Immortal 设置分组">
      <button v-for="(item, index) in tabs" :id="`immortal-tab-${item.id}`" :key="item.id" :ref="element => tabButtons[index] = element" role="tab" :aria-selected="tab === item.id" :aria-controls="`immortal-panel-${item.id}`" :tabindex="tab === item.id ? 0 : -1" :class="{ selected: tab === item.id }" @click="tab = item.id" @keydown="tabKey($event, index)">{{ item.label }}</button>
    </nav>
    <p v-if="loading" class="hint" role="status">正在读取插件配置…</p>
    <div v-if="loadError" class="message error" role="alert"><p>{{ loadError }}</p><button class="button" @click="load">重新读取</button></div>

    <div v-show="tab === 'admin'" id="immortal-panel-admin" role="tabpanel" aria-labelledby="immortal-tab-admin">
      <header class="section-head"><div><h3>Immortal</h3><p>源码内置管理台，无需另开服务。保留原有采集、订阅和下载管理界面。</p></div><button class="button" :disabled="!loaded || saving" @click="resetFrame">重新打开管理页</button></header>
      <p v-if="statusError" class="message error" role="alert">{{ statusError }} 请先启用插件。</p>
      <p v-if="session && !frameReady && !frameError" class="hint" role="status">正在连接管理页面…</p>
      <p v-if="frameError" class="message error" role="alert">{{ frameError }}</p>
      <iframe v-if="frameSrc" :key="frameRevision" ref="frame" :src="frameSrc" title="Immortal 管理页面" class="admin-frame" referrerpolicy="no-referrer" />
    </div>

    <div v-show="tab === 'settings'" id="immortal-panel-settings" role="tabpanel" aria-labelledby="immortal-tab-settings">
      <header class="section-head"><div><h3>插件设置</h3><p>三个功能默认关闭。修改后保存，设置才会生效。</p></div></header>
      <fieldset :disabled="!loaded || saving" class="settings-fields">
        <label class="toggle"><input v-model="values.auto_tasks" type="checkbox"><span><b>运行自动任务</b><small>允许运行 Immortal 内启用的定时采集和订阅任务；关闭时不自动执行。</small></span></label>
        <label class="toggle"><input v-model="values.allow_downloads" type="checkbox"><span><b>允许提交下载</b><small>开启后才允许向已配置的下载器提交任务，可能产生下载流量。</small></span></label>
        <label class="toggle"><input v-model="values.notify_results" type="checkbox"><span><b>任务结果通知</b><small>通过平台已有通知渠道发送，不需要重复填写 Telegram 或企业微信凭证。</small></span></label>
        <label class="field"><span>数据库地址（可选）</span><input v-model="values.database_url" type="password" autocomplete="new-password" placeholder="留空：使用插件独立 SQLite 数据库"><small>默认空值，使用插件独立 SQLite 文件。外部 PostgreSQL 连接使用 postgresql:// 或 postgresql+psycopg2://；不接受外部 SQLite 文件路径。切换地址不会自动迁移旧数据。</small><small v-if="values.database_url === '********'">已保存的连接信息由平台保护。保持原样不会更改；需要更换时输入新地址。</small></label>
      </fieldset>
      <p :class="['save-message', { error: failed }]" :role="failed ? 'alert' : 'status'">{{ notice || (dirty ? '有未保存的修改。' : loaded ? '当前配置已保存。' : '配置尚未读取成功。') }}</p>
      <button class="button primary" :disabled="!loaded || saving || !dirty" @click="save">{{ saving ? '正在保存…' : '保存配置' }}</button>
    </div>

    <div v-show="tab === 'status'" id="immortal-panel-status" role="tabpanel" aria-labelledby="immortal-tab-status">
      <header class="section-head"><div><h3>运行状态</h3><p>按需刷新，不进行空闲轮询。</p></div><button class="button" :disabled="refreshing" @click="refresh">{{ refreshing ? '正在读取…' : '刷新状态' }}</button></header>
      <p v-if="statusError" class="message error" role="alert">{{ statusError }}</p>
      <dl v-if="status" class="status-list"><div><dt>插件版本</dt><dd>{{ status.version || VERSION }}</dd></div><div><dt>数据库</dt><dd>{{ databaseLabel }}</dd></div><div><dt>自动任务</dt><dd>{{ status.auto_tasks ? '已开启' : '已关闭' }}</dd></div><div><dt>提交下载</dt><dd>{{ status.allow_downloads ? '允许' : '禁止' }}</dd></div><div><dt>结果通知</dt><dd>{{ status.notify_results ? '已开启' : '已关闭' }}</dd></div></dl>
      <h4>当前任务</h4>
      <ul v-if="status?.running?.length" class="jobs"><li v-for="job in status.running" :key="job.id"><b>{{ job.label || job.id }}</b><span>{{ job.error || stateLabels[job.state] || '运行中' }}</span><button v-if="['queued', 'running', 'stopping'].includes(job.state)" class="button" :disabled="!!stopping || job.state === 'stopping'" @click="stop(job)">{{ stopping === job.id || job.state === 'stopping' ? '正在停止…' : '停止任务' }}</button></li></ul>
      <p v-else class="hint">{{ status ? '当前没有任务运行。' : '尚未读取运行状态。' }}</p>
      <p class="hint">采集网站和下载器需要能从平台服务器访问；配置页打开正常不代表外部账号已经登录。</p>
    </div>
  </section>
</template>

<style scoped>
.immortal-config { color: var(--text-primary, #172b37); font: inherit; min-width: 0; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-light, #d5dee3); margin-bottom: 18px; }
.tabs button { border: 0; border-bottom: 2px solid transparent; padding: 10px 14px; background: transparent; color: var(--text-secondary, #52636e); font: inherit; cursor: pointer; }
.tabs button.selected { border-bottom-color: var(--accent, #14765e); color: var(--accent, #14765e); font-weight: 650; }
.section-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; margin: 18px 0; }
h3 { font-size: 18px; font-weight: 650; line-height: 1.4; margin: 0 0 6px; } h4 { margin: 26px 0 10px; font-size: 15px; }
p { margin: 0; line-height: 1.6; max-width: 70ch; } .section-head p, .hint, small { color: var(--text-secondary, #52636e); font-size: 13px; }
.button { border: 1px solid var(--border-light, #d5dee3); border-radius: var(--radius-sm, 6px); background: var(--bg-elevated, #fff); color: inherit; padding: 8px 13px; font: inherit; font-size: 14px; min-height: 36px; cursor: pointer; white-space: nowrap; }
.button:hover { background: var(--bg-hover, #edf3f5); } .button.primary { background: var(--accent, #14765e); border-color: var(--accent, #14765e); color: var(--text-on-accent, #fff); }.button.primary:hover { filter: brightness(.93); }
button:disabled, fieldset:disabled { opacity: .55; } button:disabled { cursor: not-allowed; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--accent, #14765e); outline-offset: 3px; }
.admin-frame { display: block; width: 100%; height: min(80vh, 1000px); min-height: 610px; border: 1px solid var(--border-light, #d5dee3); border-radius: var(--radius-sm, 6px); background: var(--bg-elevated, #fff); }
.message { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--border-light, #d5dee3); margin: 12px 0; border-radius: var(--radius-sm, 6px); }.error { color: var(--danger, #b33232); }
.settings-fields { border: 0; padding: 0; display: grid; gap: 24px; max-width: 760px; }.toggle { display: flex; align-items: start; gap: 12px; cursor: pointer; }.toggle input { width: 17px; height: 17px; accent-color: var(--accent, #14765e); margin: 3px 0 0; flex: 0 0 auto; }.toggle span { display: grid; gap: 5px; }.toggle b { font-size: 14px; font-weight: 600; } small { display: block; line-height: 1.6; max-width: 70ch; }
.field { display: grid; gap: 8px; font-size: 14px; }.field input { width: 100%; box-sizing: border-box; border: 1px solid var(--border-light, #d5dee3); border-radius: var(--radius-sm, 6px); background: var(--bg-elevated, #fff); color: inherit; padding: 10px; font: inherit; caret-color: var(--accent, #14765e); }.field input::placeholder { color: var(--text-secondary, #52636e); opacity: 1; }
.save-message { margin: 26px 0 12px; font-size: 13px; }.status-list { margin: 0; max-width: 680px; }.status-list div { display: grid; grid-template-columns: 130px 1fr; border-bottom: 1px solid var(--border-light, #d5dee3); padding: 12px 0; }.status-list dt { color: var(--text-secondary, #52636e); }.status-list dd { margin: 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }.jobs { list-style: none; padding: 0; }.jobs li { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--border-light, #d5dee3); }.jobs span { overflow-wrap: anywhere; }
::selection { background: var(--accent-dim, #d2ece3); }
@media (max-width: 600px) { .tabs button { padding-inline: 10px; }.section-head { flex-direction: column; }.admin-frame { min-height: 650px; }.message { flex-wrap: wrap; }.status-list div { grid-template-columns: 110px 1fr; }.field input { font-size: 16px; } }
</style>
