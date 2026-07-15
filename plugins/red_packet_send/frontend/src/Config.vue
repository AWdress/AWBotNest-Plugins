<script setup>
// 发红包 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 红包监控（进行中活动、可手动结束、战绩历史）。
import { ref, reactive, onMounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  enabled: true, create_word: '创建红包', status_word: '红包状态', end_word: '结束红包',
  code_length: 4, rotate_code: false,
  max_amount: 0, max_count: 0, activity_timeout_minutes: 30, end_delete_delay: 10,
  transfer_prefix: '+', congrats_text: '恭喜 {name} 抢到 {amount} 魔力！',
  blacklist_ids: '',
}

const GROUPS = [
  { key: 'main', label: '总开关' },
  { key: 'command', label: '命令' },
  { key: 'captcha', label: '验证码' },
  { key: 'limit', label: '限制' },
  { key: 'send', label: '发放与文案' },
  { key: 'block', label: '屏蔽' },
]

const tab = ref('settings')
const group = ref('main')
const loading = ref(true)
const saving = ref(false)
const cfg = reactive({ ...DEFAULTS })

// 红包监控
const activities = ref([])
const history = ref([])
const monLoading = ref(false)
const ending = ref('')

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, DEFAULTS, saved || {})
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  try {
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('配置已保存')
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

// ── 监控 ──
async function loadMonitor() {
  monLoading.value = true
  try {
    const a = await props.host.callApi('/activities')
    activities.value = a.items || []
    const h = await props.host.callApi('/history')
    history.value = h.items || []
  } catch (e) {
    props.host.toast.error('读取红包活动失败：' + (e.message || e))
  } finally {
    monLoading.value = false
  }
}
async function endOne(item) {
  if (!confirm(`提前结束红包 #${item.rp_id}？剩余 ${item.remaining_count} 个未抢的将不再发放。`)) return
  ending.value = item.key
  try {
    const r = await props.host.callApi('/end', { method: 'POST', body: { key: item.key } })
    if (r.ok) { props.host.toast.success(r.message || '已结束'); await loadMonitor() }
    else props.host.toast.error(r.message || '结束失败')
  } catch (e) { props.host.toast.error('结束失败：' + (e.message || e)) }
  finally { ending.value = '' }
}

function switchTab(t) {
  tab.value = t
  if (t === 'monitor') loadMonitor()
}
</script>

<template>
  <div class="rp">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'monitor' }]" @click="switchTab('monitor')">🧧 红包监控</button>
      </div>

      <!-- ============ 配置 ============ -->
      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">设置分组</div>
          <button v-for="g in GROUPS" :key="g.key"
                  :class="['side-item', { on: group === g.key }]" @click="group = g.key">
            <span>{{ g.label }}</span>
          </button>
        </aside>

        <div class="detail">
          <template v-if="group === 'main'">
            <h3 class="det-title">总开关</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enabled" type="checkbox" /><span>启用发红包（关闭后不响应发红包命令）</span></label>
            </section>
          </template>

          <template v-else-if="group === 'command'">
            <h3 class="det-title">命令词</h3>
            <section class="card">
              <label class="row"><span>创建命令词</span><input v-model="cfg.create_word" class="inp" /></label>
              <p class="tip">格式 `创建命令词 总额 个数`（随机验证码），或 `创建命令词 总额 个数 自定义口令`（口令做前缀+随机防挂码，一起渲染成图片）。命令发出后自动秒删。</p>
              <label class="row"><span>查看状态词</span><input v-model="cfg.status_word" class="inp" /></label>
              <label class="row"><span>结束命令词</span><input v-model="cfg.end_word" class="inp" /></label>
            </section>
          </template>

          <template v-else-if="group === 'captcha'">
            <h3 class="det-title">验证码</h3>
            <section class="card">
              <label class="row"><span>验证码位数</span>
                <input v-model.number="cfg.code_length" class="inp sm" type="number" min="4" max="8" />
                <span class="hint">4-8，去混淆字符集，不区分大小写</span></label>
              <label class="row switch"><input v-model="cfg.rotate_code" type="checkbox" /><span>每抢一个换验证码（旧码立即失效，防复制粘贴）</span></label>
            </section>
          </template>

          <template v-else-if="group === 'limit'">
            <h3 class="det-title">限制</h3>
            <section class="card">
              <div class="grid">
                <label class="row"><span>总额上限</span><input v-model.number="cfg.max_amount" class="inp sm" type="number" min="0" /><span class="hint">魔力，0=不限</span></label>
                <label class="row"><span>个数上限</span><input v-model.number="cfg.max_count" class="inp sm" type="number" min="0" /><span class="hint">0=不限</span></label>
                <label class="row"><span>活动超时</span><input v-model.number="cfg.activity_timeout_minutes" class="inp sm" type="number" min="1" max="240" /><span class="hint">分钟，无人抢完则自动结算</span></label>
                <label class="row"><span>结束后删消息</span><input v-model.number="cfg.end_delete_delay" class="inp sm" type="number" min="0" max="600" /><span class="hint">秒，0=不删</span></label>
              </div>
            </section>
          </template>

          <template v-else-if="group === 'send'">
            <h3 class="det-title">发放与文案</h3>
            <section class="card">
              <label class="row"><span>转账金额前缀</span><input v-model="cfg.transfer_prefix" class="inp sm" /><span class="hint">群转账bot据此打款，默认 +</span></label>
              <label class="row top"><span>祝贺文案</span>
                <textarea v-model="cfg.congrats_text" class="inp" rows="2" placeholder="可用 {name} {amount} {id} 占位"></textarea></label>
            </section>
          </template>

          <template v-else-if="group === 'block'">
            <h3 class="det-title">屏蔽</h3>
            <section class="card">
              <label class="row top"><span>屏蔽用户ID</span>
                <textarea v-model="cfg.blacklist_ids" class="inp" rows="3" placeholder="一行一个或逗号分隔的用户ID，这些用户参与不计入、不发放"></textarea></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 红包监控 ============ -->
      <div v-show="tab === 'monitor'" class="pane">
        <div class="toolbar">
          <span class="muted">进行中 {{ activities.length }} 个</span>
          <span class="grow"></span>
          <button class="btn" @click="loadMonitor">刷新</button>
        </div>
        <div v-if="monLoading" class="muted">加载中…</div>
        <template v-else>
          <div v-if="!activities.length" class="empty">当前没有进行中的红包<br><span class="muted">在群里用创建命令词发红包后会显示在这里</span></div>
          <table v-else class="tbl">
            <thead><tr><th>编号</th><th>群</th><th>总额</th><th>进度</th><th>剩余金额</th><th>已参与</th><th>口令</th><th></th></tr></thead>
            <tbody>
              <tr v-for="a in activities" :key="a.key">
                <td class="mono">#{{ a.rp_id }}</td>
                <td>{{ a.chat_title || a.chat_id }}</td>
                <td>{{ a.total_amount }}</td>
                <td>{{ a.packet_count - a.remaining_count }}/{{ a.packet_count }}</td>
                <td class="muted">{{ a.remaining_amount }}</td>
                <td>{{ a.participants }}</td>
                <td class="mono">{{ a.keyword }}</td>
                <td><button class="btn xs danger" :disabled="ending" @click="endOne(a)">{{ ending === a.key ? '结束中…' : '结束' }}</button></td>
              </tr>
            </tbody>
          </table>

          <div v-if="history.length" class="hist">
            <div class="hist-h">红包战绩（最近 {{ history.length }} 条）</div>
            <table class="tbl">
              <thead><tr><th>编号</th><th>群</th><th>总额</th><th>个数</th><th>参与</th><th>发放</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="(h, i) in history" :key="i">
                  <td class="mono">#{{ h.rp_id }}</td>
                  <td class="muted">{{ h.chat_id }}</td>
                  <td>{{ h.total_amount }}</td>
                  <td>{{ h.packet_count }}</td>
                  <td>{{ h.participants }}</td>
                  <td style="color:#6ee7a8">{{ h.distributed }}</td>
                  <td class="muted">{{ h.time || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.rp { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tab { padding: 8px 16px; background: none; border: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #b9c0cc); border-bottom: 2px solid transparent; }
.tab.on { color: var(--accent, #6ea8fe); border-bottom-color: var(--accent, #6ea8fe); }

.layout { display: flex; gap: 16px; align-items: flex-start; }
.sidebar { flex: 0 0 130px; display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.side-title { font-size: 11px; color: var(--text-muted, #7a8291); padding: 4px 8px 6px; }
.side-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 10px; border-radius: 8px; border: none; cursor: pointer; text-align: left; background: none; color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.side-item:hover { background: var(--bg-card, #12141c); }
.side-item.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.det-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary, #e8ebf0); }

.pane { display: flex; flex-direction: column; gap: 14px; }
.card { display: flex; flex-direction: column; gap: 12px; padding: 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child { min-width: 92px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { justify-content: flex-start; }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.tip { margin: 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.inp.sm { flex: 0 0 auto; width: 90px; }
textarea.inp { resize: vertical; font-family: inherit; line-height: 1.5; }
.btn { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn.xs { padding: 3px 9px; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }

.toolbar { display: flex; align-items: center; gap: 8px; }
.grow { flex: 1; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tbl th { color: var(--text-muted, #7a8291); font-weight: 500; font-size: 12px; }
.tbl td { color: var(--text-primary, #e8ebf0); }
.mono { font-family: ui-monospace, monospace; font-size: 12px; }
.empty { text-align: center; padding: 48px 0; font-size: 15px; color: var(--text-secondary, #b9c0cc); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.hist { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.hist-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); }

@container (max-width: 640px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
}
</style>
