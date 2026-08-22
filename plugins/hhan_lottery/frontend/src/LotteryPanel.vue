<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({ enabled: true, notify_result: true, notify_cookie_error: true, lottery_mode: 'fixed', lottery_count: 10, interval_seconds: 7, reserve_beans: 0, sync_every_draws: 20, auto_clean_lottery_mail: false, prize_notify_enabled: true, prize_notify_vip: true, prize_notify_invite: true, prize_notify_big_beans: true, prize_notify_keywords: '', prize_notify_cooldown: 300, stop_on_prize: false, stop_on_vip: true, stop_on_invite: true, stop_on_big_beans: true, big_bean_threshold: 500000, stop_prize_keywords: '', scheduled_stop_enabled: false, scheduled_stop_at: '' })
const status = ref({ running: false, completed: 0, target: 0, detail: '', last_prize: '', last_result: '', current_stats: {}, cumulative_stats: {} })
const busy = ref('')
const saving = ref(false)
const apiError = ref('')
let timer

const progress = computed(() => status.value.target ? Math.min(100, Math.round(status.value.completed / status.value.target * 100)) : 0)
const stateText = computed(() => apiError.value ? '状态连接失败' : (status.value.running ? `正在抽奖 ${status.value.completed}/${status.value.target}` : (status.value.detail || '等待开始')))
const currentStats = computed(() => status.value.current_stats || {})
const cumulativeStats = computed(() => status.value.cumulative_stats || {})
const formatNumber = value => new Intl.NumberFormat('zh-CN').format(Number(value) || 0)
const formatSigned = value => `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`
const profitTone = value => Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : 'neutral'
const prizeRows = value => Object.entries(value?.prizes || {}).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 20)

async function refresh() {
  try {
    const result = await props.host.callApi('/lottery/status', { method: 'POST', body: {} })
    if (!result || typeof result !== 'object' || !Object.hasOwn(result, 'running') || !Object.hasOwn(result, 'current_stats')) throw new Error('状态接口响应缺少运行字段')
    status.value = result
    apiError.value = String(result.setup_error || '')
  } catch (error) {
    apiError.value = error?.message || String(error)
  }
}
async function save(showToast = true) {
  if (saving.value) return
  saving.value = true
  try {
    cfg.lottery_mode = ['fixed', 'balance', 'reserve'].includes(cfg.lottery_mode) ? cfg.lottery_mode : 'fixed'
    cfg.lottery_count = Math.max(1, Math.trunc(Number(cfg.lottery_count) || 10))
    cfg.interval_seconds = Math.max(3, Math.min(Number(cfg.interval_seconds) || 7, 30))
    cfg.reserve_beans = Math.max(0, Math.trunc(Number(cfg.reserve_beans) || 0))
    cfg.sync_every_draws = Math.max(1, Math.min(200, Math.trunc(Number(cfg.sync_every_draws) || 20)))
    cfg.big_bean_threshold = Math.max(1, Math.trunc(Number(cfg.big_bean_threshold) || 500000))
    cfg.prize_notify_cooldown = Math.max(0, Math.min(86400, Math.trunc(Number(cfg.prize_notify_cooldown) || 300)))
    cfg.scheduled_stop_at = String(cfg.scheduled_stop_at || '')
    await props.host.saveConfig({ ...cfg })
    if (showToast) props.host.toast.success('转盘配置已保存')
  } catch (error) {
    if (showToast) props.host.toast.error(error.message || String(error))
    throw error
  } finally {
    saving.value = false
  }
}
async function action(name, path, method = 'POST') {
  busy.value = name
  try {
    if (name === 'run') await save(false)
    const result = await props.host.callApi(path, { method, body: method === 'POST' ? {} : undefined })
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message || '操作完成')
    await refresh()
  } catch (error) { props.host.toast.error(error.message || String(error)) }
  finally { busy.value = '' }
}

onMounted(async () => {
  Object.assign(cfg, await props.host.getConfig())
  await refresh()
  timer = setInterval(refresh, 1500)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <section class="panel">
    <header>
      <div><p class="eyebrow">HHANCLUB</p><h2>幸运转盘</h2><p class="sub">可指定任意正整数次数，或按当前余额自动抽完。</p></div>
      <span class="state" :class="{ live: status.running }"><i />{{ stateText }}</span>
    </header>

    <p v-if="apiError" class="api-error">无法读取转盘状态：{{ apiError }}。请检查插件后端启动日志或重新加载插件。</p>

    <div class="progress-card">
      <div class="progress-top"><strong>{{ status.completed }} <small>/ {{ status.target || (cfg.lottery_mode === 'balance' ? '待计算' : cfg.lottery_count) }} 次</small></strong><span>{{ progress }}%</span></div>
      <div class="track"><i :style="{ width: progress + '%' }" /></div>
      <p>{{ status.last_prize ? `最近奖品：${status.last_prize}` : '开始后这里会实时显示进度与最近奖品。' }}</p>
      <div class="live-stats">
        <section>
          <div class="stats-head"><h3>当前任务</h3><span>{{ formatNumber(currentStats.count) }} 次 · 消耗 {{ formatNumber(currentStats.cost) }}</span></div>
          <div class="balance-line"><span>憨豆奖品 {{ formatNumber(currentStats.beans) }}</span><b class="profit" :class="profitTone(currentStats.profit)">净盈亏 {{ formatSigned(currentStats.profit) }}</b></div>
          <ul v-if="prizeRows(currentStats).length"><li v-for="([name, count]) in prizeRows(currentStats)" :key="name"><span>{{ name }}</span><b>× {{ formatNumber(count) }}</b></li></ul>
          <p v-else class="empty-stat">本轮奖品将在这里实时累积。</p>
        </section>
        <section>
          <div class="stats-head"><h3>累计奖品</h3><span>{{ formatNumber(cumulativeStats.count) }} 次 · 消耗 {{ formatNumber(cumulativeStats.cost) }}</span></div>
          <div class="balance-line"><span>憨豆奖品 {{ formatNumber(cumulativeStats.beans) }}</span><b class="profit" :class="profitTone(cumulativeStats.profit)">净盈亏 {{ formatSigned(cumulativeStats.profit) }}</b></div>
          <ul v-if="prizeRows(cumulativeStats).length"><li v-for="([name, count]) in prizeRows(cumulativeStats)" :key="name"><span>{{ name }}</span><b>× {{ formatNumber(count) }}</b></li></ul>
          <p v-else class="empty-stat">完成第一次抽奖后显示累计记录。</p>
        </section>
      </div>
    </div>

    <div class="grid">
      <div class="card settings">
        <div class="card-heading">
          <div><h3>抽奖设置</h3><p>配置抽取策略、停止条件与结果通知。</p></div>
          <label class="toggle-row"><span><b>启用转盘</b><small>允许启动新任务</small></span><input v-model="cfg.enabled" type="checkbox"></label>
        </div>

        <div class="settings-columns">
          <section class="setting-group">
            <h4>抽取策略</h4>
            <label><span>抽奖方式</span><select v-model="cfg.lottery_mode"><option value="fixed">指定次数</option><option value="balance">按余额抽完</option><option value="reserve">保留余额抽取</option></select></label>
            <label v-if="cfg.lottery_mode === 'fixed'"><span>抽奖次数</span><input v-model.number="cfg.lottery_count" type="number" min="1" step="1"></label>
            <label v-else-if="cfg.lottery_mode === 'reserve'"><span>保留憨豆</span><input v-model.number="cfg.reserve_beans" type="number" min="0" step="1000"></label>
            <p v-else class="mode-note">启动时读取余额与单次消耗，自动计算本次可抽次数。</p>
            <label><span>抽奖间隔（秒）</span><input v-model.number="cfg.interval_seconds" type="number" min="3" max="30"></label>
            <label><span>余额校准间隔</span><input v-model.number="cfg.sync_every_draws" type="number" min="1" max="200"></label>
            <label class="check"><input v-model="cfg.auto_clean_lottery_mail" type="checkbox"> 校准时清理转盘通知</label>
          </section>

          <section class="setting-group">
            <h4>停止条件与通知</h4>
            <label class="check"><input v-model="cfg.scheduled_stop_enabled" type="checkbox"> 到指定日期时间自动停止</label>
            <label v-if="cfg.scheduled_stop_enabled"><span>停止日期时间</span><input v-model="cfg.scheduled_stop_at" type="datetime-local"></label>
            <p v-if="cfg.scheduled_stop_enabled" class="mode-note">计划会持久化，平台重启后继续剩余任务，并按时停止。</p>
            <label class="check"><input v-model="cfg.prize_notify_enabled" type="checkbox"> 实时大奖通知</label>
            <div v-if="cfg.prize_notify_enabled" class="stop-box">
              <div class="prize-options">
                <label class="check"><input v-model="cfg.prize_notify_vip" type="checkbox"> VIP</label>
                <label class="check"><input v-model="cfg.prize_notify_invite" type="checkbox"> 邀请</label>
                <label class="check"><input v-model="cfg.prize_notify_big_beans" type="checkbox"> 大额憨豆</label>
              </div>
              <label><span>大额门槛</span><input v-model.number="cfg.big_bean_threshold" type="number" min="1" step="10000"></label>
              <label><span>通知关键词</span><input v-model="cfg.prize_notify_keywords" type="text" placeholder="逗号分隔"></label>
              <label><span>相同奖品冷却</span><div class="input-unit"><input v-model.number="cfg.prize_notify_cooldown" type="number" min="0" max="86400"><em>秒</em></div></label>
            </div>
            <label class="check"><input v-model="cfg.stop_on_prize" type="checkbox"> 命中大奖后自动停止</label>
            <div v-if="cfg.stop_on_prize" class="stop-box">
              <div class="prize-options">
                <label class="check"><input v-model="cfg.stop_on_vip" type="checkbox"> VIP</label>
                <label class="check"><input v-model="cfg.stop_on_invite" type="checkbox"> 邀请</label>
                <label class="check"><input v-model="cfg.stop_on_big_beans" type="checkbox"> 大额憨豆</label>
              </div>
              <label><span>大额门槛</span><input v-model.number="cfg.big_bean_threshold" type="number" min="1" step="10000"></label>
              <label><span>自定义关键词</span><input v-model="cfg.stop_prize_keywords" type="text" placeholder="逗号分隔"></label>
            </div>
            <div class="notification-options">
              <label class="check"><input v-model="cfg.notify_result" type="checkbox"> 完成后推送结果</label>
              <label class="check"><input v-model="cfg.notify_cookie_error" type="checkbox"> Cookie 异常时通知</label>
            </div>
          </section>
        </div>

        <div class="settings-actions"><button class="secondary" :disabled="saving" @click="save()">{{ saving ? '保存中…' : '保存设置' }}</button></div>
      </div>
      <div class="card result">
        <div class="result-heading"><h3>最近结果</h3><span>自动刷新</span></div>
        <pre>{{ status.last_result || '还没有抽奖记录。' }}</pre>
      </div>
    </div>

    <footer>
      <button class="primary" :disabled="busy || status.running || !cfg.enabled" @click="action('run', '/lottery/run')">{{ busy === 'run' ? '正在启动…' : '开始抽奖' }}</button>
      <button class="danger" :disabled="busy || !status.running" @click="action('stop', '/lottery/stop')">停止抽奖</button>
      <button class="secondary" :disabled="busy" @click="action('cookie', '/lottery/cookie/check', 'GET')">检查 Cookie 与余额</button>
      <button class="secondary" :disabled="busy || status.running" @click="action('mail', '/lottery/mail/clean')">清理转盘通知</button>
    </footer>
  </section>
</template>

<style scoped>
.panel { --line:#26384f; --muted:#8fa1b8; --blue:#3289f5; font-family: "Microsoft YaHei", system-ui, sans-serif; }
header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:18px; } h2 { margin:2px 0 5px; color:#f4f8fd; font-size:25px; } .eyebrow { margin:0; color:var(--blue); font-size:11px; font-weight:800; letter-spacing:.16em; } .sub { margin:0; color:var(--muted); font-size:13px; }
.state { display:flex; align-items:center; gap:8px; max-width:280px; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:#aebdd0; background:#111c2b; font-size:12px; } .state i { width:7px; height:7px; border-radius:50%; background:#64748b; } .state.live i { background:#38d796; box-shadow:0 0 0 5px #38d7961d; }
.api-error{margin:0 0 14px;padding:11px 13px;border:1px solid #743b46;border-radius:9px;color:#ffc2c7;background:#291820;font-size:12px;line-height:1.55}
.progress-card,.card { border:1px solid var(--line); border-radius:14px; background:#111c2b; } .progress-card { padding:18px 20px; margin-bottom:14px; } .progress-top { display:flex; justify-content:space-between; color:#71adfa; } .progress-top strong { color:#f2f6fc; font-size:25px; } .progress-top small { color:var(--muted); font-size:13px; } .track { height:7px; margin:13px 0 9px; overflow:hidden; border-radius:9px; background:#243349; } .track i { display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg,#287de7,#55a8ff); } .progress-card p { margin:0; color:var(--muted); font-size:12px; }
.live-stats{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px;padding-top:16px;border-top:1px solid var(--line)}.live-stats section{min-width:0}.stats-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:7px}.stats-head h3{margin:0}.stats-head span{color:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}.balance-line{display:flex;justify-content:space-between;gap:12px;margin-bottom:10px;color:#8fa1b8;font-size:11px;font-variant-numeric:tabular-nums}.profit{font-weight:750}.profit.positive{color:#45cf91}.profit.negative{color:#ef777d}.profit.neutral{color:#a9b8ca}.live-stats ul{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;max-height:164px;overflow:auto;margin:0;padding:0;list-style:none}.live-stats li{display:flex;justify-content:space-between;gap:10px;min-width:0;color:#b9c8da;font-size:12px}.live-stats li span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live-stats li b{flex:none;color:#71adfa;font-variant-numeric:tabular-nums}.progress-card .empty-stat{padding:8px 0;color:#71849c}
.grid { display:grid; grid-template-columns:minmax(600px,1.55fr) minmax(300px,.8fr); align-items:start; gap:14px; } .card { padding:20px; min-width:0; } h3 { margin:0; color:#dfe9f6; font-size:14px; } .card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;padding-bottom:16px;border-bottom:1px solid var(--line)}.card-heading p{margin:5px 0 0;color:var(--muted);font-size:12px}.settings-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;padding-top:18px}.setting-group{min-width:0}.setting-group+ .setting-group{padding-left:28px;border-left:1px solid var(--line)}.setting-group h4{margin:0 0 14px;color:#dfe9f6;font-size:13px}.settings label:not(.check,.toggle-row) { display:grid; grid-template-columns:minmax(90px,1fr) minmax(150px,1.15fr); align-items:center; gap:12px; margin:12px 0; color:#bac8d9; font-size:13px; } input[type=number],input[type=datetime-local],select { width:100%; box-sizing:border-box; padding:9px 10px; border:1px solid #344861; border-radius:8px; color:#edf4fc; background:#0d1725; font:inherit; } .toggle-row { display:flex; flex:none; justify-content:space-between; align-items:center; gap:18px; margin:0; } .toggle-row span { display:grid; gap:3px; } .toggle-row small { color:var(--muted); font-size:11px; } .mode-note { margin:8px 0 13px; padding:10px 11px; border-radius:8px; color:#8fb5e4; background:#12253d; font-size:12px; line-height:1.55; } .check { display:block; margin:11px 0; color:#aebed0; font-size:13px; } .settings-actions{display:flex;justify-content:flex-end;margin-top:18px;padding-top:16px;border-top:1px solid var(--line)}
.result{align-self:start}.result-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.result-heading span{color:#71849c;font-size:11px}.result pre { min-height:180px; max-height:380px; overflow:auto; white-space:pre-wrap; margin:0; padding:14px; border-radius:9px; color:#aebdd0; background:#0d1725; font:12px/1.7 ui-monospace,Consolas,monospace; scrollbar-color:#344a65 transparent; }
.stop-box { margin:10px 0; padding:10px 12px; border:1px solid #2e425b; border-radius:9px; background:#0d1827; } .prize-options{display:flex;flex-wrap:wrap;gap:4px 14px}.stop-box .check { margin:3px 0; } .notification-options{display:grid;grid-template-columns:1fr 1fr;gap:0 14px;margin-top:12px} input[type=text] { width:100%; box-sizing:border-box; padding:9px 10px; border:1px solid #344861; border-radius:8px; color:#edf4fc; background:#0d1725; font:inherit; }
.input-unit{display:flex;align-items:center;min-width:0;border:1px solid #344861;border-radius:8px;background:#0d1725}.input-unit:focus-within{border-color:var(--blue)}.input-unit input{min-width:0;border:0}.input-unit em{padding-right:10px;color:var(--muted);font-size:11px;font-style:normal}
footer { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; } button { min-height:40px; padding:0 16px; border-radius:9px; border:1px solid transparent; color:#dce8f7; background:#18263a; font:inherit; font-weight:650; cursor:pointer; } button:disabled { opacity:.45; cursor:not-allowed; } .primary { color:white; background:#287de7; } .danger { color:#ffb0b0; border-color:#7c353d; background:#2a1920; } .secondary { border-color:#344a65; background:#152338; }
@media(max-width:1050px){.grid{grid-template-columns:1fr}.result pre{min-height:120px}.settings-columns{gap:22px}.setting-group+ .setting-group{padding-left:22px}}
@media(max-width:700px){ header{display:block}.state{margin-top:13px}.live-stats,.settings-columns{grid-template-columns:1fr}.live-stats ul,.notification-options{grid-template-columns:1fr}.setting-group+ .setting-group{padding:18px 0 0;border-left:0;border-top:1px solid var(--line)}.card-heading{display:grid}.toggle-row{width:100%}.settings label:not(.check,.toggle-row){grid-template-columns:1fr}.result{min-height:0} footer button{flex:1} }
</style>
