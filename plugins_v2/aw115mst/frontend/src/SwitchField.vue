<script setup>
defineProps({modelValue: Boolean, title: String, hint: String})
defineEmits(['update:modelValue'])
</script>

<template>
  <label class="switch-field">
    <span><b>{{ title }}</b><small v-if="hint">{{ hint }}</small></span>
    <input type="checkbox" role="switch" :checked="modelValue" @change="$emit('update:modelValue', $event.target.checked)">
    <i aria-hidden="true"></i>
  </label>
</template>

<style scoped>
.switch-field{position:relative;display:flex;align-items:center;justify-content:space-between;gap:18px;min-height:54px;cursor:pointer}.switch-field span{min-width:0}.switch-field b,.switch-field small{display:block}.switch-field b{font-size:13px;font-weight:650}.switch-field small{margin-top:3px;color:var(--mst-muted);font-size:12px;line-height:1.5}.switch-field input{position:absolute;inset-inline-end:0;width:38px;height:26px;margin:0;opacity:0;cursor:pointer}.switch-field i{position:relative;flex:0 0 38px;width:38px;height:22px;border:1px solid var(--mst-line);border-radius:11px;background:var(--mst-input);pointer-events:none}.switch-field i::after{content:"";position:absolute;inset-inline-start:3px;top:3px;width:14px;height:14px;border-radius:50%;background:var(--mst-muted)}.switch-field input:checked+i{border-color:var(--mst-accent);background:var(--mst-accent)}.switch-field input:checked+i::after{inset-inline-start:19px;background:#fff}.switch-field:has(input:focus-visible){outline:2px solid var(--mst-accent);outline-offset:3px;border-radius:6px}.switch-field:has(input:disabled){cursor:not-allowed;opacity:.6}@media(prefers-reduced-motion:no-preference){.switch-field i::after{transition:inset-inline-start .16s ease-out,background-color .16s ease-out}}@media(forced-colors:active){.switch-field i{border:1px solid CanvasText}.switch-field input:checked+i{background:Highlight}}
</style>
