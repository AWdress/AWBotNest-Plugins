<script setup>
import { onMounted, reactive, ref } from 'vue'
const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const defaults = { enabled: false, notify: true, accounts: [], delay: 3, cron: '5 8 * * *', timeout: 30 }
const form = reactive({ ...defaults })
const visible = reactive({})
const loading = ref(true); const saving = ref(false); const running = ref(false); const message = ref('')
function toast(type, text) { props.host.toast?.[type]?.(text) }
function normalize(value) {
  if (typeof value === 'string') {
    try { value = JSON.parse(value) } catch { return [] }
  }
  if (!Array.isArray(value)) return []
  return value.map((item) => ({ name: String(item?.name || '百度账号'), cookie: String(item?.cookie || '') }))
}
async function load() {
  loading.value = true; message.value = ''
  try {
    const saved = await props.host.getConfig()
    Object.assign(form, defaults, saved || {})
    form.accounts = saved?.accounts === '********' ? normalize(await props.host.revealSecret('accounts')) : normalize(saved?.accounts)
  } catch (error) { message.value = `读取配置失败：${error.message || error}` }
  finally { loading.value = false }
}
function add() { form.accounts.push({ name: `百度账号 ${form.accounts.length + 1}`, cookie: '' }) }
function remove(index) { form.accounts.splice(index, 1); delete visible[index] }
function validate() {
  const bad = form.accounts.findIndex((item) => !item.name.trim() || !item.cookie.trim())
  if (bad >= 0) { toast('error', `账号 ${bad + 1} 的名称或 Cookie 未填写完整`); return false }
  return true
}
async function save() {
  if (!validate()) return
  saving.value = true
  try { await props.host.saveConfig(JSON.parse(JSON.stringify(form))); toast('success', '配置已保存并应用') }
  catch (error) { toast('error', `保存失败：${error.message || error}`) }
  finally { saving.value = false }
}
async function run() {
  if (running.value || !validate()) return
  running.value = true
  try { const result = await props.host.callApi('/run', { method: 'POST', body: {} }); toast(result?.ok === false ? 'error' : 'success', result?.message || '签到任务已完成') }
  catch (error) { toast('error', `启动失败：${error.message || error}`) }
  finally { running.value = false }
}
onMounted(load)
</script>
<template>
  <main class="config-shell">
    <header><div><h2>百度贴吧签到</h2><p>Cookie 默认隐藏，可单独点击眼睛查看。</p></div></header>
    <p v-if="message" class="alert">{{ message }}</p>
    <section><div class="section-head"><div><h3>贴吧账号</h3><p>每个账号单独配置 Cookie。</p></div><button type="button" :disabled="loading" @click="add">添加账号</button></div>
      <div v-if="loading" class="empty">正在读取账号配置…</div>
      <div v-else-if="!form.accounts.length" class="empty">尚未添加账号，点击“添加账号”开始配置。</div>
      <article v-for="(account, index) in form.accounts" v-else :key="index" class="account-row"><b>{{ index + 1 }}</b><label>名称<input v-model.trim="account.name" placeholder="百度账号"></label><label class="wide">Cookie<div class="secret"><input v-model="account.cookie" :type="visible[index] ? 'text' : 'password'" placeholder="BDUSS=...; STOKEN=..."><button type="button" @click="visible[index] = !visible[index]">{{ visible[index] ? '隐藏' : '显示' }}</button></div></label><button type="button" class="remove" @click="remove(index)">删除</button></article>
    </section>
    <section><h3>功能与定时</h3><div class="grid"><label>启用自动签到<input v-model="form.enabled" type="checkbox"></label><label>推送签到结果<input v-model="form.notify" type="checkbox"></label><label>贴吧间隔（秒）<input v-model.number="form.delay" type="number" min="0" max="15"></label><label>请求超时（秒）<input v-model.number="form.timeout" type="number" min="5" max="120"></label><label class="wide">签到 Cron<input v-model.trim="form.cron" placeholder="5 8 * * *"></label></div></section>
    <footer><button type="button" :disabled="saving || loading" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button><button type="button" :disabled="running || loading || !form.accounts.length" @click="run">{{ running ? '执行中…' : '立即签到' }}</button></footer>
  </main>
</template>
<style scoped>
.config-shell{max-width:900px;margin:auto;padding:20px;color:var(--text,#e8edf5)}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}h2,h3{margin:0 0 6px}p{margin:0;color:var(--muted,#9aa5b5);font-size:13px}section{border:1px solid var(--border,#303846);border-radius:10px;padding:16px;margin:12px 0;background:var(--panel,#151b24)}.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.account-row{display:grid;grid-template-columns:28px 1fr 2fr auto;gap:10px;align-items:end;padding:10px 0;border-top:1px solid var(--border,#303846)}label{display:flex;flex-direction:column;gap:5px;font-size:13px}.wide{grid-column:span 1}input{box-sizing:border-box;width:100%;padding:8px;border:1px solid var(--border,#3a4555);border-radius:6px;background:var(--input,#0f141c);color:inherit}.secret{display:flex;gap:6px}.secret input{flex:1}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.grid label:nth-child(-n+2){flex-direction:row;justify-content:space-between;align-items:center}button{border:1px solid var(--border,#3a4555);border-radius:6px;background:var(--button,#253044);color:inherit;padding:8px 13px;cursor:pointer}.remove{background:#542b35}footer{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}.empty,.alert{padding:12px;border-radius:6px;background:#202a38}.alert{color:#ffb4b4}@media(max-width:650px){.account-row,.grid{grid-template-columns:1fr}.account-row>b{display:none}}
</style>
