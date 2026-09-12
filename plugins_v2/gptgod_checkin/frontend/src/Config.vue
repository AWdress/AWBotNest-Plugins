<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({pluginId: String, host: {type: Object, required: true}})
const CronInput = computed(() => props.host.ui.CronInput)
const defaults = {
  auto_checkin: true, notify: true, auto_retry: true, accounts: [],
  schedule_mode: 'daily', checkin_hour: 8, checkin_minute: 5,
  cron_expression: '5 8 * * *', retry_count: 2, retry_interval: 20,
}
const form = reactive({...defaults})
const status = reactive({running: false, last_result: null, history: []})
const visible = reactive({})
const loading = ref(true)
const saving = ref(false)
const running = ref(false)
const loadError = ref('')
let timer

function toast(type, message) { props.host.toast?.[type]?.(message) }
function normalizeAccounts(value) {
  if (Array.isArray(value)) return value.map((item) => ({email: String(item?.email || ''), password: String(item?.password || '')}))
  if (typeof value !== 'string' || !value.trim() || value === '********') return []
  return value.split(/(?:\r?\n|\s+&\s+)/).map((item) => {
    const at = item.indexOf('----')
    return at < 0 ? null : {email: item.slice(0, at).trim(), password: item.slice(at + 4).trim()}
  }).filter((item) => item?.email && item?.password)
}
function addAccount() { form.accounts.push({email: '', password: ''}) }
function removeAccount(index) { form.accounts.splice(index, 1); delete visible[index] }

async function refresh() {
  try { Object.assign(status, await props.host.callApi('/status')) } catch {}
}
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const saved = await props.host.getConfig()
    Object.assign(form, defaults, saved || {})
    if (saved?.accounts === '********') {
      const accounts = await props.host.revealSecret('accounts')
      form.accounts = normalizeAccounts(accounts)
    } else {
      form.accounts = normalizeAccounts(saved?.accounts)
    }
  } catch (error) {
    loadError.value = `读取账号配置失败：${error.message || error}`
  } finally {
    loading.value = false
  }
  await refresh()
  timer = setInterval(refresh, 3000)
}
async function save() {
  if (loadError.value) return toast('error', '账号配置尚未成功读取，请刷新后重试')
  const incomplete = form.accounts.findIndex((item) => !item.email.trim() || !item.password)
  if (incomplete >= 0) return toast('error', `账号 ${incomplete + 1} 的邮箱或密码未填写完整`)
  saving.value = true
  try {
    await props.host.saveConfig(JSON.parse(JSON.stringify(form)))
    toast('success', '配置已保存并应用')
  } catch (error) {
    toast('error', `保存失败：${error.message || error}`)
  } finally { saving.value = false }
}
async function runNow() {
  if (running.value || status.running) return
  running.value = true
  try {
    const result = await props.host.callApi('/run', {method: 'POST'})
    toast(result.ok === false ? 'error' : 'success', result.message || '签到已开始')
    await refresh()
  } catch (error) {
    toast('error', `启动失败：${error.message || error}`)
  } finally { running.value = false }
}

onMounted(load)
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <main class="config-shell">
    <header class="page-head">
      <div>
        <h2>GPT-GOD 自动签到</h2>
        <p>逐个管理签到账号，密码默认隐藏并由平台受控保存。</p>
      </div>
      <span class="state" :class="{busy: status.running}">{{ status.running ? '签到中' : '就绪' }}</span>
    </header>

    <p v-if="loadError" class="alert" role="alert">{{ loadError }}</p>

    <section aria-labelledby="switches-title">
      <h3 id="switches-title">功能开关</h3>
      <div class="switch-grid">
        <label><span>启用自动签到</span><input v-model="form.auto_checkin" type="checkbox"></label>
        <label><span>推送签到结果</span><input v-model="form.notify" type="checkbox"></label>
        <label><span>失败后自动重试</span><input v-model="form.auto_retry" type="checkbox"></label>
      </div>
    </section>

    <section aria-labelledby="accounts-title">
      <div class="section-head">
        <div><h3 id="accounts-title">签到账号</h3><p>一个账号一行，支持独立添加和删除。</p></div>
        <button class="secondary" type="button" :disabled="loading" @click="addAccount">添加账号</button>
      </div>
      <div v-if="loading" class="empty">正在安全读取账号配置…</div>
      <div v-else-if="!form.accounts.length" class="empty">尚未添加账号，点击“添加账号”开始配置。</div>
      <div v-else class="account-list">
        <article v-for="(account, index) in form.accounts" :key="index" class="account-row">
          <div class="row-number">{{ index + 1 }}</div>
          <label><span>登录邮箱</span><input v-model.trim="account.email" type="email" autocomplete="username" placeholder="name@example.com"></label>
          <label><span>账户密码</span><div class="secret"><input v-model="account.password" :type="visible[index] ? 'text' : 'password'" autocomplete="current-password" placeholder="GPT-GOD 账户密码"><button type="button" :aria-label="visible[index] ? '隐藏密码' : '显示密码'" @click="visible[index] = !visible[index]"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div></label>
          <button class="remove" type="button" @click="removeAccount(index)">删除</button>
        </article>
      </div>
    </section>

    <section aria-labelledby="schedule-title">
      <h3 id="schedule-title">定时与重试</h3>
      <div class="form-grid">
        <label><span>定时方式</span><select v-model="form.schedule_mode"><option value="daily">每天指定时间</option><option value="cron">Cron 表达式</option></select></label>
        <template v-if="form.schedule_mode === 'daily'">
          <label><span>签到小时</span><input v-model.number="form.checkin_hour" type="number" min="0" max="23"></label>
          <label><span>签到分钟</span><input v-model.number="form.checkin_minute" type="number" min="0" max="59"></label>
        </template>
        <label v-else class="wide"><span>Cron 表达式</span><component :is="CronInput" v-model="form.cron_expression" /></label>
        <label><span>失败重试次数</span><input v-model.number="form.retry_count" type="number" min="0" max="5"></label>
        <label><span>重试间隔（秒）</span><input v-model.number="form.retry_interval" type="number" min="5" max="300" step="5"></label>
      </div>
    </section>

    <footer class="actions">
      <button class="secondary" type="button" :disabled="running || status.running || !form.accounts.length" @click="runNow">{{ running || status.running ? '签到进行中…' : '立即签到' }}</button>
      <button class="primary" type="button" :disabled="saving || loading || !!loadError" @click="save">{{ saving ? '正在保存…' : '保存配置' }}</button>
    </footer>
  </main>
</template>

<style scoped>
.config-shell{color:var(--text-primary,#e8edf5);padding:4px 2px 18px;display:grid;gap:28px;min-width:0}.page-head,.section-head,.actions{display:flex;align-items:center;justify-content:space-between;gap:18px}.page-head{padding-bottom:20px;border-bottom:1px solid var(--border,#263244)}h2,h3,p{margin:0}h2{font-size:22px;letter-spacing:-.02em}h3{font-size:14px;color:var(--accent,#4f9cff);margin-bottom:14px}.page-head p,.section-head p{margin-top:7px;color:var(--text-muted,#8591a3);font-size:13px}.state{font-size:12px;color:#8bd3a9;background:#153224;padding:6px 11px;border-radius:999px}.state.busy{color:#9fc5ff;background:#172d4d}.alert{padding:12px 14px;border:1px solid #743b43;border-radius:12px;background:#2b171b;color:#ffb8c0;overflow-wrap:anywhere}.switch-grid,.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.switch-grid label{display:flex;justify-content:space-between;align-items:center;padding:13px 14px;border:1px solid var(--border,#263244);border-radius:12px;background:var(--bg-elevated,#121b28)}input[type=checkbox]{width:18px;height:18px;accent-color:var(--accent,#338cff)}button,input,select{font:inherit}.secondary,.primary,.remove{border:1px solid var(--border,#314057);border-radius:10px;padding:9px 14px;color:inherit;background:var(--bg-elevated,#152031);cursor:pointer}.primary{background:var(--accent,#287ff0);border-color:var(--accent,#287ff0);color:#fff}.remove{color:#ff9aa5;background:transparent;padding:8px 11px}.account-list{display:grid;gap:10px}.account-row{display:grid;grid-template-columns:30px minmax(180px,1fr) minmax(180px,1fr) auto;align-items:end;gap:12px;padding:14px;border:1px solid var(--border,#263244);border-radius:14px;background:var(--bg-elevated,#111a27)}.row-number{align-self:center;width:26px;height:26px;display:grid;place-items:center;border-radius:8px;background:#1b2b42;color:#8dbbff;font-variant-numeric:tabular-nums}label>span{display:block;margin-bottom:7px;font-size:12px;color:var(--text-muted,#919daf)}input:not([type=checkbox]),select{box-sizing:border-box;width:100%;height:42px;border:1px solid var(--border,#314057);border-radius:10px;background:var(--bg-input,#0c1420);color:inherit;padding:0 12px;outline:none}input:focus,select:focus{border-color:var(--accent,#338cff);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent,#338cff) 20%,transparent)}.secret{position:relative}.secret input{padding-right:44px}.secret button{position:absolute;inset-inline-end:5px;top:5px;width:32px;height:32px;border:0;background:transparent;color:#8290a4;cursor:pointer}.secret svg{width:18px;fill:none;stroke:currentColor;stroke-width:1.8}.empty{padding:20px;border:1px dashed var(--border,#314057);border-radius:12px;color:var(--text-muted,#919daf);text-align:center}.form-grid label{min-width:0}.form-grid .wide{grid-column:span 2}.actions{padding-top:18px;border-top:1px solid var(--border,#263244);justify-content:flex-end}button:disabled{opacity:.5;cursor:not-allowed}@media(max-width:760px){.switch-grid,.form-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}.account-row{grid-template-columns:28px 1fr}.account-row label{grid-column:2}.account-row .remove{grid-column:2;justify-self:start}.page-head{align-items:flex-start}.section-head{align-items:flex-end}}@media(prefers-reduced-motion:no-preference){button{transition:background-color .16s ease-out,border-color .16s ease-out,opacity .16s ease-out}}@media(forced-colors:active){button,input,select,.account-row{border:1px solid CanvasText}}
</style>
