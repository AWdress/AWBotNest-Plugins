<template>
  <div class="quiz-game-config">
    <div class="tabs">
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 设置</button>
      <button :class="{ active: tab === 'history' }" @click="tab = 'history'">📝 答题记录</button>
    </div>

    <div class="tab-content">
      <div v-if="tab === 'settings'" class="settings">
        <section class="section command-guide" aria-labelledby="command-guide-title">
          <div class="guide-heading">
            <div>
              <h3 id="command-guide-title">命令与玩法</h3>
              <p>命令仅由插件绑定的本人账号发送，群友只需直接发送答案。</p>
            </div>
            <span class="guide-badge">本人命令</span>
          </div>
          <div class="command-list">
            <div class="command-item">
              <code>开启答题</code>
              <span>按下方设置的题目数量生成题目并开始，也支持“开始答题”。</span>
            </div>
            <div class="command-item">
              <code>结束答题</code>
              <span>立即结束本场，并清理题目、奖励等答题消息。</span>
            </div>
          </div>
          <p class="guide-note">最先答对的群友获奖，答错会收到短暂提示；单题超时会公布答案并继续下一题。完成全部题目或由本人发送结束命令后，系统会清理本场消息。</p>
        </section>

        <div class="section">
          <h3>群组设置</h3>
          <label class="row"><span>允许的群组</span><input v-model="cfg.valid_groups" class="inp" placeholder="留空=不限制，多个 ID 用逗号分隔" /></label>
          <div v-if="chatNames.length" class="chat-names"><span class="chat-label">已识别：</span><span v-for="item in chatNames" :key="item.id" class="chat-name">{{ item.title }} ({{ item.id }})</span></div>
          <label class="row row-top"><span>答题黑名单</span><textarea v-model="cfg.blacklist_users" class="inp textarea" rows="4" placeholder="用户 ID 或 @username，支持逗号或换行分隔" /></label>
          <p class="tip">黑名单用户的答案将被静默忽略，不提示、不计分，也不会发放奖励。</p>
        </div>

        <div class="section">
          <h3>出题源</h3>
          <label class="row"><span>出题方式</span><select v-model="cfg.source" class="inp">
            <option value="ai">AI 模型</option>
            <option value="tianapi">天行数据</option>
          </select></label>

          <template v-if="cfg.source === 'ai'">
            <p class="tip">使用平台统一 AI 服务（在「系统设置→AI 服务」配置）。</p>
            <label class="row switch"><input v-model="cfg.ai_image_enabled" type="checkbox" /><span>启用 AI 图文题</span></label>
            <label v-if="cfg.ai_image_enabled" class="row indent"><span>配图题比例</span><div class="range-control"><input v-model.number="cfg.ai_image_ratio" type="range" min="0" max="100" step="10" /><output>{{ cfg.ai_image_ratio }}%</output></div></label>
            <p v-if="cfg.ai_image_enabled" class="tip indent-tip">仅为部分题目生成无文字配图；平台生图不可用或生成失败时自动使用纯文字题。</p>
          </template>

          <template v-if="cfg.source === 'tianapi'">
            <label class="row"><span>天行数据 Key</span><input v-model="cfg.tianapi_key" type="password" class="inp" /></label>
          </template>
        </div>

        <div class="section">
          <h3>奖励设置</h3>
          <label class="row"><span>基础奖励(魔力)</span><input v-model.number="cfg.base_reward" type="number" class="inp" min="1" /></label>
          <label class="row switch"><input v-model="cfg.streak_enabled" type="checkbox" /><span>启用连胜加成</span></label>
          <template v-if="cfg.streak_enabled">
            <label class="row indent"><span>连胜倍率</span><input v-model.number="cfg.streak_multiplier" type="number" class="inp" min="1" step="0.1" /></label>
            <label class="row indent"><span>最大连胜</span><input v-model.number="cfg.max_streak" type="number" class="inp" min="1" /></label>
          </template>
        </div>

        <div class="section">
          <h3>答题规则</h3>
          <label class="row"><span>每场题目数量</span><input v-model.number="cfg.question_count" type="number" class="inp" min="1" max="20" /></label>
          <label class="row"><span>答题超时(秒)</span><input v-model.number="cfg.timeout" type="number" class="inp" min="10" /></label>
          <label class="row"><span>自动删除延迟(秒)</span><input v-model.number="cfg.auto_delete_delay" type="number" class="inp" min="0" /></label>
        </div>

        <button @click="save" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>

      <div v-else class="history">
        <div class="toolbar">
          <button @click="loadHistory" class="btn-sm">刷新</button>
          <span class="muted">最近 {{ history.length }} 条</span>
        </div>
        <table class="tbl">
          <thead><tr><th>时间</th><th>群组</th><th>题目</th><th>答案</th><th>回答者</th><th>奖励</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in history" :key="i">
              <td class="muted">{{ h.time }}</td>
              <td>{{ h.group }}</td>
              <td>{{ h.question }}</td>
              <td><b>{{ h.answer }}</b></td>
              <td>{{ h.player || '-' }}</td>
              <td class="gold">{{ h.reward || 0 }}</td>
            </tr>
            <tr v-if="!history.length"><td colspan="6" class="empty">暂无答题记录</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})
const cfg = ref({
  valid_groups: '', blacklist_users: '', source: 'ai',
  ai_api_key: '', ai_base_url: '', ai_model: 'gpt-4o-mini',
  tianapi_key: '',
  base_reward: 500, streak_enabled: true, streak_multiplier: 1.5, max_streak: 5,
  question_count: 5, timeout: 60, auto_delete_delay: 30,
  ai_image_enabled: false, ai_image_ratio: 30,
})
const tab = ref('settings')
const saving = ref(false)
const history = ref([])
const chatNames = ref([])

onMounted(async () => {
  try {
    Object.assign(cfg.value, await props.host.getConfig() || {})
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e))
  }
  await Promise.all([loadHistory(), loadChatNames()])
})

async function save() {
  saving.value = true
  try {
    await props.host.saveConfig({ ...cfg.value })
    await loadChatNames()
    props.host.toast.success('配置已保存')
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function loadHistory() {
  try {
    const r = await props.host.callApi('/history')
    history.value = r.history || []
  } catch (e) {
    props.host.toast.error('读取答题记录失败：' + (e.message || e))
  }
}

async function loadChatNames() {
  try {
    const r = await props.host.callApi('/chat_names')
    chatNames.value = r.items || []
  } catch (e) {
    props.host.toast.error('读取群组名称失败：' + (e.message || e))
  }
}
</script>

<style scoped>
.quiz-game-config { display: flex; flex-direction: column; gap: 16px; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light, #2a2e3a); }
.tabs button { background: none; border: none; color: var(--text-secondary, #b9c0cc); padding: 10px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tabs button.active { color: var(--text-primary, #e8edf5); border-bottom-color: var(--primary, #4a9eff); }
.tab-content { padding: 16px 0; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; color: var(--text-primary, #e8edf5); margin-bottom: 12px; }
.command-guide { padding: 16px; border: 1px solid var(--border-light, #2a2e3a); border-radius: 10px; background: var(--bg-card, #12141c); }
.guide-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.guide-heading h3 { margin: 0 0 5px; font-size: 15px; }
.guide-heading p, .guide-note { margin: 0; color: var(--text-muted, #7a8291); font-size: 12px; line-height: 1.65; }
.guide-badge { flex: none; padding: 4px 9px; border: 1px solid rgba(74, 158, 255, 0.32); border-radius: 999px; background: rgba(74, 158, 255, 0.1); color: var(--primary, #4a9eff); font-size: 11px; }
.command-list { margin: 14px 0 10px; border-top: 1px solid var(--border-light, #2a2e3a); }
.command-item { display: grid; grid-template-columns: 112px 1fr; gap: 14px; align-items: center; padding: 11px 0; border-bottom: 1px solid var(--border-light, #2a2e3a); color: var(--text-secondary, #b9c0cc); font-size: 13px; }
.command-item code { width: fit-content; padding: 4px 8px; border-radius: 5px; background: rgba(74, 158, 255, 0.1); color: var(--text-primary, #e8edf5); font-family: inherit; font-weight: 600; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.row > span:first-child { min-width: 130px; font-size: 13px; color: var(--text-secondary, #b9c0cc); }
.row.switch { gap: 8px; }
.row.row-top { align-items: flex-start; }
.row.switch span { min-width: auto; }
.row.indent { margin-left: 20px; }
.row.indent > span:first-child { min-width: 110px; }
.chat-names { margin: -4px 0 12px 142px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; }
.chat-label { color: var(--text-muted, #7a8291); }
.chat-name { color: var(--text-primary, #e8edf0); }
.inp, select.inp { flex: 1; padding: 8px 12px; background: var(--bg-input, #1a1d26); border: 1px solid var(--border-light, #2a2e3a); border-radius: 6px; color: var(--text-primary, #e8edf5); font-size: 13px; }
.textarea { resize: vertical; min-height: 88px; font-family: inherit; line-height: 1.55; }
.tip { margin: -3px 0 12px 142px; color: var(--text-muted, #7a8291); font-size: 12px; line-height: 1.6; }
.indent-tip { margin-left: 162px; }
.range-control { flex: 1; display: grid; grid-template-columns: minmax(160px, 1fr) 52px; align-items: center; gap: 12px; min-width: 0; }
.range-control input { width: 100%; accent-color: var(--primary, #4a9eff); }
.range-control output { color: var(--text-primary, #e8edf5); font-variant-numeric: tabular-nums; text-align: right; }
.btn, .btn-primary, .btn-sm { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn-primary { background: var(--primary, #4a9eff); color: #fff; }
.btn { background: var(--bg-card, #12141c); color: var(--text-primary, #e8edf5); border: 1px solid var(--border-light, #2a2e3a); margin-right: 8px; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn:disabled, .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); color: var(--text-secondary, #b9c0cc); font-size: 12px; font-weight: normal; }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #2a2e3a); font-size: 13px; color: var(--text-primary, #e8edf5); }
.tbl td.muted { color: var(--text-muted, #7a8291); font-size: 12px; }
.tbl td.empty { text-align: center; color: var(--text-muted, #7a8291); padding: 40px; }
.tbl td.gold { color: #ffd700; font-weight: bold; }
@media (max-width: 640px) {
  .guide-heading { align-items: flex-start; }
  .command-item { grid-template-columns: 1fr; gap: 6px; }
  .row { align-items: flex-start; flex-direction: column; }
  .row > span:first-child { min-width: 0; }
  .chat-names { margin-left: 0; }
  .tip, .indent-tip { margin-left: 0; }
  .range-control { width: 100%; }
}
</style>
