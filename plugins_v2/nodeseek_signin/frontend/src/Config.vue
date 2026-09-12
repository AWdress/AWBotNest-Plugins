<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({pluginId: String, host: {type: Object, required: true}})
const defaults = {
  enabled: false,
  notify: true,
  auto_save_cookie: true,
  cookies: '',
  accounts: [],
  browser_login: 'Cookie 失效时自动使用 CloakBrowser 完成验证并重新登录，无需第三方验证码服务。',
  random_reward: true,
  cron: '0 8 * * *',
  timeout: 30,
  captcha_timeout: 90,
  last_result: '尚未运行',
  history: '暂无记录',
}
const form = reactive({...defaults})
const visiblePasswords = reactive({})
const cookiesVisible = ref(false)
const loading = ref(true)
const saving = ref(false)
const running = ref(false)
const loadError = ref('')
const resultText = ref('')
const savedSnapshot = ref('')
let statusTimer

function toast(type, text) { props.host.toast?.[type]?.(text) }
function snapshot() { return JSON.stringify(form) }
function normalizeAccounts(value) {
  if (Array.isArray(value)) {
    return value.map((item) => ({
      user: String(item?.user || item?.username || ''),
      password: String(item?.password || ''),
    }))
  }
  if (typeof value !== 'string' || !value.trim() || value === '********') return []
  return value.split(/(?:\r?\n|\s+&\s+)/).map((line) => {
    const separator = ['----', '，', ',', '：', ':', '|', '\t'].find((item) => line.includes(item))
    if (!separator) return null
    const at = line.indexOf(separator)
    const user = line.slice(0, at).trim()
    const password = line.slice(at + separator.length).trim()
    return user && password ? {user, password} : null
  }).filter(Boolean)
}
function addAccount() { form.accounts.push({user: '', password: ''}) }
function removeAccount(index) {
  form.accounts.splice(index, 1)
  delete visiblePasswords[index]
}
function validate() {
  const incomplete = form.accounts.findIndex((item) => !item.user.trim() || !item.password)
  if (incomplete >= 0) {
    toast('error', '账号 ' + (incomplete + 1) + ' 的用户名或密码未填写完整')
    return false
  }
  return true
}
async function refreshStatus() {
  try {
    const status = await props.host.callApi('/status')
    running.value = Boolean(status?.running)
    if (status?.last_result) {
      const item = status.last_result
      form.last_result = (item['时间'] || '') + ' · 成功 ' + (item['成功'] || 0) + '/' + (item['总数'] || 0)
    }
    if (Array.isArray(status?.history) && status.history.length) {
      form.history = status.history.map((item) =>
        (item['时间'] || '') + ' · 成功 ' + (item['成功'] || 0) + '/' + (item['总数'] || 0)
      ).join('\n')
    }
  } catch {}
}
async function load() {
  loading.value = true
  try {
    const saved = await props.host.getConfig()
    Object.assign(form, defaults, saved || {})
    if (saved?.cookies === '********') form.cookies = String(await props.host.revealSecret('cookies') || '')
    if (saved?.accounts === '********') {
      form.accounts = normalizeAccounts(await props.host.revealSecret('accounts'))
    } else {
      form.accounts = normalizeAccounts(saved?.accounts)
    }
    savedSnapshot.value = snapshot()
  } catch (error) {
    loadError.value = '读取配置失败：' + (error.message || error)
  } finally {
    loading.value = false
  }
  await refreshStatus()
  statusTimer = setInterval(refreshStatus, 3000)
}
async function save() {
  if (loadError.value) return toast('error', '配置尚未成功读取，请刷新后重试')
  if (!validate()) return
  saving.value = true
  try {
    await props.host.saveConfig(JSON.parse(JSON.stringify(form)))
    savedSnapshot.value = snapshot()
    toast('success', '配置已保存并应用')
  } catch (error) {
    toast('error', '保存失败：' + (error.message || error))
  } finally {
    saving.value = false
  }
}
async function runNow() {
  if (running.value || saving.value || !validate()) return
  if (snapshot() !== savedSnapshot.value) {
    resultText.value = '配置有未保存的修改，请先保存，待插件重载后再立即签到。'
    return toast('error', resultText.value)
  }
  running.value = true
  resultText.value = ''
  try {
    const result = await props.host.callApi('/run', {method: 'POST', body: {}})
    resultText.value = result?.message || '签到任务已开始'
    toast(result?.ok === false ? 'error' : 'success', resultText.value)
  } catch (error) {
    resultText.value = '启动签到失败：' + (error.message || error)
    toast('error', resultText.value)
  } finally {
    await refreshStatus()
  }
}

onMounted(load)
onBeforeUnmount(() => clearInterval(statusTimer))
</script>

<template>
  <main class="config-shell">
    <header class="page-head">
      <div>
        <h2>NodeSeek 签到</h2>
        <p>Cookie 可直接签到；失效时使用对应账号密码通过 CloakBrowser 自动登录。</p>
      </div>
      <span class="state" :class="{busy: running}">{{ running ? '签到中' : '就绪' }}</span>
    </header>

    <p v-if="loadError" class="alert" role="alert">{{ loadError }}</p>

    <section aria-labelledby="account-title">
      <div class="section-head">
        <div>
          <h3 id="account-title">账号与 Cookie</h3>
          <p>账号逐个添加；多个 Cookie 仍用“ &amp; ”分隔，并与账号顺序对应。</p>
        </div>
        <button class="secondary" type="button" :disabled="loading" @click="addAccount">添加账号</button>
      </div>
      <label class="field wide">
        <span>NodeSeek Cookie（可选）</span>
        <div class="secret">
          <input v-model="form.cookies" :type="cookiesVisible ? 'text' : 'password'" autocomplete="off" placeholder="多个 Cookie 使用 & 分隔">
          <button type="button" :disabled="!form.cookies" :aria-label="cookiesVisible ? '隐藏 Cookie' : '显示 Cookie'" @click="cookiesVisible = !cookiesVisible">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <small>留空也可以，插件会使用下方账密登录并获取 Cookie。</small>
      </label>
      <div v-if="loading" class="empty">正在安全读取账号配置…</div>
      <div v-else-if="!form.accounts.length" class="empty">尚未添加登录账号。已有有效 Cookie 时可以不添加。</div>
      <div v-else class="account-list">
        <article v-for="(account, index) in form.accounts" :key="index" class="account-row">
          <div class="row-number">{{ index + 1 }}</div>
          <label class="field"><span>用户名或邮箱</span><input v-model.trim="account.user" type="text" autocomplete="username"></label>
          <label class="field">
            <span>密码</span>
            <div class="secret">
              <input v-model="account.password" :type="visiblePasswords[index] ? 'text' : 'password'" autocomplete="current-password">
              <button type="button" :disabled="!account.password" :aria-label="visiblePasswords[index] ? '隐藏密码' : '显示密码'" @click="visiblePasswords[index] = !visiblePasswords[index]">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </label>
          <button class="remove" type="button" @click="removeAccount(index)">删除</button>
        </article>
      </div>
    </section>

    <section aria-labelledby="switch-title">
      <h3 id="switch-title">功能开关</h3>
      <div class="switch-grid">
        <label><span>启用自动签到</span><input v-model="form.enabled" type="checkbox"></label>
        <label><span>发送签到通知</span><input v-model="form.notify" type="checkbox"></label>
        <label><span>自动回写新 Cookie</span><input v-model="form.auto_save_cookie" type="checkbox"></label>
        <label><span>随机鸡腿奖励</span><input v-model="form.random_reward" type="checkbox"></label>
      </div>
    </section>

    <section aria-labelledby="schedule-title">
      <h3 id="schedule-title">签到设置</h3>
      <div class="form-grid">
        <label class="field wide"><span>签到 Cron</span><input v-model.trim="form.cron" type="text"><small>标准五段 Cron，默认每天 08:00。</small></label>
        <label class="field"><span>请求超时（秒）</span><input v-model.number="form.timeout" type="number" min="5" max="120"></label>
        <label class="field"><span>浏览器验证超时（秒）</span><input v-model.number="form.captcha_timeout" type="number" min="30" max="300"></label>
      </div>
    </section>

    <section aria-labelledby="status-title">
      <h3 id="status-title">运行状态</h3>
      <div class="status-grid">
        <div><span>最近结果</span><p>{{ form.last_result || '尚未运行' }}</p></div>
        <div><span>最近记录</span><pre>{{ form.history || '暂无记录' }}</pre></div>
      </div>
    </section>

    <p v-if="resultText" class="result" aria-live="polite">{{ resultText }}</p>
    <footer class="actions">
      <button class="secondary" type="button" :disabled="running || saving || loading" @click="runNow">{{ running ? '签到中…' : '立即签到' }}</button>
      <button class="primary" type="button" :disabled="saving || running || loading || !!loadError" @click="save">{{ saving ? '正在保存…' : '保存配置' }}</button>
    </footer>
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.config-shell{color:var(--text-primary,#e8edf5);padding:4px 2px max(18px,env(safe-area-inset-bottom));display:grid;gap:28px;min-width:0}.page-head,.section-head,.actions{display:flex;align-items:center;justify-content:space-between;gap:18px}.page-head{padding-bottom:20px;border-bottom:1px solid var(--border,#263244)}h2,h3,p{margin:0}h2{font-size:22px;letter-spacing:-.02em}h3{font-size:14px;color:var(--accent,#4f9cff);margin-bottom:14px}.page-head p,.section-head p{margin-top:7px;color:var(--text-muted,#9aa6b8);font-size:13px;line-height:1.55}.state{flex:0 0 auto;font-size:12px;color:#9ee2b9;background:#153224;padding:7px 12px;border-radius:999px}.state.busy{color:#b6d3ff;background:#172d4d}.alert,.result{padding:13px 14px;border:1px solid #743b43;border-radius:12px;background:#2b171b;color:#ffc2c9;overflow-wrap:anywhere}.result{border-color:#315c4c;background:#10231f;color:#aee4c7}.wide{margin:16px 0}.field{display:block;min-width:0}.field>span,.status-grid span{display:block;margin-bottom:7px;color:var(--text-muted,#a2adbc);font-size:12px}.field small{display:block;margin-top:6px;color:var(--text-muted,#9aa6b8);font-size:11px;line-height:1.45}.account-list{display:grid;gap:12px}.account-row{display:grid;grid-template-columns:32px minmax(180px,1fr) minmax(180px,1fr) auto;align-items:end;gap:12px;padding:14px;border:1px solid var(--border,#263244);border-radius:14px;background:var(--bg-elevated,#111a27)}.row-number{align-self:center;width:28px;height:28px;display:grid;place-items:center;border-radius:8px;background:#1b2b42;color:#9bc3ff;font-variant-numeric:tabular-nums}.switch-grid,.form-grid,.status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.switch-grid label,.status-grid>div{display:flex;justify-content:space-between;align-items:center;min-height:48px;padding:13px 14px;border:1px solid var(--border,#263244);border-radius:12px;background:var(--bg-elevated,#121b28)}.status-grid>div{display:block}.status-grid p,.status-grid pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;color:inherit;font:inherit;line-height:1.5}.form-grid .wide{grid-column:span 2;margin:0}input[type=checkbox]{width:20px;height:20px;accent-color:var(--accent,#338cff)}button,input{font:inherit}input:not([type=checkbox]){width:100%;height:44px;border:1px solid var(--border,#314057);border-radius:10px;background:var(--bg-input,#0c1420);color:inherit;padding:0 12px;outline:none}.secret{position:relative}.secret input{padding-right:48px}.secret button{position:absolute;inset-inline-end:0;top:0;width:44px;height:44px;border:0;background:transparent;color:#9aa7b9;cursor:pointer}.secret svg{width:19px;fill:none;stroke:currentColor;stroke-width:1.8}.secondary,.primary,.remove{min-height:44px;border:1px solid var(--border,#314057);border-radius:10px;padding:9px 14px;color:inherit;background:var(--bg-elevated,#152031);cursor:pointer}.primary{background:var(--accent,#287ff0);border-color:var(--accent,#287ff0);color:#fff}.remove{color:#ffadb6;background:transparent}.empty{padding:20px;border:1px dashed var(--border,#314057);border-radius:12px;color:var(--text-muted,#a2adbc);text-align:center}input:focus-visible,button:focus-visible{border-color:var(--accent,#338cff);outline:3px solid color-mix(in srgb,var(--accent,#338cff) 24%,transparent);outline-offset:1px}.actions{padding-top:2px;justify-content:flex-end}button:disabled{opacity:.5;cursor:not-allowed}@media(hover:hover){button:not(:disabled):hover{border-color:var(--accent,#338cff)}}@media(max-width:760px){.account-row{grid-template-columns:32px 1fr}.account-row .field,.account-row .remove{grid-column:2}.row-number{grid-row:1/span 3}.switch-grid,.form-grid,.status-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}.section-head{align-items:flex-start}}@media(max-width:520px){.page-head{align-items:flex-start}.page-head p{max-width:28ch}.actions{display:grid;grid-template-columns:1fr 1fr}.actions button{width:100%}}@media(pointer:coarse){button,input:not([type=checkbox]){min-height:48px}}@media(forced-colors:active){button,input,.account-row{border:1px solid CanvasText}}
</style>
