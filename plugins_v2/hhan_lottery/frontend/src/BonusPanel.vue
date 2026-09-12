<script setup>
import { onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({ bonus_enabled: true, auto_confirm_bonus_transfer: false, auto_grab_random_packet: false, random_packet_delay_min: 1, random_packet_delay_max: 5, notify_cookie_error: true, single_command: '.hh', batch_command: '.hhs', cooldown_seconds: 10, result_delete: 90 })
const loading = ref(true)
const saving = ref(false)
const checking = ref(false)

async function save() {
  saving.value = true
  try {
    cfg.single_command = String(cfg.single_command || '.hh').trim() || '.hh'
    cfg.batch_command = String(cfg.batch_command || '.hhs').trim() || '.hhs'
    cfg.cooldown_seconds = Math.max(0, Math.min(Number(cfg.cooldown_seconds) || 0, 600))
    cfg.result_delete = Math.max(10, Math.min(Number(cfg.result_delete) || 90, 600))
    cfg.random_packet_delay_min = Math.max(0, Math.min(Number(cfg.random_packet_delay_min) || 0, 3600))
    cfg.random_packet_delay_max = Math.max(0, Math.min(Number(cfg.random_packet_delay_max) || 0, 3600))
    if (cfg.random_packet_delay_min > cfg.random_packet_delay_max) [cfg.random_packet_delay_min, cfg.random_packet_delay_max] = [cfg.random_packet_delay_max, cfg.random_packet_delay_min]
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('赠豆配置已保存')
  } catch (error) { props.host.toast.error('保存失败：' + (error.message || error)) }
  finally { saving.value = false }
}

async function checkCookie() {
  checking.value = true
  try {
    const result = await props.host.callApi('/bonus/cookie/check')
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message)
  } catch (error) { props.host.toast.error('检查失败：' + (error.message || error)) }
  finally { checking.value = false }
}

onMounted(async () => {
  try { Object.assign(cfg, await props.host.getConfig() || {}) }
  catch (error) { props.host.toast.error('读取配置失败：' + (error.message || error)) }
  finally { loading.value = false }
})
</script>

<template>
  <section class="bonus-panel">
    <div v-if="loading" class="loading">正在读取配置…</div>
    <template v-else>
      <header>
        <div><p class="eyebrow">HHANCLUB</p><h2>赠豆助手</h2><p>通过自己的用户账号发送命令，支持单人和批量赠送。</p></div>
        <span class="badge" :class="{ on: cfg.bonus_enabled }"><i />{{ cfg.bonus_enabled ? '命令已启用' : '命令已停用' }}</span>
      </header>

      <div class="layout">
        <section class="card">
          <div class="section-head"><div><h3>命令设置</h3><p>修改后立即保存，下一条消息开始生效。</p></div><button class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存设置' }}</button></div>
          <label class="switch-row"><span><b>启用赠豆命令</b><small>监听用户账号发出的匹配命令</small></span><input v-model="cfg.bonus_enabled" type="checkbox" role="switch"></label>
          <label class="switch-row"><span><b>自动确认憨豆转赠</b><small>仅确认官方机器人 8780479105 对本账号赠豆命令发出的二次确认</small></span><input v-model="cfg.auto_confirm_bonus_transfer" type="checkbox" role="switch"></label>
          <label class="switch-row"><span><b>自动领取随机红包</b><small>解析官方机器人 8780479105 发布的口令红包，随机等待后发送口令</small></span><input v-model="cfg.auto_grab_random_packet" type="checkbox" role="switch"></label>
          <label class="switch-row"><span><b>Cookie 异常时通知</b><small>登录态失效时通过平台通知提醒</small></span><input v-model="cfg.notify_cookie_error" type="checkbox" role="switch"></label>
          <div class="fields">
            <label><span>单人命令</span><input v-model="cfg.single_command" type="text" placeholder=".hh"></label>
            <label><span>批量命令</span><input v-model="cfg.batch_command" type="text" placeholder=".hhs"></label>
            <label><span>赠送冷却</span><div><input v-model.number="cfg.cooldown_seconds" type="number" min="0" max="600"><em>秒</em></div></label>
            <label><span>结果保留</span><div><input v-model.number="cfg.result_delete" type="number" min="10" max="600"><em>秒</em></div></label>
            <label><span>红包最短延迟</span><div><input v-model.number="cfg.random_packet_delay_min" type="number" min="0" max="3600" step="0.5"><em>秒</em></div></label>
            <label><span>红包最长延迟</span><div><input v-model.number="cfg.random_packet_delay_max" type="number" min="0" max="3600" step="0.5"><em>秒</em></div></label>
          </div>
        </section>

        <aside class="card guide">
          <h3>命令格式</h3>
          <div class="example"><span>单人赠送</span><code>{{ cfg.single_command || '.hh' }} Alice 100 感谢分享</code></div>
          <div class="example"><span>批量赠送</span><code>{{ cfg.batch_command || '.hhs' }} Alice Bob 100 感谢</code></div>
          <ul><li>站点最低赠送 100 憨豆</li><li>批量任务最多 50 位用户</li><li>自动确认只识别官方机器人和“确认赠送”按钮</li><li>随机红包按账号、群组和消息去重，不会重复发送口令</li></ul>
          <button class="secondary" :disabled="checking" @click="checkCookie">{{ checking ? '检查中…' : '检查平台 Cookie' }}</button>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.bonus-panel { --line:#293a50; --muted:#91a2b8; color:#e9f0f9; font-family:"Microsoft YaHei",system-ui,sans-serif; }
.loading { padding:42px; text-align:center; color:var(--muted); }
header,.section-head,.switch-row { display:flex; align-items:center; justify-content:space-between; gap:18px; } header { align-items:flex-start; margin-bottom:18px; } h2 { margin:2px 0 5px; font-size:25px; color:#f5f8fc; } header p,.section-head p { margin:0; color:var(--muted); font-size:13px; } .eyebrow { color:#3d91f7; font-size:11px; font-weight:800; letter-spacing:.16em; }
.badge { display:flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:#9dadc1; background:#111c2b; font-size:12px; } .badge i { width:7px; height:7px; border-radius:50%; background:#64748b; } .badge.on i { background:#36d394; box-shadow:0 0 0 5px #36d3941c; }
.layout { display:grid; grid-template-columns:minmax(360px,1.25fr) minmax(270px,.75fr); gap:14px; } .card { padding:19px; border:1px solid var(--line); border-radius:14px; background:#111c2b; } h3 { margin:0 0 5px; font-size:14px; } button { min-height:38px; padding:0 14px; border:1px solid #38506c; border-radius:9px; color:#dce8f7; background:#17263a; font:inherit; font-weight:650; cursor:pointer; } button:disabled { opacity:.5; cursor:not-allowed; } .primary { border-color:#287de7; color:#fff; background:#287de7; }
.switch-row { padding:15px 0; border-bottom:1px solid #223248; } .switch-row span { display:grid; gap:3px; } .switch-row b { font-size:13px; } .switch-row small { color:var(--muted); }
.fields { display:grid; grid-template-columns:1fr 1fr; gap:13px; margin-top:16px; } .fields label { display:grid; gap:7px; color:#aebed0; font-size:12px; } .fields label>div { display:flex; align-items:center; } input[type=text],input[type=number] { width:100%; min-width:0; box-sizing:border-box; padding:9px 10px; border:1px solid #344861; border-radius:8px; color:#edf4fc; background:#0d1725; font:inherit; } em { margin-left:-33px; color:#74869e; font-style:normal; font-size:11px; pointer-events:none; }
.guide h3 { margin-bottom:15px; } .example { display:grid; gap:6px; margin-bottom:14px; } .example span { color:var(--muted); font-size:11px; } code { display:block; overflow:auto; padding:10px; border-radius:8px; color:#84bcff; background:#0c1623; font-size:12px; white-space:nowrap; } ul { padding-left:18px; margin:16px 0; color:#9dadc1; font-size:12px; line-height:1.85; } .secondary { width:100%; }
@media(max-width:720px){ header{display:block}.badge{width:fit-content;margin-top:12px}.layout{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.section-head{align-items:flex-start}.section-head button{flex:0 0 auto} }
</style>
