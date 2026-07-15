<script setup>
// AI 助手 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 对话记忆（查看、清空各会话历史）。
import { ref, reactive, onMounted, computed } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  api_key: '', base_url: '', model: 'gpt-3.5-turbo',
  enable_private_chat: true, enable_group_chat: true, group_chat_ids: '',
  system_prompt: (
    '# Role\n你是一个相处了很久的普通网友。\n\n' +
    '# Rules\n' +
    '1. 语气口语化、随性、接地气，就像在微信或QQ上聊天。\n' +
    '2. 每次回复必须精简，严禁长篇大论。\n' +
    '3. 绝对不能超过 20 个字。\n' +
    '4. 绝对不要在回复中模仿、复述或带入用户的动作动作。\n' +
    '5. 偶尔可以在句末加一个合适的 emoji（如 😂、🤷‍♂️、👀），不要过多。'
  ),
  max_history: 10,
  enable_proactive: false, proactive_chat_ids: '',
  proactive_min_minutes: 60, proactive_max_minutes: 180,
  enable_explain_command: true, enable_explain_prompt: false,
  explain_prompt: (
    '你是一个群聊消息解读助手。请根据用户【回复的消息内容】进行解释与答疑，简明清晰。\n' +
    '输出结构：\n1) 这句话/这段话的主要意思\n2) 语气/态度\n3) 可能的隐含信息（没有就写\'无\'）\n\n' +
    '需要解释的消息内容：{content}'
  ),
  white_list_chats: '',
}

const GROUPS = [
  { key: 'api', label: '接口' },
  { key: 'human', label: '人形回复', en: 'enable_private_chat' },
  { key: 'proactive', label: '主动搭话', en: 'enable_proactive' },
  { key: 'explain', label: '解释命令', en: 'enable_explain_command' },
  { key: 'scope', label: '范围' },
]

const tab = ref('settings')
const group = ref('api')
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const cfg = reactive({ ...DEFAULTS })

// 对话记忆
const histories = ref([])
const proactiveNext = ref('')
const histLoading = ref(false)
const activeChat = ref(null)
const chatMessages = ref([])
const msgLoading = ref(false)

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

async function testConn() {
  testing.value = true
  try {
    const r = await props.host.callApi('/test', { method: 'POST', body: {} })
    if (r.ok) props.host.toast.success('连接正常 ✅ ' + (r.model || ''))
    else props.host.toast.error('连接失败：' + (r.message || '未知'))
  } catch (e) {
    props.host.toast.error('连接失败：' + (e.message || e))
  } finally {
    testing.value = false
  }
}

// ── 对话记忆 ──
async function loadHistories() {
  histLoading.value = true
  try {
    const r = await props.host.callApi('/histories')
    histories.value = r.items || []
    proactiveNext.value = r.proactive_next || ''
  } catch (e) {
    props.host.toast.error('读取会话列表失败：' + (e.message || e))
  } finally {
    histLoading.value = false
  }
}
async function openChat(h) {
  activeChat.value = h
  msgLoading.value = true
  chatMessages.value = []
  try {
    const r = await props.host.callApi('/history?chat_id=' + encodeURIComponent(h.chat_id))
    chatMessages.value = r.messages || []
  } catch (e) {
    props.host.toast.error('读取会话历史失败：' + (e.message || e))
  } finally {
    msgLoading.value = false
  }
}
async function clearChat(h) {
  if (!confirm(`清空会话 ${h.chat_id} 的对话记忆？`)) return
  try {
    await props.host.callApi('/history/clear', { method: 'POST', body: { chat_id: h.chat_id } })
    histories.value = histories.value.filter(x => x.chat_id !== h.chat_id)
    if (activeChat.value && activeChat.value.chat_id === h.chat_id) {
      activeChat.value = null
      chatMessages.value = []
    }
    props.host.toast.success('已清空')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}
async function clearAll() {
  if (!confirm('清空全部会话的对话记忆？')) return
  try {
    await props.host.callApi('/history/clear', { method: 'POST', body: { all: true } })
    histories.value = []
    activeChat.value = null
    chatMessages.value = []
    props.host.toast.success('已清空全部')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}

function switchTab(t) {
  tab.value = t
  if (t === 'memory' && !histories.value.length) loadHistories()
}
</script>

<template>
  <div class="ai">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'memory' }]" @click="switchTab('memory')">💬 对话记忆</button>
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
          <!-- 接口 -->
          <template v-if="group === 'api'">
            <h3 class="det-title">OpenAI 兼容接口</h3>
            <section class="card">
              <label class="row"><span>API Key</span>
                <input v-model="cfg.api_key" class="inp" type="password" placeholder="接口密钥" /></label>
              <label class="row"><span>接口地址</span>
                <input v-model="cfg.base_url" class="inp" placeholder="https://api.openai.com/v1（留空用官方默认）" /></label>
              <label class="row"><span>模型</span>
                <input v-model="cfg.model" class="inp" placeholder="gpt-4o-mini / gpt-3.5-turbo 等" /></label>
              <div class="row"><button class="btn" :disabled="testing" @click="testConn">{{ testing ? '测试中…' : '测试连接' }}</button></div>
            </section>
          </template>

          <!-- 人形回复 -->
          <template v-else-if="group === 'human'">
            <h3 class="det-title">人形回复</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_private_chat" type="checkbox" /><span>私聊回复（私聊里直接对话）</span></label>
              <label class="row switch"><input v-model="cfg.enable_group_chat" type="checkbox" /><span>群聊回复（群里 @你 或回复你的消息时对话）</span></label>
              <label v-if="cfg.enable_group_chat" class="row top"><span>生效群组</span>
                <textarea v-model="cfg.group_chat_ids" class="inp" rows="2" placeholder="群ID逗号分隔，留空=所有群"></textarea></label>
              <label class="row top"><span>人设</span>
                <textarea v-model="cfg.system_prompt" class="inp" rows="8" placeholder="系统提示词"></textarea></label>
              <label class="row"><span>记忆轮数</span>
                <input v-model.number="cfg.max_history" class="inp sm" type="number" min="0" max="40" />
                <span class="hint">每会话保留多少条历史，0=不记忆</span></label>
            </section>
          </template>

          <!-- 主动搭话 -->
          <template v-else-if="group === 'proactive'">
            <h3 class="det-title">随机主动搭话</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_proactive" type="checkbox" /><span>开启随机主动搭话</span></label>
              <p class="tip">在下方群组里每隔随机时间挑一条群友近期消息主动接话开启话题；群友回复你后走人形对话续聊（需「群聊回复」开着）。</p>
              <template v-if="cfg.enable_proactive">
                <label class="row top"><span>搭话群组</span>
                  <textarea v-model="cfg.proactive_chat_ids" class="inp" rows="2" placeholder="群ID逗号分隔，必填"></textarea></label>
                <div class="grid">
                  <label class="row"><span>间隔最小</span><input v-model.number="cfg.proactive_min_minutes" class="inp sm" type="number" min="5" max="720" /><span class="hint">分钟</span></label>
                  <label class="row"><span>间隔最大</span><input v-model.number="cfg.proactive_max_minutes" class="inp sm" type="number" min="5" max="1440" /><span class="hint">分钟</span></label>
                </div>
              </template>
            </section>
          </template>

          <!-- 解释命令 -->
          <template v-else-if="group === 'explain'">
            <h3 class="det-title">/ai 解释命令</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_explain_command" type="checkbox" /><span>启用 /ai 解释命令</span></label>
              <p class="tip">回复一条消息（或图片）再发 /ai，让 AI 解释/解答（单次，无记忆）。</p>
              <template v-if="cfg.enable_explain_command">
                <label class="row switch"><input v-model="cfg.enable_explain_prompt" type="checkbox" /><span>用解释模板（否则直接把内容丢给 AI）</span></label>
                <label v-if="cfg.enable_explain_prompt" class="row top"><span>解释模板</span>
                  <textarea v-model="cfg.explain_prompt" class="inp" rows="6" placeholder="用 {content} 占位被解释的内容"></textarea></label>
              </template>
            </section>
          </template>

          <!-- 范围 -->
          <template v-else-if="group === 'scope'">
            <h3 class="det-title">生效范围</h3>
            <section class="card">
              <label class="row top"><span>会话白名单</span>
                <textarea v-model="cfg.white_list_chats" class="inp" rows="2" placeholder="会话ID逗号分隔，留空=所有会话"></textarea></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 对话记忆 ============ -->
      <div v-show="tab === 'memory'" class="pane">
        <div class="toolbar">
          <span class="muted">下次主动搭话：{{ proactiveNext || '—' }}</span>
          <span class="grow"></span>
          <button class="btn" @click="loadHistories">刷新</button>
          <button class="btn danger" :disabled="!histories.length" @click="clearAll">全部清空</button>
        </div>
        <div v-if="histLoading" class="muted">加载中…</div>
        <div v-else-if="!histories.length" class="empty">暂无对话记忆<br><span class="muted">私聊/群@你对话后会在这里记录会话记忆</span></div>
        <div v-else class="mem-layout">
          <div class="mem-list">
            <button v-for="h in histories" :key="h.chat_id"
                    :class="['mem-item', { on: activeChat && activeChat.chat_id === h.chat_id }]"
                    @click="openChat(h)">
              <div class="mem-h">
                <span class="mem-type">{{ h.is_private ? '私聊' : '群' }}</span>
                <span class="mem-id">{{ h.chat_id }}</span>
              </div>
              <div class="mem-last">{{ h.last || '—' }}</div>
              <div class="mem-meta">{{ h.count }} 条 · <a class="lnk" @click.stop="clearChat(h)">清空</a></div>
            </button>
          </div>
          <div class="mem-detail">
            <div v-if="!activeChat" class="muted center">← 选择一个会话查看历史</div>
            <div v-else-if="msgLoading" class="muted">加载中…</div>
            <div v-else class="chat">
              <div v-for="(m, i) in chatMessages" :key="i" :class="['bubble', m.role]">
                <div class="bubble-role">{{ m.role === 'user' ? '对方' : '我' }}</div>
                <div class="bubble-text">{{ m.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
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
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child { min-width: 72px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
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
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }

.toolbar { display: flex; align-items: center; gap: 8px; }
.grow { flex: 1; }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.muted.center { text-align: center; padding: 40px 0; }
.empty { text-align: center; padding: 48px 0; font-size: 15px; color: var(--text-secondary, #b9c0cc); }

/* 对话记忆 master-detail */
.mem-layout { display: flex; gap: 14px; align-items: flex-start; }
.mem-list { flex: 0 0 240px; display: flex; flex-direction: column; gap: 8px; max-height: 460px; overflow-y: auto; }
.mem-item { text-align: left; padding: 10px; border-radius: 8px; cursor: pointer; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); display: flex; flex-direction: column; gap: 4px; }
.mem-item:hover { border-color: var(--accent, #6ea8fe); }
.mem-item.on { border-color: var(--accent, #6ea8fe); background: var(--accent-dim, #1e3a5f); }
.mem-h { display: flex; gap: 6px; align-items: center; }
.mem-type { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); }
.mem-id { font-size: 12px; color: var(--text-primary, #e8ebf0); }
.mem-last { font-size: 12px; color: var(--text-secondary, #b9c0cc); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mem-meta { font-size: 11px; color: var(--text-muted, #7a8291); }
.lnk { color: #ff6b6b; cursor: pointer; }
.lnk:hover { text-decoration: underline; }
.mem-detail { flex: 1; min-width: 0; min-height: 200px; padding: 12px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.chat { display: flex; flex-direction: column; gap: 10px; }
.bubble { max-width: 80%; padding: 8px 12px; border-radius: 10px; }
.bubble.user { align-self: flex-start; background: var(--bg-card, #12141c); }
.bubble.assistant { align-self: flex-end; background: var(--accent-dim, #1e3a5f); }
.bubble-role { font-size: 10px; color: var(--text-muted, #7a8291); margin-bottom: 3px; }
.bubble-text { font-size: 13px; color: var(--text-primary, #e8ebf0); white-space: pre-wrap; word-break: break-word; }

@container (max-width: 620px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
  .mem-layout { flex-direction: column; }
  .mem-list { flex-basis: auto; width: 100%; max-height: 220px; }
}
</style>
