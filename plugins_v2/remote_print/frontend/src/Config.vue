<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
const sections = computed(() => {
  const groups = new Map()
  for (const [key, spec] of Object.entries(schema)) {
    if (!isVisible(spec, values.value)) continue
    const title = spec.section || '常规'
    if (!groups.has(title)) groups.set(title, [])
    groups.get(title).push({ key, spec })
  }
  return Array.from(groups, ([title, fields]) => ({
    title, fields: fields.sort((a, b) => (a.spec.order ?? 9999) - (b.spec.order ?? 9999)),
  }))
})

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

function colSpan(spec) {
  if (spec.cols !== undefined) return Math.max(1, Math.min(12, Number(spec.cols) || 1))
  return ['text', 'info', 'action'].includes(spec.type) ? 12 : 6
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
    <form v-else-if="loaded" @submit.prevent="save">
      <div class="toolbar">
        <p class="muted">{{ dirty ? '有未保存的修改。工具使用已保存的设置，请先保存再检查。' : '配置读取成功。工具只在点击后执行，不会自动打印。' }}</p>
        <button type="submit" class="button primary" :disabled="busy || secretSyncRequired">{{ saving ? '正在保存…' : '保存配置' }}</button>
      </div>
      <p v-if="saveNotice" class="notice" :class="{ error: saveFailed }" role="status">{{ saveNotice }}</p>
      <div v-if="secretSyncRequired" class="state error" role="alert">
        <p>{{ secretSyncError || '正在确认平台已保存的连接密钥，请稍候。确认完成前不能保存。' }}</p>
        <button type="button" class="button" :disabled="busy" @click="syncDeviceToken()">{{ revealing === 'device_token' ? '正在读取…' : '重新读取连接密钥' }}</button>
      </div>

      <section v-for="section in sections" :key="section.title" class="section" :aria-label="section.title">
        <h3>{{ section.title }}</h3>
        <div class="fields">
          <div v-for="{ key, spec } in section.fields" :key="key" class="field" :style="{ gridColumn: `span ${colSpan(spec)}` }" :data-field="key">
            <template v-if="spec.type === 'info'">
              <h4>{{ spec.label || key }}</h4>
              <p class="info">{{ spec.text ?? '' }}</p>
            </template>
            <template v-else-if="spec.type === 'action'">
              <button type="button" class="button" :class="{ danger: spec.danger }" :disabled="busy" @click="requestAction(key, spec)">
                {{ acting === key ? '正在执行…' : spec.label || key }}
              </button>
              <p v-if="spec.help" class="help">{{ spec.help }}</p>
              <div v-if="confirmation === key" class="confirm" role="alert">
                <p>确认执行“{{ spec.label }}”？</p>
                <p>{{ spec.help }}</p>
                <div class="button-row">
                  <button type="button" class="button danger" :disabled="busy" @click="runAction(key, spec)">确认执行</button>
                  <button type="button" class="button" @click="confirmation = ''">取消</button>
                </div>
              </div>
              <ToolResult v-if="result?.key === key" :key="`${key}-${result.message}`" :result="result" :busy="!!acting" />
            </template>
            <template v-else-if="spec.type === 'boolean'">
              <label class="switch-row" :for="`rp-${key}`">
                <span>{{ spec.label || key }}</span>
                <input :id="`rp-${key}`" type="checkbox" role="switch" :checked="values[key] === true" :disabled="busy" :aria-describedby="spec.help ? `rp-help-${key}` : undefined" @change="update(key, $event.target.checked)">
              </label>
              <p v-if="spec.help" :id="`rp-help-${key}`" class="help">{{ spec.help }}</p>
            </template>
            <template v-else>
              <label :for="`rp-${key}`">{{ spec.label || key }}<span v-if="spec.required" class="required">（必填）</span></label>
              <div v-if="spec.type === 'password' || spec.secret" class="secret-input">
                <input :id="`rp-${key}`" :type="visibleSecrets[key] ? 'text' : 'password'" :value="values[key] ?? ''" :disabled="busy || (key === 'device_token' && secretSyncRequired)" autocomplete="off" :aria-describedby="`rp-help-${key}`" @input="update(key, $event.target.value)">
                <button type="button" class="eye" :disabled="busy || (key === 'device_token' && secretSyncRequired)" :aria-label="`${visibleSecrets[key] ? '隐藏' : '查看'}${spec.label}`" :aria-pressed="!!visibleSecrets[key]" @click="toggleSecret(key)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path v-if="visibleSecrets[key]" d="m3 3 18 18"/>
                  </svg>
                </button>
              </div>
              <textarea v-else-if="spec.type === 'text'" :id="`rp-${key}`" rows="4" :value="values[key] ?? ''" :disabled="busy" :aria-describedby="`rp-help-${key}`" @input="update(key, $event.target.value)" />
              <select v-else-if="spec.type === 'select'" :id="`rp-${key}`" :value="values[key]" :disabled="busy" :aria-describedby="`rp-help-${key}`" @change="selectChange(key, spec, $event)">
                <option v-if="emptySelect(key, spec)" :value="values[key]" disabled>请选择（当前设置未选择有效选项）</option>
                <option v-for="option in options(spec)" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
              </select>
              <input v-else-if="spec.type === 'number'" :id="`rp-${key}`" type="number" :min="spec.min" :max="spec.max" :step="spec.step ?? 1" :value="values[key] ?? ''" :disabled="busy" :aria-describedby="`rp-help-${key}`" :aria-invalid="!!errors[key]" @input="update(key, $event.target.value === '' ? '' : Number($event.target.value))">
              <input v-else :id="`rp-${key}`" type="text" :value="values[key] ?? ''" :disabled="busy" :aria-describedby="`rp-help-${key}`" :aria-invalid="!!errors[key]" @input="update(key, $event.target.value)">
              <p v-if="spec.help" :id="`rp-help-${key}`" class="help">{{ spec.help }}</p>
              <p v-if="errors[key]" class="field-error" role="alert">{{ errors[key] }}</p>
            </template>
          </div>
        </div>
      </section>

      <ToolResult v-if="result && !result.key" :key="result.message" :result="result" :busy="!!acting" />

      <div class="toolbar bottom">
        <p class="muted">{{ dirty ? '设置已修改，尚未保存。' : '保存会保留已有设置；不会自动发送打印任务。' }}</p>
        <button type="submit" class="button primary" :disabled="busy || secretSyncRequired">{{ saving ? '正在保存…' : '保存配置' }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.print-config { color: var(--text-primary, #e8eaf0); font-size: 14px; line-height: 1.6; min-width: 0; }
form { display: flex; flex-direction: column; gap: 24px; }
p, h3, h4 { margin: 0; }
h3 { font-size: 15px; font-weight: 600; }
h4, label { font-size: 14px; font-weight: 600; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.toolbar p { min-width: 0; }
.muted, .help { color: var(--text-secondary, #b6bdcd); }
.help { font-size: 13px; line-height: 1.65; margin-top: 7px; overflow-wrap: anywhere; white-space: pre-wrap; }
.section { display: flex; flex-direction: column; gap: 16px; }
.section > h3 { padding-bottom: 10px; border-bottom: 1px solid var(--border, #394153); }
.fields { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 20px 16px; align-items: start; }
.field { min-width: 0; }
.field > label { display: block; margin-bottom: 8px; }
.info { margin-top: 7px; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-secondary, #b6bdcd); }
input:not([type=checkbox]), textarea, select { box-sizing: border-box; width: 100%; min-height: 42px; border: 1px solid var(--border, #394153); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #202633); color: var(--text-primary, #e8eaf0); padding: 9px 12px; font: inherit; caret-color: var(--accent, #82aaff); }
textarea { resize: vertical; line-height: 1.65; }
.button { min-height: 42px; padding: 8px 14px; border: 1px solid var(--border, #394153); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #202633); color: var(--text-primary, #e8eaf0); font: inherit; font-weight: 500; cursor: pointer; flex-shrink: 0; text-wrap: balance; }
.button:hover:not(:disabled) { border-color: var(--accent, #82aaff); }
.primary { color: var(--accent, #82aaff); border-color: var(--accent, #82aaff); background: var(--accent-dim, #243047); }
.danger { color: var(--danger, #ff8e96); }
button:disabled, input:disabled, select:disabled, textarea:disabled { opacity: .58; cursor: not-allowed; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid var(--accent, #82aaff); outline-offset: 3px; }
.switch-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 38px; cursor: pointer; }
.switch-row input { appearance: none; width: 40px; height: 24px; border-radius: 12px; border: 1px solid var(--border, #64748b); background: var(--bg-elevated, #202633); position: relative; flex-shrink: 0; cursor: pointer; }
.switch-row input::before { content: ''; position: absolute; width: 16px; height: 16px; top: 3px; inset-inline-start: 3px; border-radius: 50%; background: var(--text-secondary, #b6bdcd); }
.switch-row input:checked { background: var(--accent, #82aaff); border-color: var(--accent, #82aaff); }
.switch-row input:checked::before { inset-inline-start: 19px; background: var(--bg-elevated, #202633); }
.secret-input { position: relative; }
.secret-input input { padding-inline-end: 52px; }
.eye { position: absolute; top: 1px; inset-inline-end: 1px; width: 42px; height: calc(100% - 2px); border: 0; border-radius: var(--radius-sm, 8px); background: transparent; color: var(--text-secondary, #b6bdcd); display: grid; place-items: center; cursor: pointer; }
.eye svg { width: 21px; height: 21px; }
.eye:hover:not(:disabled) { color: var(--accent, #82aaff); }
.state, .confirm { padding: 16px; border: 1px solid var(--border, #394153); border-radius: var(--radius-sm, 8px); }
.state, .confirm { display: flex; flex-direction: column; align-items: flex-start; gap: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
.confirm { margin-top: 12px; }
.button-row { display: flex; flex-wrap: wrap; gap: 10px; }
.notice { white-space: pre-wrap; overflow-wrap: anywhere; }
.error, .field-error, .required { color: var(--danger, #ff8e96); }
.field-error { margin-top: 6px; font-size: 13px; }
[aria-invalid=true] { border-color: var(--danger, #ff8e96) !important; }
::selection { background: var(--accent-dim, #243047); color: var(--text-primary, #e8eaf0); }
@media (max-width: 768px) {
  .print-config { font-size: 16px; }
  .fields { grid-template-columns: minmax(0, 1fr); }
  .field { grid-column: 1 / -1 !important; }
  .toolbar { flex-wrap: wrap; align-items: flex-start; }
  .toolbar .button { width: 100%; }
  .button { max-width: 100%; }
  .help { font-size: 14px; }
  input:not([type=checkbox]), textarea, select { font-size: 16px; }
}
@media (forced-colors: active) {
  .switch-row input:checked { background: Highlight; }
  .switch-row input::before { background: ButtonText; }
  .switch-row input:checked::before { background: HighlightText; }
}
</style>
