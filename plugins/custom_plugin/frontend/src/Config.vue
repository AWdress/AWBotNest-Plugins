<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: { type: String, required: true }, host: { type: Object, required: true } })
const cfg = reactive({ code_enabled: false, source: '' })
const status = ref({ state: 'idle', message: '读取中…', traceback: '', template: '' })
const loading = ref(true)
const saving = ref(false)
const validating = ref(false)
const stateLabel = computed(() => ({ running: '运行中', error: '错误', disabled: '未启用', idle: '已停止' }[status.value.state] || status.value.state))

async function refresh() { status.value = await props.host.callApi('/status') }
onMounted(async () => {
  try {
    Object.assign(cfg, await props.host.getConfig() || {})
    await refresh()
    if (!cfg.source) cfg.source = status.value.template || ''
  } catch (e) { props.host.toast.error('读取失败：' + (e.message || e)) }
  finally { loading.value = false }
})
async function validate() {
  validating.value = true
  try {
    const r = await props.host.callApi('/validate', { method: 'POST', body: { source: cfg.source } })
    if (r.ok) props.host.toast.success(r.message)
    else props.host.toast.error(r.message)
    return !!r.ok
  } catch (e) { props.host.toast.error('检查失败：' + (e.message || e)); return false }
  finally { validating.value = false }
}
async function save() {
  if (!await validate()) return
  saving.value = true
  try {
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('配置已保存，平台将自动重载插件')
  } catch (e) { props.host.toast.error('保存失败：' + (e.message || e)) }
  finally { saving.value = false }
}
function restoreTemplate() {
  if (!confirm('用示例模板覆盖当前编辑内容？')) return
  cfg.source = status.value.template || ''
}
</script>

<template>
  <div class="custom" v-if="!loading">
    <section class="warning"><b>⚠️ 安全提醒</b><span>这里的 Python 源码会获得普通插件的完整权限。只粘贴你自己编写或已经审查过的代码。</span></section>
    <div class="topbar">
      <label class="switch"><input v-model="cfg.code_enabled" type="checkbox"><span>运行自定义源码</span></label>
      <span :class="['state', status.state]">{{ stateLabel }}</span>
      <span class="message">{{ status.message }}</span>
    </div>
    <section class="editor-card">
      <div class="editor-head"><div><b>Python 插件源码</b><small>必须提供 <code>async def setup(ctx)</code>，可选 <code>async def teardown(ctx)</code></small></div>
        <button class="btn" @click="restoreTemplate">恢复示例</button>
      </div>
      <textarea v-model="cfg.source" spellcheck="false" class="editor" />
    </section>
    <details v-if="status.traceback" class="trace"><summary>查看最近错误</summary><pre>{{ status.traceback }}</pre></details>
    <div class="actions"><button class="btn" :disabled="validating" @click="validate">{{ validating ? '检查中…' : '检查源码' }}</button><button class="btn primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存并运行' }}</button></div>
  </div>
  <div v-else class="loading">正在读取配置…</div>
</template>

<style scoped>
.custom{color:var(--text-primary,#e8edf5);padding:20px;font-size:13px}.warning{display:flex;gap:14px;padding:14px 16px;border:1px solid #8b6428;border-radius:10px;background:#392b16;color:#ffd68b}.warning span{color:#e5c99b}.topbar{display:flex;align-items:center;gap:14px;margin:16px 0}.switch{display:flex;align-items:center;gap:8px;font-weight:600}.state{padding:4px 9px;border-radius:999px;background:#303642}.state.running{background:#153d30;color:#68e5a7}.state.error{background:#482326;color:#ff8d94}.message{color:var(--text-muted,#8d96a6)}.editor-card{overflow:hidden;border:1px solid var(--border-light,#303642);border-radius:10px;background:var(--bg-card,#151923)}.editor-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--border-light,#303642)}.editor-head small{display:block;margin-top:5px;color:var(--text-muted,#8d96a6)}code{color:#74b7ff}.editor{box-sizing:border-box;width:100%;height:430px;padding:16px;border:0;outline:0;resize:vertical;background:#0d1118;color:#dce5f3;font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;tab-size:4}.trace{margin-top:12px;padding:11px 14px;border:1px solid #62343a;border-radius:8px;background:#26181b;color:#ffafb5}.trace pre{overflow:auto;max-height:220px;white-space:pre-wrap}.actions{display:flex;justify-content:flex-end;gap:10px;margin-top:16px}.btn{padding:8px 14px;border:1px solid var(--border-light,#3b4352);border-radius:7px;background:var(--bg-card,#202632);color:inherit;cursor:pointer}.btn.primary{border-color:var(--primary,#3d91ff);background:var(--primary,#3d91ff);color:#fff}.btn:disabled{opacity:.55}.loading{padding:30px;color:#8d96a6}@media(max-width:650px){.custom{padding:12px}.topbar,.warning{align-items:flex-start;flex-direction:column}.editor{height:360px}.message{word-break:break-all}}
</style>
