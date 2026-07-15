<script setup>
// AWEmbyPush · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧 6 分组 + 右侧明细）/ 最近推送（战绩 + 测试推送）。
// 注：Webhook 入站地址由平台在配置弹窗底部独立展示，不在本组件内。
import { ref, reactive, onMounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  enable_tmdb: true, tmdb_api_key: '', tmdb_api_domain: 'api.themoviedb.org',
  tmdb_image_domain: 'image.tmdb.org', emby_server_url: '',
  dedup_window: 60, episode_cache_timeout: 30,
  enable_watch_link: false, watch_link_type: 'server', link_redirect_prefix: '',
  tg_bot_token: '', tg_chat_id: '', tg_api_host: '',
  wx_corp_id: '', wx_corp_secret: '', wx_agent_id: '', wx_user_id: '@all',
  wx_msg_type: 'news_notice', wx_proxy_url: '', wx_no_proxy: true,
  bark_server: 'https://api.day.app', bark_keys: '',
  enable_custom_template: false, tg_template: '', wx_title_template: '',
  wx_body_template: '', bark_title_template: '', bark_body_template: '',
}

const GROUPS = [
  { key: 'base', label: '基础' },
  { key: 'watch', label: '观看链接', en: 'enable_watch_link' },
  { key: 'tg', label: 'Telegram' },
  { key: 'wx', label: '企业微信' },
  { key: 'bark', label: 'Bark' },
  { key: 'tpl', label: '自定义模板', en: 'enable_custom_template' },
]
const WATCH_TYPES = [
  { v: 'server', l: 'server（Emby/Jellyfin 直链）' },
  { v: 'forward', l: 'forward（Forward App）' },
  { v: 'infuse', l: 'infuse（Infuse）' },
]
const WX_MSG_TYPES = [
  { v: 'news_notice', l: 'news_notice（卡片）' },
  { v: 'news', l: 'news（图文）' },
]
// 模板可用变量说明（含双大括号，放 JS 常量里避免被 Vue 模板编译器当插值解析）。
const TPL_VARS = '{{server_name}} {{status_text}} {{item_name}} {{episode_text}} {{genres}} {{cast}} {{rating}} {{release_date}} {{overview}} {{play_url}} {{tmdb_url}}'

const tab = ref('settings')
const group = ref('base')
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const cfg = reactive({ ...DEFAULTS })

const recent = ref([])
const recentLoading = ref(false)

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

async function testPush() {
  testing.value = true
  try {
    const r = await props.host.callApi('/test', { method: 'POST', body: {} })
    if (r.ok) props.host.toast.success(r.message || '已发送测试通知')
    else props.host.toast.error(r.message || '测试失败')
  } catch (e) { props.host.toast.error('测试失败：' + (e.message || e)) }
  finally { testing.value = false }
}

async function loadRecent() {
  recentLoading.value = true
  try {
    const r = await props.host.callApi('/recent')
    recent.value = r.items || []
  } catch (e) { props.host.toast.error('读取推送记录失败：' + (e.message || e)) }
  finally { recentLoading.value = false }
}
async function clearRecent() {
  if (!confirm('清空最近推送记录？')) return
  try {
    await props.host.callApi('/clear', { method: 'POST', body: {} })
    recent.value = []
    props.host.toast.success('已清空')
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)) }
}

function switchTab(t) {
  tab.value = t
  if (t === 'recent' && !recent.value.length) loadRecent()
}
</script>

<template>
  <div class="ep">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="['tab', { on: tab === 'settings' }]" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="['tab', { on: tab === 'recent' }]" @click="switchTab('recent')">📮 最近推送</button>
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
          <!-- 基础 -->
          <template v-if="group === 'base'">
            <h3 class="det-title">基础</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_tmdb" type="checkbox" /><span>TMDB 元数据增强</span></label>
              <template v-if="cfg.enable_tmdb">
                <label class="row"><span>TMDB API Key</span><input v-model="cfg.tmdb_api_key" class="inp" type="password" placeholder="留空则不做 TMDB 增强" /></label>
                <div class="grid">
                  <label class="row"><span>API 域名</span><input v-model="cfg.tmdb_api_domain" class="inp" /></label>
                  <label class="row"><span>图片域名</span><input v-model="cfg.tmdb_image_domain" class="inp" /></label>
                </div>
              </template>
              <label class="row"><span>Emby 地址</span><input v-model="cfg.emby_server_url" class="inp" placeholder="https://your-emby.com（生成播放链接/图片降级）" /></label>
              <div class="grid">
                <label class="row"><span>去重窗口</span><input v-model.number="cfg.dedup_window" class="inp sm" type="number" /><span class="hint">秒</span></label>
                <label class="row"><span>剧集合并等待</span><input v-model.number="cfg.episode_cache_timeout" class="inp sm" type="number" /><span class="hint">秒</span></label>
              </div>
            </section>
          </template>

          <!-- 观看链接 -->
          <template v-else-if="group === 'watch'">
            <h3 class="det-title">观看链接</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_watch_link" type="checkbox" /><span>生成观看按钮/链接</span></label>
              <template v-if="cfg.enable_watch_link">
                <label class="row"><span>播放链接类型</span><select v-model="cfg.watch_link_type" class="inp"><option v-for="o in WATCH_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
                <label class="row top"><span>非HTTP中转前缀</span><textarea v-model="cfg.link_redirect_prefix" class="inp" rows="2" placeholder="把 infuse:// 等包装成 http 按钮，支持 {url} 占位"></textarea></label>
              </template>
            </section>
          </template>

          <!-- Telegram -->
          <template v-else-if="group === 'tg'">
            <h3 class="det-title">Telegram</h3>
            <section class="card">
              <label class="row"><span>Bot Token</span><input v-model="cfg.tg_bot_token" class="inp" type="password" placeholder="@BotFather 获取，可填平台机器人 token" /></label>
              <label class="row"><span>Chat ID</span><input v-model="cfg.tg_chat_id" class="inp" placeholder="目标用户或群组 ID" /></label>
              <label class="row"><span>API Host</span><input v-model="cfg.tg_api_host" class="inp" placeholder="留空=官方；自建反代可改" /></label>
            </section>
          </template>

          <!-- 企业微信 -->
          <template v-else-if="group === 'wx'">
            <h3 class="det-title">企业微信</h3>
            <section class="card">
              <label class="row"><span>Corp ID</span><input v-model="cfg.wx_corp_id" class="inp" /></label>
              <label class="row"><span>Corp Secret</span><input v-model="cfg.wx_corp_secret" class="inp" type="password" /></label>
              <div class="grid">
                <label class="row"><span>Agent ID</span><input v-model="cfg.wx_agent_id" class="inp" /></label>
                <label class="row"><span>接收用户</span><input v-model="cfg.wx_user_id" class="inp" placeholder="@all" /></label>
              </div>
              <label class="row"><span>消息类型</span><select v-model="cfg.wx_msg_type" class="inp"><option v-for="o in WX_MSG_TYPES" :key="o.v" :value="o.v">{{ o.l }}</option></select></label>
              <label class="row"><span>API 地址</span><input v-model="cfg.wx_proxy_url" class="inp" placeholder="留空=官方；自建反代可改" /></label>
              <label class="row switch"><input v-model="cfg.wx_no_proxy" type="checkbox" /><span>企微请求不走代理</span></label>
            </section>
          </template>

          <!-- Bark -->
          <template v-else-if="group === 'bark'">
            <h3 class="det-title">Bark</h3>
            <section class="card">
              <label class="row"><span>Bark 服务器</span><input v-model="cfg.bark_server" class="inp" /></label>
              <label class="row top"><span>设备 Key</span><textarea v-model="cfg.bark_keys" class="inp" rows="2" placeholder="多个 Key 用英文逗号分隔；留空不启用 Bark"></textarea></label>
            </section>
          </template>

          <!-- 自定义模板 -->
          <template v-else-if="group === 'tpl'">
            <h3 class="det-title">自定义推送模板（测试）</h3>
            <section class="card">
              <label class="row switch"><input v-model="cfg.enable_custom_template" type="checkbox" /><span>启用自定义推送模板（测试中，不建议生产）</span></label>
              <template v-if="cfg.enable_custom_template">
                <p class="tip">变量：{{ TPL_VARS }}；留空用默认。</p>
                <label class="row top"><span>TG 模板(HTML)</span><textarea v-model="cfg.tg_template" class="inp" rows="4"></textarea></label>
                <label class="row top"><span>企微标题</span><textarea v-model="cfg.wx_title_template" class="inp" rows="2"></textarea></label>
                <label class="row top"><span>企微正文</span><textarea v-model="cfg.wx_body_template" class="inp" rows="3"></textarea></label>
                <label class="row top"><span>Bark 标题</span><textarea v-model="cfg.bark_title_template" class="inp" rows="2"></textarea></label>
                <label class="row top"><span>Bark 正文</span><textarea v-model="cfg.bark_body_template" class="inp" rows="3"></textarea></label>
              </template>
            </section>
          </template>

          <div class="savebar">
            <button class="btn" :disabled="testing" @click="testPush">{{ testing ? '发送中…' : '测试推送' }}</button>
            <button class="btn primary lg" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button>
          </div>
        </div>
      </div>

      <!-- ============ 最近推送 ============ -->
      <div v-show="tab === 'recent'" class="pane">
        <div class="toolbar">
          <span class="muted">最近 {{ recent.length }} 条推送</span>
          <span class="grow"></span>
          <button class="btn" :disabled="testing" @click="testPush">{{ testing ? '发送中…' : '测试推送' }}</button>
          <button class="btn" @click="loadRecent">刷新</button>
          <button class="btn danger" :disabled="!recent.length" @click="clearRecent">清空</button>
        </div>
        <div v-if="recentLoading" class="muted">加载中…</div>
        <div v-else-if="!recent.length" class="empty">暂无推送记录<br><span class="muted">Emby/Jellyfin 入库并成功推送后，这里会显示最近 10 条</span></div>
        <div v-else class="cards">
          <div v-for="(r, i) in recent" :key="i" class="rcard">
            <div class="rimg" :style="r.image_url ? { backgroundImage: `url(${r.image_url})` } : {}">
              <span v-if="!r.image_url" class="rimg-ph">{{ r.item_type === 'TV' ? '📺' : '🎬' }}</span>
            </div>
            <div class="rbody">
              <div class="rname">{{ r.item_name }}</div>
              <div v-if="r.episode_text" class="rep">{{ r.episode_text }}</div>
              <div class="rmeta">
                <span class="rtag">{{ r.item_type === 'TV' ? '剧集' : '电影' }}</span>
                <span class="rch">{{ r.channels || '—' }}</span>
              </div>
              <div class="rtime">{{ r.time }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ep { display: flex; flex-direction: column; gap: 14px; container-type: inline-size; }
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
.row > span:first-child { min-width: 108px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch span { min-width: 0; }
.hint { min-width: 0 !important; font-size: 12px; color: var(--text-muted, #7a8291); white-space: nowrap; }
.tip { margin: 0; font-size: 12px; color: var(--text-muted, #7a8291); line-height: 1.6; word-break: break-all; }
.inp { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 6px; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-primary, #e8ebf0); border: 1px solid var(--border-light, #2a2e3a); }
.inp.sm { flex: 0 0 auto; width: 100px; }
textarea.inp { resize: vertical; font-family: inherit; line-height: 1.5; }
.btn { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); border: 1px solid var(--border-light, #2a2e3a); }
.btn:hover { border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.primary { background: var(--accent-dim, #1e3a5f); border-color: var(--accent, #6ea8fe); color: var(--accent, #6ea8fe); }
.btn.danger:hover { border-color: #ff6b6b; color: #ff6b6b; }
.btn.lg { padding: 9px 22px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.savebar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: 8px; padding-top: 4px; }

.toolbar { display: flex; align-items: center; gap: 8px; }
.grow { flex: 1; }
.empty { text-align: center; padding: 48px 0; font-size: 15px; color: var(--text-secondary, #b9c0cc); }
.muted { font-size: 12px; color: var(--text-muted, #7a8291); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.rcard { display: flex; gap: 10px; padding: 10px; border-radius: 10px; background: var(--bg-elevated, #1a1d27); border: 1px solid var(--border-light, #2a2e3a); }
.rimg { flex: 0 0 54px; width: 54px; height: 80px; border-radius: 6px; background: var(--bg-card, #12141c) center/cover no-repeat; display: flex; align-items: center; justify-content: center; }
.rimg-ph { font-size: 22px; }
.rbody { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.rname { font-size: 13px; font-weight: 600; color: var(--text-primary, #e8ebf0); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rep { font-size: 12px; color: var(--text-secondary, #b9c0cc); }
.rmeta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.rtag { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: var(--bg-card, #12141c); color: var(--text-secondary, #b9c0cc); }
.rch { font-size: 11px; color: var(--accent, #6ea8fe); }
.rtime { font-size: 11px; color: var(--text-muted, #7a8291); margin-top: auto; }

@container (max-width: 640px) {
  .layout { flex-direction: column; }
  .sidebar { flex-basis: auto; width: 100%; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .side-title { display: none; }
}
</style>
