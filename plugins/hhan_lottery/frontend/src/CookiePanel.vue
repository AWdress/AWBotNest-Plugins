<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({ cookie_source: 'platform', manual_cookie: '' })
const loading = ref(true)
const saving = ref(false)
const checking = ref(false)
const checked = ref(null)
const hasManual = computed(() => Boolean(String(cfg.manual_cookie || '').trim()))

async function save(showToast = true) {
  saving.value = true
  try {
    cfg.cookie_source = cfg.cookie_source === 'manual' ? 'manual' : 'platform'
    cfg.manual_cookie = String(cfg.manual_cookie || '').trim().replace(/^cookie:\s*/i, '')
    if (cfg.cookie_source === 'manual' && !cfg.manual_cookie) throw new Error('请先填写手动 Cookie')
    await props.host.saveConfig({ ...cfg })
    checked.value = null
    if (showToast) props.host.toast.success('登录设置已保存')
    return true
  } catch (error) { props.host.toast.error('保存失败：' + (error.message || error)); return false }
  finally { saving.value = false }
}

async function check() {
  checking.value = true
  try {
    if (!await save(false)) return
    const result = await props.host.callApi('/auth/check')
    checked.value = result
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message)
  } catch (_) { checked.value = { ok: false, message: '登录设置未通过检查' } }
  finally { checking.value = false }
}

async function clearManual() {
  if (!confirm('清空已保存的手动 Cookie？')) return
  cfg.manual_cookie = ''
  if (cfg.cookie_source === 'manual') cfg.cookie_source = 'platform'
  try { await props.host.saveConfig({ ...cfg }); checked.value = null; props.host.toast.success('手动 Cookie 已清空，已切换到平台读取') }
  catch (error) { props.host.toast.error('清空失败：' + (error.message || error)) }
}

onMounted(async () => {
  try { Object.assign(cfg, await props.host.getConfig() || {}) }
  catch (error) { props.host.toast.error('读取登录设置失败：' + (error.message || error)) }
  finally { loading.value = false }
})
</script>

<template>
  <section class="cookie-panel">
    <div v-if="loading" class="loading">正在读取登录设置…</div>
    <template v-else>
      <header><div><p class="eyebrow">ACCOUNT ACCESS</p><h2>登录设置</h2><p>选择憨憨小助手访问 HHanClub 时使用的 Cookie 来源。</p></div><span class="source-badge">{{ cfg.cookie_source === 'manual' ? '手动 Cookie' : '平台同步' }}</span></header>

      <div class="source-grid" role="radiogroup" aria-label="Cookie 来源">
        <label :class="{ selected: cfg.cookie_source === 'platform' }"><input v-model="cfg.cookie_source" type="radio" value="platform"><span class="radio-dot" /><span><b>从平台读取</b><small>使用 AWBotNest 已同步的 hhanclub.net Cookie</small></span></label>
        <label :class="{ selected: cfg.cookie_source === 'manual' }"><input v-model="cfg.cookie_source" type="radio" value="manual"><span class="radio-dot" /><span><b>手动填写</b><small>使用下方保存的 Cookie，适合平台同步不可用时</small></span></label>
      </div>

      <section class="card" :class="{ inactive: cfg.cookie_source !== 'manual' }">
        <div class="card-head"><div><h3>手动 Cookie</h3><p>从浏览器开发者工具复制完整 Cookie 值，不需要填写“Cookie:”前缀。</p></div><button class="text-danger" :disabled="!hasManual" @click="clearManual">清空</button></div>
        <input v-model="cfg.manual_cookie" type="password" autocomplete="off" spellcheck="false" placeholder="name=value; name2=value2" :disabled="cfg.cookie_source !== 'manual'">
        <p class="security">Cookie 相当于账号登录凭证。请勿发送给他人，建议定期更新。</p>
      </section>

      <div v-if="checked" class="result" :class="checked.ok ? 'success' : 'danger'"><b>{{ checked.ok ? '连接正常' : '连接失败' }}</b><span>{{ checked.message }}</span></div>
      <footer><button class="primary" :disabled="saving || checking" @click="save()">{{ saving ? '保存中…' : '保存设置' }}</button><button class="secondary" :disabled="saving || checking" @click="check">{{ checking ? '检查中…' : '保存并检查连接' }}</button></footer>
    </template>
  </section>
</template>

<style scoped>
.cookie-panel { --line:#293b52; --muted:#91a3b9; color:#eaf1fa; font-family:"Microsoft YaHei",system-ui,sans-serif; }
.loading { padding:44px; text-align:center; color:var(--muted); } header,.card-head,footer { display:flex; align-items:center; justify-content:space-between; gap:18px; } header { align-items:flex-start; margin-bottom:18px; } .eyebrow { margin:0; color:#3c91f6; font-size:11px; font-weight:800; letter-spacing:.15em; } h2 { margin:2px 0 5px; font-size:25px; } header p,.card-head p { margin:0; color:var(--muted); font-size:13px; } .source-badge { padding:8px 12px; border:1px solid #31547c; border-radius:999px; color:#83baff; background:#13243a; font-size:12px; }
.source-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; } .source-grid label { display:flex; align-items:center; gap:12px; padding:17px; border:1px solid var(--line); border-radius:13px; background:#111c2b; cursor:pointer; } .source-grid label.selected { border-color:#378cf0; background:#122640; box-shadow:inset 0 0 0 1px #378cf04d; } .source-grid input { position:absolute; opacity:0; pointer-events:none; } .radio-dot { width:15px; height:15px; flex:0 0 auto; border:2px solid #61758e; border-radius:50%; } .selected .radio-dot { border:5px solid #3d94f7; } .source-grid label>span:last-child { display:grid; gap:4px; } .source-grid b { font-size:14px; } .source-grid small { color:var(--muted); font-size:12px; }
.card { padding:19px; border:1px solid var(--line); border-radius:14px; background:#111c2b; } .card.inactive { opacity:.65; } h3 { margin:0 0 4px; font-size:14px; } .text-danger { border:0; color:#ff929d; background:transparent; cursor:pointer; } .text-danger:disabled { opacity:.4; cursor:not-allowed; } .card>input { width:100%; box-sizing:border-box; margin-top:15px; padding:11px 12px; border:1px solid #354a64; border-radius:9px; color:#edf5fe; background:#0c1623; font:13px ui-monospace,Consolas,monospace; } .card>input:focus { outline:2px solid #378cf0; outline-offset:2px; } .security { margin:10px 0 0; color:#bd9d68; font-size:11px; }
.result { display:grid; gap:3px; margin-top:14px; padding:13px 15px; border:1px solid; border-radius:11px; font-size:12px; } .result.success { border-color:#276c56; color:#81dbb5; background:#102b25; } .result.danger { border-color:#743943; color:#ffabb3; background:#2a171d; } footer { justify-content:flex-start; margin-top:14px; } footer button { min-height:40px; padding:0 16px; border-radius:9px; font:inherit; font-weight:650; cursor:pointer; } .primary { border:1px solid #287de7; color:#fff; background:#287de7; } .secondary { border:1px solid #38506c; color:#dce8f7; background:#17263a; } footer button:disabled { opacity:.5; cursor:not-allowed; }
@media(max-width:650px){ header{display:block}.source-badge{display:inline-block;margin-top:12px}.source-grid{grid-template-columns:1fr}.card-head{align-items:flex-start}footer{flex-wrap:wrap}footer button{flex:1} }
</style>
