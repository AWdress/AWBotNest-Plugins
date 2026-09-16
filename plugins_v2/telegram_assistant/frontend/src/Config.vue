<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({
  pluginId: {type: String, required: true},
  host: {type: Object, required: true},
})

const TABS = [
  {key: 'forward', label: '消息转发'},
  {key: 'tools', label: '消息工具'},
  {key: 'avatar', label: '自动头像'},
  {key: 'nickname', label: '报时昵称'},
]
const MESSAGE_TYPES = [
  {value: 'text', label: '文本'},
  {value: 'link', label: '链接'},
  {value: 'photo', label: '图片'},
  {value: 'video', label: '视频'},
  {value: 'document', label: '文件'},
  {value: 'audio', label: '音频'},
]

function defaults() {
  return {
    forward_enable: false,
    forward_album: false,
    forward_backfill_limit: 50,
    forward_auto_backfill: false,
    forward_backfill_interval_min: 60,
    forward_repeat_enabled: false,
    forward_repeat_command: '.zf',
    forward_repeat_mode: false,
    forward_repeat_interval: 0.3,
    forward_repeat_max_times: 50,
    forward_rules: [],
    forward_resolved_chat_names: '',
    delete_enabled: false,
    delete_command: '.dme',
    delete_tip_seconds: 2,
    id_enabled: false,
    id_delete_command: false,
    id_command: '.id',
    id_auto_delete: 20,
    getmsg_enabled: false,
    getmsg_delete_command: false,
    getmsg_command: '.getmsg',
    sticker_enabled: false,
    sticker_command: '.贴图',
    sticker_delete_command: false,
    avatar_enabled: false,
    avatar_delete_old: false,
    avatar_interval_min: 60,
    avatar_add_command: '.avataradd',
    avatar_list_command: '.avatarlist',
    avatar_clear_command: '.avatarclear',
    nickname_enabled: false,
    nickname_interval_min: 5,
    nickname_name_format: '{boldH}:{boldM} {weather_icon} {temp}°C',
    nickname_name_field: 'last_name',
    nickname_location: 'Guangzhou',
    nickname_weather_interval: 30,
  }
}

const form = reactive(defaults())
const activeTab = ref('forward')
const loading = ref(true)
const saving = ref(false)
const backfilling = ref(false)
const loadError = ref('')
const savedSnapshot = ref('')

function toast(type, message) {
  props.host.toast?.[type]?.(message)
}

function normalizeRule(rule = {}) {
  return {
    source: String(rule.source || ''),
    targets: String(rule.targets || ''),
    types: Array.isArray(rule.types) ? rule.types.filter((value) => MESSAGE_TYPES.some((item) => item.value === value)) : [],
    kw: String(rule.kw || ''),
    nkw: String(rule.nkw || ''),
    sender: String(rule.sender || ''),
    copy: Boolean(rule.copy),
  }
}

function snapshot() {
  return JSON.stringify(form)
}

const dirty = computed(() => !loading.value && snapshot() !== savedSnapshot.value)
const enabledCount = computed(() => [
  form.forward_enable,
  form.forward_repeat_enabled,
  form.delete_enabled,
  form.id_enabled,
  form.getmsg_enabled,
  form.sticker_enabled,
  form.avatar_enabled,
  form.nickname_enabled,
].filter(Boolean).length)

function tabEnabled(key) {
  if (key === 'forward') return form.forward_enable || form.forward_repeat_enabled
  if (key === 'tools') return form.delete_enabled || form.id_enabled || form.getmsg_enabled || form.sticker_enabled
  if (key === 'avatar') return form.avatar_enabled
  return form.nickname_enabled
}

function addRule() {
  form.forward_rules.push(normalizeRule())
}

function removeRule(index) {
  form.forward_rules.splice(index, 1)
}

function validate() {
  if (form.forward_enable) {
    if (!form.forward_rules.length) {
      toast('error', '启用规则转发后至少需要一条转发规则')
      activeTab.value = 'forward'
      return false
    }
    const incomplete = form.forward_rules.findIndex((rule) => !rule.source.trim() || !rule.targets.trim())
    if (incomplete >= 0) {
      toast('error', `转发规则 ${incomplete + 1} 的来源或目标未填写`)
      activeTab.value = 'forward'
      return false
    }
  }
  const requiredCommands = [
    ['delete_enabled', 'delete_command', '删除消息'],
    ['id_enabled', 'id_command', '查 ID'],
    ['getmsg_enabled', 'getmsg_command', '消息结构'],
    ['sticker_enabled', 'sticker_command', '消息贴图'],
  ]
  for (const [enabled, command, label] of requiredCommands) {
    if (form[enabled] && !String(form[command] || '').trim()) {
      toast('error', `${label}命令不能为空`)
      activeTab.value = 'tools'
      return false
    }
  }
  if (form.avatar_enabled && [form.avatar_add_command, form.avatar_list_command, form.avatar_clear_command].some((value) => !String(value || '').trim())) {
    toast('error', '自动头像的图片池命令不能为空')
    activeTab.value = 'avatar'
    return false
  }
  if (form.nickname_enabled && (!String(form.nickname_name_format || '').trim() || !String(form.nickname_location || '').trim())) {
    toast('error', '报时昵称模板和天气城市不能为空')
    activeTab.value = 'nickname'
    return false
  }
  return true
}

function normalizeNumbers(payload) {
  const ranges = {
    forward_backfill_limit: [1, 500],
    forward_backfill_interval_min: [1, 1440],
    forward_repeat_interval: [0, 5],
    forward_repeat_max_times: [1, 500],
    delete_tip_seconds: [0, 10],
    id_auto_delete: [0, 120],
    avatar_interval_min: [10, 1440],
    nickname_interval_min: [1, 60],
    nickname_weather_interval: [10, 120],
  }
  for (const [key, [min, max]] of Object.entries(ranges)) {
    const value = Number(payload[key])
    payload[key] = Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : defaults()[key]
  }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const saved = await props.host.getConfig()
    const initial = defaults()
    Object.assign(form, initial)
    for (const key of Object.keys(initial)) {
      if (saved && Object.hasOwn(saved, key)) form[key] = saved[key]
    }
    form.forward_rules = Array.isArray(saved?.forward_rules) ? saved.forward_rules.map(normalizeRule) : []
    savedSnapshot.value = snapshot()
  } catch (error) {
    loadError.value = `读取配置失败：${error.message || error}`
  } finally {
    loading.value = false
  }
}

async function save() {
  if (loadError.value) {
    toast('error', '配置尚未成功读取，请刷新后重试')
    return
  }
  if (!validate()) return
  saving.value = true
  try {
    const payload = JSON.parse(JSON.stringify(form))
    payload.forward_rules = payload.forward_rules.map(normalizeRule)
    normalizeNumbers(payload)
    await props.host.saveConfig(payload)
    Object.assign(form, payload)
    savedSnapshot.value = snapshot()
    toast('success', 'Telegram 助手配置已保存并应用')
  } catch (error) {
    toast('error', `保存失败：${error.message || error}`)
  } finally {
    saving.value = false
  }
}

async function runBackfill() {
  if (dirty.value) {
    toast('error', '请先保存当前修改，再立即检查遗漏')
    return
  }
  if (!form.forward_enable || !form.forward_rules.length || backfilling.value) return
  backfilling.value = true
  try {
    const result = await props.host.callApi('/backfill', {method: 'POST', body: {}})
    toast(result?.ok === false ? 'error' : 'success', result?.message || '遗漏检查已启动')
  } catch (error) {
    toast('error', `启动遗漏检查失败：${error.message || error}`)
  } finally {
    backfilling.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="assistant-shell">
    <header class="page-head">
      <div>
        <h2>Telegram 助手</h2>
        <p>{{ enabledCount }} 个功能已启用</p>
      </div>
      <span class="save-state" :class="{changed: dirty}">{{ dirty ? '有未保存修改' : '配置已同步' }}</span>
    </header>

    <p v-if="loadError" class="alert" role="alert">{{ loadError }}</p>
    <div v-if="loading" class="loading">正在读取 Telegram 助手配置…</div>

    <div v-else class="workspace">
      <nav class="section-nav" role="tablist" aria-label="Telegram 助手配置分组">
        <button
          v-for="item in TABS"
          :key="item.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === item.key"
          :class="{active: activeTab === item.key}"
          @click="activeTab = item.key"
        >
          <span>{{ item.label }}</span>
          <i :class="{on: tabEnabled(item.key)}" aria-hidden="true"></i>
        </button>
      </nav>

      <section class="panel" role="tabpanel">
        <template v-if="activeTab === 'forward'">
          <div class="panel-head">
            <div><h3>消息转发</h3><p>规则转发和回复复读分别控制。</p></div>
          </div>

          <div class="switch-grid">
            <label class="switch"><span><b>规则转发</b><small>按来源、类型和关键词匹配消息</small></span><input v-model="form.forward_enable" type="checkbox"><i></i></label>
            <label class="switch"><span><b>整组转发相册</b><small>相册消息保持为同一组</small></span><input v-model="form.forward_album" type="checkbox"><i></i></label>
            <label class="switch"><span><b>自动检查遗漏</b><small>按设定间隔回查来源消息</small></span><input v-model="form.forward_auto_backfill" type="checkbox"><i></i></label>
            <label class="switch"><span><b>回复复读</b><small>回复消息后按命令重复发送</small></span><input v-model="form.forward_repeat_enabled" type="checkbox"><i></i></label>
          </div>

          <div class="subsection">
            <div class="subsection-head">
              <div><h4>转发规则</h4><span>{{ form.forward_rules.length }} 条</span></div>
              <button class="secondary" type="button" @click="addRule">添加规则</button>
            </div>
            <div v-if="!form.forward_rules.length" class="empty">尚未添加转发规则</div>
            <div v-else class="rule-list">
              <article v-for="(rule, index) in form.forward_rules" :key="index" class="rule-item">
                <div class="rule-head"><b>规则 {{ index + 1 }}</b><button class="text-danger" type="button" @click="removeRule(index)">删除</button></div>
                <div class="form-grid">
                  <label><span>来源会话</span><input v-model.trim="rule.source" placeholder="群组 ID 或用户名"></label>
                  <label><span>转发目标</span><input v-model.trim="rule.targets" placeholder="多个目标用逗号分隔"></label>
                  <label><span>包含关键词</span><input v-model.trim="rule.kw" placeholder="留空为不限"></label>
                  <label><span>排除关键词</span><input v-model.trim="rule.nkw" placeholder="留空为不限"></label>
                  <label><span>限定发送者</span><input v-model.trim="rule.sender" placeholder="用户 ID 或用户名"></label>
                  <label class="inline-check"><input v-model="rule.copy" type="checkbox"><span>复制搬运，不显示转发来源</span></label>
                </div>
                <fieldset class="type-field"><legend>消息类型</legend><label v-for="type in MESSAGE_TYPES" :key="type.value"><input v-model="rule.types" type="checkbox" :value="type.value"><span>{{ type.label }}</span></label></fieldset>
              </article>
            </div>
          </div>

          <div class="subsection">
            <div class="subsection-head"><div><h4>遗漏检查</h4></div><button class="secondary" type="button" :disabled="!form.forward_enable || !form.forward_rules.length || backfilling" @click="runBackfill">{{ backfilling ? '正在启动…' : '立即检查遗漏' }}</button></div>
            <div class="form-grid three">
              <label><span>每次回查条数</span><input v-model.number="form.forward_backfill_limit" type="number" min="1" max="500"></label>
              <label><span>自动检查间隔（分钟）</span><input v-model.number="form.forward_backfill_interval_min" type="number" min="1" max="1440"></label>
              <label class="wide"><span>已识别会话</span><input :value="form.forward_resolved_chat_names || '尚未识别'" readonly></label>
            </div>
          </div>

          <div class="subsection">
            <div class="subsection-head"><div><h4>回复复读</h4></div></div>
            <div class="form-grid three">
              <label><span>复读命令</span><input v-model.trim="form.forward_repeat_command"></label>
              <label><span>间隔（秒）</span><input v-model.number="form.forward_repeat_interval" type="number" min="0" max="5" step="0.1"></label>
              <label><span>最多次数</span><input v-model.number="form.forward_repeat_max_times" type="number" min="1" max="500"></label>
              <label class="inline-check"><input v-model="form.forward_repeat_mode" type="checkbox"><span>复制重发，不显示转发来源</span></label>
            </div>
          </div>
        </template>

        <template v-else-if="activeTab === 'tools'">
          <div class="panel-head"><div><h3>消息工具</h3><p>每项工具独立启用和配置。</p></div></div>

          <div class="feature-group">
            <label class="feature-switch"><span><b>删除消息</b><small>删除当前会话中自己最近发送的消息</small></span><input v-model="form.delete_enabled" type="checkbox"><i></i></label>
            <div class="form-grid">
              <label><span>删除命令</span><input v-model.trim="form.delete_command"></label>
              <label><span>提示停留（秒）</span><input v-model.number="form.delete_tip_seconds" type="number" min="0" max="10"></label>
            </div>
          </div>

          <div class="feature-group">
            <label class="feature-switch"><span><b>查 ID</b><small>查询当前会话、用户或回复消息的 ID</small></span><input v-model="form.id_enabled" type="checkbox"><i></i></label>
            <div class="form-grid">
              <label><span>查询命令</span><input v-model.trim="form.id_command"></label>
              <label><span>结果自动删除（秒）</span><input v-model.number="form.id_auto_delete" type="number" min="0" max="120"></label>
              <label class="inline-check"><input v-model="form.id_delete_command" type="checkbox"><span>查询后删除命令消息</span></label>
            </div>
          </div>

          <div class="feature-group">
            <label class="feature-switch"><span><b>消息结构</b><small>将回复消息的 Telethon 结构导出到收藏夹</small></span><input v-model="form.getmsg_enabled" type="checkbox"><i></i></label>
            <div class="form-grid">
              <label><span>导出命令</span><input v-model.trim="form.getmsg_command"></label>
              <label class="inline-check"><input v-model="form.getmsg_delete_command" type="checkbox"><span>导出后删除命令消息</span></label>
            </div>
          </div>

          <div class="feature-group">
            <label class="feature-switch"><span><b>消息贴图</b><small>把回复消息渲染为 Telegram 原生贴纸</small></span><input v-model="form.sticker_enabled" type="checkbox"><i></i></label>
            <div class="form-grid">
              <label><span>贴图命令</span><input v-model.trim="form.sticker_command"></label>
              <label class="inline-check"><input v-model="form.sticker_delete_command" type="checkbox"><span>发送成功后删除命令</span></label>
            </div>
          </div>
        </template>

        <template v-else-if="activeTab === 'avatar'">
          <div class="panel-head"><div><h3>自动头像</h3><p>管理头像图片池与轮换计划。</p></div></div>
          <label class="feature-switch primary-switch"><span><b>启用自动换头像</b><small>定时从当前账号的图片池随机更换头像</small></span><input v-model="form.avatar_enabled" type="checkbox"><i></i></label>
          <div class="form-grid avatar-grid">
            <label><span>换头像间隔（分钟）</span><input v-model.number="form.avatar_interval_min" type="number" min="10" max="1440" step="10"></label>
            <label class="inline-check"><input v-model="form.avatar_delete_old" type="checkbox"><span>更换后删除上一个插件头像</span></label>
            <label><span>添加图片命令</span><input v-model.trim="form.avatar_add_command"></label>
            <label><span>查看图片池命令</span><input v-model.trim="form.avatar_list_command"></label>
            <label><span>清空图片池命令</span><input v-model.trim="form.avatar_clear_command"></label>
          </div>
        </template>

        <template v-else>
          <div class="panel-head"><div><h3>报时昵称</h3><p>按时间和天气更新 Telegram 姓名。</p></div></div>
          <label class="feature-switch primary-switch"><span><b>启用报时昵称</b><small>按设定间隔更新选定的姓名字段</small></span><input v-model="form.nickname_enabled" type="checkbox"><i></i></label>
          <div class="form-grid nickname-grid">
            <label class="wide"><span>昵称模板</span><input v-model="form.nickname_name_format"></label>
            <label><span>修改字段</span><select v-model="form.nickname_name_field"><option value="last_name">姓</option><option value="first_name">名</option><option value="both">姓和名</option></select></label>
            <label><span>更新时间（分钟）</span><input v-model.number="form.nickname_interval_min" type="number" min="1" max="60"></label>
            <label><span>天气城市（英文）</span><input v-model.trim="form.nickname_location" placeholder="Guangzhou"></label>
            <label><span>天气刷新（分钟）</span><input v-model.number="form.nickname_weather_interval" type="number" min="10" max="120" step="5"></label>
            <p class="template-help wide">可用占位符：{boldH}、{boldM}、{H}、{M}、{weather_icon}、{temp}、{emoji}、{date}、{week}</p>
          </div>
        </template>
      </section>
    </div>

    <footer v-if="!loading" class="save-bar">
      <span>{{ dirty ? '修改尚未保存' : '当前配置已保存' }}</span>
      <button class="primary" type="button" :disabled="saving || !!loadError || !dirty" @click="save">{{ saving ? '正在保存…' : '保存配置' }}</button>
    </footer>
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.assistant-shell{--bg:#0c141f;--surface:#111c2a;--surface-2:#162334;--line:#29394e;--line-soft:#202f42;--text:#edf3fb;--muted:#9eacbd;--accent:#36a3e8;--accent-strong:#178bd4;--green:#61d6a2;--danger:#ff8f99;min-width:0;min-height:620px;padding:22px 22px max(18px,env(safe-area-inset-bottom));color:var(--text);background:var(--bg);font-family:inherit;font-size:14px;line-height:1.5;letter-spacing:0;accent-color:var(--accent)}.assistant-shell *{letter-spacing:0}.assistant-shell ::selection{color:#fff;background:#197db8}.page-head{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 2px 18px;border-bottom:1px solid var(--line)}h2,h3,h4,p{margin:0}h2{font-size:22px;line-height:1.25}h3{font-size:19px;line-height:1.3}h4{font-size:15px}.page-head p,.panel-head p{margin-top:4px;color:var(--muted);font-size:12px}.save-state{flex:0 0 auto;padding:6px 10px;border:1px solid #2e5748;border-radius:999px;color:#9ce5c2;background:#112a22;font-size:12px}.save-state.changed{border-color:#755f32;color:#f0ce83;background:#2b2416}.alert{margin-top:16px;padding:12px 14px;border:1px solid #773e48;border-radius:8px;color:#ffc2c8;background:#2a171d;overflow-wrap:anywhere}.loading{padding:56px 20px;color:var(--muted);text-align:center}.workspace{display:grid;grid-template-columns:188px minmax(0,1fr);gap:20px;margin-top:20px}.section-nav{display:flex;flex-direction:column;gap:6px;align-self:start;position:sticky;top:16px}.section-nav button{display:grid;grid-template-columns:1fr 8px;align-items:center;gap:12px;width:100%;min-height:44px;padding:0 12px;border:1px solid transparent;border-radius:8px;color:#aebaca;background:transparent;font:inherit;text-align:left;cursor:pointer}.section-nav button:hover{color:var(--text);background:#121e2d}.section-nav button:focus-visible,.primary:focus-visible,.secondary:focus-visible,.text-danger:focus-visible,input:focus-visible,select:focus-visible,.switch:has(input:focus-visible),.feature-switch:has(input:focus-visible){outline:2px solid #77c5f4;outline-offset:2px}.section-nav button.active{border-color:#315575;color:#f3f8ff;background:#15283a}.section-nav i{width:7px;height:7px;border-radius:50%;background:#4b5a6c}.section-nav i.on{background:var(--green)}.panel{min-width:0;border:1px solid var(--line);border-radius:8px;background:var(--surface);overflow:hidden}.panel-head{padding:20px 22px;border-bottom:1px solid var(--line-soft)}.switch-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:18px 22px}.switch,.feature-switch{display:flex;align-items:center;justify-content:space-between;gap:16px;min-width:0;cursor:pointer}.switch{min-height:64px;padding:11px 13px;border:1px solid var(--line);border-radius:8px;background:#0e1825}.switch span,.feature-switch span{min-width:0}.switch b,.switch small,.feature-switch b,.feature-switch small{display:block}.switch b,.feature-switch b{font-size:13px}.switch small,.feature-switch small{margin-top:3px;color:var(--muted);font-size:11px;line-height:1.4}.switch input,.feature-switch input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}.switch>i,.feature-switch>i{position:relative;flex:0 0 38px;width:38px;height:22px;border:1px solid #456078;border-radius:11px;background:#1b2938}.switch>i::after,.feature-switch>i::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:#91a0b2;transition:left .16s ease-out,background-color .16s ease-out}.switch input:checked+i,.feature-switch input:checked+i{border-color:#3ba8eb;background:#187fbe}.switch input:checked+i::after,.feature-switch input:checked+i::after{left:19px;background:#fff}.subsection,.feature-group{padding:20px 22px;border-top:1px solid var(--line-soft)}.subsection-head,.rule-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.subsection-head{margin-bottom:14px}.subsection-head>div{display:flex;align-items:center;gap:8px}.subsection-head span{color:var(--muted);font-size:12px}.secondary,.primary{min-height:40px;padding:0 14px;border:1px solid #38506a;border-radius:8px;color:var(--text);background:#162538;font:inherit;font-weight:650;cursor:pointer}.secondary:hover:not(:disabled){border-color:#5795c4;background:#1a2e45}.primary{min-width:112px;border-color:var(--accent-strong);color:#fff;background:var(--accent-strong)}.primary:hover:not(:disabled){background:#2499dc}.secondary:disabled,.primary:disabled{opacity:.45;cursor:not-allowed}.empty{padding:24px;border:1px dashed #35485f;border-radius:8px;color:var(--muted);text-align:center}.rule-list{display:grid;gap:12px}.rule-item{padding:15px;border:1px solid var(--line);border-radius:8px;background:#0e1825}.rule-head{padding-bottom:12px}.text-danger{min-height:36px;padding:0 8px;border:0;color:var(--danger);background:transparent;font:inherit;cursor:pointer}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.form-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.form-grid label{min-width:0}.form-grid label>span,.type-field legend{display:block;margin-bottom:6px;color:#aebaca;font-size:12px}input:not([type=checkbox]),select{width:100%;height:42px;padding:0 11px;border:1px solid #344962;border-radius:7px;color:var(--text);background:#0a1420;font:inherit;outline:none}input[readonly]{color:#8f9dae;background:#101923}input::placeholder{color:#6f7e90;opacity:1}select{cursor:pointer}.inline-check{display:flex!important;align-items:center;gap:9px;min-height:42px;padding-top:19px;color:#c7d0dc;cursor:pointer}.inline-check input,.type-field input{flex:0 0 auto;width:18px;height:18px;margin:0}.inline-check span{margin:0!important;color:inherit!important;font-size:13px!important}.type-field{display:flex;align-items:center;flex-wrap:wrap;gap:8px 14px;margin:14px 0 0;padding:12px;border:1px solid var(--line-soft);border-radius:7px}.type-field legend{padding:0 5px;margin:0}.type-field label{display:flex;align-items:center;gap:6px;cursor:pointer}.type-field span{font-size:12px}.wide{grid-column:1/-1}.feature-group:first-of-type{border-top:0}.feature-switch{min-height:48px;margin-bottom:16px}.primary-switch{padding:18px 22px;margin:0;border-bottom:1px solid var(--line-soft)}.primary-switch+.form-grid{padding:20px 22px}.avatar-grid,.nickname-grid{align-items:end}.template-help{padding:10px 12px;border:1px solid var(--line-soft);border-radius:7px;color:#9fb0c3;background:#0e1825;font-size:12px;overflow-wrap:anywhere}.save-bar{position:sticky;z-index:3;bottom:0;display:flex;align-items:center;justify-content:flex-end;gap:16px;margin-top:18px;padding:12px 0 max(4px,env(safe-area-inset-bottom));border-top:1px solid var(--line-soft);background:var(--bg)}.save-bar span{color:var(--muted);font-size:12px}button,input,select{font-family:inherit}@media(max-width:900px){.workspace{grid-template-columns:1fr}.section-nav{position:static;display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));overflow-x:auto;padding-bottom:3px}.section-nav button{white-space:nowrap}.form-grid.three{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.assistant-shell{min-height:0;padding:16px 12px max(14px,env(safe-area-inset-bottom))}.page-head{align-items:flex-start}.save-state{max-width:132px;text-align:center}.workspace{gap:14px;margin-top:14px}.section-nav{grid-template-columns:repeat(4,136px);margin-inline:-2px}.panel-head,.subsection,.feature-group,.switch-grid,.primary-switch,.primary-switch+.form-grid{padding-inline:14px}.switch-grid,.form-grid,.form-grid.three{grid-template-columns:1fr}.inline-check{padding-top:0}.wide{grid-column:auto}.rule-item{padding:12px}.save-bar{justify-content:space-between}.save-bar .primary{min-width:132px}}@media(pointer:coarse){.section-nav button,.secondary,.primary,.text-danger,input:not([type=checkbox]),select{min-height:46px}}@media(forced-colors:active){.panel,.rule-item,.switch,input,select,.secondary,.primary{border:1px solid CanvasText}.section-nav i.on{background:Highlight}}
</style>
