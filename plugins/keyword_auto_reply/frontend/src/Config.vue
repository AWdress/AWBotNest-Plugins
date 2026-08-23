<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({ enabled: true, midnight_reset: false, leaderboard_enabled: true, rules_text: [], chat_ids: [], delete_after: 0, blacklist_ids: '', leaderboard_command: '.羊毛榜', leaderboard_size: 10 })
const loading = ref(true)
const saving = ref(false)
const openRule = ref(0)

const activeRules = computed(() => cfg.rules_text.filter(rule => rule.reply?.trim() && Number(rule.trigger_chance) > 0).length)
const leaderboardRuleCount = computed(() => cfg.rules_text.filter(rule => rule.count_for_leaderboard !== false).length)
const scopeText = computed(() => Array.isArray(cfg.chat_ids) && cfg.chat_ids.length ? `${cfg.chat_ids.length} 个群组` : '全部群组')

function normalizeRule(rule = {}) {
  return { keyword: String(rule.keyword || ''), reply: String(rule.reply || ''), match_type: ['exact', 'contains'].includes(rule.match_type) ? rule.match_type : 'contains', trigger_mode: ['any', 'reply_to_me'].includes(rule.trigger_mode) ? rule.trigger_mode : 'any', trigger_chance: Math.max(0, Math.min(100, Number(rule.trigger_chance ?? 100))), cooldown_hours: Math.max(0, Number(rule.cooldown_hours ?? 24) || 0), cooldown_notify: rule.cooldown_notify !== false, reset_at_midnight: rule.reset_at_midnight === true, count_for_leaderboard: rule.count_for_leaderboard !== false, fun_reply_chance: Math.max(0, Math.min(100, Number(rule.fun_reply_chance) || 0)), fun_replies: Array.isArray(rule.fun_replies) ? rule.fun_replies.join('\n---\n') : String(rule.fun_replies || ''), extra_reply_enabled: rule.extra_reply_enabled === true, extra_reply: String(rule.extra_reply ?? '叮！恭喜你喜提特等奖掉落。') }
}
function addRule() { cfg.rules_text.push(normalizeRule()); openRule.value = cfg.rules_text.length - 1 }
function duplicateRule(index) { cfg.rules_text.splice(index + 1, 0, normalizeRule(cfg.rules_text[index])); openRule.value = index + 1 }
function removeRule(index) { cfg.rules_text.splice(index, 1); openRule.value = Math.min(openRule.value, cfg.rules_text.length - 1) }
function move(index, delta) { const next = index + delta; if (next < 0 || next >= cfg.rules_text.length) return; const [rule] = cfg.rules_text.splice(index, 1); cfg.rules_text.splice(next, 0, rule); openRule.value = next }

async function save() {
  const invalid = cfg.rules_text.findIndex(rule => !rule.reply.trim())
  if (invalid >= 0) { openRule.value = invalid; props.host.toast.error(`第 ${invalid + 1} 条规则需要填写回复内容`); return }
  const keys = cfg.rules_text.map(rule => rule.keyword.trim()).filter(Boolean)
  if (new Set(keys).size !== keys.length) { props.host.toast.error('关键词不能重复'); return }
  const missingFun = cfg.rules_text.findIndex(rule => rule.fun_reply_chance > 0 && !rule.fun_replies.trim())
  if (missingFun >= 0) { openRule.value = missingFun; props.host.toast.error(`第 ${missingFun + 1} 条规则设置了趣味概率，请至少填写一条趣味文字`); return }
  const missingExtra = cfg.rules_text.findIndex(rule => rule.extra_reply_enabled && !rule.extra_reply.trim())
  if (missingExtra >= 0) { openRule.value = missingExtra; props.host.toast.error(`第 ${missingExtra + 1} 条规则已开启追加回复，请填写追加回复内容`); return }
  saving.value = true
  try {
    cfg.rules_text = cfg.rules_text.map(normalizeRule)
    cfg.delete_after = Math.max(0, Math.min(3600, Math.trunc(Number(cfg.delete_after) || 0)))
    cfg.leaderboard_size = Math.max(3, Math.min(30, Math.trunc(Number(cfg.leaderboard_size) || 10)))
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('聊天互动助手配置已保存')
  } catch (error) { props.host.toast.error(error.message || String(error)) }
  finally { saving.value = false }
}

onMounted(async () => {
  try {
    const saved = await props.host.getConfig()
    Object.assign(cfg, saved || {})
    const fallbackMatch = ['exact', 'contains'].includes(saved?.match_type) ? saved.match_type : 'contains'
    const fallbackCooldown = Number(saved?.cooldown_hours ?? 24) || 24
    const fallbackMidnight = saved?.midnight_reset === true
    cfg.rules_text = Array.isArray(saved?.rules_text) ? saved.rules_text.map(rule => normalizeRule({ match_type: fallbackMatch, cooldown_hours: fallbackCooldown, reset_at_midnight: fallbackMidnight, ...rule })) : []
  } catch (error) { props.host.toast.error(error.message || String(error)) }
  finally { loading.value = false }
})
</script>

<template>
  <main class="surface" :aria-busy="loading">
    <header class="masthead">
      <div><h2>聊天互动助手</h2><p>无需关键词也能按概率参与群聊，每条规则独立控制触发与冷却。</p></div>
      <button class="save" :disabled="loading || saving" @click="save">{{ saving ? '保存中…' : '保存并应用' }}</button>
    </header>

    <section class="status-strip">
      <label class="master"><input v-model="cfg.enabled" type="checkbox"><span><b>{{ cfg.enabled ? '互动已启用' : '互动已暂停' }}</b><small>关闭后保留规则与统计</small></span></label>
      <dl><div><dt>有效规则</dt><dd>{{ activeRules }}</dd></div><div><dt>生效范围</dt><dd>{{ scopeText }}</dd></div><div><dt>回复清理</dt><dd>{{ cfg.delete_after ? `${cfg.delete_after} 秒` : '不删除' }}</dd></div></dl>
    </section>

    <div class="workspace">
      <section class="rules-pane">
        <div class="section-head"><div><h3>互动规则</h3><p>从上到下判断；概率未命中时继续尝试下一条规则。</p></div><button class="add" @click="addRule">新增规则</button></div>
        <div v-if="!cfg.rules_text.length" class="empty"><strong>还没有规则</strong><p>新增第一条规则，设置回复内容、触发概率与独立冷却。</p><button class="add" @click="addRule">创建第一条规则</button></div>
        <ol v-else class="rule-list">
          <li v-for="(rule, index) in cfg.rules_text" :key="index" :class="{ open: openRule === index }">
            <button class="rule-summary" @click="openRule = openRule === index ? -1 : index">
              <span class="order">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="summary-copy"><b>{{ rule.keyword || '任意消息' }}</b><small>{{ rule.keyword ? (rule.match_type === 'exact' ? '完全匹配' : '包含匹配') : '无需关键词' }} · {{ rule.trigger_chance }}% 触发 · {{ rule.trigger_mode === 'reply_to_me' ? '需回复我的消息' : '普通消息' }} · {{ rule.cooldown_hours ? (rule.reset_at_midnight ? '每日零点重置' : `${rule.cooldown_hours} 小时冷却`) : '无冷却' }}{{ rule.extra_reply_enabled ? ' · 追加回复' : '' }}{{ rule.fun_reply_chance ? ` · ${rule.fun_reply_chance}% 彩蛋` : '' }}</small></span>
              <span class="chevron">{{ openRule === index ? '收起' : '编辑' }}</span>
            </button>
            <div v-if="openRule === index" class="editor">
              <div class="field-grid"><label><span>关键词（可选）</span><input v-model="rule.keyword" placeholder="留空则匹配任意消息"><small class="field-help">不填写关键词时，每条群消息都会进入概率判断。</small></label><label><span>匹配方式</span><select v-model="rule.match_type" :disabled="!rule.keyword.trim()"><option value="contains">消息包含关键词</option><option value="exact">消息完全等于关键词</option></select></label></div>
              <label><span>触发概率（%）</span><input v-model.number="rule.trigger_chance" type="number" min="0" max="100" step="1"><small class="field-help">100 表示每次满足条件都触发，0 表示暂停此规则。</small></label>
              <label><span>触发方式</span><select v-model="rule.trigger_mode"><option value="any">普通消息（不要求回复我）</option><option value="reply_to_me">回复我的消息才触发</option></select><small class="field-help">选择“回复我的消息”后，只有别人回复本账号发出的消息且满足关键词条件时才执行。</small></label>
              <label><span>回复内容</span><textarea v-model="rule.reply" rows="4" placeholder="支持 {uname}、{uid} 和 10-100 随机数"></textarea></label>
              <label class="check"><input v-model="rule.extra_reply_enabled" type="checkbox"><span>发送一条追加回复</span></label>
              <label v-if="rule.extra_reply_enabled"><span>追加回复内容</span><textarea v-model="rule.extra_reply" rows="3" placeholder="叮！恭喜你喜提特等奖掉落。"></textarea><small class="field-help">标准回复发出后，再单独发送此消息；同样支持 {uname}、{uid} 和随机数。</small></label>
              <div class="field-grid"><label><span>此规则冷却（小时）</span><input v-model.number="rule.cooldown_hours" type="number" min="0" max="720" step="0.5"></label><label><span>冷却计算方式</span><select v-model="rule.reset_at_midnight"><option :value="false">按小时滚动计算</option><option :value="true">每天零点重置</option></select></label></div>
              <div class="option-row"><label class="check"><input v-model="rule.cooldown_notify" type="checkbox"><span>冷却中回复剩余时间</span></label><label class="check"><input v-model="rule.count_for_leaderboard" type="checkbox"><span>命中后计入羊毛榜</span></label></div>
              <div class="field-grid"><label><span>趣味文字概率（%）</span><input v-model.number="rule.fun_reply_chance" type="number" min="0" max="100" step="1"><small class="field-help">设为 0 表示始终发送标准回复。</small></label><label><span>趣味回复文案</span><textarea v-model="rule.fun_replies" rows="7" placeholder="【系统提示】：该 NPC 暂无掉落物。&#10;建议获取途径：&#10;&#10;1、日常任务：老实做种；&#10;&#10;2、隐藏副本：去隔壁群乞讨。"></textarea><small class="field-help">一整段会完整发送并保留换行；配置多条随机文案时，用单独一行 --- 分隔。</small></label></div>
              <div class="rule-actions"><button @click="move(index,-1)" :disabled="index===0">上移</button><button @click="move(index,1)" :disabled="index===cfg.rules_text.length-1">下移</button><button @click="duplicateRule(index)">复制</button><button class="remove" @click="removeRule(index)">删除</button></div>
            </div>
          </li>
        </ol>
      </section>

      <aside class="settings-pane">
        <section><h3>范围与清理</h3><label><span>生效群组 ID</span><textarea :value="Array.isArray(cfg.chat_ids) ? cfg.chat_ids.join('\n') : cfg.chat_ids" @input="cfg.chat_ids=$event.target.value.split(/[\s,]+/).filter(Boolean)" rows="4" placeholder="留空表示全部群组"></textarea></label><label><span>回复自动删除（秒）</span><input v-model.number="cfg.delete_after" type="number" min="0" max="3600"></label><label><span>屏蔽用户 ID</span><textarea v-model="cfg.blacklist_ids" rows="3" placeholder="逗号或换行分隔"></textarea></label></section>
        <section><h3>薅羊毛排行榜</h3><label class="check"><input v-model="cfg.leaderboard_enabled" type="checkbox"><span>启用排行榜</span></label><template v-if="cfg.leaderboard_enabled"><label><span>本人查询命令</span><input v-model="cfg.leaderboard_command"></label><label><span>显示人数</span><input v-model.number="cfg.leaderboard_size" type="number" min="3" max="30"></label><p class="note">当前有 {{ leaderboardRuleCount }} 条规则计入榜单，可在各规则中单独开关。Premium 使用富文本表格，普通账号自动回退文本。</p></template></section>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.surface{--bg:#0c1624;--panel:#111e2e;--line:#263a52;--text:#e8f0fa;--muted:#91a4bc;--accent:#4b96f3;min-height:640px;color:var(--text);font-family:"Microsoft YaHei",system-ui,sans-serif}.masthead{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:4px 2px 20px;border-bottom:1px solid var(--line)}h2,h3,p{margin:0}.masthead h2{font-size:24px;letter-spacing:-.02em}.masthead p,.section-head p{margin-top:6px;color:var(--muted);font-size:13px}.save,.add{border:0;border-radius:10px;background:var(--accent);color:white;font-weight:700;padding:11px 18px;cursor:pointer}.save:disabled,button:disabled{opacity:.45;cursor:not-allowed}.status-strip{display:flex;justify-content:space-between;gap:22px;align-items:center;padding:18px 0}.master{display:flex;align-items:center;gap:11px}.master span{display:grid;gap:3px}.master small{color:var(--muted)}.status-strip dl{display:flex;gap:28px;margin:0}.status-strip dl div{display:grid;gap:3px}.status-strip dt{color:var(--muted);font-size:11px}.status-strip dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px}.rules-pane,.settings-pane section{background:var(--panel);border:1px solid var(--line);border-radius:14px}.rules-pane{padding:20px}.section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}.section-head h3,.settings-pane h3{font-size:15px}.rule-list{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}.rule-list li{border-bottom:1px solid var(--line)}.rule-summary{width:100%;display:flex;align-items:center;gap:14px;padding:15px 4px;border:0;background:transparent;color:var(--text);text-align:left;cursor:pointer}.order{color:#66809e;font-size:12px;font-variant-numeric:tabular-nums}.summary-copy{display:grid;gap:4px;flex:1;min-width:0}.summary-copy b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.summary-copy small,.chevron{color:var(--muted);font-size:12px}.editor{padding:4px 4px 18px 34px}.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label:not(.master,.check){display:grid;gap:7px;margin:12px 0;color:#b7c6d8;font-size:12px}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #344b66;border-radius:9px;background:#0b1624;color:var(--text);padding:10px 11px;font:inherit;outline:none}textarea{resize:vertical;line-height:1.55}input:focus,select:focus,textarea:focus,button:focus-visible{border-color:#69aaf8;box-shadow:0 0 0 3px #4b96f326}.check{display:flex;align-items:center;gap:9px;color:#b7c6d8;font-size:13px}.check input,.master input{width:17px;height:17px;accent-color:var(--accent)}.rule-actions{display:flex;gap:8px;margin-top:12px}.rule-actions button{border:1px solid #344b66;border-radius:8px;background:#16263a;color:#b9c9dc;padding:7px 11px;cursor:pointer}.rule-actions .remove{margin-left:auto;color:#ffb5b8;border-color:#693941;background:#281a22}.settings-pane{display:grid;align-content:start;gap:14px}.settings-pane section{padding:18px}.settings-pane h3{padding-bottom:12px;border-bottom:1px solid var(--line)}.note{color:var(--muted);font-size:12px;line-height:1.6}.empty{text-align:center;padding:64px 20px;border:1px dashed #38506b;border-radius:12px;color:var(--muted)}.empty strong{display:block;color:var(--text);font-size:16px}.empty p{margin:8px 0 18px}::selection{background:#347fdc;color:white}*{scrollbar-color:#39516d #101b29;scrollbar-width:thin}@media(max-width:760px){.masthead{align-items:flex-start}.status-strip{align-items:flex-start}.status-strip dl{gap:13px;flex-wrap:wrap}.workspace{grid-template-columns:1fr}.field-grid{grid-template-columns:1fr}.editor{padding-left:0}.settings-pane{grid-template-columns:1fr}.save{white-space:nowrap}}
.field-help{color:var(--muted);font-size:12px;line-height:1.55}.option-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px 28px;margin:12px 0}
</style>
