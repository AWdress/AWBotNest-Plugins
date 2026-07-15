<script setup>
// 小菜抽奖 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 待发奖（列出待发奖、手动发奖、清空、发奖历史）。
import { ref, reactive, onMounted, computed } from 'vue'
import ChatPicker from './ChatPicker.vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  auto_lottery_enabled: false, lottery_bot_id: '6461022460', auto_lottery_username: '',
  auto_lottery_time: '', lottery_target_groups: [], custom_lottery_groups: [],
  lottery_forward_enabled: false, lottery_forward_first_participant: false,
  prize_list: '', universal_prize_match: false, prize_case_sensitive: false,
  trap_enabled: true, trap_case_sensitive: false, trap_enable_prize_pattern_check: true,
  trap_enable_creator_blacklist: true, trap_enable_participant_check: true,
  trap_max_participants: 1, trap_blacklist_creator_ids: '',
  trap_suspicious_keywords: '脚本,挂机,机器人,外挂,bot,自动,作弊,刷,假人,封禁,封,禁,ban,封号,script,auto,cheat,hack,fake,test,腳本,掛機,機器人,外掛,自動,封號',
  lottery_wait_enabled: false, lottery_participate_wait_min: 25, lottery_participate_wait_max: 65,
  lottery_thank_wait_min: 10, lottery_thank_wait_max: 45, lottery_heimu_wait_min: 20, lottery_heimu_wait_max: 40,
  lottery_negative_wait_min: 10, lottery_negative_wait_max: 60, group_wait_overrides: '',
  lottery_thank_message: false, thank_texts: '感谢{boss}大佬\n{boss}爷，谢谢\n感谢老板，小弟在这',
  username_reply_switch: false, transfer_groups: [],
  lottery_heimu_message: false, heimu_texts: '黑幕\n这也能不中\n下次一定',
  lose_reply_switch: false, negative_texts: '怎么可能啊\n别开玩笑啊\n啊绝对不是\n我是真的\n不要黑我\n？',
  auto_prize_enabled: false, manual_prize_mode: false, prize_send_interval_enabled: true,
  prize_send_interval_min: 2, prize_send_interval_max: 5, prize_send_blacklist: '',
  notify_owner: true, notify_skips: false,
}

const GROUPS = [
  { key: 'lottery', label: '自动抽奖', en: 'auto_lottery_enabled' },
  { key: 'participate', label: '参与方式' },
  { key: 'prize', label: '奖品匹配' },
  { key: 'trap', label: '陷阱检测', en: 'trap_enabled' },
  { key: 'wait', label: '等待时间', en: 'lottery_wait_enabled' },
  { key: 'react', label: '中奖回应' },
  { key: 'negative', label: '负面回复', en: 'lose_reply_switch' },
  { key: 'send', label: '自动发奖', en: 'auto_prize_enabled' },
  { key: 'notify', label: '通知', en: 'notify_owner' },
]

const tab = ref('settings')
const group = ref('lottery')
const loading = ref(true)
const saving = ref(false)
const cfg = reactive({ ...DEFAULTS })
const dialogs = ref([])

// 待发奖
const pending = ref([])
const prizeHistory = ref([])
const pendingLoading = ref(false)
const sending = ref('')

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, DEFAULTS, saved || {})
    // 归一化数组字段（老配置可能是逗号字符串）
    for (const k of ['lottery_target_groups', 'custom_lottery_groups', 'transfer_groups']) {
      if (!Array.isArray(cfg[k])) {
        cfg[k] = String(cfg[k] || '').split(',').map(s => Number(s.trim())).filter(Boolean)
      }
    }
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
  try {
    const r = await props.host.callApi('/dialogs')
    dialogs.value = r.items || []
  } catch (e) { /* 群列表拉取失败不致命，可手动补ID */ }
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

// ── 待发奖 ──
async function loadPending() {
  pendingLoading.value = true
  try {
    const r = await props.host.callApi('/pending')
    pending.value = r.items || []
    const h = await props.host.callApi('/history')
    prizeHistory.value = h.items || []
  } catch (e) {
    props.host.toast.error('读取待发奖失败：' + (e.message || e))
  } finally {
    pendingLoading.value = false
  }
}
// 发奖在后端是后台任务（避免长耗时超时），返回 started 后延迟刷新待发奖列表。
async function doSend(body, tag) {
  sending.value = tag
  try {
    const r = await props.host.callApi('/send', { method: 'POST', body })
    if (r.ok) {
      props.host.toast.success(r.message || '已开始发奖')
      setTimeout(loadPending, 6000)
    } else {
      props.host.toast.error(r.message || '发奖失败')
    }
  } catch (e) { props.host.toast.error('发奖失败：' + (e.message || e)) }
  finally { sending.value = '' }
}
async function sendOne(item) {
  if (!confirm(`给抽奖 ${item.lottery_id.slice(0, 8)} 的 ${item.winners} 位中奖者发奖？`)) return
  await doSend({ lottery_id: item.lottery_id }, item.lottery_id)
}
async function sendAll() {
  if (!pending.value.length) return
  if (!confirm(`给全部 ${pending.value.length} 个待发奖发奖？`)) return
  await doSend({ all: true }, 'all')
}
async function clearPending() {
  if (!confirm('清空待发奖列表？(不影响已发出的奖)')) return
  try {
    await props.host.callApi('/clear', { method: 'POST', body: {} })
    pending.value = []
    props.host.toast.success('已清空')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}

function switchTab(t) {
  tab.value = t
  if (t === 'prize' && !pending.value.length && !prizeHistory.value.length) loadPending()
}
</script>

<template>
  <div class="al">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'prize' }]" @click="switchTab('prize')">🎁 待发奖</button>
      </div>

      <!-- ============ 配置 ============ -->
      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">设置分组</div>
          <button v-for="g in GROUPS" :key="g.key"
                  :class="['side-item', { on: group === g.key }]" @click="group = g.key">
            <span>{{ g.label }}</span>
            <span v-if="g.en && cfg[g.en]" class="dot"></span>
          </button>
        </aside>

        <div class="detail">
          <!-- 自动抽奖 -->
          <template v-if="group === 'lottery'">
            <h3 class="det-title">自动抽奖</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.auto_lottery_enabled" type="checkbox" /><span>自动抽奖总开关</span></label>
              <template v-if="cfg.auto_lottery_enabled">
                <div class="grid">
                  <label class="row"><span>抽奖机器人ID</span><input v-model="cfg.lottery_bot_id" class="inp" /></label>
                  <label class="row"><span>PT用户名</span><input v-model="cfg.auto_lottery_username" class="inp" placeholder="如 AWdress" /></label>
                </div>
                <label class="row"><span>抽奖时间段</span><input v-model="cfg.auto_lottery_time" class="inp" placeholder="08:00-11:00,20:00-23:00，留空=全天" /></label>
                <div class="fld"><span class="lbl">预定义抽奖群组</span>
                  <ChatPicker v-model="cfg.lottery_target_groups" :dialogs="dialogs" /></div>
                <div class="fld"><span class="lbl">自定义抽奖群组</span>
                  <ChatPicker v-model="cfg.custom_lottery_groups" :dialogs="dialogs" /></div>
                <p class="tip">两组群合并去重后生效；都留空 = 不参与任何群。</p>
              </template>
            </section>
          </template>

          <!-- 参与方式 -->
          <template v-else-if="group === 'participate'">
            <h3 class="det-title">参与方式</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.lottery_forward_enabled" type="checkbox" /><span>转发原始抽奖消息参与（关闭则直接发文本关键词）</span></label>
              <label class="row switch"><input v-model="cfg.lottery_forward_first_participant" type="checkbox" /><span>转发第一个参与者（最多等30秒，超时降级）</span></label>
              <p class="tip">优先级：特殊格式(@、/)→转发原消息 &gt; 转发第一参与者 &gt; 转发原消息 &gt; 直接发文本。</p>
            </section>
          </template>

          <!-- 奖品匹配 -->
          <template v-else-if="group === 'prize'">
            <h3 class="det-title">奖品匹配</h3>
            <section class="card">
              <label class="row top"><span>奖品列表</span>
                <textarea v-model="cfg.prize_list" class="inp" rows="4" placeholder="每行 群组ID|奖品1,奖品2&#10;例：-1001234567890|魔力,积分"></textarea></label>
              <label class="row switch"><input v-model="cfg.universal_prize_match" type="checkbox" /><span>通用奖品匹配（所有群共用全部关键词；关闭=精确模式，建议关闭）</span></label>
              <label class="row switch"><input v-model="cfg.prize_case_sensitive" type="checkbox" /><span>奖品关键词区分大小写</span></label>
            </section>
          </template>

          <!-- 陷阱检测 -->
          <template v-else-if="group === 'trap'">
            <h3 class="det-title">陷阱检测</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.trap_enabled" type="checkbox" /><span>启用陷阱抽奖检测（命中任一特征则跳过）</span></label>
              <template v-if="cfg.trap_enabled">
                <label class="row switch"><input v-model="cfg.trap_case_sensitive" type="checkbox" /><span>陷阱关键词区分大小写</span></label>
                <label class="row switch"><input v-model="cfg.trap_enable_prize_pattern_check" type="checkbox" /><span>启用关键词检测</span></label>
                <label v-if="cfg.trap_enable_prize_pattern_check" class="row top"><span>可疑关键词</span>
                  <textarea v-model="cfg.trap_suspicious_keywords" class="inp" rows="3" placeholder="逗号或换行分隔"></textarea></label>
                <label class="row switch"><input v-model="cfg.trap_enable_creator_blacklist" type="checkbox" /><span>启用创建者黑名单</span></label>
                <label v-if="cfg.trap_enable_creator_blacklist" class="row top"><span>创建者黑名单</span>
                  <textarea v-model="cfg.trap_blacklist_creator_ids" class="inp" rows="2" placeholder="逗号或换行分隔的用户ID"></textarea></label>
                <label class="row switch"><input v-model="cfg.trap_enable_participant_check" type="checkbox" /><span>启用参与人数检测</span></label>
                <label v-if="cfg.trap_enable_participant_check" class="row"><span>人数阈值</span>
                  <input v-model.number="cfg.trap_max_participants" class="inp sm" type="number" min="1" max="1000" />
                  <span class="hint">参与人数 ≤ 此值视为陷阱（=1 即只拦单人抽奖）</span></label>
              </template>
            </section>
          </template>

          <!-- 等待时间 -->
          <template v-else-if="group === 'wait'">
            <h3 class="det-title">抽奖等待时间</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.lottery_wait_enabled" type="checkbox" /><span>抽奖等待时间总开关（关闭则相关动作立即执行）</span></label>
              <template v-if="cfg.lottery_wait_enabled">
                <div class="grid">
                  <label class="row"><span>参与前(最小)</span><input v-model.number="cfg.lottery_participate_wait_min" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>参与前(最大)</span><input v-model.number="cfg.lottery_participate_wait_max" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>感谢(最小)</span><input v-model.number="cfg.lottery_thank_wait_min" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>感谢(最大)</span><input v-model.number="cfg.lottery_thank_wait_max" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>黑幕(最小)</span><input v-model.number="cfg.lottery_heimu_wait_min" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>黑幕(最大)</span><input v-model.number="cfg.lottery_heimu_wait_max" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>负面(最小)</span><input v-model.number="cfg.lottery_negative_wait_min" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>负面(最大)</span><input v-model.number="cfg.lottery_negative_wait_max" class="inp sm" type="number" /><span class="hint">秒</span></label>
                </div>
                <label class="row top"><span>按群专属等待</span>
                  <textarea v-model="cfg.group_wait_overrides" class="inp" rows="2" placeholder="每行 群组ID|最小秒|最大秒&#10;例：-1001234567890|30|90"></textarea></label>
              </template>
            </section>
          </template>

          <!-- 中奖回应 -->
          <template v-else-if="group === 'react'">
            <h3 class="det-title">中奖回应</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.lottery_thank_message" type="checkbox" /><span>中奖后发感谢消息</span></label>
              <label v-if="cfg.lottery_thank_message" class="row top"><span>感谢文案</span>
                <textarea v-model="cfg.thank_texts" class="inp" rows="3" placeholder="每行一条随机选，{boss}=创建者名字"></textarea></label>
              <label class="row switch"><input v-model="cfg.username_reply_switch" type="checkbox" /><span>中奖回复用户名（无转账功能的群，需填上方 PT用户名）</span></label>
              <div v-if="cfg.username_reply_switch" class="fld"><span class="lbl">转账群组（免回用户名）</span>
                <ChatPicker v-model="cfg.transfer_groups" :dialogs="dialogs" /></div>
              <label class="row switch"><input v-model="cfg.lottery_heimu_message" type="checkbox" /><span>未中奖发黑幕消息</span></label>
              <label v-if="cfg.lottery_heimu_message" class="row top"><span>黑幕文案</span>
                <textarea v-model="cfg.heimu_texts" class="inp" rows="3" placeholder="每行一条随机选"></textarea></label>
            </section>
          </template>

          <!-- 负面回复 -->
          <template v-else-if="group === 'negative'">
            <h3 class="det-title">负面回复（被质疑是机器人）</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.lose_reply_switch" type="checkbox" /><span>负面回复开关（有人回你说机器人/脚本等时随机反驳）</span></label>
              <label v-if="cfg.lose_reply_switch" class="row top"><span>反驳文案</span>
                <textarea v-model="cfg.negative_texts" class="inp" rows="3" placeholder="每行一条随机选"></textarea></label>
            </section>
          </template>

          <!-- 自动发奖 -->
          <template v-else-if="group === 'send'">
            <h3 class="det-title">自动发奖</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.auto_prize_enabled" type="checkbox" /><span>自动发奖功能总开关（开启才记录自己发起的抽奖中奖者）</span></label>
              <template v-if="cfg.auto_prize_enabled">
                <label class="row switch"><input v-model="cfg.manual_prize_mode" type="checkbox" /><span>手动发奖模式（只记录，用「待发奖」页或 .sendprize 发）</span></label>
                <label class="row switch"><input v-model="cfg.prize_send_interval_enabled" type="checkbox" /><span>发奖间隔（每次发奖后随机等待，建议开启）</span></label>
                <div v-if="cfg.prize_send_interval_enabled" class="grid">
                  <label class="row"><span>间隔(最小)</span><input v-model.number="cfg.prize_send_interval_min" class="inp sm" type="number" /><span class="hint">秒</span></label>
                  <label class="row"><span>间隔(最大)</span><input v-model.number="cfg.prize_send_interval_max" class="inp sm" type="number" /><span class="hint">秒</span></label>
                </div>
                <label class="row top"><span>发奖黑名单</span>
                  <textarea v-model="cfg.prize_send_blacklist" class="inp" rows="2" placeholder="逗号或换行分隔的用户ID，这些中奖者不发奖"></textarea></label>
              </template>
            </section>
          </template>

          <!-- 通知 -->
          <template v-else-if="group === 'notify'">
            <h3 class="det-title">通知</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.notify_owner" type="checkbox" /><span>关键事件通知我（参与成功/中奖/发奖完成）</span></label>
              <label v-if="cfg.notify_owner" class="row switch"><input v-model="cfg.notify_skips" type="checkbox" /><span>通知跳过原因（奖品不符/陷阱/不在时间段等，较吵）</span></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 待发奖 ============ -->
      <div v-show="tab === 'prize'" class="pane">
        <div class="toolbar">
          <span class="muted">待发奖 {{ pending.length }} 个</span>
          <span class="grow"></span>
          <button class="btn" @click="loadPending">刷新</button>
          <button class="btn primary" :disabled="!pending.length || sending" @click="sendAll">{{ sending === 'all' ? '发奖中…' : '全部发奖' }}</button>
          <button class="btn danger" :disabled="!pending.length" @click="clearPending">清空</button>
        </div>
        <div v-if="pendingLoading" class="muted">加载中…</div>
        <template v-else>
          <div v-if="!pending.length" class="empty">暂无待发奖<br><span class="muted">开启「自动发奖」并用「手动发奖模式」后，自己发起的抽奖中奖者会记录在这里</span></div>
          <table v-else class="tbl">
            <thead><tr><th>抽奖ID</th><th>群</th><th>奖品</th><th>中奖人数</th><th>时间</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in pending" :key="p.lottery_id">
                <td class="mono">#{{ p.lottery_id.slice(0, 8) }}</td>
                <td>{{ p.chat_title || '—' }}</td>
                <td class="muted">{{ p.prize || '—' }}</td>
                <td>{{ p.winners }}</td>
                <td class="muted">{{ p.time || '—' }}</td>
                <td><button class="btn xs" :disabled="sending" @click="sendOne(p)">{{ sending === p.lottery_id ? '发奖中…' : '发奖' }}</button></td>
              </tr>
            </tbody>
          </table>

          <div v-if="prizeHistory.length" class="hist">
            <div class="hist-h">发奖历史（最近 {{ prizeHistory.length }} 条）</div>
            <table class="tbl">
              <thead><tr><th>抽奖ID</th><th>中奖</th><th>成功</th><th>失败</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="(h, i) in prizeHistory" :key="i">
                  <td class="mono">#{{ String(h.lottery_id || '').slice(0, 8) }}</td>
                  <td>{{ h.total }}</td>
                  <td style="color:#6ee7a8">{{ h.success }}</td>
                  <td :style="{ color: h.failed ? '#ff6b6b' : '' }">{{ h.failed }}</td>
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
.al { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
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
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child, .lbl { min-width: 92px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { justify-content: flex-start; }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.tip { margin: 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.inp.sm { flex: 0 0 auto; width: 90px; }
textarea.inp { resize: vertical; font-family: inherit; line-height: 1.5; }
.fld { display: flex; flex-direction: column; gap: 6px; }
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
