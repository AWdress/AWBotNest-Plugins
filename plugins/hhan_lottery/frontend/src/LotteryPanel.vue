<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({ enabled: true, notify_result: true, notify_cookie_error: true, lottery_count: 10, max_count: 100, interval_seconds: 7 })
const status = ref({ running: false, completed: 0, target: 0, detail: '', last_prize: '', last_result: '' })
const stats = ref('暂无累计统计')
const busy = ref('')
let timer

const progress = computed(() => status.value.target ? Math.min(100, Math.round(status.value.completed / status.value.target * 100)) : 0)
const stateText = computed(() => status.value.running ? `正在抽奖 ${status.value.completed}/${status.value.target}` : (status.value.detail || '等待开始'))

async function refresh() { try { status.value = await props.host.callApi('/lottery/status') } catch (_) {} }
async function loadStats() { try { stats.value = (await props.host.callApi('/lottery/stats')).text || '暂无累计统计' } catch (_) {} }
async function save(showToast = true) {
  cfg.lottery_count = Math.max(1, Math.min(Number(cfg.lottery_count) || 10, Number(cfg.max_count) || 100))
  cfg.interval_seconds = Math.max(3, Math.min(Number(cfg.interval_seconds) || 7, 30))
  await props.host.saveConfig({ ...cfg })
  if (showToast) props.host.toast.success('转盘配置已保存')
}
async function action(name, path, method = 'POST') {
  busy.value = name
  try {
    if (name === 'run') await save(false)
    const result = await props.host.callApi(path, { method, body: method === 'POST' ? {} : undefined })
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message || '操作完成')
    await refresh(); await loadStats()
  } catch (error) { props.host.toast.error(error.message || String(error)) }
  finally { busy.value = '' }
}

onMounted(async () => {
  Object.assign(cfg, await props.host.getConfig())
  await Promise.all([refresh(), loadStats()])
  timer = setInterval(refresh, 1500)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <section class="panel">
    <header>
      <div><p class="eyebrow">HHANCLUB</p><h2>幸运转盘</h2><p class="sub">使用平台已登录 Cookie，在后台按设定次数抽奖。</p></div>
      <span class="state" :class="{ live: status.running }"><i />{{ stateText }}</span>
    </header>

    <div class="progress-card">
      <div class="progress-top"><strong>{{ status.completed }} <small>/ {{ status.target || cfg.lottery_count }} 次</small></strong><span>{{ progress }}%</span></div>
      <div class="track"><i :style="{ width: progress + '%' }" /></div>
      <p>{{ status.last_prize ? `最近奖品：${status.last_prize}` : '开始后这里会实时显示进度与最近奖品。' }}</p>
    </div>

    <div class="grid">
      <div class="card settings">
        <h3>抽奖设置</h3>
        <label class="toggle-row"><span><b>启用转盘</b><small>关闭后不能启动新任务</small></span><input v-model="cfg.enabled" type="checkbox"></label>
        <label><span>抽奖次数</span><input v-model.number="cfg.lottery_count" type="number" min="1" :max="cfg.max_count"></label>
        <label><span>抽奖间隔（秒）</span><input v-model.number="cfg.interval_seconds" type="number" min="3" max="30"></label>
        <label class="check"><input v-model="cfg.notify_result" type="checkbox"> 完成后推送结果</label>
        <label class="check"><input v-model="cfg.notify_cookie_error" type="checkbox"> Cookie 异常时通知</label>
        <button class="secondary" :disabled="busy" @click="save()">保存设置</button>
      </div>
      <div class="card result">
        <h3>最近结果</h3>
        <pre>{{ status.last_result || '还没有抽奖记录。' }}</pre>
        <h3>累计统计</h3>
        <pre>{{ stats }}</pre>
      </div>
    </div>

    <footer>
      <button class="primary" :disabled="busy || status.running || !cfg.enabled" @click="action('run', '/lottery/run')">{{ busy === 'run' ? '正在启动…' : '开始抽奖' }}</button>
      <button class="danger" :disabled="busy || !status.running" @click="action('stop', '/lottery/stop')">停止抽奖</button>
      <button class="secondary" :disabled="busy" @click="action('cookie', '/lottery/cookie/check', 'GET')">检查平台 Cookie</button>
    </footer>
  </section>
</template>

<style scoped>
.panel { --line:#26384f; --muted:#8fa1b8; --blue:#3289f5; font-family: "Microsoft YaHei", system-ui, sans-serif; }
header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:18px; } h2 { margin:2px 0 5px; color:#f4f8fd; font-size:25px; } .eyebrow { margin:0; color:var(--blue); font-size:11px; font-weight:800; letter-spacing:.16em; } .sub { margin:0; color:var(--muted); font-size:13px; }
.state { display:flex; align-items:center; gap:8px; max-width:280px; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:#aebdd0; background:#111c2b; font-size:12px; } .state i { width:7px; height:7px; border-radius:50%; background:#64748b; } .state.live i { background:#38d796; box-shadow:0 0 0 5px #38d7961d; }
.progress-card,.card { border:1px solid var(--line); border-radius:14px; background:#111c2b; } .progress-card { padding:18px 20px; margin-bottom:14px; } .progress-top { display:flex; justify-content:space-between; color:#71adfa; } .progress-top strong { color:#f2f6fc; font-size:25px; } .progress-top small { color:var(--muted); font-size:13px; } .track { height:7px; margin:13px 0 9px; overflow:hidden; border-radius:9px; background:#243349; } .track i { display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg,#287de7,#55a8ff); } .progress-card p { margin:0; color:var(--muted); font-size:12px; }
.grid { display:grid; grid-template-columns:minmax(270px,.8fr) minmax(320px,1.2fr); gap:14px; } .card { padding:18px; min-width:0; } h3 { margin:0 0 14px; color:#dfe9f6; font-size:14px; } label:not(.check,.toggle-row) { display:grid; grid-template-columns:1fr 120px; align-items:center; gap:12px; margin:12px 0; color:#bac8d9; font-size:13px; } input[type=number] { width:100%; box-sizing:border-box; padding:9px 10px; border:1px solid #344861; border-radius:8px; color:#edf4fc; background:#0d1725; font:inherit; } .toggle-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; } .toggle-row span { display:grid; gap:3px; } .toggle-row small { color:var(--muted); } .check { display:block; margin:11px 0; color:#aebed0; font-size:13px; } pre { max-height:150px; overflow:auto; white-space:pre-wrap; margin:0 0 17px; color:#9fb1c6; font:12px/1.6 ui-monospace,Consolas,monospace; }
footer { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; } button { min-height:40px; padding:0 16px; border-radius:9px; border:1px solid transparent; color:#dce8f7; background:#18263a; font:inherit; font-weight:650; cursor:pointer; } button:disabled { opacity:.45; cursor:not-allowed; } .primary { color:white; background:#287de7; } .danger { color:#ffb0b0; border-color:#7c353d; background:#2a1920; } .secondary { border-color:#344a65; background:#152338; }
@media(max-width:700px){ header{display:block}.state{margin-top:13px}.grid{grid-template-columns:1fr}.result{min-height:0} footer button{flex:1} }
</style>
