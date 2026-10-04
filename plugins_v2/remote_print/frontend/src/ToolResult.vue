<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
  busy: { type: Boolean, default: false },
})
const area = ref(null)
const panel = ref(null)
const copyNotice = ref('')
const rows = computed(() => Math.max(2, Math.min(10,
  String(props.result.message).split('\n').reduce((count, line) => count + Math.max(1, Math.ceil(line.length / 70)), 0))))
let mounted = true
onBeforeUnmount(() => { mounted = false })
onMounted(() => panel.value?.scrollIntoView?.({ block: 'center' }))

async function copy() {
  try {
    if (!navigator.clipboard?.writeText) throw new Error('当前页面不支持自动复制')
    await navigator.clipboard.writeText(props.result.message)
    if (mounted) copyNotice.value = '已复制。'
  } catch {
    if (!mounted) return
    area.value?.focus()
    area.value?.select()
    copyNotice.value = '已选中结果，请使用系统复制菜单或 Ctrl+C 复制。'
  }
}
</script>

<template>
  <section ref="panel" class="result" :class="{ 'result-error': !result.ok }" aria-label="工具执行结果">
    <div class="result-head">
      <h4>{{ result.title }}{{ busy ? '' : result.ok ? ' · 已完成' : ' · 未完成' }}</h4>
      <button type="button" class="button" :disabled="busy" @click="copy">复制结果</button>
    </div>
    <label class="sr-only" for="rp-tool-result">工具执行结果，可选中复制</label>
    <textarea id="rp-tool-result" ref="area" class="result-text" :rows="rows" readonly :value="result.message" />
    <p class="sr-only" role="status">{{ busy ? '正在执行，请稍候。' : result.ok ? '操作已完成，详细结果可在下方查看或复制。' : result.message }}</p>
    <p v-if="copyNotice" class="help" role="status">{{ copyNotice }}</p>
  </section>
</template>

<style scoped>
.result { min-width: 0; padding-top: 20px; border-top: 1px solid var(--border-light, #2a3c52); scroll-margin-block: 96px; }
.result-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
h4, p { margin: 0; }
h4 { font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.result-error .result-head { color: var(--danger, #ff8e96); }
.button { min-height: 44px; padding: 10px 16px; border: 1px solid var(--border-light, #2a3c52); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #172131); color: var(--text-primary, #eef1f7); font: inherit; cursor: pointer; flex-shrink: 0; }
.button:hover:not(:disabled) { border-color: var(--accent, #82aaff); }
.button:disabled { opacity: .58; cursor: not-allowed; }
.result-text { box-sizing: border-box; width: 100%; min-height: 64px; max-height: 320px; border: 1px solid var(--border-light, #2a3c52); border-radius: var(--radius-sm, 8px); background: var(--bg-elevated, #172131); color: var(--text-primary, #eef1f7); padding: 10px 12px; font: inherit; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; resize: vertical; caret-color: var(--accent, #3080f0); scrollbar-color: var(--border-light, #2a3c52) var(--bg-elevated, #172131); scrollbar-width: thin; }
button:focus-visible, textarea:focus-visible { outline: 2px solid var(--accent, #82aaff); outline-offset: 3px; }
.help { font-size: 13px; line-height: 1.65; margin-top: 7px; color: var(--text-secondary, #b6bdcd); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
::selection { background: var(--accent-dim, #243047); color: var(--text-primary, #e8eaf0); }
@media (max-width: 768px) {
  .result-head { flex-wrap: wrap; align-items: flex-start; }
  .result-text { font-size: 16px; }
  .help { font-size: 14px; }
}
</style>
