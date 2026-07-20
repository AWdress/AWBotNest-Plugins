<script setup>
// 多站点转账 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（站点开关矩阵 + 排行榜/延迟/进阶）/ 排行榜（查看各站点榜单、最近流水、清空）。
import { ref, reactive, onMounted, computed } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

// 站点（key 对应 config 字段；群组/bot 平台内置写死，这里只开关功能）
const SITES = [
  { key: 'site_audiences', label: 'Audiences', bonus: '爆米花' },
  { key: 'site_hddolby', label: 'HDDolby', bonus: '鲸币' },
  { key: 'site_azusa', label: 'Azusa', bonus: '魔力值' },
  { key: 'site_zm', label: 'ZmPT', bonus: '电力', note: '致谢/榜单自动延后约11秒发出' },
  { key: 'site_springsunday', label: 'SpringSunday', bonus: '茉莉', note: '含两个群' },
  { key: 'site_hdsky', label: 'HDSky', bonus: '银元' },
  { key: 'site_mocktest', label: 'MockTest', bonus: '测试', note: '默认关' },
]
const TOGGLES = [
  { v: 'on', l: '启用' }, { v: 'notify', l: '群内致谢' },
  { v: 'lb_in', l: '打赏榜' }, { v: 'lb_out', l: '赏赐榜' },
]
const RANK_OUTPUTS = [
  { v: 'image', l: '图片（默认）' },
  { v: 'native_table', l: 'Telegram 原生表格' },
  { v: 'text', l: '文本' },
]
const SSD_MODES = [{ v: 'off', l: '关闭' }, { v: 'once', l: '单次确认' }, { v: '5min', l: '5分钟确认' }]

const DEFAULTS = {
  site_audiences: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hddolby: ['on', 'notify', 'lb_in', 'lb_out'],
  site_azusa: ['on', 'notify', 'lb_in', 'lb_out'],
  site_zm: ['on', 'notify', 'lb_in', 'lb_out'],
  site_springsunday: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hdsky: ['on', 'notify', 'lb_in', 'lb_out'],
  site_mocktest: [],
  rank_output: 'image', rank_size: 10, rank_command: '转账排行',
  notify_delay_min: 0, notify_delay_max: 0,
  ssd_click_mode: 'off', owner_notify: false,
}

const GROUPS = [
  { key: 'sites', label: '站点' },
  { key: 'rank', label: '排行榜' },
  { key: 'delay', label: '致谢延迟' },
  { key: 'adv', label: '进阶' },
]

const tab = ref('settings')
const group = ref('sites')
const loading = ref(true)
const saving = ref(false)
const cfg = reactive({ ...DEFAULTS })

// 排行榜面板
const sites = ref([])
const lbSite = ref('')
const lbDir = ref('in')
const lbRows = ref([])
const lbLoading = ref(false)
const recent = ref([])

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, DEFAULTS, saved || {})
    for (const s of SITES) if (!Array.isArray(cfg[s.key])) cfg[s.key] = []
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
})

function has(key, v) { return (cfg[key] || []).includes(v) }
function toggle(key, v) {
  const arr = (cfg[key] || []).slice()
  const i = arr.indexOf(v)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(v)
  cfg[key] = arr
}

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

// ── 排行榜面板 ──
async function loadSites() {
  try {
    const r = await props.host.callApi('/sites')
    sites.value = r.sites || []
    if (!lbSite.value && sites.value.length) {
      const withData = sites.value.find(s => s.has_data) || sites.value[0]
      lbSite.value = withData.name
    }
    await loadLeaderboard()
    await loadRecent()
  } catch (e) {
    props.host.toast.error('读取站点失败：' + (e.message || e))
  }
}
async function loadLeaderboard() {
  if (!lbSite.value) { lbRows.value = []; return }
  lbLoading.value = true
  try {
    const r = await props.host.callApi(`/leaderboard?site=${encodeURIComponent(lbSite.value)}&dir=${lbDir.value}&limit=${cfg.rank_size || 10}`)
    lbRows.value = r.items || []
  } catch (e) {
    props.host.toast.error('读取排行榜失败：' + (e.message || e))
  } finally {
    lbLoading.value = false
  }
}
async function loadRecent() {
  try {
    const r = await props.host.callApi('/recent')
    recent.value = r.items || []
  } catch (e) { /* 流水拉取失败不致命 */ }
}
const bonusOf = computed(() => {
  const s = sites.value.find(x => x.name === lbSite.value)
  return s ? s.bonus : ''
})
async function resetSite() {
  if (!lbSite.value) return
  if (!confirm(`清空站点「${lbSite.value}」的全部转账记录与排行榜？此操作不可恢复。`)) return
  try {
    await props.host.callApi('/reset', { method: 'POST', body: { site: lbSite.value } })
    lbRows.value = []
    props.host.toast.success('已清空')
    await loadSites()
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}
function fmtTime(ts) { return String(ts || '').replace('T', ' ').slice(0, 16) }

function switchTab(t) {
  tab.value = t
  if (t === 'rank' && !sites.value.length) loadSites()
}
</script>

<template>
  <div class="tf">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'rank' }]" @click="switchTab('rank')">🏆 排行榜</button>
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
          <!-- 站点 -->
          <template v-if="group === 'sites'">
            <h3 class="det-title">站点开关</h3>
            <p class="tip">群组/转账bot 平台内置写死，这里只按站点开关功能：启用=监听记录；群内致谢=收/发后群里回一句；打赏榜/赏赐榜=致谢里附转入/转出排行榜。</p>
            <section v-for="s in SITES" :key="s.key" class="card site">
              <div class="site-h">
                <span class="site-name">{{ s.label }}</span>
                <span class="site-bonus">{{ s.bonus }}</span>
                <span v-if="s.note" class="site-note">{{ s.note }}</span>
              </div>
              <div class="chips">
                <label v-for="t in TOGGLES" :key="t.v" :class="['chip', { on: has(s.key, t.v) }]">
                  <input type="checkbox" :checked="has(s.key, t.v)" @change="toggle(s.key, t.v)" />{{ t.l }}
                </label>
              </div>
            </section>
          </template>

          <!-- 排行榜 -->
          <template v-else-if="group === 'rank'">
            <h3 class="det-title">排行榜</h3>
            <section class="card">
              <label class="row"><span>输出形式</span>
                <select v-model="cfg.rank_output" class="inp"><option v-for="o in RANK_OUTPUTS" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
              <p class="tip">原生表格由平台 Bot 发送，Bot 需在目标群且可发消息；不支持时自动回退文本。图片失败同样回退文本。</p>
              <label class="row"><span>排行榜人数</span><input v-model.number="cfg.rank_size" class="inp sm" type="number" min="3" max="30" /></label>
              <label class="row"><span>命令词</span><input v-model="cfg.rank_command" class="inp" /></label>
              <p class="tip">在任意聊天发「.命令词 [站点] [in/out]」拉排行榜，如 .转账排行 hdsky in。</p>
            </section>
          </template>

          <!-- 致谢延迟 -->
          <template v-else-if="group === 'delay'">
            <h3 class="det-title">致谢延迟</h3>
            <section class="card">
              <p class="tip">记录到转账后等待若干秒再发致谢，模拟人工（0=不等）。</p>
              <div class="grid">
                <label class="row"><span>最小</span><input v-model.number="cfg.notify_delay_min" class="inp sm" type="number" min="0" max="300" /><span class="hint">秒</span></label>
                <label class="row"><span>最大</span><input v-model.number="cfg.notify_delay_max" class="inp sm" type="number" min="0" max="300" /><span class="hint">秒</span></label>
              </div>
            </section>
          </template>

          <!-- 进阶 -->
          <template v-else-if="group === 'adv'">
            <h3 class="det-title">进阶</h3>
            <section class="card">
              <label class="row"><span>SSD 大额自动确认</span>
                <select v-model="cfg.ssd_click_mode" class="inp"><option v-for="o in SSD_MODES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
              <p class="tip">SpringSunday 大额转账时 bot 会要你点确认按钮，开启后自动点。</p>
              <label class="row switch"><input v-model="cfg.owner_notify" type="checkbox" /><span>每笔转账推送给平台主人</span></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 排行榜 ============ -->
      <div v-show="tab === 'rank'" class="pane">
        <div class="toolbar">
          <select v-model="lbSite" class="inp sm2" @change="loadLeaderboard">
            <option v-if="!sites.length" value="">（无数据）</option>
            <option v-for="s in sites" :key="s.name" :value="s.name">{{ s.name }}{{ s.has_data ? '' : '（空）' }}</option>
          </select>
          <div class="seg">
            <button :class="['segbtn', { on: lbDir === 'in' }]" @click="lbDir = 'in'; loadLeaderboard()">打赏榜(转入)</button>
            <button :class="['segbtn', { on: lbDir === 'out' }]" @click="lbDir = 'out'; loadLeaderboard()">赏赐榜(转出)</button>
          </div>
          <span class="grow"></span>
          <button class="btn" @click="loadSites">刷新</button>
          <button class="btn danger" :disabled="!lbSite" @click="resetSite">清空该站</button>
        </div>
        <div v-if="lbLoading" class="muted">加载中…</div>
        <div v-else-if="!lbRows.length" class="empty">该站点暂无{{ lbDir === 'in' ? '转入' : '转出' }}数据</div>
        <table v-else class="tbl">
          <thead><tr><th>名次</th><th>用户</th><th>累计{{ bonusOf }}</th><th>笔数</th></tr></thead>
          <tbody>
            <tr v-for="r in lbRows" :key="r.rank">
              <td class="rank">{{ r.rank <= 3 ? ['🥇','🥈','🥉'][r.rank-1] : r.rank }}</td>
              <td>{{ r.user_name }}</td>
              <td>{{ r.total }}</td>
              <td class="muted">{{ r.count }}</td>
            </tr>
          </tbody>
        </table>

        <div v-if="recent.length" class="hist">
          <div class="hist-h">最近流水（{{ recent.length }} 条）</div>
          <table class="tbl">
            <thead><tr><th>站点</th><th>方向</th><th>用户</th><th>金额</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in recent" :key="i">
                <td class="muted">{{ r.site }}</td>
                <td><span :style="{ color: r.direction === 'in' ? '#6ee7a8' : '#6ea8fe' }">{{ r.direction === 'in' ? '转入' : '转出' }}</span></td>
                <td>{{ r.user_name }}</td>
                <td>{{ r.amount }}</td>
                <td class="muted">{{ fmtTime(r.ts) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tf { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tab { padding: 8px 16px; background: none; border: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #b9c0cc); border-bottom: 2px solid transparent; }
.tab.on { color: var(--accent, #6ea8fe); border-bottom-color: var(--accent, #6ea8fe); }

.layout { display: flex; gap: 16px; align-items: flex-start; }
.sidebar { flex: 0 0 130px; display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.side-title { font-size: 11px; color: var(--text-muted, #7a8291); padding: 4px 8px 6px; }
.side-item { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border-radius: 8px; border: none; cursor: pointer; text-align: left; background: none; color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.side-item:hover { background: var(--bg-card, #12141c); }
.side-item.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.det-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary, #e8ebf0); }

.pane { display: flex; flex-direction: column; gap: 14px; }
.card { display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.card.site { gap: 8px; }
.site-h { display: flex; align-items: baseline; gap: 8px; }
.site-name { font-size: 14px; font-weight: 600; color: var(--text-primary, #e8ebf0); }
.site-bonus { font-size: 12px; color: var(--accent, #6ea8fe); }
.site-note { font-size: 11px; color: var(--text-muted, #7a8291); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row > span:first-child { min-width: 108px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.tip { margin: 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.inp.sm { flex: 0 0 auto; width: 90px; }
.inp.sm2 { flex: 0 0 auto; width: 150px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-secondary, #b9c0cc); cursor: pointer; padding: 4px 10px; border-radius: 6px; background: var(--bg-card, #12141c); border: 1px solid var(--border-light, #2a2e3a); }
.chip.on { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); background: var(--accent-dim, #1e3a5f); }
.btn { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }

.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.grow { flex: 1; }
.seg { display: inline-flex; border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; overflow: hidden; }
.segbtn { padding: 6px 12px; background: var(--bg-card, #12141c); border: none; cursor: pointer; font-size: 12px; color: var(--text-secondary, #b9c0cc); }
.segbtn.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tbl th { color: var(--text-muted, #7a8291); font-weight: 500; font-size: 12px; }
.tbl td { color: var(--text-primary, #e8ebf0); }
.rank { width: 44px; }
.empty { text-align: center; padding: 40px 0; font-size: 14px; color: var(--text-secondary, #b9c0cc); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.hist { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.hist-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); }

@container (max-width: 640px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
}
</style>
