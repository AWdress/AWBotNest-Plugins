<script setup>
// 自动订阅助手 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 三个页签：配置（左侧分组 + 右侧明细，宽屏 master-detail）/ 历史 / 订阅。
import { ref, reactive, onMounted, computed } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})
const CronInput = computed(() => props.host.ui.CronInput)

// ── 静态选项（与后端取值一一对应）──
const DOUBAN_RANKS = [
  { v: 'movie-hot-gaia', l: '热门电影' }, { v: 'tv-hot', l: '热门电视剧' },
  { v: 'movie-real-time', l: '实时热门电影' }, { v: 'show-domestic', l: '热门综艺' },
  { v: 'movie-weekly', l: '一周口碑电影榜' }, { v: 'movie-ustop', l: '电影北美票房榜' },
  { v: 'movie-top250', l: '电影TOP250' },
]
const MEDIA_TYPES = [{ v: 'all', l: '全部' }, { v: 'movie', l: '仅电影' }, { v: 'tv', l: '仅剧集' }]
const MIKAN_SEASONS = [
  { v: '当前', l: '当前季度(自动)' }, { v: '冬', l: '冬季' }, { v: '春', l: '春季' },
  { v: '夏', l: '夏季' }, { v: '秋', l: '秋季' },
]
const NF_DATASETS = [{ v: 'all-weeks-global', l: '最新周榜' }, { v: 'most-popular', l: '史上最热(不分周)' }]
const NF_CATS = [
  { v: 'Films (English)', l: '英语电影' }, { v: 'Films (Non-English)', l: '非英语电影' },
  { v: 'TV (English)', l: '英语剧集' }, { v: 'TV (Non-English)', l: '非英语剧集' },
]
const NF_COUNTRY_TYPES = [{ v: 'Films', l: '电影' }, { v: 'TV', l: '剧集' }]
const MY_PLATFORMS = [
  { v: 'all', l: '全网' }, { v: 'tx', l: '腾讯视频' }, { v: 'iqiyi', l: '爱奇艺' },
  { v: 'youku', l: '优酷' }, { v: 'mgtv', l: '芒果TV' }, { v: 'letv', l: '乐视' },
  { v: 'pptv', l: 'PPTV' }, { v: 'sohu', l: '搜狐' },
]
const MY_TYPES = [
  { v: 'series', l: '电视剧+网络剧' }, { v: 'tv', l: '电视剧' },
  { v: 'web', l: '网络剧' }, { v: 'variety', l: '综艺' },
]
const STATUS_LABELS = {
  subscribed: '新增订阅', exists: '已订阅', in_library: '库中已有',
  unrecognized: '未识别', filtered: '已过滤', already_handled: '已处理', error: '失败',
}
const STATUS_COLORS = {
  subscribed: '#6ee7a8', exists: '#6ea8fe', in_library: '#b9c0cc',
  unrecognized: '#e0b34d', filtered: '#7a8291', already_handled: '#7a8291', error: '#ff6b6b',
}
// 历史顶部统计卡顺序。
const STAT_CARDS = ['subscribed', 'in_library', 'exists', 'filtered', 'unrecognized', 'error']

// 配置分组（左侧导航）。en=对应启用开关键（有则显示启用小圆点）。
const GROUPS = [
  { key: 'global', label: '全局设置' },
  { key: 'missing', label: '本地缺集', en: 'auto_subscribe_missing' },
  { key: 'moviepilot', label: 'MoviePilot 接口', en: 'mp_api_enabled' },
  { key: 'douban', label: '豆瓣榜单', en: 'douban_enabled' },
  { key: 'mikan', label: 'Mikan 新番', en: 'mikan_enabled' },
  { key: 'netflix', label: '奈飞榜单', en: 'netflix_enabled' },
  { key: 'maoyan', label: '猫眼榜单', en: 'maoyan_enabled' },
]
const SOURCE_ENABLE_KEYS = ['douban_enabled', 'mikan_enabled', 'netflix_enabled', 'maoyan_enabled']

const DEFAULTS = {
  api_url: '', api_key: '', schedule: '0 8 * * *', notify: true, ai_assist_recognition: false,
  mp_api_enabled: false, mp_api_key: '', mp_whole_series: false,
  auto_fill_missing: false, auto_fill_missing_limit: 20,
  auto_subscribe_missing: false, auto_subscribe_missing_limit: 0,
  emby_server: '', emby_api_key: '', tmdb_key: '', missing_air_delay_days: 1,
  min_year: 0, min_vote: 0, min_popularity: 0, media_type: 'all',
  douban_enabled: false, douban_ranks: ['movie-hot-gaia', 'tv-hot'],
  douban_rsshub: 'https://rsshub.app', douban_rss_custom: '',
  douban_filter_custom: false, douban_min_year: 0, douban_min_vote: 0, douban_media_type: 'all',
  mikan_enabled: false, mikan_season: '当前', mikan_year: 0, mikan_resolve_detail: true,
  mikan_filter_custom: false, mikan_min_year: 0, mikan_min_vote: 0,
  netflix_enabled: false, netflix_global: true, netflix_dataset: 'all-weeks-global',
  netflix_media_types: ['Films (English)', 'Films (Non-English)', 'TV (English)', 'TV (Non-English)'],
  netflix_countries: [], netflix_country_types: ['Films', 'TV'],
  netflix_limit: 10, netflix_rich: true,
  netflix_filter_custom: false, netflix_min_year: 0, netflix_min_vote: 0, netflix_media_type: 'all',
  maoyan_enabled: false, maoyan_movie_box: true, maoyan_web_platforms: [], maoyan_web_types: [],
  maoyan_num: 10, maoyan_filter_custom: false, maoyan_min_year: 0, maoyan_min_vote: 0, maoyan_media_type: 'all',
}

const tab = ref('settings')
const group = ref('global')
const loading = ref(true)
const configReady = ref(false)
const saving = ref(false)
const running = ref(false)
const testing = ref(false)
const secretVisible = reactive({ api_key: false, emby_api_key: false, tmdb_key: false, mp_api_key: false })
const secretLoading = reactive({ api_key: false, emby_api_key: false, tmdb_key: false, mp_api_key: false })
const mpGenerating = ref(false)
const mpBasePath = ref('/api/plugin/auto_subscribe/mp')
const mpUsername = ref('forward')
const mpAddress = computed(() => `${globalThis.location?.origin || ''}${mpBasePath.value}`)
const libraryTesting = ref(false)
const libraryTestOutput = ref('')
const missingStats = ref({})
const cfg = reactive({ ...DEFAULTS })
const countries = ref([])
const runOutput = ref('')

const history = ref([])
const lastRun = ref('')
const histStats = ref({})
const historyLoading = ref(false)
const statusFilter = ref('all')
const subs = ref([])
const subsLoading = ref(false)
const subsError = ref('')

const enabledCount = computed(() => SOURCE_ENABLE_KEYS.filter(k => cfg[k]).length)

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, DEFAULTS, saved || {})
    configReady.value = true
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
  try {
    const meta = await props.host.callApi('/meta')
    countries.value = meta.countries || []
    mpBasePath.value = meta.mp_base_path || mpBasePath.value
    mpUsername.value = meta.mp_username || mpUsername.value
  } catch (e) { /* 国家选项拉取失败不致命 */ }
})

function toggle(arr, val) {
  const i = arr.indexOf(val)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(val)
}

async function save() {
  if (!configReady.value || saving.value) {
    if (!configReady.value) props.host.toast.error('配置未成功读取，请重新打开配置页后再保存')
    return
  }
  saving.value = true
  try {
    if (cfg.auto_subscribe_missing && (!String(cfg.emby_server || '').trim() || !String(cfg.emby_api_key || '').trim() || !String(cfg.tmdb_key || '').trim())) {
      throw new Error('请在「本地缺集」填写 Emby 地址、Emby API Key 和 TMDB 密钥')
    }
    if (!Number.isInteger(cfg.missing_air_delay_days) || cfg.missing_air_delay_days < 0 || cfg.missing_air_delay_days > 30) {
      throw new Error('播出缓冲天数请填写 0～30 的整数')
    }
    if (cfg.mp_api_enabled && cfg.mp_api_key !== '********' && !/^[A-Za-z0-9._~-]{32,256}$/.test(cfg.mp_api_key)) {
      throw new Error('请在「MoviePilot 接口」生成专用密码，再保存配置')
    }
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('配置已保存')
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function toggleSecret(key) {
  if (secretLoading[key]) return
  if (secretVisible[key]) { secretVisible[key] = false; return }
  secretLoading[key] = true
  try {
    if (cfg[key] === '********') cfg[key] = await props.host.revealSecret(key)
    secretVisible[key] = true
  } catch (e) {
    props.host.toast.error('读取密钥失败：' + (e.message || e))
  } finally { secretLoading[key] = false }
}

async function generateMpKey() {
  if (mpGenerating.value || !configReady.value) return
  mpGenerating.value = true
  try {
    const result = await props.host.callApi('/mp/key', { method: 'POST', body: {} })
    if (!/^[A-Za-z0-9._~-]{32,256}$/.test(result.key || '')) throw new Error('返回的密码格式无效')
    cfg.mp_api_key = result.key
    secretVisible.mp_api_key = false
    props.host.toast.success('专用密码已生成，请保存配置；更换后需在 Forward 更新密码并重新登录')
  } catch (e) {
    props.host.toast.error('生成密码失败：' + (e.message || e))
  } finally { mpGenerating.value = false }
}

async function testLibrary() {
  libraryTesting.value = true
  libraryTestOutput.value = '正在检查已保存的 Emby 和 TMDB 连接…'
  try {
    const r = await props.host.callApi('/test-library')
    libraryTestOutput.value = r.message || (r.ok ? `连接正常，可读取 ${r.series_count || 0} 部 Emby 剧集` : '连接检查失败')
    if (!r.ok) props.host.toast.error(libraryTestOutput.value)
  } catch (e) {
    libraryTestOutput.value = '连接检查失败：' + (e.message || e)
    props.host.toast.error(libraryTestOutput.value)
  } finally { libraryTesting.value = false }
}

async function testConn() {
  testing.value = true
  try {
    const r = await props.host.callApi('/test')
    if (r.ok) props.host.toast.success('连接正常 ✅ ' + JSON.stringify(r.quota || {}))
    else props.host.toast.error('连接失败：' + (r.message || '未知'))
  } catch (e) {
    props.host.toast.error('连接失败：' + (e.message || e))
  } finally {
    testing.value = false
  }
}

async function runNow() {
  running.value = true
  runOutput.value = '运行中…'
  try {
    const r = await props.host.callApi('/run', { method: 'POST', body: {} })
    runOutput.value = r.summary || r.message || '完成'
    if (r.ok === false) props.host.toast.error('运行失败，详见下方')
    else props.host.toast.success(r.started ? '已在后台开始运行' : '已运行一轮')
  } catch (e) {
    runOutput.value = '运行失败：' + (e.message || e)
    props.host.toast.error('运行失败：' + (e.message || e))
  } finally {
    running.value = false
  }
}

// ── 历史 ──
async function loadHistory() {
  historyLoading.value = true
  try {
    const r = await props.host.callApi('/history')
    history.value = r.items || []
    lastRun.value = r.last_run || ''
    histStats.value = r.stats || {}
    missingStats.value = r.missing || {}
  } catch (e) {
    props.host.toast.error('读取历史失败：' + (e.message || e))
  } finally {
    historyLoading.value = false
  }
}
const filteredHistory = computed(() =>
  statusFilter.value === 'all' ? history.value : history.value.filter(h => h.status === statusFilter.value)
)
function typeOfKey(key) { return String(key || '').startsWith('tv:') ? '剧集' : '电影' }
async function delHistory(key) {
  try {
    const r = await props.host.callApi('/history/delete', { method: 'POST', body: { key } })
    if (r.ok === false) throw new Error(r.message || '历史记录未删除')
    history.value = history.value.filter(h => h.key !== key)
  } catch (e) { props.host.toast.error('删除失败：' + (e.message || e)) }
}
async function clearHistory() {
  if (!confirm('确定清空全部处理历史？(不影响已在 NextFind 的订阅)')) return
  try {
    const r = await props.host.callApi('/history/delete', { method: 'POST', body: { clear: true } })
    if (r.ok === false) throw new Error(r.message || '历史记录未清空')
    history.value = []
    props.host.toast.success('已清空历史')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}

// ── 订阅 ──
async function loadSubs() {
  subsLoading.value = true
  subsError.value = ''
  try {
    const r = await props.host.callApi('/subscriptions')
    subs.value = r.items || []
    if (r.error) subsError.value = r.error
  } catch (e) {
    subsError.value = e.message || String(e)
  } finally {
    subsLoading.value = false
  }
}
async function removeSub(s) {
  if (!confirm(`取消订阅《${s.title}》？`)) return
  try {
    const r = await props.host.callApi('/subscriptions/remove', {
      method: 'POST', body: { tmdb_id: s.tmdb_id, media_type: s.media_type },
    })
    if (r.ok) {
      subs.value = subs.value.filter(x => !(x.tmdb_id === s.tmdb_id && x.media_type === s.media_type))
      props.host.toast.success('已取消订阅')
    } else props.host.toast.error('取消失败：' + (r.message || ''))
  } catch (e) { props.host.toast.error('取消失败：' + (e.message || e)) }
}

function switchTab(t) {
  tab.value = t
  if (t === 'history' && !history.value.length) loadHistory()
  if (t === 'subs' && !subs.value.length) loadSubs()
}
</script>

<template>
  <div class="asub">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div v-if="!configReady" class="muted err" role="alert">配置读取失败，已禁止保存以保护已有配置。请重新打开配置页重试。</div>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 订阅配置</button>
        <button :class="['tab', { on: tab === 'history' }]" @click="switchTab('history')">↻ 订阅历史</button>
        <button :class="['tab', { on: tab === 'subs' }]" @click="switchTab('subs')">🔔 订阅管理</button>
      </div>

      <!-- ============ 配置：左分组 + 右明细 ============ -->
      <div v-show="tab === 'settings'" class="layout">
        <aside class="sidebar">
          <div class="side-title">设置分组</div>
          <button v-for="g in GROUPS" :key="g.key"
                  :class="['side-item', { on: group === g.key }]" @click="group = g.key">
            <span>{{ g.label }}</span>
            <span v-if="g.en && cfg[g.en]" class="dot"></span>
          </button>
          <div class="side-foot">启用来源 {{ enabledCount }} / 4</div>
        </aside>

        <div class="detail">
          <!-- 全局 -->
          <template v-if="group === 'global'">
            <h3 class="det-title">全局设置</h3>
            <section class="card">
              <div class="card-h">NextFind 连接</div>
              <div class="grid">
                <label class="row"><span>地址</span>
                  <input v-model="cfg.api_url" class="inp" placeholder="https://你的域名/api/openapi" /></label>
                <label class="row"><span>密钥</span><div class="secret-field">
                  <input v-model="cfg.api_key" class="inp" :type="secretVisible.api_key ? 'text' : 'password'" placeholder="X-API-Key" />
                  <button type="button" :disabled="secretLoading.api_key" :aria-label="secretVisible.api_key ? '隐藏密钥' : '显示密钥'" @click="toggleSecret('api_key')">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button></div></label>
              </div>
              <div class="row"><button class="btn" :disabled="testing" @click="testConn">{{ testing ? '测试中…' : '测试连接' }}</button></div>
            </section>
            <section class="card">
              <div class="card-h">运行</div>
              <div class="grid">
                <label class="row"><span>定时（Cron）</span><component :is="CronInput" v-model="cfg.schedule" /></label>
                <label class="row switch"><input v-model="cfg.notify" type="checkbox" /><span>推送运行结果</span></label>
                <label class="row switch"><input v-model="cfg.ai_assist_recognition" type="checkbox" /><span>平台 AI 辅助识别</span></label>
                <label class="row switch"><input v-model="cfg.auto_fill_missing" type="checkbox" /><span>自动补缺集</span></label>
                <label v-if="cfg.auto_fill_missing" class="row"><span>每轮补缺上限</span><input v-model.number="cfg.auto_fill_missing_limit" class="inp" type="number" min="1" max="100" /></label>
              </div>
              <div v-if="cfg.ai_assist_recognition" class="hint">仅在常规搜索无结果时调用平台 AI 清洗片名、判断电影/剧集及季号；识别结果仍须经 NextFind 核验，平台 AI 不可用时自动降级。</div>
              <div v-if="cfg.auto_fill_missing" class="hint flow-hint">检查已有剧集订阅的入库进度，将明确缺集的项目加入补缺队列，每轮按补缺上限处理。不新增订阅，也无需启用榜单源。</div>
              <div class="hint flow-hint">本地缺集自动订阅请在左侧「本地缺集」设置。先保存配置，再测试连接或立即运行。</div>
              <div class="row">
                <button class="btn primary" :disabled="running" @click="runNow">{{ running ? '运行中…' : '立即运行一次' }}</button>
              </div>
              <pre v-if="runOutput" class="output">{{ runOutput }}</pre>
            </section>
            <section class="card">
              <div class="card-h">全局过滤（各来源默认；可在来源内单独覆盖）</div>
              <div class="grid">
                <label class="row"><span>年份≥</span><input v-model.number="cfg.min_year" class="inp" type="number" /><span class="hint">0=不限</span></label>
                <label class="row"><span>评分≥</span><input v-model.number="cfg.min_vote" class="inp" type="number" min="0" max="10" step="0.5" /><span class="hint">0=不限</span></label>
                <label class="row"><span>热度≥</span><input v-model.number="cfg.min_popularity" class="inp" type="number" /><span class="hint">0=不限</span></label>
                <label class="row"><span>媒体类型</span>
                  <select v-model="cfg.media_type" class="inp"><option v-for="o in MEDIA_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
              </div>
            </section>
          </template>

          <template v-else-if="group === 'missing'">
            <h3 class="det-title">本地缺集</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.auto_subscribe_missing" type="checkbox" /><span>本地缺集自动订阅</span></label>
              <div class="hint flow-hint">从 Emby 读取本地剧集，按季号和集号对比 TMDB 已播集。一次订阅全部未订阅的缺集剧集；不再使用 NextFind 本地缺集接口，也不调用 AI。</div>
              <div class="hint flow-hint">已有订阅不会重复新增。需要让 NextFind 搜索补缺时，请在「全局设置」开启「自动补缺集」。</div>
            </section>
            <section class="card">
              <div class="card-h">Emby 与 TMDB 连接</div>
              <label class="fld"><span class="lbl">Emby 服务地址</span>
                <input v-model="cfg.emby_server" class="inp" placeholder="https://你的Emby域名" />
              </label>
              <div class="hint flow-hint">填写平台所在服务器能访问的 Emby 地址，支持反代域名和带 /emby 的地址。API Key 需能读取完整剧集库。</div>
              <label class="fld"><span class="lbl">Emby API Key</span><div class="secret-field">
                <input v-model="cfg.emby_api_key" class="inp" :type="secretVisible.emby_api_key ? 'text' : 'password'" autocomplete="off" placeholder="在 Emby 控制台 → 高级 → API 密钥中创建" />
                <button type="button" :disabled="secretLoading.emby_api_key" :aria-label="secretVisible.emby_api_key ? '隐藏 Emby API Key' : '显示 Emby API Key'" @click="toggleSecret('emby_api_key')">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                </button></div>
              </label>
              <label class="fld"><span class="lbl">TMDB 密钥</span><div class="secret-field">
                <input v-model="cfg.tmdb_key" class="inp" :type="secretVisible.tmdb_key ? 'text' : 'password'" autocomplete="off" placeholder="TMDB API Key 或 API Read Access Token" />
                <button type="button" :disabled="secretLoading.tmdb_key" :aria-label="secretVisible.tmdb_key ? '隐藏 TMDB 密钥' : '显示 TMDB 密钥'" @click="toggleSecret('tmdb_key')">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                </button></div>
              </label>
              <div class="hint flow-hint">这些配置仅用于 NextFind 助手，不读取其他插件。仅检查 Emby 已有且带 TMDB ID 的剧集；电影、特别篇和季集号不明的条目不参与。</div>
              <label class="row"><span>播出缓冲天数</span><input v-model.number="cfg.missing_air_delay_days" class="inp sm" type="number" min="0" max="30" /></label>
              <div class="hint flow-hint">默认 1 天：按北京时间只核对截至昨天已播出的集，避免当天未放送就判缺集。填 0 包含今天；未来集或没有明确播出日期的集不计入。</div>
              <div class="hint flow-hint">先保存，再测试连接。测试只读取 Emby 和 TMDB，不新增订阅、不补缺，也不修改 Emby。</div>
              <div class="row"><button class="btn" :disabled="libraryTesting" @click="testLibrary">{{ libraryTesting ? '检查中…' : '测试 Emby / TMDB 连接' }}</button></div>
              <pre v-if="libraryTestOutput" class="output" role="status" aria-live="polite">{{ libraryTestOutput }}</pre>
            </section>
          </template>

          <template v-else-if="group === 'moviepilot'">
            <h3 class="det-title">MoviePilot 订阅接口</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.mp_api_enabled" type="checkbox" /><span>接收第三方订阅，转交 NextFind（默认关闭）</span></label>
              <div class="hint flow-hint">提供 MoviePilot v2 风格的登录、新增订阅和订阅列表接口。使用上方「全局设置」中已保存的 NextFind 连接；不需要安装 MoviePilot。</div>
              <div class="hint flow-hint">NextFind 按整部作品订阅，不按季限制。默认拒绝指定季的请求；如果接受追整部剧，请开启下方选项。画质、站点、下载目录等 MoviePilot 专属筛选不支持，不能把它当作完整 MoviePilot 服务。</div>
              <label class="row switch"><input v-model="cfg.mp_whole_series" type="checkbox" /><span>允许把指定季的请求转为整部剧订阅（默认关闭）</span></label>
              <div class="hint flow-hint">开启后，Forward 例如“只订阅第 2 季”的请求也会订阅整部剧；关闭时会明确拒绝，不会悄悄扩大范围。</div>
              <label class="fld"><span class="lbl">接口专用密码 / API Key</span><div class="secret-field">
                <input v-model="cfg.mp_api_key" class="inp" :type="secretVisible.mp_api_key ? 'text' : 'password'" autocomplete="new-password" placeholder="点击下方按钮生成；不是平台登录密码或 NextFind 密钥" />
                <button type="button" :disabled="secretLoading.mp_api_key" :aria-label="secretVisible.mp_api_key ? '隐藏接口专用密码' : '显示接口专用密码'" @click="toggleSecret('mp_api_key')">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                </button></div>
              </label>
              <div class="row"><button type="button" class="btn" :disabled="mpGenerating || !configReady" @click="generateMpKey">{{ mpGenerating ? '生成中…' : (cfg.mp_api_key ? '生成新的专用密码' : '生成专用密码') }}</button></div>
              <div class="hint flow-hint">先生成密码，再启用并保存。密码默认隐藏，点眼睛查看和复制。更换后旧登录凭据立即失效，Forward 需要更新密码并重新登录。</div>
            </section>
            <section class="card">
              <div class="card-h">Forward 怎么填写</div>
              <label class="fld"><span class="lbl">MoviePilot 服务器地址</span><input class="inp" :value="mpAddress" readonly aria-label="Forward MoviePilot 服务器地址" /></label>
              <div class="hint flow-hint">在 Forward「设置 → 服务 → 服务器订阅」填写这个完整地址，不再追加 /api/v1。请从你服务器的域名打开平台，再复制地址；手机须能访问该地址，外网请使用 HTTPS。</div>
              <label class="row"><span>用户名</span><input class="inp" :value="mpUsername" readonly aria-label="Forward 用户名" /></label>
              <div class="hint flow-hint">开启「是否需要登录」。用户名填上面的值，密码填本页的接口专用密码。关闭「同步移除订阅」：此入口只新增和查询，不删除 NextFind 订阅。</div>
              <div class="hint flow-hint">已按 MoviePilot 官方源码校验协议；Forward 内置客户端未公开源码，仍需在你的设备点「测试连接」确认。若它请求了其他接口，请提供报错或请求日志，不会伪造未支持接口的成功结果。</div>
            </section>
          </template>

          <!-- 豆瓣 -->
          <template v-else-if="group === 'douban'">
            <h3 class="det-title">豆瓣榜单</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.douban_enabled" type="checkbox" /><span>启用豆瓣榜单</span></label>
              <template v-if="cfg.douban_enabled">
                <div class="fld"><span class="lbl">订阅榜单</span>
                  <div class="chips">
                    <label v-for="o in DOUBAN_RANKS" :key="o.v" class="chip"><input type="checkbox" :checked="cfg.douban_ranks.includes(o.v)" @change="toggle(cfg.douban_ranks, o.v)" />{{ o.l }}</label>
                  </div>
                </div>
                <label class="row"><span>RSSHub</span><input v-model="cfg.douban_rsshub" class="inp" /></label>
                <label class="row top"><span>自定义RSS</span><textarea v-model="cfg.douban_rss_custom" class="inp" rows="2" placeholder="每行一个完整 RSS 地址"></textarea></label>
                <label class="row switch"><input v-model="cfg.douban_filter_custom" type="checkbox" /><span>独立过滤(否则用全局)</span></label>
                <div v-if="cfg.douban_filter_custom" class="grid subfilter">
                  <label class="row"><span>年份≥</span><input v-model.number="cfg.douban_min_year" class="inp" type="number" /></label>
                  <label class="row"><span>评分≥</span><input v-model.number="cfg.douban_min_vote" class="inp" type="number" min="0" max="10" step="0.5" /></label>
                  <label class="row"><span>类型</span><select v-model="cfg.douban_media_type" class="inp"><option v-for="o in MEDIA_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                </div>
              </template>
            </section>
          </template>

          <!-- Mikan -->
          <template v-else-if="group === 'mikan'">
            <h3 class="det-title">Mikan 季度新番</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.mikan_enabled" type="checkbox" /><span>启用 Mikan 新番</span></label>
              <template v-if="cfg.mikan_enabled">
                <div class="grid">
                  <label class="row"><span>季度</span><select v-model="cfg.mikan_season" class="inp"><option v-for="o in MIKAN_SEASONS" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                  <label class="row"><span>年份</span><input v-model.number="cfg.mikan_year" class="inp" type="number" /><span class="hint">0=当前年</span></label>
                </div>
                <label class="row switch"><input v-model="cfg.mikan_resolve_detail" type="checkbox" /><span>抓详情补放送年(更准更慢)</span></label>
                <label class="row switch"><input v-model="cfg.mikan_filter_custom" type="checkbox" /><span>独立过滤(否则用全局)</span></label>
                <div v-if="cfg.mikan_filter_custom" class="grid subfilter">
                  <label class="row"><span>年份≥</span><input v-model.number="cfg.mikan_min_year" class="inp" type="number" /></label>
                  <label class="row"><span>评分≥</span><input v-model.number="cfg.mikan_min_vote" class="inp" type="number" min="0" max="10" step="0.5" /></label>
                </div>
              </template>
            </section>
          </template>

          <!-- 奈飞 -->
          <template v-else-if="group === 'netflix'">
            <h3 class="det-title">奈飞榜单</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.netflix_enabled" type="checkbox" /><span>启用奈飞榜单</span></label>
              <template v-if="cfg.netflix_enabled">
                <div class="grid">
                  <label class="row switch"><input v-model="cfg.netflix_global" type="checkbox" /><span>全球榜</span></label>
                  <label class="row"><span>数据源</span><select v-model="cfg.netflix_dataset" class="inp"><option v-for="o in NF_DATASETS" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                  <label class="row"><span>每榜前N</span><input v-model.number="cfg.netflix_limit" class="inp" type="number" /></label>
                </div>
                <div class="fld"><span class="lbl">全球类型</span>
                  <div class="chips">
                    <label v-for="o in NF_CATS" :key="o.v" class="chip"><input type="checkbox" :checked="cfg.netflix_media_types.includes(o.v)" @change="toggle(cfg.netflix_media_types, o.v)" />{{ o.l }}</label>
                  </div>
                </div>
                <div class="fld"><span class="lbl">国家/地区榜</span>
                  <div class="chips scroll">
                    <label v-for="o in countries" :key="o.value" class="chip"><input type="checkbox" :checked="cfg.netflix_countries.includes(o.value)" @change="toggle(cfg.netflix_countries, o.value)" />{{ o.label }}</label>
                  </div>
                </div>
                <div class="fld" v-if="cfg.netflix_countries.length"><span class="lbl">国家榜类型</span>
                  <div class="chips">
                    <label v-for="o in NF_COUNTRY_TYPES" :key="o.v" class="chip"><input type="checkbox" :checked="cfg.netflix_country_types.includes(o.v)" @change="toggle(cfg.netflix_country_types, o.v)" />{{ o.l }}</label>
                  </div>
                </div>
                <label class="row switch"><input v-model="cfg.netflix_rich" type="checkbox" /><span>富元数据(带年份，识别更准 · 推荐)</span></label>
                <label class="row switch"><input v-model="cfg.netflix_filter_custom" type="checkbox" /><span>独立过滤(否则用全局)</span></label>
                <div v-if="cfg.netflix_filter_custom" class="grid subfilter">
                  <label class="row"><span>年份≥</span><input v-model.number="cfg.netflix_min_year" class="inp" type="number" /></label>
                  <label class="row"><span>评分≥</span><input v-model.number="cfg.netflix_min_vote" class="inp" type="number" min="0" max="10" step="0.5" /></label>
                  <label class="row"><span>类型</span><select v-model="cfg.netflix_media_type" class="inp"><option v-for="o in MEDIA_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                </div>
              </template>
            </section>
          </template>

          <!-- 猫眼 -->
          <template v-else-if="group === 'maoyan'">
            <h3 class="det-title">猫眼榜单</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.maoyan_enabled" type="checkbox" /><span>启用猫眼榜单</span></label>
              <template v-if="cfg.maoyan_enabled">
                <label class="row switch"><input v-model="cfg.maoyan_movie_box" type="checkbox" /><span>电影票房榜</span></label>
                <div class="fld"><span class="lbl">网播平台</span>
                  <div class="chips">
                    <label v-for="o in MY_PLATFORMS" :key="o.v" class="chip"><input type="checkbox" :checked="cfg.maoyan_web_platforms.includes(o.v)" @change="toggle(cfg.maoyan_web_platforms, o.v)" />{{ o.l }}</label>
                  </div>
                </div>
                <div class="fld"><span class="lbl">网播类型</span>
                  <div class="chips">
                    <label v-for="o in MY_TYPES" :key="o.v" class="chip"><input type="checkbox" :checked="cfg.maoyan_web_types.includes(o.v)" @change="toggle(cfg.maoyan_web_types, o.v)" />{{ o.l }}</label>
                  </div>
                </div>
                <label class="row"><span>每榜条数</span><input v-model.number="cfg.maoyan_num" class="inp" type="number" /></label>
                <label class="row switch"><input v-model="cfg.maoyan_filter_custom" type="checkbox" /><span>独立过滤(否则用全局)</span></label>
                <div v-if="cfg.maoyan_filter_custom" class="grid subfilter">
                  <label class="row"><span>年份≥</span><input v-model.number="cfg.maoyan_min_year" class="inp" type="number" /></label>
                  <label class="row"><span>评分≥</span><input v-model.number="cfg.maoyan_min_vote" class="inp" type="number" min="0" max="10" step="0.5" /></label>
                  <label class="row"><span>类型</span><select v-model="cfg.maoyan_media_type" class="inp"><option v-for="o in MEDIA_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                </div>
              </template>
            </section>
          </template>

          <div class="savebar"><button class="btn primary lg" :disabled="saving || !configReady" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </div>
      </div>

      <!-- ============ 历史 ============ -->
      <div v-show="tab === 'history'" class="pane">
        <div v-if="Object.keys(missingStats).length" class="output" role="status">
          <div v-if="missingStats.scan_error">上轮本地缺集：已读取 Emby 剧集 {{ missingStats.scanned ?? '—' }} 部。扫描未完成，未执行缺集订阅。</div>
          <div v-else>上轮本地缺集：Emby 剧集 {{ missingStats.scanned ?? '—' }} 部，缺集剧集 {{ missingStats.checked || 0 }} 部，缺 {{ missingStats.missing_episodes || 0 }} 集；新增 {{ missingStats.added || 0 }} 部，已订阅跳过 {{ missingStats.skipped || 0 }} 部，资料不全跳过 {{ missingStats.unknown || 0 }} 部，失败 {{ missingStats.failed || 0 }} 部。</div>
          <div v-if="missingStats.error" class="muted err">{{ missingStats.error }}</div>
        </div>
        <div class="stats">
          <div v-for="k in STAT_CARDS" :key="k" class="stat" :style="{ borderColor: STATUS_COLORS[k] + '55' }">
            <div class="stat-n" :style="{ color: STATUS_COLORS[k] }">{{ histStats[k] || 0 }}</div>
            <div class="stat-l">{{ STATUS_LABELS[k] }}</div>
          </div>
        </div>
        <div class="toolbar">
          <span class="muted">上次运行：{{ lastRun || '—' }}</span>
          <span class="grow"></span>
          <select v-model="statusFilter" class="inp sm">
            <option value="all">全部状态</option>
            <option v-for="(l, k) in STATUS_LABELS" :key="k" :value="k">{{ l }}</option>
          </select>
          <button class="btn" @click="loadHistory">刷新</button>
          <button class="btn danger" @click="clearHistory">清空</button>
        </div>
        <div v-if="historyLoading" class="muted">加载中…</div>
        <div v-else-if="!filteredHistory.length" class="empty">暂无订阅历史记录<br><span class="muted">启用来源并运行后，这里会记录每次订阅结果</span></div>
        <table v-else class="tbl">
          <thead><tr><th>标题</th><th>类型</th><th>状态</th><th>来源</th><th>时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="h in filteredHistory" :key="h.key">
              <td>{{ h.title }}</td>
              <td>{{ typeOfKey(h.key) }}</td>
              <td><span :style="{ color: STATUS_COLORS[h.status] || '#b9c0cc' }">{{ STATUS_LABELS[h.status] || h.status }}</span></td>
              <td class="muted">{{ h.source || '—' }}</td>
              <td class="muted">{{ h.time }}</td>
              <td><button class="btn xs" @click="delHistory(h.key)">删除</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ============ 订阅 ============ -->
      <div v-show="tab === 'subs'" class="pane">
        <div class="toolbar">
          <span class="muted">NextFind 活跃订阅</span>
          <span class="grow"></span>
          <button class="btn" @click="loadSubs">刷新</button>
        </div>
        <div v-if="subsLoading" class="muted">加载中…</div>
        <div v-else-if="subsError" class="muted err">读取失败：{{ subsError }}</div>
        <div v-else-if="!subs.length" class="empty">暂无本插件创建的订阅<br><span class="muted">启用来源运行后，订阅会出现在这里</span></div>
        <table v-else class="tbl">
          <thead><tr><th>标题</th><th>类型</th><th>年份</th><th>评分</th><th>进度</th><th>状态</th><th></th></tr></thead>
          <tbody>
            <tr v-for="s in subs" :key="s.tmdb_id + s.media_type">
              <td>{{ s.title }}</td>
              <td>{{ s.media_type === 'tv' ? '剧集' : '电影' }}</td>
              <td class="muted">{{ s.year || '—' }}</td>
              <td class="muted">{{ s.rating || '—' }}</td>
              <td class="muted">{{ s.media_type === 'tv' ? `${s.local_episodes || 0}/${s.total_episodes || 0}` : (s.is_in_library ? '已入库' : '—') }}</td>
              <td class="muted">{{ s.sub_status || s.status || '—' }}</td>
              <td><button class="btn xs danger" @click="removeSub(s)">取消</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* container-type：让下面的 @container 按「本组件(=配置弹窗)实际宽度」自适应，
   而非浏览器视口宽度——平台弹窗被 max-width:90vw 夹窄时也能正确收起侧栏。 */
.asub { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tab {
  padding: 8px 16px; background: none; border: none; cursor: pointer; font-size: 13px;
  color: var(--text-secondary, #b9c0cc); border-bottom: 2px solid transparent;
}
.tab.on { color: var(--accent, #6ea8fe); border-bottom-color: var(--accent, #6ea8fe); }

/* master-detail 布局 */
.layout { display: flex; gap: 16px; align-items: flex-start; }
.sidebar {
  flex: 0 0 150px; display: flex; flex-direction: column; gap: 4px;
  padding: 10px; border-radius: 10px;
  background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a);
}
.side-title { font-size: 11px; color: var(--text-muted, #7a8291); padding: 4px 8px 6px; }
.side-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 9px 10px; border-radius: 8px; border: none; cursor: pointer; text-align: left;
  background: none; color: var(--text-secondary, #b9c0cc); font-size: 13px;
}
.side-item:hover { background: var(--bg-card, #12141c); }
.side-item.on { background: var(--accent-dim, #1e3a5f); color: var(--accent, #6ea8fe); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #6ee7a8; flex: 0 0 auto; }
.side-foot { margin-top: 8px; padding: 8px; font-size: 11px; color: var(--text-muted, #7a8291); border-top: 1px solid var(--border-light, #2a2e3a); }
.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.det-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary, #e8ebf0); }

.pane { display: flex; flex-direction: column; gap: 14px; }
.card {
  display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 10px;
  background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a);
}
.card-h { font-size: 13px; font-weight: 600; color: var(--accent, #6ea8fe); }
/* 表单自适应：窄模态单列（输入框占满、不截断），够宽才两列。 */
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px 20px; }
.subfilter { padding: 12px; border-radius: 8px; background: var(--bg-card, #12141c); border: 1px dashed var(--border-light, #2a2e3a); }
.row { display: flex; align-items: center; gap: 10px; }
.row.top { align-items: flex-start; }
.row > span:first-child, .lbl { min-width: 64px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { justify-content: flex-start; }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.flow-hint { white-space: normal; line-height: 1.6; overflow-wrap: anywhere; color: var(--text-secondary, #b9c0cc); }
.secret-field { position: relative; flex: 1; min-width: 0; }
.fld .secret-field { flex: auto; }
.secret-field .inp { width: 100%; box-sizing: border-box; padding-right: 44px; }
.secret-field button { position: absolute; inset-inline-end: 4px; top: 50%; transform: translateY(-50%); width: 34px; height: 34px; display: grid; place-items: center; border: 0; border-radius: 7px; background: transparent; color: var(--text-muted, #7a8291); cursor: pointer; }
.secret-field button:hover { color: var(--accent, #6ea8fe); background: var(--accent-dim, #1e3a5f); }
.secret-field svg { width: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; }
.inp {
  flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px;
  background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0);
  border: 1px solid var(--border-light, #2a2e3a);
}
.inp.sm { flex: 0 0 auto; width: 130px; }
textarea.inp { resize: vertical; font-family: inherit; }
.fld { display: flex; flex-direction: column; gap: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips.scroll { max-height: 150px; overflow-y: auto; padding: 8px; border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; }
.chip {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
  color: var(--text-secondary, #b9c0cc); cursor: pointer;
  padding: 4px 8px; border-radius: 6px; background: var(--bg-card, #12141c);
  border: 1px solid var(--border-light, #2a2e3a);
}
.btn {
  padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
  background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc);
  border: 1px solid var(--border-light, #2a2e3a);
}
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn.xs { padding: 3px 9px; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.inp:focus-visible, button:focus-visible { outline: 2px solid var(--accent, #6ea8fe); outline-offset: 2px; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; padding-top: 4px; }
.output { margin: 0; padding: 10px; border-radius: 6px; font-size: 12px; white-space: pre-wrap; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }

/* 历史统计卡：横向铺开 */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.stat { padding: 14px 16px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.stat-n { font-size: 26px; font-weight: 700; line-height: 1.1; }
.stat-l { margin-top: 4px; font-size: 12px; color: var(--text-secondary, #b9c0cc); }

.toolbar { display: flex; align-items: center; gap: 8px; }
.grow { flex: 1; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tbl th { color: var(--text-muted, #7a8291); font-weight: 500; font-size: 12px; }
.tbl td { color: var(--text-primary, #e8ebf0); }
.empty { text-align: center; padding: 48px 0; font-size: 15px; color: var(--text-secondary, #b9c0cc); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.muted.err { color: #ff6b6b; }

/* 弹窗较窄时：分组栏从左侧竖排改为顶部横排 chips，把整宽让给明细。 */
@container (max-width: 620px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
  .side-item { flex: 0 1 auto; }
  .side-foot { width: 100%; margin-top: 4px; border-top: none; }
  .stats { grid-template-columns: repeat(3, 1fr); }
}
/* 更窄（手机）：统计卡两列 */
@container (max-width: 380px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
</style>
