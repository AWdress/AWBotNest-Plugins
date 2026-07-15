<script setup>
// 群组选择器：从账号最近对话（/dialogs）里勾选群，值为群ID数组。
// Vue 模式没有平台内置 chat 选择器，故自带一个（含搜索 + 手动补 ID）。
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  dialogs: { type: Array, default: () => [] }, // [{id, title}]
})
const emit = defineEmits(['update:modelValue'])

const kw = ref('')
const manualId = ref('')

const selected = computed(() => (props.modelValue || []).map(Number))
const titleOf = (id) => {
  const d = props.dialogs.find(x => Number(x.id) === Number(id))
  return d ? d.title : String(id)
}
const filtered = computed(() => {
  const k = kw.value.trim().toLowerCase()
  if (!k) return props.dialogs
  return props.dialogs.filter(d =>
    String(d.title || '').toLowerCase().includes(k) || String(d.id).includes(k))
})
// 已选但不在对话列表里的 ID（手动补的 / 已退群的）
const extra = computed(() => selected.value.filter(id => !props.dialogs.some(d => Number(d.id) === id)))

function toggle(id) {
  id = Number(id)
  const arr = selected.value.slice()
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
  emit('update:modelValue', arr)
}
function addManual() {
  const id = Number(String(manualId.value).trim())
  if (!id) return
  if (!selected.value.includes(id)) emit('update:modelValue', [...selected.value, id])
  manualId.value = ''
}
</script>

<template>
  <div class="picker">
    <div class="picker-bar">
      <input v-model="kw" class="pinp" placeholder="搜索群名/ID…" />
      <span class="cnt">已选 {{ selected.length }}</span>
    </div>
    <div class="picker-list">
      <label v-for="d in filtered" :key="d.id" class="pchip">
        <input type="checkbox" :checked="selected.includes(Number(d.id))" @change="toggle(d.id)" />
        <span class="ptitle">{{ d.title }}</span>
        <span class="pid">{{ d.id }}</span>
      </label>
      <div v-if="!filtered.length" class="pempty">没有匹配的群（可下方手动补 ID）</div>
    </div>
    <div v-if="extra.length" class="extra">
      <span class="extra-l">列表外已选：</span>
      <span v-for="id in extra" :key="id" class="etag">{{ id }}<a class="ex" @click="toggle(id)">×</a></span>
    </div>
    <div class="manual">
      <input v-model="manualId" class="pinp" placeholder="手动补群ID（如 -1001234567890）" @keyup.enter="addManual" />
      <button class="mbtn" type="button" @click="addManual">添加</button>
    </div>
  </div>
</template>

<style scoped>
.picker { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.picker-bar { display: flex; align-items: center; gap: 8px; }
.cnt { font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.pinp { flex: 1; min-width: 0; padding: 6px 9px; border-radius: 6px; font-size: 12px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.picker-list { display: flex; flex-direction: column; gap: 2px; max-height: 200px; overflow-y: auto; padding: 6px; border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; }
.pchip { display: flex; align-items: center; gap: 8px; padding: 5px 6px; border-radius: 5px; cursor: pointer; font-size: 12px; }
.pchip:hover { background: var(--bg-card, #12141c); }
.ptitle { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary, #e8ebf0); }
.pid { font-size: 11px; color: var(--text-muted, #7a8291); }
.pempty { padding: 8px; font-size: 12px; color: var(--text-muted, #7a8291); }
.extra { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; }
.extra-l { color: var(--text-muted, #7a8291); }
.etag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); }
.ex { cursor: pointer; color: #ff6b6b; }
.manual { display: flex; gap: 8px; }
.mbtn { padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.mbtn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
</style>
