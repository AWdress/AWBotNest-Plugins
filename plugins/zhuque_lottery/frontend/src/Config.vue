<script setup>
// 朱雀 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧 11 分组 + 右侧明细）/ 战绩（个人信息 实时查 / 转账榜 / 大劫 / 骰子YDX）。
import { ref, reactive, onMounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  cookie: '', xcsrf: '', my_name: '我',
  enable_getinfo: true, getinfo_command: 'getinfo',
  enable_prizewheel: true, prizewheel_command: 'prizewheel', prize_tasks: 4,
  enable_betbonus: true, betbonus_command: 'betbonus',
  enable_firegenshin: false, firegenshin_interval: 20,
  enable_raiding: false, fanda_mode: 'off', fanxian: false,
  fanxian_probability: 1, fanxian_blacklist: '', raid_cd_minutes: 5,
  enable_redpocket: false, redpocket_max_retry: 20,
  enable_transform: false, transform_notification: false,
  transform_leaderboard: false, transform_payleaderboard: false,
  enable_ydx: false, ydx_dice_reveal: true, ydx_dice_bet: false,
  ydx_wwd_switch: false, ydx_start_count: 5, ydx_stop_count: 5,
  ydx_start_bouns: 500, ydx_bet_model: 'a',
  enable_card: false, card_command: 'card',
  card_id_1: '1', card_id_2: '2', card_id_3: '3', card_id_4: '4',
  owner_notify: true,
}

const GROUPS = [
  { key: 'cred', label: '凭据' },
  { key: 'getinfo', label: '个人查询', en: 'enable_getinfo' },
  { key: 'wheel', label: '大转盘', en: 'enable_prizewheel' },
  { key: 'betbonus', label: '倍投计算', en: 'enable_betbonus' },
  { key: 'fire', label: '魔法卡定时', en: 'enable_firegenshin' },
  { key: 'raid', label: '大劫反击', en: 'enable_raiding' },
  { key: 'redpocket', label: '红包雨', en: 'enable_redpocket' },
  { key: 'transform', label: '转账记录', en: 'enable_transform' },
  { key: 'ydx', label: '鳄鱼丼YDX', en: 'enable_ydx' },
  { key: 'card', label: '道具卡回收', en: 'enable_card' },
  { key: 'notify', label: '通知', en: 'owner_notify' },
]
const FANDA_MODES = [
  { v: 'off', l: '关闭' }, { v: 'lose', l: '仅被打输时反打' },
  { v: 'win', l: '仅被打赢时反打' }, { v: 'all', l: '都反打' },
]
const YDX_MODELS = [
  { v: 'a', l: 'A 打反' }, { v: 'b', l: 'B 打顺' }, { v: 'e', l: 'E 随机' }, { v: 's', l: 'S KDJ指标' },
]

const tab = ref('settings')
const group = ref('cred')
const view = ref('info')  // 战绩子视图
const loading = ref(true)
const saving = ref(false)
const cfg = reactive({ ...DEFAULTS })

// 战绩数据
const infoLoading = ref(false)
const info = ref(null)
const fireTotal = ref(0)
const fireDate = ref('')
const transform = ref(null)
const raids = ref(null)
const ydx = ref(null)
const dataLoading = ref(false)

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

// ── 战绩 ──
async function loadInfo() {
  infoLoading.value = true
  try {
    const r = await props.host.callApi('/info', { method: 'POST', body: {} })
    if (r.ok) {
      info.value = r.info || {}
      fireTotal.value = r.firegenshin_total || 0
      fireDate.value = r.firegenshin_last_date || ''
    } else {
      info.value = null
      props.host.toast.error(r.message || '查询失败')
    }
  } catch (e) { props.host.toast.error('查询失败：' + (e.message || e)) }
  finally { infoLoading.value = false }
}
async function loadTransform() {
  dataLoading.value = true
  try { transform.value = await props.host.callApi('/transform') }
  catch (e) { props.host.toast.error('读取失败：' + (e.message || e)) }
  finally { dataLoading.value = false }
}
async function loadRaids() {
  dataLoading.value = true
  try { raids.value = await props.host.callApi('/raids') }
  catch (e) { props.host.toast.error('读取失败：' + (e.message || e)) }
  finally { dataLoading.value = false }
}
async function loadYdx() {
  dataLoading.value = true
  try { ydx.value = await props.host.callApi('/ydx') }
  catch (e) { props.host.toast.error('读取失败：' + (e.message || e)) }
  finally { dataLoading.value = false }
}
async function clearData(type, label) {
  if (!confirm(`清空${label}记录？不可恢复。`)) return
  try {
    await props.host.callApi('/clear', { method: 'POST', body: { type } })
    props.host.toast.success('已清空')
    if (type === 'transform') transform.value = null
    if (type === 'raids') raids.value = null
    if (type === 'ydx') ydx.value = null
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}

function switchView(v) {
  view.value = v
  if (v === 'info' && !info.value) loadInfo()
  if (v === 'transform' && !transform.value) loadTransform()
  if (v === 'raids' && !raids.value) loadRaids()
  if (v === 'ydx' && !ydx.value) loadYdx()
}
function switchTab(t) {
  tab.value = t
  if (t === 'data') switchView(view.value)
}
function fmtTime(ts) { return String(ts || '').replace('T', ' ').slice(0, 16) }
function fmtNum(n) { return Number(n || 0).toLocaleString() }
</script>

<template>
  <div class="zq">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'data' }]" @click="switchTab('data')">📊 战绩</button>
      </div>

      <!-- ============ 配置 ============ -->
      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">功能分组</div>
          <button v-for="g in GROUPS" :key="g.key"
                  :class="['side-item', { on: group === g.key }]" @click="group = g.key">
            <span>{{ g.label }}</span>
            <span v-if="g.en && cfg[g.en]" class="dot"></span>
          </button>
        </aside>

        <div class="detail">
          <template v-if="group === 'cred'">
            <h3 class="det-title">凭据</h3>
            <section class="card">
              <label class="row"><span>Cookie</span><input v-model="cfg.cookie" class="inp" type="password" placeholder="F12 里 zhuque.in 请求的整条 Cookie" /></label>
              <label class="row"><span>X-Csrf-Token</span><input v-model="cfg.xcsrf" class="inp" type="password" placeholder="F12 请求头 x-csrf-token" /></label>
              <label class="row"><span>主人昵称</span><input v-model="cfg.my_name" class="inp" placeholder="用于生成打劫反击文案" /></label>
              <p class="tip">配好后可到「战绩 → 个人信息」点查询验证凭据是否有效。</p>
            </section>
          </template>

          <template v-else-if="group === 'getinfo'">
            <h3 class="det-title">个人查询</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_getinfo" type="checkbox" /><span>启用个人信息查询</span></label>
              <label v-if="cfg.enable_getinfo" class="row"><span>查询命令词</span><input v-model="cfg.getinfo_command" class="inp" /></label>
            </section>
          </template>

          <template v-else-if="group === 'wheel'">
            <h3 class="det-title">大转盘</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_prizewheel" type="checkbox" /><span>启用大转盘</span></label>
              <template v-if="cfg.enable_prizewheel">
                <label class="row"><span>大转盘命令词</span><input v-model="cfg.prizewheel_command" class="inp" /><span class="hint">用法 /命令词 次数</span></label>
                <label class="row"><span>并发任务数</span><input v-model.number="cfg.prize_tasks" class="inp sm" type="number" min="1" max="8" /></label>
              </template>
            </section>
          </template>

          <template v-else-if="group === 'betbonus'">
            <h3 class="det-title">倍投计算</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_betbonus" type="checkbox" /><span>启用倍投起手表</span></label>
              <label v-if="cfg.enable_betbonus" class="row"><span>倍投命令词</span><input v-model="cfg.betbonus_command" class="inp" /><span class="hint">/命令词 本金 连输次数</span></label>
            </section>
          </template>

          <template v-else-if="group === 'fire'">
            <h3 class="det-title">魔法卡定时释放</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_firegenshin" type="checkbox" /><span>启用魔法卡定时释放（每天一次，失败按间隔重试）</span></label>
              <label v-if="cfg.enable_firegenshin" class="row"><span>检查间隔</span><input v-model.number="cfg.firegenshin_interval" class="inp sm" type="number" min="5" max="240" /><span class="hint">分钟</span></label>
            </section>
          </template>

          <template v-else-if="group === 'raid'">
            <h3 class="det-title">大劫监听/反击</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_raiding" type="checkbox" /><span>启用大劫监听/反击</span></label>
              <template v-if="cfg.enable_raiding">
                <label class="row"><span>自动反击模式</span><select v-model="cfg.fanda_mode" class="inp"><option v-for="o in FANDA_MODES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                <label class="row"><span>反打劫冷却</span><input v-model.number="cfg.raid_cd_minutes" class="inp sm" type="number" min="0" max="1440" /><span class="hint">分钟</span></label>
                <label class="row switch"><input v-model="cfg.fanxian" type="checkbox" /><span>被打赢时概率返现</span></label>
                <template v-if="cfg.fanxian">
                  <label class="row"><span>返现概率</span><input v-model.number="cfg.fanxian_probability" class="inp sm" type="number" min="0" max="100" /><span class="hint">%</span></label>
                  <label class="row top"><span>返现黑名单</span><textarea v-model="cfg.fanxian_blacklist" class="inp" rows="2" placeholder="逗号分隔的 TGID，这些人不返现"></textarea></label>
                </template>
              </template>
            </section>
          </template>

          <template v-else-if="group === 'redpocket'">
            <h3 class="det-title">红包雨</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_redpocket" type="checkbox" /><span>启用自动抢红包（监听群内朱雀红包，自动点回调抢灵石）</span></label>
              <label v-if="cfg.enable_redpocket" class="row"><span>最大重试</span><input v-model.number="cfg.redpocket_max_retry" class="inp sm" type="number" min="1" max="50" /></label>
            </section>
          </template>

          <template v-else-if="group === 'transform'">
            <h3 class="det-title">灵石转账记录</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_transform" type="checkbox" /><span>启用灵石转账记录（监听群内转入/转出并记录）</span></label>
              <template v-if="cfg.enable_transform">
                <label class="row switch"><input v-model="cfg.transform_notification" type="checkbox" /><span>转账通知（记录后在群里回一条，含累计/排名；关闭则只记录）</span></label>
                <label class="row switch"><input v-model="cfg.transform_leaderboard" type="checkbox" /><span>转入榜（打赏总榜，需开转账通知）</span></label>
                <label class="row switch"><input v-model="cfg.transform_payleaderboard" type="checkbox" /><span>转出榜（赏赐总榜，需开转账通知）</span></label>
                <p class="tip">榜单数据随时可在「战绩 → 转账」查看，与通知开关无关。</p>
              </template>
            </section>
          </template>

          <template v-else-if="group === 'ydx'">
            <h3 class="det-title">鳄鱼丼 YDX（骰子大小投注）</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_ydx" type="checkbox" /><span>启用鳄鱼丼YDX（依赖bot文案/回调，需实盘校验，谨慎开启）</span></label>
              <template v-if="cfg.enable_ydx">
                <label class="row switch"><input v-model="cfg.ydx_dice_reveal" type="checkbox" /><span>记录开奖结果</span></label>
                <label class="row switch"><input v-model="cfg.ydx_dice_bet" type="checkbox" /><span>自动下注</span></label>
                <label class="row switch"><input v-model="cfg.ydx_wwd_switch" type="checkbox" /><span>下注二级开关(wwd)：关闭时只计算不实际下注</span></label>
                <div class="grid">
                  <label class="row"><span>几连开始下注</span><input v-model.number="cfg.ydx_start_count" class="inp sm" type="number" min="0" max="9" /></label>
                  <label class="row"><span>最大追投次数</span><input v-model.number="cfg.ydx_stop_count" class="inp sm" type="number" min="1" max="10" /></label>
                  <label class="row"><span>起手金额</span><input v-model.number="cfg.ydx_start_bouns" class="inp sm" type="number" min="500" /></label>
                  <label class="row"><span>下注模型</span><select v-model="cfg.ydx_bet_model" class="inp"><option v-for="o in YDX_MODELS" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                </div>
              </template>
            </section>
          </template>

          <template v-else-if="group === 'card'">
            <h3 class="det-title">道具卡回收</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_card" type="checkbox" /><span>启用道具卡回收（.card 换灵石，需实盘校验，默认关）</span></label>
              <template v-if="cfg.enable_card">
                <label class="row"><span>回收命令词</span><input v-model="cfg.card_command" class="inp" /><span class="hint">/命令词 [卡号] [数量]</span></label>
                <div class="grid">
                  <label class="row"><span>改名卡ID</span><input v-model="cfg.card_id_1" class="inp sm" /></label>
                  <label class="row"><span>神佑7天卡ID</span><input v-model="cfg.card_id_2" class="inp sm" /></label>
                  <label class="row"><span>邀请卡ID</span><input v-model="cfg.card_id_3" class="inp sm" /></label>
                  <label class="row"><span>释放7天卡ID</span><input v-model="cfg.card_id_4" class="inp sm" /></label>
                </div>
              </template>
            </section>
          </template>

          <template v-else-if="group === 'notify'">
            <h3 class="det-title">通知</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.owner_notify" type="checkbox" /><span>推送给平台主人（抢红包/魔法卡释放/转账等事件）</span></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 战绩 ============ -->
      <div v-show="tab === 'data'" class="pane">
        <div class="subtabs">
          <button :class="['stab', { on: view === 'info' }]" @click="switchView('info')">个人信息</button>
          <button :class="['stab', { on: view === 'transform' }]" @click="switchView('transform')">转账</button>
          <button :class="['stab', { on: view === 'raids' }]" @click="switchView('raids')">大劫</button>
          <button :class="['stab', { on: view === 'ydx' }]" @click="switchView('ydx')">骰子YDX</button>
        </div>

        <!-- 个人信息 -->
        <div v-show="view === 'info'">
          <div class="toolbar"><span class="grow"></span><button class="btn" :disabled="infoLoading" @click="loadInfo">{{ infoLoading ? '查询中…' : '刷新查询' }}</button></div>
          <div v-if="!info && !infoLoading" class="empty">点「刷新查询」实时拉取朱雀个人信息</div>
          <div v-else-if="info" class="cards">
            <div v-for="(v, k) in info" :key="k" class="stat">
              <div class="stat-l">{{ k }}</div><div class="stat-n">{{ v }}</div>
            </div>
            <div class="stat"><div class="stat-l">魔法卡累计</div><div class="stat-n">{{ fmtNum(fireTotal) }}</div></div>
            <div class="stat"><div class="stat-l">魔法卡上次</div><div class="stat-n sm">{{ fireDate || '—' }}</div></div>
          </div>
        </div>

        <!-- 转账 -->
        <div v-show="view === 'transform'">
          <div class="toolbar">
            <span v-if="transform" class="muted">打赏共 {{ fmtNum(transform.get_total) }} · 赏赐共 {{ fmtNum(transform.pay_total) }}</span>
            <span class="grow"></span>
            <button class="btn" @click="loadTransform">刷新</button>
            <button class="btn danger" @click="clearData('transform','转账')">清空</button>
          </div>
          <div v-if="dataLoading" class="muted">加载中…</div>
          <template v-else-if="transform">
            <div class="lbs">
              <div class="lb">
                <div class="lb-h">打赏榜（转入 TOP{{ transform.get_leaderboard.length }}）</div>
                <div v-if="!transform.get_leaderboard.length" class="muted">暂无</div>
                <table v-else class="tbl"><tbody>
                  <tr v-for="(e, i) in transform.get_leaderboard" :key="i"><td class="rank">{{ i+1 }}</td><td>{{ e.name }}</td><td>{{ fmtNum(e.total) }}</td><td class="muted">{{ e.count }}次</td></tr>
                </tbody></table>
              </div>
              <div class="lb">
                <div class="lb-h">赏赐榜（转出 TOP{{ transform.pay_leaderboard.length }}）</div>
                <div v-if="!transform.pay_leaderboard.length" class="muted">暂无</div>
                <table v-else class="tbl"><tbody>
                  <tr v-for="(e, i) in transform.pay_leaderboard" :key="i"><td class="rank">{{ i+1 }}</td><td>{{ e.name }}</td><td>{{ fmtNum(e.total) }}</td><td class="muted">{{ e.count }}次</td></tr>
                </tbody></table>
              </div>
            </div>
            <div class="hist-h">最近流水</div>
            <table class="tbl">
              <thead><tr><th>方向</th><th>金额</th><th>对方</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in transform.recent" :key="i">
                  <td><span :style="{ color: r.direction === 'get' ? '#6ee7a8' : '#6ea8fe' }">{{ r.direction === 'get' ? '转入' : '转出' }}</span></td>
                  <td>{{ fmtNum(Math.abs(r.amount)) }}</td><td>{{ r.user_name || '—' }}</td><td class="muted">{{ fmtTime(r.ts) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>

        <!-- 大劫 -->
        <div v-show="view === 'raids'">
          <div class="toolbar"><span class="grow"></span><button class="btn" @click="loadRaids">刷新</button><button class="btn danger" @click="clearData('raids','大劫')">清空</button></div>
          <div v-if="dataLoading" class="muted">加载中…</div>
          <template v-else-if="raids">
            <div class="cards">
              <div class="stat"><div class="stat-l">主动打劫·获得</div><div class="stat-n" style="color:#6ee7a8">{{ fmtNum(raids.raiding.gain) }}</div></div>
              <div class="stat"><div class="stat-l">主动打劫·亏损</div><div class="stat-n" style="color:#ff6b6b">{{ fmtNum(raids.raiding.loss) }}</div></div>
              <div class="stat"><div class="stat-l">被打劫·获得</div><div class="stat-n" style="color:#6ee7a8">{{ fmtNum(raids.beraided.gain) }}</div></div>
              <div class="stat"><div class="stat-l">被打劫·亏损</div><div class="stat-n" style="color:#ff6b6b">{{ fmtNum(raids.beraided.loss) }}</div></div>
            </div>
            <div class="hist-h">最近记录</div>
            <table class="tbl">
              <thead><tr><th>类型</th><th>金额</th><th>连打</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in raids.recent" :key="i">
                  <td>{{ r.action === 'raiding' ? '主动打劫' : '被打劫' }}</td>
                  <td :style="{ color: r.amount >= 0 ? '#6ee7a8' : '#ff6b6b' }">{{ fmtNum(r.amount) }}</td>
                  <td class="muted">{{ r.count }}</td><td class="muted">{{ fmtTime(r.ts) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>

        <!-- 骰子 YDX -->
        <div v-show="view === 'ydx'">
          <div class="toolbar"><span class="grow"></span><button class="btn" @click="loadYdx">刷新</button><button class="btn danger" @click="clearData('ydx','骰子')">清空</button></div>
          <div v-if="dataLoading" class="muted">加载中…</div>
          <template v-else-if="ydx">
            <div class="cards">
              <div class="stat"><div class="stat-l">总局数</div><div class="stat-n">{{ ydx.total }}</div></div>
              <div class="stat"><div class="stat-l">大 / 小</div><div class="stat-n">{{ ydx.big }} / {{ ydx.small }}</div></div>
              <div class="stat"><div class="stat-l">下注共</div><div class="stat-n">{{ fmtNum(ydx.bet_total) }}</div></div>
              <div class="stat"><div class="stat-l">中奖共</div><div class="stat-n" style="color:#6ee7a8">{{ fmtNum(ydx.win_total) }}</div></div>
            </div>
            <div class="hist-h">最近开奖</div>
            <table class="tbl">
              <thead><tr><th>点数</th><th>结果</th><th>下注方</th><th>下注</th><th>中奖</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in ydx.recent" :key="i">
                  <td>{{ r.die_point }}</td>
                  <td>{{ r.lottery_result === 'Big' ? '大' : (r.lottery_result === 'Small' ? '小' : '?') }}</td>
                  <td class="muted">{{ r.bet_side || '—' }}</td>
                  <td>{{ fmtNum(r.bet_amount) }}</td>
                  <td :style="{ color: r.win_amount > 0 ? '#6ee7a8' : '' }">{{ fmtNum(r.win_amount) }}</td>
                  <td class="muted">{{ fmtTime(r.ts) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.zq { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tab { padding: 8px 16px; background: none; border: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #b9c0cc); border-bottom: 2px solid transparent; }
.tab.on { color: var(--accent, #6ea8fe); border-bottom-color: var(--accent, #6ea8fe); }

.layout { display: flex; gap: 16px; align-items: flex-start; }
.sidebar { flex: 0 0 130px; display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.side-title { font-size: 11px; color: var(--text-muted, #7a8291); padding: 4px 8px 6px; }
.side-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 10px; border-radius: 8px; border: none; cursor: pointer; text-align: left; background: none; color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.side-item:hover { background: var(--bg-card, #12141c); }
.side-item.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #6ee7a8; flex: 0 0 auto; }
.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.det-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary, #e8ebf0); }

.pane { display: flex; flex-direction: column; gap: 14px; }
.card { display: flex; flex-direction: column; gap: 12px; padding: 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child { min-width: 88px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.tip { margin: 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.inp.sm { flex: 0 0 auto; width: 100px; }
textarea.inp { resize: vertical; font-family: inherit; line-height: 1.5; }
.btn { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }

.subtabs { display: flex; gap: 6px; }
.stab { padding: 6px 14px; border-radius: 6px; background: var(--bg-card, #12141c); border: 1px solid var(--border-light, #2a2e3a); cursor: pointer; font-size: 12px; color: var(--text-secondary, #b9c0cc); }
.stab.on { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.toolbar { display: flex; align-items: center; gap: 8px; margin: 12px 0; }
.grow { flex: 1; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; }
.stat { padding: 14px 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.stat-l { font-size: 12px; color: var(--text-secondary, #b9c0cc); }
.stat-n { margin-top: 6px; font-size: 20px; font-weight: 700; color: var(--text-primary, #e8ebf0); word-break: break-all; }
.stat-n.sm { font-size: 14px; font-weight: 500; }
.lbs { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-bottom: 14px; }
.lb { padding: 12px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.lb-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); margin-bottom: 8px; }
.hist-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); margin: 8px 0; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tbl th { color: var(--text-muted, #7a8291); font-weight: 500; font-size: 12px; }
.tbl td { color: var(--text-primary, #e8ebf0); }
.rank { width: 32px; color: var(--text-muted, #7a8291); }
.empty { text-align: center; padding: 40px 0; font-size: 14px; color: var(--text-secondary, #b9c0cc); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }

@container (max-width: 640px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
  .lbs { grid-template-columns: 1fr; }
}
</style>
