<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  enabled: false,
  trigger_keywords: '验证码,发送图中字符,识别上方,幸运红包',
  target_senders: '', target_groups: [],
  ocr_enabled: true, copy_fallback: true,
  code_min_len: 4, code_max_len: 8, join_delay: 2,
  slash_command_protection: true, slash_min_total: 0,
  success_markers: '抢到,恭喜', transfer_prefix: '+',
  activity_ttl_minutes: 30, notify_owner: true,
}
const GROUPS = [
  { key: 'main', label: '总开关' }, { key: 'scope', label: '识别范围' },
  { key: 'recognize', label: '口令识别' }, { key: 'behavior', label: '参与行为' },
  { key: 'general', label: '通用' },
]

const cfg = reactive({ ...DEFAULTS })
const tab = ref('settings')
const group = ref('main')
const loading = ref(true)
const configReady = ref(false)
const saving = ref(false)
const historyLoading = ref(false)
const clearing = ref(false)
const history = ref([])
const chatNames = ref([])
const status = ref({ ocr_available: false, active_count: 0 })
const groupsText = computed({
  get: () => Array.isArray(cfg.target_groups) ? cfg.target_groups.join('\n') : String(cfg.target_groups || ''),
  set: value => { cfg.target_groups = value.split(/[\s,]+/).map(x => x.trim()).filter(Boolean) },
})

onMounted(async () => {
  try {
    Object.assign(cfg, DEFAULTS, await props.host.getConfig() || {})
    configReady.value = true
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally { loading.value = false }
  try { status.value = await props.host.callApi('/status') }
  catch (e) { props.host.toast.error('读取运行状态失败：' + (e.message || e)) }
  await loadChatNames()
})

async function save() {
  if (!configReady.value || saving.value) {
    if (!configReady.value) props.host.toast.error('配置未成功读取，请重新打开配置页后再保存')
    return
  }
  saving.value = true
  try {
    if (typeof cfg.slash_min_total !== 'number' || !Number.isFinite(cfg.slash_min_total) || cfg.slash_min_total < 0) {
      throw new Error('斜杠红包最低总额请填写大于或等于 0 的有效数字，0 表示不限制')
    }
    await props.host.saveConfig({ ...cfg })
    await loadChatNames()
    props.host.toast.success('配置已保存')
  } catch (e) { props.host.toast.error('保存失败：' + (e.message || e)) }
  finally { saving.value = false }
}
async function switchTab(value) {
  tab.value = value
  if (value === 'history') await loadHistory()
}
async function loadHistory() {
  historyLoading.value = true
  try {
    const [h, s] = await Promise.all([
      props.host.callApi('/history'), props.host.callApi('/status'),
    ])
    history.value = h.items || []
    status.value = s
    await loadChatNames()
  } catch (e) { props.host.toast.error('读取记录失败：' + (e.message || e)) }
  finally { historyLoading.value = false }
}
async function clearHistory() {
  if (!confirm('清空全部抢包记录？')) return
  clearing.value = true
  try {
    await props.host.callApi('/history/clear', { method: 'POST', body: {} })
    history.value = []
    props.host.toast.success('记录已清空')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
  finally { clearing.value = false }
}
function timeText(ts) {
  if (!ts) return '—'
  return new Date(Number(ts) * 1000).toLocaleString()
}

async function loadChatNames() {
  try {
    const r = await props.host.callApi('/chat_names')
    chatNames.value = r.items || []
  } catch {}
}

function nameOf(id) {
  const item = chatNames.value.find(x => String(x.id) === String(id))
  return item ? item.title : String(id)
}
</script>

<template>
  <div class="rpg">
    <div v-if="loading" class="muted loading">加载配置…</div>
    <template v-else>
      <p v-if="!configReady" class="tip error" role="alert">配置读取失败，已禁止保存以保护已有配置。请重新打开配置页重试。</p>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'history' }]" @click="switchTab('history')">🧧 抢包记录</button>
      </div>

      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">设置分组</div>
          <button v-for="g in GROUPS" :key="g.key" :class="['side-item', { on: group === g.key }]" @click="group = g.key">{{ g.label }}</button>
        </aside>
        <main class="detail">
          <template v-if="group === 'main'">
            <h3>总开关</h3><section class="card">
              <label class="switch"><input v-model="cfg.enabled" type="checkbox"><span>启用自动抢红包</span></label>
              <p class="tip">处理群内正文口令、图片财富密码和验证码口令红包，不会响应自己发出的红包。</p>
            </section>
          </template>
          <template v-else-if="group === 'scope'">
            <h3>识别范围</h3><section class="card">
              <label class="row top"><span>触发关键词</span><textarea v-model="cfg.trigger_keywords" class="inp" rows="3" /></label>
              <p class="tip indent">验证码图片说明含任一关键词才尝试参与；正文拼手气红包按固定格式自动识别。</p>
              <label class="row top"><span>发包人白名单</span><textarea v-model="cfg.target_senders" class="inp" rows="4" placeholder="一行一个：用户ID 备注；留空不限" /></label>
              <label class="row top"><span>群组白名单</span><textarea v-model="groupsText" class="inp" rows="4" placeholder="一行一个群ID；留空不限" /></label>
              <div v-if="chatNames.length" class="chat-names"><span class="chat-label">已识别：</span><span v-for="item in chatNames" :key="item.id" class="chat-name">{{ item.title }} ({{ item.id }})</span></div>
            </section>
          </template>
          <template v-else-if="group === 'recognize'">
            <h3>口令识别</h3><section class="card">
              <div class="badge ok">支持正文直接口令</div>
              <p class="tip">识别“发送下方口令领取：”后的文字；新消息和后续编辑都会检查。</p>
              <div class="badge ok">支持动态财富密码</div>
              <p class="tip">自动 OCR“财富密码见图片”的红包；图片更新后可重新识别，红包领完后停止。</p>
              <label class="switch"><input v-model="cfg.ocr_enabled" type="checkbox"><span>启用 OCR 识别验证码</span></label>
              <div :class="['badge', status.ocr_available ? 'ok' : 'warn']">{{ status.ocr_available ? 'ddddocr 可用' : 'ddddocr 不可用，将使用复制兜底' }}</div>
              <label class="switch"><input v-model="cfg.copy_fallback" type="checkbox"><span>启用复制兜底</span></label>
              <p class="tip">监听他人的中奖确认，支持独立发送或回复红包的口令；缓存漏记时会现场回查原消息。</p>
              <div class="grid"><label class="row"><span>最短位数</span><input v-model.number="cfg.code_min_len" class="inp sm" type="number" min="1" max="12"></label>
              <label class="row"><span>最长位数</span><input v-model.number="cfg.code_max_len" class="inp sm" type="number" min="1" max="30"></label></div>
            </section>
          </template>
          <template v-else-if="group === 'behavior'">
            <h3>参与行为</h3><section class="card">
              <label class="row"><span>参与延迟</span><input v-model.number="cfg.join_delay" class="inp sm" type="number" min="0" max="60" step="0.5"><span class="hint">秒</span></label>
              <label class="switch"><input v-model="cfg.slash_command_protection" type="checkbox" aria-describedby="slash-protection-tip"><span>斜杠口令防误触保护</span></label>
              <p id="slash-protection-tip" class="tip">仅保护 / 开头的口令：在 / 后插入零宽空格，显示不变，但实际发送文本会变化。严格匹配原口令的红包可能拒收；会移除零宽字符的机器人仍可能识别为命令。</p>
              <label class="row"><span>斜杠红包最低总额</span><input v-model.number="cfg.slash_min_total" class="inp sm" type="number" min="0" step="any" inputmode="decimal" aria-describedby="slash-min-total-tip"></label>
              <p id="slash-min-total-tip" class="tip">只筛选 / 开头的口令，红包总额低于此值就跳过；0 表示不限制。设置大于 0 时，总额无法识别的红包也会跳过，普通口令不受影响。</p>
              <label class="row"><span>中奖关键词</span><input v-model="cfg.success_markers" class="inp"></label>
              <label class="row"><span>金额前缀</span><input v-model="cfg.transfer_prefix" class="inp sm"></label>
            </section>
          </template>
          <template v-else>
            <h3>通用</h3><section class="card">
              <label class="row"><span>监听时长</span><input v-model.number="cfg.activity_ttl_minutes" class="inp sm" type="number" min="1" max="240"><span class="hint">分钟</span></label>
              <label class="switch"><input v-model="cfg.notify_owner" type="checkbox"><span>发送口令和中奖时通知我</span></label>
            </section>
          </template>
          <div class="savebar"><button class="btn primary" :disabled="saving || !configReady" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </main>
      </div>

      <div v-show="tab === 'history'" class="pane">
        <div class="summary"><div><b>{{ status.active_count || 0 }}</b><span>监听中</span></div><div><b>{{ history.length }}</b><span>中奖记录</span></div><div><b>{{ status.ocr_available ? '可用' : '不可用' }}</b><span>OCR</span></div></div>
        <div class="toolbar"><span class="muted">仅成功确认中奖后写入记录</span><span class="grow"/><button class="btn" @click="loadHistory">刷新</button><button class="btn danger" :disabled="clearing || !history.length" @click="clearHistory">清空</button></div>
        <div class="table-wrap"><table><thead><tr><th>时间</th><th>群组</th><th>发包人</th><th>口令</th><th>方式</th><th>结果</th></tr></thead>
          <tbody><tr v-for="(item, i) in history" :key="i"><td>{{ timeText(item.ts) }}</td><td>{{ nameOf(item.group_id) }} ({{ item.group_id }})</td><td>{{ item.sender || '—' }}</td><td class="code">{{ item.code || '—' }}</td><td><span class="badge ok">{{ item.mode || '—' }}</span></td><td class="success">{{ item.ok ? '成功' : '失败' }}</td></tr>
          <tr v-if="!historyLoading && !history.length"><td colspan="6" class="empty">暂无抢包记录</td></tr><tr v-if="historyLoading"><td colspan="6" class="empty">加载中…</td></tr></tbody></table></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.rpg{color:var(--text-primary,#e8edf5);font-size:13px}.loading{padding:30px}.tabs{display:flex;border-bottom:1px solid var(--border-light,#2a2e3a)}.tab{padding:11px 18px;border:0;border-bottom:2px solid transparent;background:none;color:var(--text-secondary,#b9c0cc);cursor:pointer}.tab.on{color:var(--text-primary,#fff);border-bottom-color:var(--primary,#4a9eff)}.layout{display:grid;grid-template-columns:150px minmax(0,1fr);min-height:430px}.sidebar{padding:18px 10px;border-right:1px solid var(--border-light,#2a2e3a)}.side-title{padding:0 10px 8px;color:var(--text-muted,#7a8291);font-size:11px}.side-item{display:block;width:100%;padding:9px 10px;border:0;border-radius:6px;background:none;color:var(--text-secondary,#b9c0cc);text-align:left;cursor:pointer}.side-item.on{background:var(--bg-card,#20242e);color:var(--text-primary,#fff)}.detail{padding:20px;min-width:0}.detail h3{margin:0 0 12px}.card{padding:16px;border:1px solid var(--border-light,#2a2e3a);border-radius:8px;background:var(--bg-card,#151821)}.row,.switch{display:flex;align-items:center;gap:10px;margin:10px 0}.row>span:first-child{width:115px;flex:none;color:var(--text-secondary,#b9c0cc)}.row.top{align-items:flex-start}.inp{box-sizing:border-box;min-width:0;flex:1;padding:8px 10px;border:1px solid var(--border-light,#343946);border-radius:6px;background:var(--bg-input,#11141b);color:inherit}.inp.sm{max-width:150px}.tip,.hint,.muted{color:var(--text-muted,#7a8291)}.tip{margin:5px 0 14px;line-height:1.6;overflow-wrap:anywhere}.tip.error{color:var(--danger,#ff7777)}.tip.indent{margin-left:125px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.savebar{margin-top:16px}.btn{padding:7px 13px;border:1px solid var(--border-light,#343946);border-radius:6px;background:var(--bg-card,#20242e);color:inherit;cursor:pointer}.btn.primary{padding:9px 22px;border-color:var(--primary,#4a9eff);background:var(--primary,#4a9eff);color:#fff}.btn.danger{color:#ff7777}.btn:disabled{opacity:.5;cursor:not-allowed}.inp:focus-visible,button:focus-visible{outline:2px solid var(--primary,#4a9eff);outline-offset:2px}.badge{display:inline-block;padding:3px 8px;border-radius:10px;font-size:11px}.badge.ok{background:#193c31;color:#6ee7a8}.badge.warn{background:#463b1c;color:#e0b34d}.pane{padding:20px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}.summary>div{padding:14px;border:1px solid var(--border-light,#2a2e3a);border-radius:8px;background:var(--bg-card,#151821)}.summary b,.summary span{display:block}.summary b{font-size:20px}.summary span{margin-top:3px;color:var(--text-muted,#7a8291)}.toolbar{display:flex;align-items:center;gap:8px;margin-bottom:10px}.grow{flex:1}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:9px 10px;border-bottom:1px solid var(--border-light,#2a2e3a);text-align:left;white-space:nowrap}th{color:var(--text-secondary,#b9c0cc);font-weight:500}.code{font-family:monospace}.success{color:#6ee7a8}.empty{text-align:center;color:var(--text-muted,#7a8291);padding:35px}@media(max-width:620px){.inp{width:100%}.layout{grid-template-columns:1fr}.sidebar{display:flex;overflow:auto;border-right:0;border-bottom:1px solid var(--border-light,#2a2e3a)}.side-title{display:none}.side-item{width:auto;white-space:nowrap}.grid{grid-template-columns:1fr}.row{align-items:flex-start;flex-direction:column}.row>span:first-child{width:auto}.tip.indent{margin-left:0}.summary{grid-template-columns:1fr}}
</style>
