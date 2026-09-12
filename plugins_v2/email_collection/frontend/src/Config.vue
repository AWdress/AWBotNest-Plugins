<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({pluginId: String, host: {type: Object, required: true}})
const providers = [
  {value: 'qq', label: 'QQ 邮箱', hint: '使用 IMAP 授权码'},
  {value: '163', label: '163 邮箱', hint: '使用客户端授权密码'},
  {value: '126', label: '126 邮箱', hint: '使用客户端授权密码'},
  {value: 'gmail', label: 'Gmail', hint: '使用 Google 应用专用密码'},
  {value: 'outlook', label: 'Outlook', hint: '使用应用密码或可用的 IMAP 密码'},
  {value: 'sina', label: '新浪邮箱', hint: '使用客户端授权码'},
]
const defaults = {
  enabled: false,
  push_all: false,
  mailboxes: [],
  keywords: '验证码|重要通知|账单|订单',
  poll_seconds: 30,
  manual_check_limit: 100,
  ai_verification: false,
  ai_summary_enabled: false,
  verification_prompt: '',
  summary_prompt: '',
  ai_timeout: 60,
}
const form = reactive({...defaults})
const visible = reactive({})
const loading = ref(true)
const saving = ref(false)
const checking = ref(false)
const running = ref(false)
const loadError = ref('')
const lastResult = ref('')
const savedSnapshot = ref('')
let timer

function toast(type, message) { props.host.toast?.[type]?.(message) }
function normalizeMailboxes(value) {
  if (Array.isArray(value)) {
    return value.map((item) => ({
      provider: String(item?.provider || 'qq'),
      email: String(item?.email || ''),
      password: String(item?.password || ''),
    }))
  }
  if (typeof value !== 'string' || !value.trim() || value === '********') return []
  const domainProvider = {'qq.com': 'qq', '163.com': '163', '126.com': '126', 'gmail.com': 'gmail', 'outlook.com': 'outlook', 'hotmail.com': 'outlook', 'live.com': 'outlook', 'sina.com': 'sina', 'sina.cn': 'sina'}
  return value.split(/(?:\r?\n|\s+&\s+)/).map((line) => {
    const at = line.indexOf('|')
    if (at < 0) return null
    const email = line.slice(0, at).trim()
    const password = line.slice(at + 1).trim()
    const provider = domainProvider[email.split('@').pop()?.toLowerCase()] || 'qq'
    return email && password ? {provider, email, password} : null
  }).filter(Boolean)
}
function addMailbox() { form.mailboxes.push({provider: 'qq', email: '', password: ''}) }
function removeMailbox(index) { form.mailboxes.splice(index, 1); delete visible[index] }
function providerHint(value) { return providers.find((item) => item.value === value)?.hint || '' }
function snapshot() { return JSON.stringify(form) }
function validate() {
  const incomplete = form.mailboxes.findIndex((item) => !item.provider || !item.email.trim() || !item.password)
  if (incomplete >= 0) {
    toast('error', `邮箱 ${incomplete + 1} 的类型、地址或授权码未填写完整`)
    return false
  }
  return true
}
async function refreshStatus() {
  try { running.value = Boolean((await props.host.callApi('/status'))?.running) } catch {}
}
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const saved = await props.host.getConfig()
    Object.assign(form, defaults, saved || {})
    if (saved?.mailboxes === '********') {
      form.mailboxes = normalizeMailboxes(await props.host.revealSecret('mailboxes'))
    } else {
      form.mailboxes = normalizeMailboxes(saved?.mailboxes)
    }
    savedSnapshot.value = snapshot()
  } catch (error) {
    loadError.value = `读取邮箱配置失败：${error.message || error}`
  } finally {
    loading.value = false
  }
  await refreshStatus()
  timer = setInterval(refreshStatus, 3000)
}
async function save(showToast = true) {
  if (loadError.value) {
    toast('error', '邮箱配置尚未成功读取，请刷新后重试')
    return false
  }
  if (!validate()) return false
  saving.value = true
  try {
    await props.host.saveConfig(JSON.parse(JSON.stringify(form)))
    savedSnapshot.value = snapshot()
    if (showToast) toast('success', '配置已保存并应用')
    return true
  } catch (error) {
    toast('error', `保存失败：${error.message || error}`)
    return false
  } finally {
    saving.value = false
  }
}
async function checkNow() {
  if (checking.value || running.value) return
  if (!validate()) return
  if (snapshot() !== savedSnapshot.value) {
    lastResult.value = '配置有未保存的修改，请先保存配置，待插件重载后再点击立即检查。'
    toast('error', lastResult.value)
    return
  }
  checking.value = true
  lastResult.value = ''
  try {
    const result = await props.host.callApi('/check', {method: 'POST', body: {}})
    lastResult.value = result.message || '检查完成'
    toast(result.ok === false ? 'error' : 'success', lastResult.value)
  } catch (error) {
    lastResult.value = `检查失败：${error.message || error}`
    toast('error', lastResult.value)
  } finally {
    checking.value = false
    await refreshStatus()
  }
}

onMounted(load)
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <main class="config-shell">
    <header class="page-head">
      <div>
        <h2>邮件集</h2>
        <p>后台按间隔检查未读邮件；立即检查会回查近期已读和未读邮件。</p>
      </div>
      <span class="state" :class="{busy: running || checking}">{{ running || checking ? '检查中' : '就绪' }}</span>
    </header>

    <p v-if="loadError" class="alert" role="alert">{{ loadError }}</p>

    <section aria-labelledby="mailboxes-title">
      <div class="section-head">
        <div><h3 id="mailboxes-title">邮箱账号</h3><p>每个邮箱单独选择服务商，授权码默认隐藏。</p></div>
        <button class="secondary" type="button" :disabled="loading" @click="addMailbox">添加邮箱</button>
      </div>
      <div v-if="loading" class="empty">正在安全读取邮箱配置…</div>
      <div v-else-if="!form.mailboxes.length" class="empty">尚未添加邮箱，点击“添加邮箱”开始配置。</div>
      <div v-else class="mailbox-list">
        <article v-for="(mailbox, index) in form.mailboxes" :key="index" class="mailbox-row">
          <div class="row-number">{{ index + 1 }}</div>
          <label><span>邮箱类型</span><select v-model="mailbox.provider"><option v-for="provider in providers" :key="provider.value" :value="provider.value">{{ provider.label }}</option></select><small>{{ providerHint(mailbox.provider) }}</small></label>
          <label><span>邮箱地址</span><input v-model.trim="mailbox.email" type="email" autocomplete="username" placeholder="name@example.com"></label>
          <label><span>授权码或应用密码</span><div class="secret"><input v-model="mailbox.password" :type="visible[index] ? 'text' : 'password'" autocomplete="current-password" placeholder="不是网页登录密码"><button type="button" :aria-label="visible[index] ? '隐藏授权码' : '显示授权码'" @click="visible[index] = !visible[index]"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div></label>
          <button class="remove" type="button" @click="removeMailbox(index)">删除</button>
        </article>
      </div>
    </section>

    <section aria-labelledby="monitor-title">
      <h3 id="monitor-title">监控与过滤</h3>
      <div class="switch-grid">
        <label><span>启用后台监控</span><input v-model="form.enabled" type="checkbox"></label>
        <label><span>全部邮件都推送</span><input v-model="form.push_all" type="checkbox"></label>
      </div>
      <div class="form-grid monitor-grid">
        <label class="wide"><span>关键词（用 | 分隔）</span><input v-model.trim="form.keywords" type="text" placeholder="验证码|重要通知|账单|订单"></label>
        <label><span>轮询间隔（秒）</span><input v-model.number="form.poll_seconds" type="number" min="10" max="300"></label>
        <label><span>立即检查回查数量</span><input v-model.number="form.manual_check_limit" type="number" min="1" max="500"></label>
      </div>
    </section>

    <section aria-labelledby="ai-title">
      <h3 id="ai-title">AI 处理</h3>
      <div class="switch-grid">
        <label><span>AI 验证码识别</span><input v-model="form.ai_verification" type="checkbox"></label>
        <label><span>AI 邮件概要</span><input v-model="form.ai_summary_enabled" type="checkbox"></label>
      </div>
      <div class="form-grid">
        <label class="wide"><span>验证码提示词</span><textarea v-model="form.verification_prompt" rows="3" placeholder="留空使用内置提示词"></textarea></label>
        <label class="wide"><span>概要提示词</span><textarea v-model="form.summary_prompt" rows="3" placeholder="留空使用内置提示词"></textarea></label>
        <label><span>AI 超时（秒）</span><input v-model.number="form.ai_timeout" type="number" min="10" max="180"></label>
      </div>
    </section>

    <p v-if="lastResult" class="result" aria-live="polite">{{ lastResult }}</p>
    <footer class="actions">
      <button class="secondary" type="button" :disabled="checking || running || saving || loading || !form.mailboxes.length" @click="checkNow">{{ checking || running ? '正在检查…' : '立即检查' }}</button>
      <button class="primary" type="button" :disabled="saving || checking || loading || !!loadError" @click="save()">{{ saving ? '正在保存…' : '保存配置' }}</button>
    </footer>
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.config-shell{color:var(--text-primary,#e8edf5);padding:4px 2px max(18px,env(safe-area-inset-bottom));display:grid;gap:28px;min-width:0}.page-head,.section-head,.actions{display:flex;align-items:center;justify-content:space-between;gap:18px}.page-head{padding-bottom:20px;border-bottom:1px solid var(--border,#263244)}h2,h3,p{margin:0}h2{font-size:22px;letter-spacing:-.02em}h3{font-size:14px;color:var(--accent,#4f9cff);margin-bottom:14px}.page-head p,.section-head p{margin-top:7px;color:var(--text-muted,#9aa6b8);font-size:13px;line-height:1.55}.state{flex:0 0 auto;font-size:12px;color:#9ee2b9;background:#153224;padding:7px 12px;border-radius:999px}.state.busy{color:#b6d3ff;background:#172d4d}.alert,.result{padding:13px 14px;border:1px solid #743b43;border-radius:12px;background:#2b171b;color:#ffc2c9;overflow-wrap:anywhere}.result{border-color:#315c4c;background:#10231f;color:#aee4c7}.switch-grid,.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:14px}.switch-grid label{display:flex;justify-content:space-between;align-items:center;min-height:48px;padding:13px 14px;border:1px solid var(--border,#263244);border-radius:12px;background:var(--bg-elevated,#121b28)}input[type=checkbox]{width:20px;height:20px;accent-color:var(--accent,#338cff)}button,input,select,textarea{font:inherit}.secondary,.primary,.remove{min-height:44px;border:1px solid var(--border,#314057);border-radius:10px;padding:9px 14px;color:inherit;background:var(--bg-elevated,#152031);cursor:pointer}.section-head .secondary{flex:0 0 auto;min-width:96px}.primary{background:var(--accent,#287ff0);border-color:var(--accent,#287ff0);color:#fff}.remove{color:#ffadb6;background:transparent;align-self:end}.mailbox-list{display:grid;gap:12px}.mailbox-row{display:grid;grid-template-columns:32px minmax(145px,.7fr) minmax(190px,1fr) minmax(190px,1fr) auto;align-items:start;gap:12px;padding:14px;border:1px solid var(--border,#263244);border-radius:14px;background:var(--bg-elevated,#111a27)}.row-number{margin-top:25px;width:28px;height:28px;display:grid;place-items:center;border-radius:8px;background:#1b2b42;color:#9bc3ff;font-variant-numeric:tabular-nums}label>span{display:block;margin-bottom:7px;font-size:12px;color:var(--text-muted,#a2adbc)}label small{display:block;margin-top:6px;color:var(--text-muted,#9aa6b8);font-size:11px;line-height:1.4}input:not([type=checkbox]),select,textarea{width:100%;border:1px solid var(--border,#314057);border-radius:10px;background:var(--bg-input,#0c1420);color:inherit;padding:0 12px;outline:none}input:not([type=checkbox]),select{height:44px}textarea{padding-block:10px;resize:vertical;line-height:1.5}input:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible{border-color:var(--accent,#338cff);outline:3px solid color-mix(in srgb,var(--accent,#338cff) 24%,transparent);outline-offset:1px}.secret{position:relative}.secret input{padding-right:48px}.secret button{position:absolute;inset-inline-end:0;top:0;width:44px;height:44px;border:0;background:transparent;color:#9aa7b9;cursor:pointer}.secret svg{width:19px;fill:none;stroke:currentColor;stroke-width:1.8}.empty{padding:22px;border:1px dashed var(--border,#314057);border-radius:12px;color:var(--text-muted,#a2adbc);text-align:center}.form-grid label{min-width:0}.form-grid .wide{grid-column:span 2}.actions{padding:16px 0 max(4px,env(safe-area-inset-bottom));justify-content:flex-end}button:disabled{opacity:.5;cursor:not-allowed}@media(hover:hover){button:not(:disabled):hover{border-color:var(--accent,#338cff)}}@media(max-width:820px){.mailbox-row{grid-template-columns:32px 1fr}.mailbox-row label,.mailbox-row .remove{grid-column:2}.mailbox-row .remove{justify-self:start}.row-number{grid-row:1/span 4}.form-grid,.switch-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}}@media(max-width:520px){.config-shell{gap:24px}.page-head,.section-head{align-items:flex-start}.page-head p{max-width:28ch}.mailbox-row{padding:12px;gap:10px}.actions{display:grid;grid-template-columns:1fr 1fr}.actions button{width:100%}}@media(pointer:coarse){.secondary,.primary,.remove,.secret button,input:not([type=checkbox]),select{min-height:48px}}@media(forced-colors:active){button,input,select,textarea,.mailbox-row{border:1px solid CanvasText}}
</style>
