<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: { type: String, required: true }, host: { type: Object, required: true } })
const config = reactive({ auto_checkin: true, notify_result: true, headless: true, checkin_hour: 8, checkin_minute: 10, retry_count: 2, retry_interval: 20, tjupt_ai_assist: true, tjupt_confirm_timeout: 300, selected_sites: [] })
const sites = ref([]), history = ref([]), cookieState = reactive({})
const status = reactive({ running: false, current: '', completed: 0, total: 0, finished_at: '' })
const loading = ref(true), saving = ref(false), checking = ref(false)
let timer
const groups = computed(() => Object.entries(sites.value.reduce((all, site) => ((all[site.group] ||= []).push(site), all), {})))
const progress = computed(() => status.total ? Math.round(status.completed / status.total * 100) : 0)

async function refresh() {
  Object.assign(status, await props.host.callApi('/status'))
  const data = await props.host.callApi('/history'); history.value = data.items || []
  if (!status.running && timer) { clearInterval(timer); timer = null }
}
async function load() {
  try {
    const [saved, meta] = await Promise.all([props.host.getConfig(), props.host.callApi('/meta')])
    Object.assign(config, meta.defaults || {}, saved || {})
    sites.value = meta.sites || []
    if (!Array.isArray(config.selected_sites)) config.selected_sites = sites.value.map(site => site.key)
    await refresh()
  } catch (error) { props.host.toast.error(`读取失败：${error.message || error}`) }
  finally { loading.value = false }
}
async function save() {
  saving.value = true
  try { await props.host.saveConfig({ ...config, selected_sites: [...config.selected_sites] }); props.host.toast.success('配置已保存') }
  catch (error) { props.host.toast.error(`保存失败：${error.message || error}`) }
  finally { saving.value = false }
}
async function run() {
  const result = await props.host.callApi('/run', { method: 'POST' })
  result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message)
  await refresh(); if (!timer) timer = setInterval(refresh, 2500)
}
async function checkCookies() {
  checking.value = true
  try { const data = await props.host.callApi('/cookies/check'); (data.items || []).forEach(item => { cookieState[item.key] = item }); props.host.toast[data.ok ? 'success' : 'warning'](data.ok ? '所选站点 Cookie 均可用' : '部分站点 Cookie 不可用') }
  catch (error) { props.host.toast.error(`检查失败：${error.message || error}`) }
  finally { checking.value = false }
}
function toggleGroup(items, enabled) { const keys = new Set(config.selected_sites); items.forEach(site => enabled ? keys.add(site.key) : keys.delete(site.key)); config.selected_sites = [...keys] }
async function clearHistory() { const result = await props.host.callApi('/history/clear', { method: 'POST' }); if (result.ok) { history.value = []; props.host.toast.success(result.message) } }
onMounted(load); onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <!-- Design contract: PT-SIGNIN-OPERATE-2. Dense operations console with restrained blue accent, flat grouped rows, visible progress and practical controls. Avoid decorative gradients, card grids, oversized headings, pill-heavy styling, hidden critical state, and manual credential fields. -->
  <div class="console" v-if="!loading">
    <header class="mast">
      <div><p class="eyebrow">PT AUTOMATION</p><h2>签到控制台</h2><p>统一使用平台同步 Cookie · {{ config.selected_sites.length }} / {{ sites.length }} 个站点已启用</p></div>
      <div class="mast-actions"><button class="secondary" :disabled="checking" @click="checkCookies">{{ checking ? '检查中…' : '检查 Cookie' }}</button><button class="primary" :disabled="status.running || !config.selected_sites.length" @click="run">{{ status.running ? '签到进行中' : '立即签到' }}</button></div>
    </header>

    <section v-if="status.running || status.finished_at" class="runline" aria-live="polite">
      <div class="run-copy"><b>{{ status.running ? `正在处理 ${status.current}` : '最近任务已完成' }}</b><span>{{ status.completed }} / {{ status.total }} · {{ progress }}%</span></div>
      <div class="bar"><i :style="{ width: `${progress}%` }"></i></div>
    </section>

    <section class="settings">
      <label class="switch"><input v-model="config.auto_checkin" type="checkbox"><span>每日自动签到</span></label>
      <label class="switch"><input v-model="config.notify_result" type="checkbox"><span>推送签到结果</span></label>
      <label class="switch"><input v-model="config.headless" type="checkbox"><span>后台浏览器</span></label>
      <label>执行时间 <span class="time"><input v-model.number="config.checkin_hour" type="number" min="0" max="23">:<input v-model.number="config.checkin_minute" type="number" min="0" max="59"></span></label>
      <label>失败重试 <input v-model.number="config.retry_count" type="number" min="0" max="5"></label>
      <label>间隔（秒） <input v-model.number="config.retry_interval" type="number" min="5" max="300"></label>
    </section>

    <div class="section-head"><div><h3>站点范围</h3><p>交互验证站会在无法安全识别时明确提示，不会随机提交。</p></div><button class="secondary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
    <section class="site-list">
      <div v-for="[group, items] in groups" :key="group" class="site-group">
        <div class="group-head"><b>{{ group }}</b><button @click="toggleGroup(items, !items.every(site => config.selected_sites.includes(site.key)))">{{ items.every(site => config.selected_sites.includes(site.key)) ? '取消全选' : '全选' }}</button></div>
        <label v-for="site in items" :key="site.key" class="site-row">
          <input v-model="config.selected_sites" type="checkbox" :value="site.key">
          <span class="site-name">{{ site.name }}<small>{{ site.domain }}</small></span>
          <span v-if="cookieState[site.key]" :class="['cookie', cookieState[site.key].ok ? 'good' : 'bad']">{{ cookieState[site.key].ok ? 'Cookie 可用' : 'Cookie 缺失' }}</span>
        </label>
      </div>
    </section>

    <div class="section-head history-head"><div><h3>最近记录</h3><p>最多保留 30 次运行结果。</p></div><button class="text-button" :disabled="!history.length" @click="clearHistory">清空</button></div>
    <section class="history" v-if="history.length">
      <details v-for="item in history" :key="item.time"><summary><span :class="['dot', item.ok ? 'good' : 'bad']"></span><b>{{ item.summary }}</b><time>{{ item.time }}</time></summary><ul><li v-for="site in item.sites" :key="site.key || site.site"><span>{{ site.site }}</span><em :class="site.ok ? 'good' : 'bad'">{{ site.message }}</em></li></ul></details>
    </section>
    <p v-else class="empty">还没有签到记录。</p>
  </div>
  <div v-else class="loading">正在读取签到配置…</div>
</template>

<style scoped>
.console{color:#dce7f5;font:14px/1.5 Inter,"Microsoft YaHei",sans-serif}.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:4px 0 20px;border-bottom:1px solid #26384d}.eyebrow{margin:0 0 5px!important;color:#55a4ff!important;font-size:11px!important;font-weight:800;letter-spacing:.16em}.mast h2{margin:0;font-size:24px;line-height:1.2}.mast p,.section-head p{margin:5px 0 0;color:#8fa1b8}.mast-actions,.section-head{display:flex;align-items:center;gap:10px}button{min-height:38px;padding:0 15px;border:1px solid #304963;border-radius:8px;color:#dce7f5;background:#111d2c;font:inherit;font-weight:650;cursor:pointer}button:hover:not(:disabled){border-color:#4a8fdc}button:disabled{opacity:.5;cursor:not-allowed}.primary{border-color:#287de7;background:#287de7;color:white}.secondary{background:#132033}.runline{padding:14px 0;border-bottom:1px solid #26384d}.run-copy{display:flex;justify-content:space-between;margin-bottom:8px}.run-copy span{color:#8fa1b8}.bar{height:5px;overflow:hidden;background:#1c2a3d}.bar i{display:block;height:100%;background:#3991f3}.settings{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:12px 22px;padding:18px 0;border-bottom:1px solid #26384d}.settings label{display:flex;align-items:center;justify-content:space-between;gap:10px;color:#b7c5d7}.settings input[type=number]{width:66px;box-sizing:border-box;padding:7px 8px;border:1px solid #30445c;border-radius:6px;color:#eaf2fc;background:#0d1724}.time{display:flex;align-items:center;gap:4px}.switch{justify-content:flex-start!important}.switch input,.site-row input{accent-color:#3289ee}.section-head{justify-content:space-between;padding:22px 0 12px}.section-head h3{margin:0;font-size:16px}.site-list{border:1px solid #26384d;border-radius:10px;overflow:hidden}.site-group+.site-group{border-top:1px solid #30445c}.group-head{display:flex;justify-content:space-between;align-items:center;padding:9px 14px;color:#9cadc2;background:#101b29}.group-head button,.text-button{min-height:auto;padding:2px 0;border:0;color:#63adff;background:transparent;font-size:12px}.site-row{display:grid;grid-template-columns:24px 1fr auto;align-items:center;min-height:50px;padding:0 14px;border-top:1px solid #213145;cursor:pointer}.site-row:hover{background:#142033}.site-name{font-weight:650}.site-name small{display:block;color:#778aa3;font-weight:400}.cookie{font-size:12px}.good{color:#55c896}.bad{color:#ff7a83}.history-head{padding-top:24px}.history{border-top:1px solid #26384d}.history details{border-bottom:1px solid #26384d}.history summary{display:grid;grid-template-columns:12px 1fr auto;align-items:center;gap:10px;padding:13px 4px;cursor:pointer}.history time{color:#778aa3;font-size:12px}.dot{width:7px;height:7px;border-radius:50%;background:currentColor}.history ul{margin:0 0 12px;padding:0 4px 0 26px;list-style:none}.history li{display:flex;justify-content:space-between;gap:20px;padding:5px 0}.history em{font-style:normal;text-align:right}.empty,.loading{padding:24px 0;color:#778aa3;text-align:center}
@media(max-width:720px){.mast{align-items:stretch;flex-direction:column}.mast-actions button{flex:1}.settings{grid-template-columns:1fr}.section-head{align-items:flex-end}.history summary{grid-template-columns:12px 1fr}.history time{grid-column:2}.history li{flex-direction:column;gap:2px}.history em{text-align:left}}
</style>
