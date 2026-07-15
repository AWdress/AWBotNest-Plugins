<script setup>
// AWPulse 色花堂助手 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 页签：运行状态 / 设置(左分组+右明细) / 记录 / Cookie / 日志。
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const AI_TYPES = [{ v: 'openai', l: 'OpenAI 兼容' }, { v: 'claude', l: 'Claude' }, { v: 'custom', l: '自定义' }]

// Discuz 论坛固定的安全提问（值为字符串，与后端一致）。
const SECURITY_QUESTIONS = [
  { v: '0', l: '不设置安全提问' },
  { v: '1', l: '母亲的名字' },
  { v: '2', l: '爷爷的名字' },
  { v: '3', l: '父亲出生的城市' },
  { v: '4', l: '您其中一位老师的名字' },
  { v: '5', l: '您个人计算机的型号' },
  { v: '6', l: '您最喜欢的餐馆名称' },
  { v: '7', l: '驾驶执照最后四位数字' },
]

// 配置分组（左侧导航）。en=对应启用开关键（有则显示启用小圆点）。
const GROUPS = [
  { key: 'account', label: '账号' },
  { key: 'features', label: '功能开关' },
  { key: 'reply', label: '回复设置', en: 'enable_auto_reply' },
  { key: 'autopost', label: '自动发帖', en: 'enable_auto_post' },
  { key: 'ai', label: 'AI 设置', en: 'enable_ai_reply' },
  { key: 'schedule', label: '定时/通知' },
  { key: 'net', label: '代理/浏览器' },
]

// 与后端 DEFAULTS 对齐（深合并，含嵌套对象）。
const DEFAULTS = {
  base_url: 'https://sehuatang.org/', username: '', password: '',
  security_question_id: '0', security_answer: '', headless: true,
  enable_auto_reply: true, enable_daily_checkin: true, enable_smart_reply: true,
  enable_ai_reply: false, enable_ai_post_filter: true, enable_auto_post: false,
  enable_random_delay: false,
  enable_test_mode: false, enable_test_checkin: false, enable_test_reply: false, enable_test_post: false,
  skip_admin_posts: true, max_replies_per_day: 3, reply_interval: [60, 120],
  schedule_cron: '', schedule_times: ['03:00', '09:00', '15:00', '21:00'], schedule_time: '03:00',
  target_forums: ['fid=141'],
  reply_templates: ['谢谢楼主分享！', '感谢分享，收藏了！'],
  skip_keywords: [], skip_prefixes: [], admin_usernames: [],
  auto_post: {
    enabled: false, target_fid: 139, category_id: null, post_folder: 'novels', posted_folder: 'posted',
    post_interval: 300, max_posts_per_day: 5, content_preview_length: 500, move_after_post: true, skip_posted_files: true,
  },
  ai_api_type: 'openai', ai_api_url: '', ai_api_key: '', ai_model: 'gpt-3.5-turbo',
  ai_temperature: 0.8, ai_max_tokens: 200, ai_timeout: 10,
  ai_system_prompt: '你是一个论坛用户，需要根据帖子标题和内容生成简短的回复。回复要自然、简洁，不超过50字。',
  proxy: { enabled: false, http_proxy: '', https_proxy: '', no_proxy: 'localhost,127.0.0.1', use_for_browser: false, use_for_ai: true },
  browser_headers: { user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36', accept_language: 'zh-CN,zh;q=0.9,en;q=0.8' },
  notify: true,
}

function deepMerge(base, over) {
  const out = Array.isArray(base) ? [...base] : { ...base }
  for (const k in (over || {})) {
    const bv = base ? base[k] : undefined
    const ov = over[k]
    if (ov && typeof ov === 'object' && !Array.isArray(ov) && bv && typeof bv === 'object' && !Array.isArray(bv)) {
      out[k] = deepMerge(bv, ov)
    } else if (ov !== undefined) {
      out[k] = ov
    }
  }
  return out
}

const tab = ref('run')
const group = ref('account')
const loading = ref(true)
const saving = ref(false)
const running = ref(false)
const stopping = ref(false)
const testingAi = ref(false)
const cfg = reactive(JSON.parse(JSON.stringify(DEFAULTS)))

// 运行状态
const status = ref({})
let statusTimer = null
// 记录
const recTab = ref('replies')
const posts = ref([])
const replies = ref([])
const messages = ref({ messages: [], total: 0, unread: 0, timestamp: null })
const recLoading = ref(false)
const refreshingMsg = ref(false)
// Cookie
const cookie = ref({})
const cookieImport = ref('')
// 日志
const logs = ref([])
let logTimer = null
// AI 测试
const aiTestTitle = ref('')
const aiTestResult = ref('')

// ── 行文本 <-> 数组（每行一项） ──
function lineModel(key) {
  return computed({
    get: () => (cfg[key] || []).join('\n'),
    set: (v) => { cfg[key] = v.split('\n').map(s => s.trim()).filter(Boolean) },
  })
}
const templatesText = lineModel('reply_templates')
const keywordsText = lineModel('skip_keywords')
const prefixesText = lineModel('skip_prefixes')
const adminsText = lineModel('admin_usernames')
const timesText = lineModel('schedule_times')
const replyMin = computed({ get: () => cfg.reply_interval[0], set: v => { cfg.reply_interval[0] = Number(v) } })
const replyMax = computed({ get: () => cfg.reply_interval[1], set: v => { cfg.reply_interval[1] = Number(v) } })

// 目标版块：已知版块用勾选(fid -> 名称)，另留「自定义」文本框补充列表外的 fid。
const knownForums = computed(() => Object.entries(cfg.forum_names || {}).map(([v, l]) => ({ v, l })))
function toggleForum(fid) {
  const arr = cfg.target_forums || (cfg.target_forums = [])
  const i = arr.indexOf(fid)
  if (i >= 0) arr.splice(i, 1); else arr.push(fid)
}
// 只暴露「不在已知列表里」的额外 fid，避免与勾选互相覆盖。
const customForumsText = computed({
  get: () => (cfg.target_forums || []).filter(f => !(f in (cfg.forum_names || {}))).join('\n'),
  set: (v) => {
    const known = (cfg.target_forums || []).filter(f => f in (cfg.forum_names || {}))
    const custom = v.split('\n').map(s => s.trim()).filter(Boolean)
    cfg.target_forums = [...known, ...custom]
  },
})

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, deepMerge(DEFAULTS, saved || {}))
    if (!Array.isArray(cfg.reply_interval) || cfg.reply_interval.length < 2) cfg.reply_interval = [60, 120]
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
  loadStatus()
  statusTimer = setInterval(() => { if (tab.value === 'run') loadStatus() }, 5000)
})
onUnmounted(() => { clearInterval(statusTimer); clearInterval(logTimer) })

async function save() {
  saving.value = true
  try {
    await props.host.saveConfig(JSON.parse(JSON.stringify(cfg)))
    props.host.toast.success('配置已保存（定时任务将随之更新）')
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

// ── 运行状态 ──
async function loadStatus() {
  try {
    status.value = await props.host.callApi('/status')
    cookie.value = status.value.cookie || {}
  } catch (e) { /* 静默 */ }
}
async function runNow() {
  running.value = true
  try {
    const r = await props.host.callApi('/run', { method: 'POST', body: {} })
    if (r.ok === false) props.host.toast.error(r.message || '启动失败')
    else props.host.toast.success('已在后台开始运行')
    setTimeout(loadStatus, 800)
  } catch (e) {
    props.host.toast.error('启动失败：' + (e.message || e))
  } finally {
    running.value = false
  }
}
async function stopNow() {
  stopping.value = true
  try {
    const r = await props.host.callApi('/stop', { method: 'POST', body: {} })
    props.host.toast.success(r.message || '已请求停止')
    setTimeout(loadStatus, 800)
  } catch (e) {
    props.host.toast.error('停止失败：' + (e.message || e))
  } finally {
    stopping.value = false
  }
}

// ── 记录 ──
async function loadRecords(which) {
  recLoading.value = true
  try {
    if (which === 'replies') replies.value = (await props.host.callApi('/replies')).items || []
    else if (which === 'posts') posts.value = (await props.host.callApi('/posts')).items || []
    else if (which === 'messages') messages.value = await props.host.callApi('/messages')
  } catch (e) {
    props.host.toast.error('读取失败：' + (e.message || e))
  } finally {
    recLoading.value = false
  }
}
function switchRec(t) { recTab.value = t; loadRecords(t) }
async function refreshMessages() {
  refreshingMsg.value = true
  try {
    const r = await props.host.callApi('/messages/refresh', { method: 'POST', body: {} })
    if (r.ok) { props.host.toast.success(`已刷新，共 ${r.count} 条（未读 ${r.unread}）`); loadRecords('messages') }
    else props.host.toast.error('刷新失败：' + (r.message || ''))
  } catch (e) {
    props.host.toast.error('刷新失败：' + (e.message || e))
  } finally {
    refreshingMsg.value = false
  }
}

// ── Cookie ──
async function checkCookie() {
  try { cookie.value = await props.host.callApi('/cookie/check') } catch (e) { props.host.toast.error('检查失败：' + (e.message || e)) }
}
async function importCookie() {
  if (!cookieImport.value.trim()) return props.host.toast.error('请先粘贴 storage_state JSON')
  try {
    const r = await props.host.callApi('/cookie/import', { method: 'POST', body: { storage_state: cookieImport.value } })
    if (r.ok) { props.host.toast.success(r.message || '已导入'); cookieImport.value = ''; checkCookie() }
    else props.host.toast.error(r.message || '导入失败')
  } catch (e) { props.host.toast.error('导入失败：' + (e.message || e)) }
}
async function deleteCookie() {
  if (!confirm('确定删除已保存的登录状态？下次运行需重新登录。')) return
  try {
    const r = await props.host.callApi('/cookie/delete', { method: 'POST', body: {} })
    props.host.toast.success(r.message || '已删除'); checkCookie()
  } catch (e) { props.host.toast.error('删除失败：' + (e.message || e)) }
}

// ── 日志 ──
async function loadLogs() {
  try { logs.value = (await props.host.callApi('/logs')).lines || [] } catch (e) { /* 静默 */ }
}
async function clearLogs() {
  try { await props.host.callApi('/logs/clear', { method: 'POST', body: {} }); logs.value = [] } catch (e) { /* 静默 */ }
}

// ── AI 测试 ──
async function testAi() {
  testingAi.value = true
  aiTestResult.value = '生成中…'
  try {
    const r = await props.host.callApi('/test_ai', { method: 'POST', body: { title: aiTestTitle.value } })
    aiTestResult.value = r.ok ? ('✅ ' + r.reply) : ('❌ ' + (r.message || '失败'))
  } catch (e) {
    aiTestResult.value = '❌ ' + (e.message || e)
  } finally {
    testingAi.value = false
  }
}

function switchTab(t) {
  tab.value = t
  clearInterval(logTimer); logTimer = null
  if (t === 'run') loadStatus()
  if (t === 'records') loadRecords(recTab.value)
  if (t === 'cookie') checkCookie()
  if (t === 'logs') { loadLogs(); logTimer = setInterval(loadLogs, 4000) }
}
</script>

<template>
  <div class="awp">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'run' }]" @click="switchTab('run')">▶ 运行状态</button>
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 设置</button>
        <button :class="['tab', { on: tab === 'records' }]" @click="switchTab('records')">📄 记录</button>
        <button :class="['tab', { on: tab === 'cookie' }]" @click="switchTab('cookie')">🍪 Cookie</button>
        <button :class="['tab', { on: tab === 'logs' }]" @click="switchTab('logs')">📜 日志</button>
      </div>

      <!-- ============ 运行状态 ============ -->
      <div v-show="tab === 'run'" class="pane">
        <section class="card">
          <div class="card-h">运行</div>
          <div class="run-row">
            <span :class="['badge', status.running ? 'live' : 'idle']">{{ status.running ? '运行中 · ' + (status.task || '') : '空闲' }}</span>
            <span class="grow"></span>
            <button class="btn primary" :disabled="running || status.running" @click="runNow">{{ status.running ? '进行中…' : (running ? '启动中…' : '立即运行一次') }}</button>
            <button class="btn danger" :disabled="stopping || !status.running" @click="stopNow">{{ stopping ? '停止中…' : '停止' }}</button>
            <button class="btn" @click="loadStatus">刷新</button>
          </div>
          <div class="metaline">
            <span class="muted">上次开始：{{ status.started_at || '—' }}</span>
            <span class="muted">上次结束：{{ status.finished_at || '—' }}</span>
            <span class="muted">计划：{{ status.schedule || '未设置' }}</span>
          </div>
          <pre v-if="status.last_result" class="output">{{ status.last_result }}</pre>
        </section>

        <div class="stats">
          <div class="stat"><div class="stat-n">{{ (status.today && status.today.reply_count) || 0 }}</div><div class="stat-l">今日回复</div></div>
          <div class="stat"><div class="stat-n">{{ (status.today && status.today.checkin_success) ? '✓' : '—' }}</div><div class="stat-l">今日签到</div></div>
          <div class="stat"><div class="stat-n">{{ (status.today && status.today.post_count) || 0 }}</div><div class="stat-l">今日发帖</div></div>
          <div class="stat"><div class="stat-n" :style="{ color: cookie.valid ? '#6ee7a8' : '#e0b34d' }">{{ cookie.exists ? (cookie.valid ? '有效' : '过期') : '无' }}</div><div class="stat-l">登录状态</div></div>
        </div>

        <section v-if="status.user_info && status.user_info.user_group" class="card">
          <div class="card-h">账号信息</div>
          <div class="metaline">
            <span class="muted">用户组：{{ status.user_info.user_group }}</span>
            <span class="muted">积分：{{ status.user_info.credits }}</span>
            <span class="muted">花币：{{ status.user_info.money }}</span>
          </div>
        </section>
      </div>

      <!-- ============ 设置：左分组 + 右明细 ============ -->
      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">设置分组</div>
          <button v-for="g in GROUPS" :key="g.key" :class="['side-item', { on: group === g.key }]" @click="group = g.key">
            <span>{{ g.label }}</span>
            <span v-if="g.en && cfg[g.en]" class="dot"></span>
          </button>
        </aside>

        <div class="detail">
          <!-- 账号 -->
          <template v-if="group === 'account'">
            <h3 class="det-title">论坛账号</h3>
            <section class="card">
              <div class="grid">
                <label class="row"><span>站点地址</span><input v-model="cfg.base_url" class="inp" /></label>
                <label class="row"><span>用户名</span><input v-model="cfg.username" class="inp" /></label>
                <label class="row"><span>密码</span><input v-model="cfg.password" class="inp" type="password" /></label>
                <label class="row"><span>安全提问</span><select v-model="cfg.security_question_id" class="inp"><option v-for="o in SECURITY_QUESTIONS" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                <label class="row"><span>安全答案</span><input v-model="cfg.security_answer" class="inp" type="password" /></label>
              </div>
              <p class="tip">💡 建议先在「Cookie」页导入已登录的 storage_state，可减少触发 Cloudflare 验证。容器内浏览器恒为无头(headless)模式。</p>
            </section>
          </template>

          <!-- 功能开关 -->
          <template v-else-if="group === 'features'">
            <h3 class="det-title">功能开关</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_daily_checkin" type="checkbox" /><span>每日签到</span></label>
              <label class="row switch"><input v-model="cfg.enable_auto_reply" type="checkbox" /><span>自动回复</span></label>
              <label class="row switch"><input v-model="cfg.enable_smart_reply" type="checkbox" /><span>智能回复（按帖子特征选模板/规则）</span></label>
              <label class="row switch"><input v-model="cfg.enable_ai_reply" type="checkbox" /><span>AI 回复（需在「AI 设置」配置接口）</span></label>
              <label class="row switch"><input v-model="cfg.enable_ai_post_filter" type="checkbox" /><span>AI 帖子类型识别/过滤</span></label>
              <label class="row switch"><input v-model="cfg.enable_auto_post" type="checkbox" /><span>自动发帖</span></label>
              <label class="row switch"><input v-model="cfg.skip_admin_posts" type="checkbox" /><span>跳过管理员/版主帖子</span></label>
              <label class="row switch"><input v-model="cfg.enable_random_delay" type="checkbox" /><span>随机延迟（更拟人）</span></label>
            </section>
            <section class="card">
              <div class="card-h">测试模式（只跑单个动作，用于验证浏览器链路）</div>
              <label class="row switch"><input v-model="cfg.enable_test_mode" type="checkbox" /><span>总测试模式（签到+回复+发帖各测一次）</span></label>
              <label class="row switch"><input v-model="cfg.enable_test_checkin" type="checkbox" /><span>仅测试签到</span></label>
              <label class="row switch"><input v-model="cfg.enable_test_reply" type="checkbox" /><span>仅测试回复</span></label>
              <label class="row switch"><input v-model="cfg.enable_test_post" type="checkbox" /><span>仅测试发帖</span></label>
            </section>
          </template>

          <!-- 回复设置 -->
          <template v-else-if="group === 'reply'">
            <h3 class="det-title">回复设置</h3>
            <section class="card">
              <div class="grid">
                <label class="row"><span>每日上限</span><input v-model.number="cfg.max_replies_per_day" class="inp" type="number" /></label>
                <label class="row"><span>间隔(秒)</span><input v-model="replyMin" class="inp" type="number" /><span class="hint">~</span><input v-model="replyMax" class="inp" type="number" /></label>
              </div>
              <div class="fld"><span class="lbl">目标版块</span>
                <div class="chips">
                  <label v-for="o in knownForums" :key="o.v" class="chip"><input type="checkbox" :checked="(cfg.target_forums || []).includes(o.v)" @change="toggleForum(o.v)" />{{ o.l }}<span class="fid">{{ o.v }}</span></label>
                </div>
              </div>
              <label class="row top"><span>自定义版块</span><textarea v-model="customForumsText" class="inp" rows="2" placeholder="列表外的版块，每行一个，如 fid=999"></textarea></label>
            </section>
            <section class="card">
              <div class="card-h">回复模板（智能/AI 关闭时随机取用）</div>
              <textarea v-model="templatesText" class="inp" rows="6" placeholder="每行一条模板"></textarea>
            </section>
            <section class="card">
              <div class="card-h">过滤</div>
              <label class="row top"><span>跳过关键词</span><textarea v-model="keywordsText" class="inp" rows="4" placeholder="每行一个，标题含则跳过"></textarea></label>
              <label class="row top"><span>跳过前缀</span><textarea v-model="prefixesText" class="inp" rows="2" placeholder="每行一个"></textarea></label>
              <label class="row top"><span>管理员名</span><textarea v-model="adminsText" class="inp" rows="2" placeholder="每行一个用户名"></textarea></label>
            </section>
          </template>

          <!-- 自动发帖 -->
          <template v-else-if="group === 'autopost'">
            <h3 class="det-title">自动发帖</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.auto_post.enabled" type="checkbox" /><span>启用自动发帖（同时需打开「功能开关」里的自动发帖）</span></label>
              <div class="grid">
                <label class="row"><span>目标版块fid</span><input v-model.number="cfg.auto_post.target_fid" class="inp" type="number" /></label>
                <label class="row"><span>分类ID</span><input v-model="cfg.auto_post.category_id" class="inp" placeholder="留空=不选" /></label>
                <label class="row"><span>待发文件夹</span><input v-model="cfg.auto_post.post_folder" class="inp" /></label>
                <label class="row"><span>已发文件夹</span><input v-model="cfg.auto_post.posted_folder" class="inp" /></label>
                <label class="row"><span>发帖间隔(秒)</span><input v-model.number="cfg.auto_post.post_interval" class="inp" type="number" /></label>
                <label class="row"><span>每日上限</span><input v-model.number="cfg.auto_post.max_posts_per_day" class="inp" type="number" /></label>
              </div>
              <label class="row switch"><input v-model="cfg.auto_post.move_after_post" type="checkbox" /><span>发布后移动到已发文件夹</span></label>
              <label class="row switch"><input v-model="cfg.auto_post.skip_posted_files" type="checkbox" /><span>跳过已发布过的文件</span></label>
              <p class="tip">💡 待发文件放在插件数据目录的 <code>novels/</code> 下（.txt/.pdf/.doc/.docx/.epub/.mobi）。</p>
            </section>
          </template>

          <!-- AI -->
          <template v-else-if="group === 'ai'">
            <h3 class="det-title">AI 设置（OpenAI 兼容接口）</h3>
            <section class="card">
              <div class="grid">
                <label class="row"><span>接口类型</span><select v-model="cfg.ai_api_type" class="inp"><option v-for="o in AI_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                <label class="row"><span>接口地址</span><input v-model="cfg.ai_api_url" class="inp" placeholder="https://api.openai.com/v1/chat/completions" /></label>
                <label class="row"><span>密钥</span><input v-model="cfg.ai_api_key" class="inp" type="password" /></label>
                <label class="row"><span>模型</span><input v-model="cfg.ai_model" class="inp" /></label>
                <label class="row"><span>温度</span><input v-model.number="cfg.ai_temperature" class="inp" type="number" step="0.1" /></label>
                <label class="row"><span>最大tokens</span><input v-model.number="cfg.ai_max_tokens" class="inp" type="number" /></label>
                <label class="row"><span>超时(秒)</span><input v-model.number="cfg.ai_timeout" class="inp" type="number" /></label>
              </div>
              <label class="row top"><span>系统提示词</span><textarea v-model="cfg.ai_system_prompt" class="inp" rows="4"></textarea></label>
              <div class="run-row">
                <input v-model="aiTestTitle" class="inp" placeholder="测试帖子标题（留空用默认）" />
                <button class="btn" :disabled="testingAi" @click="testAi">{{ testingAi ? '生成中…' : '测试生成' }}</button>
              </div>
              <pre v-if="aiTestResult" class="output">{{ aiTestResult }}</pre>
            </section>
          </template>

          <!-- 定时/通知 -->
          <template v-else-if="group === 'schedule'">
            <h3 class="det-title">定时与通知</h3>
            <section class="card">
              <label class="row"><span>Cron</span><input v-model="cfg.schedule_cron" class="inp" placeholder="留空则用下方每日时刻" /></label>
              <label class="row top"><span>每日时刻</span><textarea v-model="timesText" class="inp" rows="4" placeholder="每行一个 HH:MM，如 03:00"></textarea></label>
              <label class="row switch"><input v-model="cfg.notify" type="checkbox" /><span>运行结果推送通知</span></label>
              <p class="tip">💡 优先使用 Cron；Cron 留空时按「每日时刻」逐个定时。保存后定时任务自动更新。</p>
            </section>
          </template>

          <!-- 代理/浏览器 -->
          <template v-else-if="group === 'net'">
            <h3 class="det-title">代理与浏览器</h3>
            <section class="card">
              <div class="card-h">代理</div>
              <label class="row switch"><input v-model="cfg.proxy.enabled" type="checkbox" /><span>启用自定义代理（关闭则出站默认走平台代理）</span></label>
              <template v-if="cfg.proxy.enabled">
                <div class="grid">
                  <label class="row"><span>HTTP</span><input v-model="cfg.proxy.http_proxy" class="inp" placeholder="http://127.0.0.1:7890" /></label>
                  <label class="row"><span>HTTPS</span><input v-model="cfg.proxy.https_proxy" class="inp" placeholder="http://127.0.0.1:7890" /></label>
                  <label class="row"><span>no_proxy</span><input v-model="cfg.proxy.no_proxy" class="inp" /></label>
                </div>
                <label class="row switch"><input v-model="cfg.proxy.use_for_ai" type="checkbox" /><span>用于 AI 接口</span></label>
                <label class="row switch"><input v-model="cfg.proxy.use_for_browser" type="checkbox" /><span>用于浏览器</span></label>
              </template>
            </section>
            <section class="card">
              <div class="card-h">浏览器指纹</div>
              <label class="row top"><span>User-Agent</span><textarea v-model="cfg.browser_headers.user_agent" class="inp" rows="2"></textarea></label>
              <label class="row"><span>Accept-Language</span><input v-model="cfg.browser_headers.accept_language" class="inp" /></label>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 记录 ============ -->
      <div v-show="tab === 'records'" class="pane">
        <div class="subtabs">
          <button :class="['stab', { on: recTab === 'replies' }]" @click="switchRec('replies')">回复记录</button>
          <button :class="['stab', { on: recTab === 'posts' }]" @click="switchRec('posts')">发帖记录</button>
          <button :class="['stab', { on: recTab === 'messages' }]" @click="switchRec('messages')">论坛消息</button>
        </div>
        <div class="toolbar">
          <span v-if="recTab === 'messages'" class="muted">未读 {{ messages.unread || 0 }} · 共 {{ messages.total || 0 }} · {{ messages.timestamp || '未刷新' }}</span>
          <span class="grow"></span>
          <button class="btn" @click="loadRecords(recTab)">刷新列表</button>
          <button v-if="recTab === 'messages'" class="btn primary" :disabled="refreshingMsg" @click="refreshMessages">{{ refreshingMsg ? '抓取中…' : '登录抓取最新' }}</button>
        </div>
        <div v-if="recLoading" class="muted">加载中…</div>
        <template v-else>
          <table v-if="recTab === 'replies'" class="tbl">
            <thead><tr><th>帖子</th><th>回复内容</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in replies" :key="i"><td><a :href="r.url" target="_blank">{{ r.title || '—' }}</a></td><td>{{ r.content }}</td><td class="muted">{{ r.time }}</td></tr>
              <tr v-if="!replies.length"><td colspan="3" class="empty">暂无回复记录</td></tr>
            </tbody>
          </table>
          <table v-else-if="recTab === 'posts'" class="tbl">
            <thead><tr><th>标题</th><th>文件</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(p, i) in posts" :key="i"><td><a :href="p.url" target="_blank">{{ p.title || '—' }}</a></td><td class="muted">{{ p.file }}</td><td class="muted">{{ p.time }}</td></tr>
              <tr v-if="!posts.length"><td colspan="3" class="empty">暂无发帖记录</td></tr>
            </tbody>
          </table>
          <table v-else class="tbl">
            <thead><tr><th>标题</th><th>内容</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(m, i) in messages.messages" :key="i"><td>{{ m.title || '—' }}<span v-if="m.is_read === false" class="dot" style="margin-left:6px"></span></td><td>{{ m.content }}</td><td class="muted">{{ m.time }}</td></tr>
              <tr v-if="!messages.messages.length"><td colspan="3" class="empty">暂无消息（点「登录抓取最新」拉取）</td></tr>
            </tbody>
          </table>
        </template>
      </div>

      <!-- ============ Cookie ============ -->
      <div v-show="tab === 'cookie'" class="pane">
        <section class="card">
          <div class="card-h">当前登录状态</div>
          <div class="run-row">
            <span :class="['badge', cookie.valid ? 'live' : 'idle']">{{ cookie.message || '未知' }}</span>
            <span v-if="cookie.cookie_count" class="muted">{{ cookie.cookie_count }} 个 cookie</span>
            <span class="grow"></span>
            <button class="btn" @click="checkCookie">重新检查</button>
            <button class="btn danger" :disabled="!cookie.exists" @click="deleteCookie">删除登录状态</button>
          </div>
        </section>
        <section class="card">
          <div class="card-h">导入 storage_state</div>
          <p class="tip">从本地浏览器/AWPulse 导出的 <code>storage_state.json</code> 全文粘贴到下方导入，可跳过账号登录、降低 Cloudflare 触发。</p>
          <textarea v-model="cookieImport" class="inp" rows="8" placeholder='粘贴 {"cookies":[...],"origins":[...]} JSON'></textarea>
          <div class="savebar"><button class="btn primary" @click="importCookie">导入</button></div>
        </section>
      </div>

      <!-- ============ 日志 ============ -->
      <div v-show="tab === 'logs'" class="pane">
        <div class="toolbar">
          <span class="muted">实时日志（每 4 秒刷新，最多 800 行）</span>
          <span class="grow"></span>
          <button class="btn" @click="loadLogs">刷新</button>
          <button class="btn danger" @click="clearLogs">清空</button>
        </div>
        <pre class="logbox">{{ logs.length ? logs.join('\n') : '暂无日志' }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.awp { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tab { padding: 8px 14px; background: none; border: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #b9c0cc); border-bottom: 2px solid transparent; }
.tab.on { color: var(--accent, #6ea8fe); border-bottom-color: var(--accent, #6ea8fe); }

.layout { display: flex; gap: 16px; align-items: flex-start; }
.sidebar { flex: 0 0 150px; display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.side-title { font-size: 11px; color: var(--text-muted, #7a8291); padding: 4px 8px 6px; }
.side-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 10px; border-radius: 8px; border: none; cursor: pointer; text-align: left; background: none; color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.side-item:hover { background: var(--bg-card, #12141c); }
.side-item.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #6ee7a8; flex: 0 0 auto; display: inline-block; }
.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.det-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary, #e8ebf0); }

.pane { display: flex; flex-direction: column; gap: 14px; }
.card { display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.card-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px 20px; }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child { min-width: 82px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { justify-content: flex-start; }
.row.switch span { min-width: 0; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
textarea.inp { resize: vertical; font-family: inherit; }
.fld { display: flex; flex-direction: column; gap: 6px; }
.lbl { font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-secondary, #b9c0cc); cursor: pointer; padding: 4px 8px; border-radius: 6px; background: var(--bg-card, #12141c); border: 1px solid var(--border-light, #2a2e3a); }
.fid { color: var(--text-muted, #7a8291); font-size: 11px; }
.tip { margin: 4px 0 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; }
.tip code { background: var(--bg-card, #12141c); padding: 1px 5px; border-radius: 4px; }

.btn { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }
.output { margin: 0; padding: 10px; border-radius: 6px; font-size: 12px; white-space: pre-wrap; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }

.run-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.metaline { display: flex; flex-wrap: wrap; gap: 14px; }
.badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; border: 1px solid var(--border-light, #2a2e3a); }
.badge.live { color: #6ee7a8; border-color: #6ee7a855; }
.badge.idle { color: var(--text-muted, #7a8291); }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.stat { padding: 14px 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.stat-n { font-size: 24px; font-weight: 700; line-height: 1.1; color: var(--text-primary, #e8ebf0); }
.stat-l { margin-top: 4px; font-size: 12px; color: var(--text-secondary, #b9c0cc); }

.subtabs { display: flex; gap: 6px; }
.stab { padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border-light, #2a2e3a); background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); cursor: pointer; font-size: 13px; }
.stab.on { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.toolbar { display: flex; align-items: center; gap: 8px; }
.grow { flex: 1; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); vertical-align: top; }
.tbl th { color: var(--text-muted, #7a8291); font-weight: 500; font-size: 12px; }
.tbl td { color: var(--text-primary, #e8ebf0); }
.tbl a { color: var(--accent, #6ea8fe); text-decoration: none; }
.empty { text-align: center; padding: 32px 0; color: var(--text-muted, #7a8291); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.logbox { margin: 0; padding: 12px; border-radius: 8px; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; max-height: 460px; overflow-y: auto; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }

@container (max-width: 620px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
}
</style>
