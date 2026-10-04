<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import schema from './schema.json'
import { apiError, configPayload, configValues, isVisible, validateConfig } from './config.js'
import ToolResult from './ToolResult.vue'

const props = defineProps({ host: { type: Object, required: true } })
const values = ref({})
const baseline = ref({})
const loaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const acting = ref('')
const revealing = ref('')
const visibleSecrets = ref({})
const secretSyncRequired = ref(false)
const secretSyncError = ref('')
const errors = ref({})
const loadError = ref('')
const saveNotice = ref('')
const saveFailed = ref(false)
const result = ref(null)
const confirmation = ref('')
let mounted = true
onBeforeUnmount(() => { mounted = false })

const busy = computed(() => loading.value || saving.value || !!acting.value || !!revealing.value)
const dirty = computed(() => loaded.value && JSON.stringify(configPayload(schema, values.value)) !== JSON.stringify(baseline.value))
const tabs = [
  { id: 'print', label: '打印设置', title: '连接打印机', note: '先设置连接，再保存并检查。打印机地址不是管理网页地址。' },
  { id: 'family', label: '家人权限', title: '允许谁打印', note: '机器人与企业微信应用从平台读取，这里只设置允许使用的家人。' },
  { id: 'tools', label: '任务与工具', title: '任务与连接', note: '点击后才查询，不会自动打印。工具使用已保存的设置。' },
  { id: 'help', label: '使用帮助', title: '怎么开始使用', note: '日常只需要发送文件，再回复“打印”。详细说明按需展开。' },
]
const activeTab = ref('print')
const formElement = ref(null)
const tabButtons = []
const groupDefinitions = [
  { id: 'connection', tab: 'print', title: '' },
  { id: 'reception', tab: 'print', title: '收件与确认' },
  { id: 'advanced', tab: 'print', title: '高级设置' },
  { id: 'people', tab: 'family', title: '' },
  { id: 'wecom', tab: 'family', title: '企业微信接收' },
  { id: 'status', tab: 'tools', title: '' },
  { id: 'maintenance', tab: 'tools', title: '任务维护', danger: true },
  { id: 'guides', tab: 'help', title: '' },
]

function groupFor(key, spec) {
  if (spec.type === 'info') return 'guides'
  if (['cleanup_files', 'archive_unknown'].includes(key)) return 'maintenance'
  if (spec.section === '允许谁打印') return 'people'
  if (spec.section === '企业微信接收设置') return 'wecom'
  if (spec.section === '开始接收') return 'reception'
  if (spec.section === '高级设置') return 'advanced'
  if (spec.section === '查看打印状态') return 'status'
  return 'connection'
}
function tabFor(key) {
  const group = groupFor(key, schema[key] || {})
  return groupDefinitions.find((item) => item.id === group)?.tab || 'print'
}
const resultTab = computed(() => result.value?.key ? tabFor(result.value.key) : activeTab.value)
const sections = computed(() => groupDefinitions.map((group) => ({
  ...group,
  fields: Object.entries(schema)
    .filter(([key, spec]) => key !== 'show_advanced' && groupFor(key, spec) === group.id
      && (spec.type === 'info' || group.id === 'maintenance' || isVisible(spec, values.value)))
    .map(([key, spec]) => ({ key, spec }))
    .sort((a, b) => (a.spec.order ?? 9999) - (b.spec.order ?? 9999)),
})).filter((group) => group.fields.length || group.id === 'advanced'))

function chooseTab(id) {
  activeTab.value = id
  confirmation.value = ''
}
function tabKey(event, index) {
  const positions = { ArrowRight: (index + 1) % tabs.length, ArrowDown: (index + 1) % tabs.length,
    ArrowLeft: (index + tabs.length - 1) % tabs.length, ArrowUp: (index + tabs.length - 1) % tabs.length,
    Home: 0, End: tabs.length - 1 }
  if (!(event.key in positions)) return
  event.preventDefault()
  const next = positions[event.key]
  chooseTab(tabs[next].id)
  tabButtons[next]?.focus()
}

const shortLabels = {
  print_mode: '连接方式', ipp_url: '打印机访问地址', device_id: '电脑端设备名称',
  printer_name: 'Windows 打印机名称', telegram_users: 'Telegram 用户 ID',
  wecom_users: '企业微信成员账号', public_base_url: '平台访问地址',
  auto_print: '收到文件直接打印', ipp_printer_uri: '打印机内部地址',
  ipp_timeout_seconds: '连接超时（秒）', default_copies: '默认份数', max_copies: '最多份数',
  max_pages: '最多页数', max_file_mb: '文件上限（MB）', max_queue: '未结束任务上限',
  max_storage_mb: '缓存上限（MB）', retention_hours: '文件保留（小时）',
}
const shortHints = {
  print_mode: '支持 IPP 的网络打印机选直连；USB 打印机等通过 Windows 电脑打印。',
  ipp_url: '填写平台能够访问的 IPP 地址。同一局域网不需要 FRP。',
  device_id: '与电脑端 device_id 一致。', device_token: '留空时先生成密钥，再点眼睛查看，复制到电脑端。',
  printer_name: '留空使用电脑端默认打印机。', telegram_users: '数字 ID，每行一个；留空不允许任何人。',
  wecom_users: '通讯录 UserID，每行一个；同一成员也须在平台回调名单中授权。',
  public_base_url: '填写平台 HTTPS 地址，用于查看回调或连接电脑端；不是打印机地址。',
  enabled: '默认关闭。连接和家人名单设置完成后再开启。',
  auto_print: '默认关闭。保持关闭时，家人回复“打印”后才开始，避免误打。',
  ipp_printer_uri: '通常留空，由打印机自动提供。', ipp_timeout_seconds: '默认 30 秒，范围 5–120 秒。',
  default_copies: '默认 1 份。', max_copies: '默认 3 份，最多 5 份。',
  max_pages: '默认 50 页，超限拒绝整份文件。', max_file_mb: '默认 20 MB；企微最高 20 MB。',
  max_queue: '默认 30 个，包含待核查任务。', max_storage_mb: '默认 200 MB。',
  retention_hours: '默认 24 小时，不会自动重打。',
}
function fieldLabel(key, spec) { return shortLabels[key] || spec.label || key }
function actionHint(key, spec) {
  return { test_ipp: '只检查连接和格式，不会用纸。', generate_device_token: '已有密钥会失效，必须同步更新电脑端。',
    show_wecom_setup: '查看关联应用的完整回调地址和填写步骤。',
    show_connection: '查询当前打印方式、打印机状态和接收地址。',
    show_jobs: '查询最近任务与失败原因。已提交不代表已经出纸。',
    cleanup_files: '仅清理已到期的结束任务文件，不清理未结束任务。',
    archive_unknown: '仅归档已核查的待核查任务，不重新打印。执行前请确认是否已出纸。' }[key] || spec.help
}

async function load() {
  if (busy.value) return
  if (dirty.value) {
    saveFailed.value = true
    saveNotice.value = '你有尚未保存的修改，请先保存，再重新读取。'
    return
  }
  loading.value = true
  loaded.value = false
  loadError.value = ''
  try {
    const saved = configValues(schema, await props.host.getConfig())
    if (!mounted) return
    values.value = saved
    baseline.value = configPayload(schema, saved)
    visibleSecrets.value = {}
    secretSyncRequired.value = false
    secretSyncError.value = ''
    errors.value = {}
    confirmation.value = ''
    loaded.value = true
  } catch (error) {
    if (mounted) loadError.value = apiError(error, '读取配置') + '\n未读取成功前不能保存，也不会执行任何工具。'
  } finally {
    if (mounted) loading.value = false
  }
}

function update(key, value) {
  values.value[key] = value
  if (errors.value[key]) delete errors.value[key]
  saveNotice.value = ''
  confirmation.value = ''
}

async function save() {
  if (!loaded.value || busy.value) return
  if (secretSyncRequired.value) {
    saveFailed.value = true
    saveNotice.value = '未保存：连接密钥的更新结果尚未确认，请先点击“重新读取连接密钥”。其他填写内容已保留。'
    return
  }
  errors.value = validateConfig(schema, values.value)
  if (Object.keys(errors.value).length) {
    saveNotice.value = '未保存：请检查标红的设置。'
    saveFailed.value = true
    const first = Object.keys(errors.value)[0]
    activeTab.value = tabFor(first)
    await nextTick()
    formElement.value?.querySelector(`#rp-${first}`)?.focus()
    return
  }
  saving.value = true
  saveNotice.value = ''
  const payload = configPayload(schema, values.value)
  try {
    const response = await props.host.saveConfig(payload)
    if (!mounted) return
    if (response?.ok === false) throw new Error(response.message || '平台拒绝保存配置。')
    baseline.value = payload
    saveFailed.value = false
    saveNotice.value = '配置已保存。'
    confirmation.value = ''
  } catch (error) {
    if (mounted) {
      saveFailed.value = true
      saveNotice.value = apiError(error, '保存配置') + ' 你的填写内容已保留。'
    }
  } finally {
    if (mounted) saving.value = false
  }
}

async function toggleSecret(key) {
  if (!loaded.value || busy.value) return
  if (key === 'device_token' && secretSyncRequired.value) return
  if (visibleSecrets.value[key]) {
    visibleSecrets.value[key] = false
    return
  }
  if (values.value[key] !== '********') {
    visibleSecrets.value[key] = true
    return
  }
  revealing.value = key
  const current = values.value[key]
  try {
    const value = await props.host.revealSecret(key)
    if (!mounted || values.value[key] !== current) return
    if (value === '********' || value === undefined) throw new Error('平台未返回可查看的密钥，请重试。')
    values.value[key] = value
    // Viewing a secret is not an edit and must not make an action silently save it.
    if (baseline.value[key] === current) baseline.value[key] = value
    visibleSecrets.value[key] = true
  } catch (error) {
    if (mounted) showResult('查看密钥', apiError(error, '读取密钥'), false)
  } finally {
    if (mounted) revealing.value = ''
  }
}

function showResult(title, message, ok, key = '') {
  result.value = { title, message: String(message), ok, key }
}

function readyForAction(spec) {
  if (!loaded.value || busy.value) return false
  if (secretSyncRequired.value) {
    showResult(spec.label, '连接密钥的更新结果尚未确认，请先点击“重新读取连接密钥”。未执行此操作。', false, spec.action)
    return false
  }
  if (dirty.value) {
    confirmation.value = ''
    showResult(spec.label, '尚有未保存的设置。请先点击“保存配置”，再执行此操作。', false, spec.action)
    return false
  }
  return true
}

function requestAction(key, spec) {
  if (!readyForAction(spec)) return
  if (spec.danger) confirmation.value = key
  else runAction(key, spec)
}

async function runAction(key, spec) {
  if (!readyForAction(spec)) return
  if (spec.danger && confirmation.value !== key) return
  confirmation.value = ''
  acting.value = key
  showResult(spec.label, '正在执行，请稍候…', true, key)
  if (key === 'generate_device_token') {
    // A server-side rotation may succeed even when its response is lost. Drop
    // the old revealed value before the request, and lock saving until a read
    // confirms the current stored mask (or empty value).
    secretSyncRequired.value = true
    visibleSecrets.value.device_token = false
    values.value.device_token = '********'
    baseline.value.device_token = '********'
  }
  try {
    const body = { action: spec.action || key }
    if (spec.danger) body.confirmed = true
    const response = await props.host.callApi('/tools', { method: 'POST', body })
    if (!mounted) return
    if (!response || typeof response.ok !== 'boolean' || typeof response.message !== 'string') {
      throw new Error('平台未返回工具结果，请更新插件后重试。')
    }
    showResult(spec.label, response.message, response.ok, key)
  } catch (error) {
    if (mounted) showResult(spec.label, apiError(error, spec.label), false, key)
  } finally {
    if (mounted && key === 'generate_device_token') await syncDeviceToken(true)
    if (mounted) acting.value = ''
  }
}

async function syncDeviceToken(duringAction = false) {
  if (!mounted || !loaded.value || (!duringAction && busy.value)) return false
  revealing.value = 'device_token'
  secretSyncError.value = ''
  try {
    const saved = configValues(schema, await props.host.getConfig())
    if (!mounted) return false
    const token = saved.device_token
    if (token !== '********' && token !== '' && token !== null) {
      throw new Error('平台未返回有效的连接密钥状态。')
    }
    // Never replace other fields: the user may edit them before retrying this
    // read. An unchanged mask lets the platform preserve the newest key on PUT.
    values.value.device_token = token
    baseline.value.device_token = token
    visibleSecrets.value.device_token = false
    secretSyncRequired.value = false
    secretSyncError.value = ''
    saveNotice.value = ''
    return true
  } catch (error) {
    if (mounted) {
      secretSyncRequired.value = true
      secretSyncError.value = apiError(error, '重新读取连接密钥')
        + '\n为避免写回旧密钥，保存和管理工具已暂停。请点击下方按钮重新读取；其他填写内容不会被覆盖。'
    }
    return false
  } finally {
    if (mounted) revealing.value = ''
  }
}

function colSpan(spec, key) {
  return spec.type === 'number' || spec.type === 'text' || ['print_mode', 'ipp_url'].includes(key) ? 6 : 12
}

function options(spec) {
  return (spec.options || []).map((option) => typeof option === 'object'
    ? { value: option.value, label: option.label ?? option.value }
    : { value: option, label: option })
}

function emptySelect(key, spec) {
  return !options(spec).some((option) => option.value === values.value[key])
}

function selectChange(key, spec, event) {
  const index = event.target.selectedIndex - (emptySelect(key, spec) ? 1 : 0)
  const option = options(spec)[index]
  if (option) update(key, option.value)
}

onMounted(load)
</script>

<template>
  <div class="print-config">
    <p v-if="loading" class="state" role="status">正在读取配置…</p>
    <div v-else-if="loadError" class="state error" role="alert">
      <p>{{ loadError }}</p>
      <button type="button" class="button" @click="load">重新读取配置</button>
    </div>
    <form v-else-if="loaded" ref="formElement" @submit.prevent="save">
      <div class="tabs" role="tablist" aria-label="远程打印设置分类">
        <button v-for="(tab, index) in tabs" :id="`rp-tab-${tab.id}`" :key="tab.id"
          :ref="(el) => tabButtons[index] = el" type="button" role="tab" :data-tab="tab.id"
          :aria-selected="activeTab === tab.id" :aria-controls="`rp-panel-${tab.id}`"
          :tabindex="activeTab === tab.id ? 0 : -1" @click="chooseTab(tab.id)" @keydown="tabKey($event, index)">
          {{ tab.label }}
        </button>
      </div>

      <div v-if="secretSyncRequired" class="state error" role="alert">
        <p>{{ secretSyncError || '正在确认平台已保存的连接密钥，确认完成前不能保存。' }}</p>
        <button type="button" class="button" :disabled="busy" @click="syncDeviceToken()">{{ revealing === 'device_token' ? '正在读取…' : '重新读取连接密钥' }}</button>
      </div>

      <div v-for="tab in tabs" v-show="activeTab === tab.id" :id="`rp-panel-${tab.id}`" :key="tab.id"
        class="tab-panel" role="tabpanel" :aria-labelledby="`rp-tab-${tab.id}`" tabindex="0">
        <header class="page-heading">
          <h3>{{ tab.title }}</h3>
          <p>{{ tab.note }}</p>
        </header>

        <template v-for="section in sections.filter((item) => item.tab === tab.id)" :key="section.id">
        <section
          class="section" :class="{ maintenance: section.danger, advanced: section.id === 'advanced' }"
          :aria-label="section.title || tab.title">
          <template v-if="section.id === 'advanced'">
            <label class="advanced-toggle" for="rp-show_advanced" data-field="show_advanced">
              <span><strong>高级设置</strong><small>份数、文件限制与保留时间，通常保持默认即可。</small></span>
              <input id="rp-show_advanced" type="checkbox" role="switch" :checked="values.show_advanced === true"
                :disabled="busy" aria-label="显示高级设置" @change="update('show_advanced', $event.target.checked)">
            </label>
          </template>
          <h4 v-else-if="section.title" class="group-title">{{ section.title }}</h4>
          <p v-if="section.danger" class="maintenance-note">先核查任务，再按需处理。以下操作不重打，也不取消打印机里的任务。</p>
          <div v-show="section.id !== 'advanced' || values.show_advanced === true" class="fields">
            <div v-for="{ key, spec } in section.fields" :key="key" class="field"
              :class="{ 'tool-row': spec.type === 'action' }"
              :style="{ gridColumn: `span ${colSpan(spec, key)}` }" :data-field="key">
              <template v-if="spec.type === 'info'">
                <details class="guide" :open="key === 'usage'">
                  <summary>{{ spec.label || key }}</summary>
                  <p class="info">{{ spec.text ?? '' }}</p>
                </details>
              </template>
              <template v-else-if="spec.type === 'action'">
                <div class="tool-main">
                  <button type="button" class="button" :class="{ danger: spec.danger }" :disabled="busy"
                    @click="requestAction(key, spec)">{{ acting === key ? '正在执行…' : spec.label || key }}</button>
                  <p class="help">{{ actionHint(key, spec) }}</p>
                </div>
                <div v-if="confirmation === key" class="confirm" role="alert">
                  <strong>确认执行“{{ spec.label }}”？</strong>
                  <p>{{ spec.help }}</p>
                  <div class="button-row">
                    <button type="button" class="button danger" :disabled="busy" @click="runAction(key, spec)">确认执行</button>
                    <button type="button" class="button" @click="confirmation = ''">取消</button>
                  </div>
                </div>
              </template>
              <template v-else-if="spec.type === 'boolean'">
                <label class="switch-row" :for="`rp-${key}`">
                  <span><strong>{{ fieldLabel(key, spec) }}</strong><small>{{ shortHints[key] || spec.help }}</small></span>
                  <input :id="`rp-${key}`" type="checkbox" role="switch" :checked="values[key] === true"
                    :disabled="busy" :aria-label="spec.label" @change="update(key, $event.target.checked)">
                </label>
              </template>
              <template v-else>
                <label :for="`rp-${key}`">{{ fieldLabel(key, spec) }}<span v-if="spec.required" class="required">（必填）</span></label>
                <div v-if="spec.type === 'password' || spec.secret" class="secret-input">
                  <input :id="`rp-${key}`" :type="visibleSecrets[key] ? 'text' : 'password'" :value="values[key] ?? ''"
                    :disabled="busy || (key === 'device_token' && secretSyncRequired)" autocomplete="off"
                    :aria-label="spec.label" :aria-describedby="`rp-help-${key}`" @input="update(key, $event.target.value)">
                  <button type="button" class="eye" :disabled="busy || (key === 'device_token' && secretSyncRequired)"
                    :aria-label="`${visibleSecrets[key] ? '隐藏' : '查看'}${spec.label}`" :aria-pressed="!!visibleSecrets[key]" @click="toggleSecret(key)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path v-if="visibleSecrets[key]" d="m3 3 18 18"/>
                    </svg>
                  </button>
                </div>
                <textarea v-else-if="spec.type === 'text'" :id="`rp-${key}`" rows="3" :value="values[key] ?? ''"
                  :disabled="busy" :aria-label="spec.label" :aria-describedby="`rp-help-${key}`" @input="update(key, $event.target.value)" />
                <select v-else-if="spec.type === 'select'" :id="`rp-${key}`" :value="values[key]" :disabled="busy"
                  :aria-label="spec.label" :aria-describedby="`rp-help-${key}`" @change="selectChange(key, spec, $event)">
                  <option v-if="emptySelect(key, spec)" :value="values[key]" disabled>请选择连接方式</option>
                  <option v-for="option in options(spec)" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
                </select>
                <input v-else-if="spec.type === 'number'" :id="`rp-${key}`" type="number" :min="spec.min" :max="spec.max"
                  :step="spec.step ?? 1" :value="values[key] ?? ''" :disabled="busy" :aria-label="spec.label"
                  :aria-describedby="`rp-help-${key}`" :aria-invalid="!!errors[key]"
                  @input="update(key, $event.target.value === '' ? '' : Number($event.target.value))">
                <input v-else :id="`rp-${key}`" type="text" :value="values[key] ?? ''" :disabled="busy"
                  :aria-label="spec.label" :aria-describedby="`rp-help-${key}`" :aria-invalid="!!errors[key]"
                  @input="update(key, $event.target.value)">
                <p v-if="shortHints[key]" :id="`rp-help-${key}`" class="help">{{ shortHints[key] }}</p>
                <details v-if="spec.help" class="field-help">
                  <summary>详细说明</summary>
                  <p :id="shortHints[key] ? undefined : `rp-help-${key}`">{{ spec.help }}</p>
                </details>
                <p v-if="errors[key]" class="field-error" role="alert">{{ errors[key] }}</p>
              </template>
            </div>
          </div>
        </section>
        <ToolResult v-if="section.id === 'status' && result && resultTab === tab.id"
          :key="`${tab.id}-${result.message}`" :result="result" :busy="!!acting" />
        </template>
        <ToolResult v-if="tab.id !== 'tools' && result && resultTab === tab.id"
          :key="`${tab.id}-${result.message}`" :result="result" :busy="!!acting" />
      </div>

      <footer class="savebar">
        <p :class="{ error: saveFailed && saveNotice, changed: dirty && !saveNotice }" role="status">
          {{ saveNotice || (dirty ? '有未保存的更改' : '设置已读取') }}
          <small v-if="!saveNotice">{{ dirty ? '切换分类不会丢失填写，保存后才生效。' : '保存不会发送打印任务。' }}</small>
        </p>
        <button type="submit" class="button primary" :disabled="busy || secretSyncRequired">{{ saving ? '正在保存…' : '保存配置' }}</button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.print-config { --rp-space-sm: 8px; --rp-space-md: 16px; --rp-space-lg: 24px; --rp-space-section: 28px; color: var(--text-primary, #eef1f7); font-size: 14px; line-height: 1.6; min-width: 0; }
form, .tab-panel { display: flex; flex-direction: column; gap: var(--rp-space-section); min-width: 0; }
p, h3, h4 { margin: 0; }
.tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--border-light, #2a3c52); gap: 4px; }
.tabs button { min-height: 44px; padding: 10px var(--rp-space-sm); background: transparent; border: 0; border-bottom: 2px solid transparent; color: var(--text-secondary, #9aa3b5); font: inherit; font-weight: 500; cursor: pointer; }
.tabs button:hover { color: var(--text-primary, #eef1f7); background: var(--bg-hover, #142238); }
.tabs button[aria-selected=true] { color: var(--text-primary, #eef1f7); border-bottom-color: var(--accent, #3080f0); background: var(--accent-dim, #162b48); }
.page-heading h3 { font-size: 18px; font-weight: 600; line-height: 1.4; text-wrap: balance; }
.page-heading p { color: var(--text-secondary, #9aa3b5); margin-top: var(--rp-space-sm); max-width: 72ch; }
.section { min-width: 0; }
.group-title { font-size: 15px; font-weight: 600; margin-bottom: var(--rp-space-md); }
.fields { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: var(--rp-space-lg) var(--rp-space-md); align-items: start; }
.field { min-width: 0; }
.field > label:not(.switch-row) { display: block; margin-bottom: var(--rp-space-sm); font-weight: 500; }
.help, .field-help, .switch-row small, .advanced-toggle small { color: var(--text-secondary, #9aa3b5); font-size: 13px; font-weight: 400; line-height: 1.6; }
.help { margin-top: var(--rp-space-sm); overflow-wrap: anywhere; max-width: 72ch; }
.field-help { margin-top: 4px; }
.field-help summary { display: inline-list-item; cursor: pointer; width: fit-content; min-height: 24px; padding: 2px 0; }
.field-help p { padding-top: var(--rp-space-sm); white-space: pre-wrap; overflow-wrap: anywhere; max-width: 72ch; }
input:not([type=checkbox]), textarea, select { box-sizing: border-box; width: 100%; min-height: 44px; border: 1px solid var(--border-light, #2a3c52); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #172131); color: var(--text-primary, #eef1f7); padding: 10px 12px; font: inherit; caret-color: var(--accent, #3080f0); }
input[type=number] { font-variant-numeric: tabular-nums; }
textarea { resize: vertical; line-height: 1.6; }
.button { min-height: 44px; padding: 10px var(--rp-space-md); border: 1px solid var(--border-light, #2a3c52); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #172131); color: var(--text-primary, #eef1f7); font: inherit; font-weight: 500; cursor: pointer; flex-shrink: 0; max-width: 100%; }
.button:hover:not(:disabled) { border-color: var(--accent, #3080f0); background: var(--bg-hover, #142238); }
.primary { border-color: var(--accent, #3080f0); background: var(--accent-dim, #162b48); }
.danger { color: var(--danger, #ff8e96); }
button:disabled, input:disabled, select:disabled, textarea:disabled { opacity: .58; cursor: not-allowed; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, summary:focus-visible, .tab-panel:focus-visible { outline: 2px solid var(--accent, #3080f0); outline-offset: 3px; }
.switch-row, .advanced-toggle { display: flex; align-items: center; justify-content: space-between; gap: var(--rp-space-lg); cursor: pointer; }
.switch-row strong, .advanced-toggle strong { display: block; font-size: 14px; font-weight: 500; }
.switch-row small, .advanced-toggle small { display: block; margin-top: 4px; max-width: 72ch; }
input[type=checkbox] { appearance: none; width: 42px; height: 26px; border-radius: 13px; border: 1px solid var(--border-light, #2a3c52); background: var(--bg-elevated, #172131); position: relative; flex-shrink: 0; cursor: pointer; }
input[type=checkbox]::before { content: ''; position: absolute; width: 18px; height: 18px; top: 3px; inset-inline-start: 3px; border-radius: 50%; background: var(--text-secondary, #9aa3b5); }
input[type=checkbox]:checked { background: var(--accent, #3080f0); border-color: var(--accent, #3080f0); }
input[type=checkbox]:checked::before { inset-inline-start: 19px; background: var(--text-primary, #eef1f7); }
.secret-input { position: relative; }
.secret-input input { padding-inline-end: 52px; }
.eye { position: absolute; top: 1px; inset-inline-end: 1px; width: 44px; height: calc(100% - 2px); border: 0; border-radius: var(--radius-sm, 8px); background: transparent; color: var(--text-secondary, #9aa3b5); display: grid; place-items: center; cursor: pointer; }
.eye svg { width: 21px; height: 21px; }
.eye:hover:not(:disabled) { color: var(--text-primary, #eef1f7); }
.advanced { border-top: 1px solid var(--border, #1b2a3b); padding-top: var(--rp-space-lg); }
.advanced-toggle { min-height: 48px; }
.advanced .fields { margin-top: var(--rp-space-lg); }
.tool-main { display: flex; align-items: center; gap: var(--rp-space-md); }
.tool-main .help { margin: 0; }
.maintenance { border-top: 1px solid var(--border, #1b2a3b); padding-top: var(--rp-space-section); }
.maintenance-note { color: var(--text-secondary, #9aa3b5); font-size: 13px; margin-bottom: var(--rp-space-lg); max-width: 72ch; }
.state, .confirm { display: flex; flex-direction: column; align-items: flex-start; gap: 12px; padding: var(--rp-space-md); border: 1px solid var(--border-light, #2a3c52); border-radius: var(--radius-sm, 8px); white-space: pre-wrap; overflow-wrap: anywhere; }
.confirm { margin-top: var(--rp-space-md); }
.button-row { display: flex; flex-wrap: wrap; gap: var(--rp-space-sm); }
.guide { padding-bottom: var(--rp-space-lg); border-bottom: 1px solid var(--border, #1b2a3b); }
.guide summary { font-size: 15px; font-weight: 500; min-height: 44px; cursor: pointer; padding: 10px 0; }
.info { padding-top: var(--rp-space-sm); color: var(--text-secondary, #9aa3b5); white-space: pre-wrap; overflow-wrap: anywhere; max-width: 72ch; }
.savebar { position: sticky; bottom: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: var(--rp-space-md); padding: var(--rp-space-md) 0; border-top: 1px solid var(--border-light, #2a3c52); background: var(--bg-card, #0d1623); }
.savebar p { font-size: 13px; overflow-wrap: anywhere; white-space: pre-wrap; min-width: 0; }
.savebar small { display: block; color: var(--text-secondary, #9aa3b5); font-size: 12px; margin-top: 2px; }
.changed { color: var(--warning, #e0a020); }
.error, .field-error, .required { color: var(--danger, #ff8e96); }
.field-error { margin-top: var(--rp-space-sm); font-size: 13px; }
[aria-invalid=true] { border-color: var(--danger, #ff8e96) !important; }
::selection { background: var(--accent-dim, #162b48); color: var(--text-primary, #eef1f7); }
@media (max-width: 600px) {
  .print-config { font-size: 16px; }
  .tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tab-panel { gap: var(--rp-space-lg); }
  .fields { grid-template-columns: minmax(0, 1fr); }
  .field { grid-column: 1 / -1 !important; }
  .tool-main { flex-direction: column; align-items: flex-start; gap: var(--rp-space-sm); }
  .help, .field-help, .switch-row small, .advanced-toggle small { font-size: 14px; }
  .savebar { align-items: center; gap: 12px; }
  .savebar .button { padding-inline: 12px; }
  input:not([type=checkbox]), textarea, select { font-size: 16px; }
}
@media (forced-colors: active) {
  input[type=checkbox]:checked { background: Highlight; }
  input[type=checkbox]::before { background: ButtonText; }
  input[type=checkbox]:checked::before { background: HighlightText; }
}
</style>
