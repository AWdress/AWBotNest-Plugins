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
  <!-- THESIS: Fast PT operations through glanceable controls and tactile checked labels, refusing spreadsheet-like site rows. OWN-WORLD: Ink-blue surfaces, crisp blue selection outlines, compact square checks, quiet cyan status. STORY: Choose sites, confirm platform cookies, save, and run with progress always visible. FIRST VIEWPORT: Title and actions lead; schedule controls sit in one rail; site chips fill grouped fields below. FORM: Compact operator console, seed PT-CHECK-CHIPS-3. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md. -->
  <main class="console" v-if="!loading">
    <header class="mast">
      <div class="title-block"><span class="brand-mark" aria-hidden="true">PT</span><div><h2>多站签到</h2><p>平台 Cookie 自动同步 · 已选择 <b>{{ config.selected_sites.length }}</b> / {{ sites.length }} 个站点</p></div></div>
      <div class="mast-actions"><button class="button quiet" :disabled="checking" @click="checkCookies"><span class="button-icon" aria-hidden="true"></span>{{ checking ? '正在检查' : '检查 Cookie' }}</button><button class="button primary" :disabled="status.running || !config.selected_sites.length" @click="run"><span class="play" aria-hidden="true"></span>{{ status.running ? '签到进行中' : '立即签到' }}</button></div>
    </header>

    <section class="control-rail" aria-label="签到设置">
      <div class="toggles">
        <label class="toggle"><input v-model="config.auto_checkin" type="checkbox"><i></i><span>自动签到</span></label>
        <label class="toggle"><input v-model="config.notify_result" type="checkbox"><i></i><span>结果推送</span></label>
        <label class="toggle"><input v-model="config.headless" type="checkbox"><i></i><span>后台运行</span></label>
      </div>
      <div class="schedule-fields">
        <label><span>每天执行</span><span class="time-field"><input v-model.number="config.checkin_hour" aria-label="执行小时" type="number" min="0" max="23"><b>:</b><input v-model.number="config.checkin_minute" aria-label="执行分钟" type="number" min="0" max="59"></span></label>
        <label><span>重试次数</span><input v-model.number="config.retry_count" type="number" min="0" max="5"></label>
        <label><span>重试间隔</span><span class="unit-field"><input v-model.number="config.retry_interval" type="number" min="5" max="300"><i>秒</i></span></label>
      </div>
    </section>

    <section v-if="status.running || status.finished_at" class="run-status" aria-live="polite">
      <span :class="['pulse', { active: status.running }]"></span><div><b>{{ status.running ? `正在签到 · ${status.current}` : '最近任务已完成' }}</b><small>{{ status.completed }} / {{ status.total }} 个站点</small></div><strong>{{ progress }}%</strong><div class="progress"><i :style="{ width: `${progress}%` }"></i></div>
    </section>

    <section class="sites-panel">
      <div class="section-head"><div><h3>选择签到站点</h3><p>点击标签即可勾选。除 TJUPT 外，验证码由平台 AI 自动识别。</p></div><div class="section-actions"><button class="link-button" @click="toggleGroup(sites, true)">全选</button><span></span><button class="link-button" @click="toggleGroup(sites, false)">清空</button></div></div>
      <div v-for="[group, items] in groups" :key="group" class="site-group">
        <div class="group-title"><span>{{ group }}</span><small>{{ items.filter(site => config.selected_sites.includes(site.key)).length }}/{{ items.length }}</small><button @click="toggleGroup(items, !items.every(site => config.selected_sites.includes(site.key)))">{{ items.every(site => config.selected_sites.includes(site.key)) ? '取消本组' : '选择本组' }}</button></div>
        <div class="site-chips">
          <label v-for="site in items" :key="site.key" :class="['site-chip', { selected: config.selected_sites.includes(site.key), checked: cookieState[site.key]?.ok, missing: cookieState[site.key] && !cookieState[site.key].ok }]">
            <input v-model="config.selected_sites" type="checkbox" :value="site.key">
            <span class="checkmark"><i></i></span>
            <span class="site-badge">{{ site.name.slice(0, 2).toUpperCase() }}</span>
            <span class="site-copy"><b>{{ site.name }}</b><small>{{ site.domain }}</small></span>
            <span v-if="cookieState[site.key]" class="cookie-dot" :title="cookieState[site.key].message"></span>
          </label>
        </div>
      </div>
      <footer class="save-bar"><p><span class="shield" aria-hidden="true"></span>Cookie 只从平台读取，不会保存在插件配置中。</p><button class="button primary" :disabled="saving" @click="save">{{ saving ? '正在保存…' : '保存并应用' }}</button></footer>
    </section>

    <section class="history-panel">
      <div class="section-head"><div><h3>最近运行</h3><p>保留最近 30 次签到结果。</p></div><button class="link-button danger" :disabled="!history.length" @click="clearHistory">清空记录</button></div>
      <div class="history" v-if="history.length"><details v-for="item in history" :key="item.time"><summary><span :class="['result-mark', item.ok ? 'success' : 'failed']"></span><b>{{ item.summary }}</b><time>{{ item.time }}</time><span class="chevron"></span></summary><ul><li v-for="site in item.sites" :key="site.key || site.site"><span>{{ site.site }}</span><em :class="site.ok ? 'success-text' : 'failed-text'">{{ site.message }}</em></li></ul></details></div>
      <div v-else class="empty"><span class="empty-mark"></span><b>等待第一次签到</b><p>运行完成后，站点结果会显示在这里。</p></div>
    </section>
  </main>
  <div v-else class="loading">正在读取签到配置…</div>
</template>

<style scoped>
.console{--bg:#0b1421;--panel:#101b2a;--panel-2:#142238;--line:#273a54;--line-soft:#1e3047;--text:#edf5ff;--muted:#91a4bc;--blue:#2f89f5;--blue-soft:#173a66;--green:#55d39a;--red:#ff7c88;min-height:100%;padding:22px;border-radius:16px;color:var(--text);background:var(--bg);font:14px/1.5 "Segoe UI","Microsoft YaHei",sans-serif;scrollbar-color:#38516e var(--bg);accent-color:var(--blue);overflow:hidden}.console *{box-sizing:border-box}.console ::selection{color:#fff;background:#226fc9}.mast{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:2px 0 20px}.title-block{display:flex;align-items:center;gap:13px}.brand-mark{display:grid;place-items:center;width:42px;height:42px;border:1px solid #3978bd;border-radius:12px;color:#80bdff;background:#142945;font-size:13px;font-weight:850;letter-spacing:-.02em}.mast h2,.section-head h3{margin:0;letter-spacing:-.02em}.mast h2{font-size:22px}.mast p,.section-head p{margin:3px 0 0;color:var(--muted)}.mast p b{color:#82bdff}.mast-actions,.section-actions{display:flex;align-items:center;gap:9px}.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:40px;padding:0 16px;border:1px solid var(--line);border-radius:9px;color:var(--text);background:#142136;font:inherit;font-weight:700;cursor:pointer}.button:hover:not(:disabled){border-color:#4c759f;background:#182944}.button:focus-visible,.link-button:focus-visible,.group-title button:focus-visible,.site-chip:has(input:focus-visible){outline:2px solid #75b6ff;outline-offset:2px}.button:disabled,.link-button:disabled{opacity:.48;cursor:not-allowed}.button.primary{border-color:#3791f7;color:#fff;background:#287fe5;box-shadow:0 8px 22px rgba(19,92,176,.26)}.button.primary:hover:not(:disabled){background:#3692fb}.button.quiet{background:#111d2e}.button-icon{position:relative;width:17px;height:17px;border:1px solid #51759e;border-radius:5px}.button-icon::after,.shield::after,.result-mark.success::after,.empty-mark::after{content:"";display:block;width:8px;height:5px;border-left:2px solid currentColor;border-bottom:2px solid currentColor;transform:translate(3px,4px) rotate(-45deg)}.play{width:0;height:0;border-top:5px solid transparent;border-bottom:5px solid transparent;border-left:8px solid currentColor}.control-rail{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:24px;padding:16px 18px;border:1px solid var(--line);border-radius:14px;background:var(--panel)}.toggles{display:grid!important;grid-template-columns:repeat(3,minmax(124px,max-content));align-items:center;justify-content:start;gap:12px 18px;min-width:0}.schedule-fields{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:14px 18px}.toggle{display:grid!important;grid-template-columns:36px auto;align-items:center;gap:10px;min-width:124px;margin:0!important;padding:0!important;white-space:nowrap;cursor:pointer}.toggle input,.site-chip input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}.toggle>i{position:relative!important;display:block!important;flex:0 0 36px!important;width:36px!important;min-width:36px!important;max-width:36px!important;height:20px!important;min-height:20px!important;margin:0!important;padding:0!important;border:1px solid #3a526e!important;border-radius:10px!important;background:#182638!important;overflow:hidden}.toggle>i::before{content:none!important}.toggle>i::after{content:""!important;position:absolute!important;top:3px!important;left:3px!important;width:12px!important;height:12px!important;margin:0!important;border:0!important;border-radius:50%!important;background:#8193a8!important;transform:none!important}.toggle input:checked+i{border-color:#338bf1!important;background:#216fce!important}.toggle input:checked+i::after{left:19px!important;background:#fff!important}.toggle>span{display:block!important;margin:0!important;padding:0!important;line-height:20px!important}.schedule-fields>label{display:flex;align-items:center;gap:8px;color:var(--muted);white-space:nowrap}.schedule-fields input{width:58px;height:34px;padding:0 7px;border:1px solid #354c68;border-radius:7px;color:var(--text);background:#0d1725;font:inherit;text-align:center;font-variant-numeric:tabular-nums}.time-field,.unit-field{display:flex;align-items:center;gap:3px}.time-field input{width:45px}.time-field b{color:#71859f}.unit-field{position:relative}.unit-field input{padding-right:25px}.unit-field i{position:absolute;right:8px;color:#71859f;font-size:11px;font-style:normal}.run-status{display:grid;grid-template-columns:10px 1fr auto;align-items:center;gap:10px;margin-top:12px;padding:12px 16px;border:1px solid #28527f;border-radius:10px;background:#10243d}.run-status>div:first-of-type{display:flex;gap:12px}.run-status small{color:#8fa7c2}.run-status strong{color:#83bfff;font-variant-numeric:tabular-nums}.pulse{width:8px;height:8px;border-radius:50%;background:#668098}.pulse.active{background:var(--green);box-shadow:0 2px 9px rgba(85,211,154,.5)}.progress{grid-column:1/-1;height:3px;overflow:hidden;background:#1c3858}.progress i{display:block;height:100%;background:#51a2ff}.sites-panel,.history-panel{margin-top:18px;border:1px solid var(--line);border-radius:14px;background:var(--panel)}.section-head{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:17px 19px;border-bottom:1px solid var(--line-soft)}.section-head h3{font-size:16px}.link-button,.group-title button{min-height:auto;padding:3px 0;border:0;color:#72b5ff;background:transparent;font:inherit;font-size:12px;cursor:pointer}.link-button.danger{color:#ff939c}.section-actions span{width:1px;height:13px;background:var(--line)}.site-group{padding:0 18px 17px}.site-group+.site-group{border-top:1px solid var(--line-soft)}.group-title{display:flex;align-items:center;gap:8px;padding:15px 1px 10px;color:#bdcadd}.group-title span{font-weight:750}.group-title small{padding:1px 6px;border-radius:6px;color:#7f94ac;background:#19283c;font-variant-numeric:tabular-nums}.group-title button{margin-left:auto}.site-chips{display:flex;flex-wrap:wrap;gap:9px}.site-chip{position:relative;display:grid;grid-template-columns:17px 29px minmax(70px,1fr) 7px;align-items:center;gap:8px;min-width:174px;min-height:54px;padding:7px 10px;border:1px solid #30445d;border-radius:9px;color:#b8c7d9;background:#111d2d;cursor:pointer;user-select:none}.site-chip:hover{border-color:#4b7098;background:#15243a}.site-chip.selected{border-color:#318af1;color:#eaf5ff;background:#142a47;box-shadow:0 6px 18px rgba(4,13,25,.2)}.checkmark{display:grid;place-items:center;width:16px;height:16px;border:1px solid #526a85;border-radius:4px;background:#0d1724}.selected .checkmark{border-color:#3795ff;background:#2f89f5}.selected .checkmark i{width:8px;height:5px;border-left:2px solid #fff;border-bottom:2px solid #fff;transform:translateY(-1px) rotate(-45deg)}.site-badge{display:grid;place-items:center;width:29px;height:29px;border:1px solid #38516f;border-radius:8px;color:#8ebce9;background:#192a40;font-size:9px;font-weight:850;letter-spacing:-.02em}.selected .site-badge{border-color:#3d75ad;color:#b8dcff;background:#19395f}.site-copy{min-width:0}.site-copy b,.site-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.site-copy b{font-size:13px}.site-copy small{color:#758ba4;font-size:10px}.cookie-dot{width:7px;height:7px;border-radius:50%;background:var(--green)}.site-chip.missing .cookie-dot{background:var(--red)}.save-bar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:14px 18px;border-top:1px solid var(--line-soft);background:#0d1826}.save-bar p{display:flex;align-items:center;gap:8px;margin:0;color:#8297b0;font-size:12px}.shield{position:relative;width:18px;height:18px;border:1px solid #397d65;border-radius:6px;color:var(--green);background:#112c27}.result-mark{position:relative;width:22px;height:22px;border-radius:7px}.result-mark.success{color:var(--green);background:#123228}.result-mark.failed{color:var(--red);background:#361c27}.result-mark.failed::after{content:"";position:absolute;left:10px;top:5px;width:2px;height:8px;border-radius:1px;background:currentColor;box-shadow:0 10px 0 -0.5px currentColor}.history-panel{overflow:hidden}.history details+details{border-top:1px solid var(--line-soft)}.history summary{display:grid;grid-template-columns:25px 1fr auto 12px;align-items:center;gap:10px;padding:13px 18px;cursor:pointer;list-style:none}.history summary::-webkit-details-marker{display:none}.history time{color:#7389a2;font-size:12px;font-variant-numeric:tabular-nums}.chevron{width:7px;height:7px;border-right:1px solid #8094ab;border-bottom:1px solid #8094ab;transform:rotate(45deg)}details[open] .chevron{transform:rotate(225deg)}.history ul{margin:0;padding:0 18px 13px 53px;list-style:none}.history li{display:flex;justify-content:space-between;gap:20px;padding:5px 0;color:#aebdd0}.history em{font-style:normal;text-align:right}.success-text{color:var(--green)}.failed-text{color:var(--red)}.empty{padding:31px;text-align:center;color:#8295ac}.empty-mark{position:relative;display:block;width:34px;height:34px;margin:0 auto 9px;border:1px solid #345477;border-radius:10px;color:#6aabed;background:#13243a}.empty-mark::after{width:11px;height:7px;transform:translate(10px,10px) rotate(-45deg)}.empty b{display:block;color:#c8d5e5}.empty p{margin:3px 0 0}.loading{padding:36px;color:#8498b0;text-align:center}
@media(max-width:940px){.control-rail{grid-template-columns:1fr}.schedule-fields{justify-content:flex-start}.site-chip{flex:1 1 180px}}
@media(max-width:620px){.mast{align-items:stretch;flex-direction:column}.mast-actions .button{flex:1}.control-rail{padding:15px}.toggles,.schedule-fields{align-items:stretch;flex-direction:column;gap:12px}.schedule-fields>label{justify-content:space-between}.section-head{align-items:flex-start}.section-head p{max-width:34ch}.site-group{padding-inline:12px}.site-chip{flex-basis:100%}.save-bar{align-items:stretch;flex-direction:column}.save-bar .button{width:100%}.history summary{grid-template-columns:25px 1fr 12px}.history time{grid-column:2}.history ul{padding-left:53px}.history li{flex-direction:column;gap:2px}.history em{text-align:left}}

/* 平台宿主也使用 .toggle/input/i；这里完全重置本组件开关，避免原生控件与宿主伪元素叠加。 */
.control-rail .toggles>.toggle{all:unset!important;display:grid!important;grid-template-columns:36px max-content!important;align-items:center!important;gap:10px!important;min-width:124px!important;color:var(--text)!important;font:inherit!important;white-space:nowrap!important;cursor:pointer!important;box-sizing:border-box!important}.control-rail .toggles>.toggle::before,.control-rail .toggles>.toggle::after{content:none!important;display:none!important}.control-rail .toggles>.toggle>input{display:none!important;appearance:none!important;width:0!important;height:0!important;margin:0!important;padding:0!important;border:0!important;opacity:0!important}.control-rail .toggles>.toggle>i{all:unset!important;position:relative!important;display:block!important;width:36px!important;height:20px!important;border:1px solid #3a526e!important;border-radius:10px!important;background:#182638!important;overflow:hidden!important;box-sizing:border-box!important}.control-rail .toggles>.toggle>i::before{content:none!important;display:none!important}.control-rail .toggles>.toggle>i::after{content:""!important;position:absolute!important;display:block!important;top:3px!important;left:3px!important;width:12px!important;height:12px!important;margin:0!important;padding:0!important;border:0!important;border-radius:50%!important;background:#8193a8!important;box-shadow:none!important;transform:none!important}.control-rail .toggles>.toggle>input:checked+i{border-color:#338bf1!important;background:#216fce!important}.control-rail .toggles>.toggle>input:checked+i::after{left:19px!important;background:#fff!important}.control-rail .toggles>.toggle>span{all:unset!important;display:block!important;color:var(--text)!important;font:inherit!important;line-height:20px!important;white-space:nowrap!important}
@media(max-width:620px){.control-rail>.toggles{grid-template-columns:1fr!important}.control-rail .toggles>.toggle{min-width:0!important}}
</style>
