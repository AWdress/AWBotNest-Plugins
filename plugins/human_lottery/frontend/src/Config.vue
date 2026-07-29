<script setup>
import { onMounted, reactive, ref } from 'vue'

const props = defineProps({
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
})

const DEFAULTS = {
  enabled: true, create_word: '创建抽奖', status_word: '抽奖状态',
  draw_word: '立即开奖', cancel_word: '取消抽奖',
  default_keyword: '参与抽奖', default_duration: 10, default_winners: 1,
  min_participants: 1, max_duration: 1440, max_winners: 100,
  allow_creator: false, require_reply: false, delete_commands: true,
  announce_delay_min: 1, announce_delay_max: 3,
  draw_delay_min: 2, draw_delay_max: 8, progress_every: 0,
  blacklist_ids: '', notify_owner: true,
  auto_award: true, award_command: '+{amount}',
  award_delay_min: 1, award_delay_max: 3,
  announce_template: '🎉 抽奖开始啦！\n\n🎁 奖品：{prize}\n🏆 中奖人数：{winners} 人\n⏰ 开奖时间：{draw_time}\n🔑 参与方式：发送「{keyword}」\n\n每人只能参与一次，祝大家好运～',
  result_template: '🎊 开奖啦！\n\n🎁 奖品：{prize}\n👥 参与人数：{participants}\n🏆 中奖名单：\n{winner_list}\n\n恭喜中奖，感谢大家参与～',
  empty_template: '这次抽奖参与人数不足（{participants}/{minimum}），先取消啦，下次再来～',
}
const groups = [
  ['basic', '基本设置'], ['commands', '群内命令'], ['award', '自动发奖'], ['rules', '参与规则'],
  ['human', '人形行为'], ['text', '发布文案'], ['block', '黑名单'],
]
const cfg = reactive({ ...DEFAULTS })
const tab = ref('settings')
const group = ref('basic')
const loading = ref(true)
const saving = ref(false)
const monitorLoading = ref(false)
const activities = ref([])
const history = ref([])
const operating = ref('')

onMounted(async () => {
  try { Object.assign(cfg, DEFAULTS, await props.host.getConfig() || {}) }
  catch (e) { props.host.toast.error('读取配置失败：' + (e.message || e)) }
  finally { loading.value = false }
})
async function save() {
  saving.value = true
  try { await props.host.saveConfig({ ...cfg }); props.host.toast.success('配置已保存') }
  catch (e) { props.host.toast.error('保存失败：' + (e.message || e)) }
  finally { saving.value = false }
}
async function refresh() {
  monitorLoading.value = true
  try {
    activities.value = (await props.host.callApi('/activities')).items || []
    history.value = (await props.host.callApi('/history')).items || []
  } catch (e) { props.host.toast.error('读取活动失败：' + (e.message || e)) }
  finally { monitorLoading.value = false }
}
async function operate(path, item) {
  const action = path === '/draw' ? '提前开奖' : '取消'
  if (!confirm(`${action}抽奖 #${item.lottery_id}？`)) return
  operating.value = item.key
  try {
    const result = await props.host.callApi(path, { method: 'POST', body: { key: item.key } })
    result.ok ? props.host.toast.success(result.message || '操作成功') : props.host.toast.error(result.message || '操作失败')
    await refresh()
  } catch (e) { props.host.toast.error('操作失败：' + (e.message || e)) }
  finally { operating.value = '' }
}
function switchTab(value) { tab.value = value; if (value === 'monitor') refresh() }
</script>

<template>
  <div class="root">
    <div v-if="loading" class="muted">加载配置…</div>
    <template v-else>
      <div class="tabs">
        <button :class="{ on: tab === 'settings' }" @click="switchTab('settings')">⚙ 配置</button>
        <button :class="{ on: tab === 'monitor' }" @click="switchTab('monitor')">🎟 抽奖管理</button>
      </div>
      <div v-show="tab === 'settings'" class="layout">
        <aside><button v-for="g in groups" :key="g[0]" :class="{ on: group === g[0] }" @click="group = g[0]">{{ g[1] }}</button></aside>
        <main>
          <section v-if="group === 'basic'" class="card">
            <h3>基本设置</h3>
            <label class="switch"><input v-model="cfg.enabled" type="checkbox">启用幸运抽奖</label>
            <label class="switch"><input v-model="cfg.notify_owner" type="checkbox">开奖结果通知我</label>
            <div class="grid">
              <label>默认参与词<input v-model="cfg.default_keyword"></label>
              <label>默认持续分钟<input v-model.number="cfg.default_duration" type="number" min="1"></label>
              <label>默认中奖人数<input v-model.number="cfg.default_winners" type="number" min="1"></label>
              <label>最低参与人数<input v-model.number="cfg.min_participants" type="number" min="1"></label>
              <label>最长持续分钟<input v-model.number="cfg.max_duration" type="number" min="1"></label>
              <label>最大中奖人数<input v-model.number="cfg.max_winners" type="number" min="1"></label>
            </div>
          </section>
          <section v-else-if="group === 'commands'" class="card">
            <h3>群内命令</h3>
            <div class="grid">
              <label>创建抽奖<input v-model="cfg.create_word"></label>
              <label>查看状态<input v-model="cfg.status_word"></label>
              <label>提前开奖<input v-model="cfg.draw_word"></label>
              <label>取消抽奖<input v-model="cfg.cancel_word"></label>
            </div>
            <label class="switch"><input v-model="cfg.delete_commands" type="checkbox">执行后删除我的命令消息</label>
            <p class="tip">格式：{{ cfg.create_word }} 奖品 | 中奖人数 | 持续分钟 | 参与关键词 | 每人奖励<br>最后一项可省略，插件会从奖品名称提取数字。示例：{{ cfg.create_word }} 1000魔力 | 3 | 10 | 冲鸭</p>
          </section>
          <section v-else-if="group === 'award'" class="card">
            <h3>自动发奖</h3>
            <label class="switch"><input v-model="cfg.auto_award" type="checkbox">开奖后自动给中奖者发奖</label>
            <label>发奖命令模板<input v-model="cfg.award_command" placeholder="+{amount}"></label>
            <div class="grid">
              <label>逐人间隔最少秒<input v-model.number="cfg.award_delay_min" type="number" min="0" step=".5"></label>
              <label>逐人间隔最多秒<input v-model.number="cfg.award_delay_max" type="number" min="0" step=".5"></label>
            </div>
            <p class="tip">默认回复中奖者的参与消息发送“+金额”，供群转账 Bot 打款。模板可用 {amount} {prize} {lottery_id}。</p>
          </section>
          <section v-else-if="group === 'rules'" class="card">
            <h3>参与规则</h3>
            <label class="switch"><input v-model="cfg.allow_creator" type="checkbox">允许创建者参与</label>
            <label class="switch"><input v-model="cfg.require_reply" type="checkbox">必须回复抽奖公告才计入</label>
            <label>每 N 人播报一次（0=关闭）<input v-model.number="cfg.progress_every" type="number" min="0"></label>
          </section>
          <section v-else-if="group === 'human'" class="card">
            <h3>人形随机延迟</h3>
            <div class="grid">
              <label>发布最少秒<input v-model.number="cfg.announce_delay_min" type="number" min="0" step=".5"></label>
              <label>发布最多秒<input v-model.number="cfg.announce_delay_max" type="number" min="0" step=".5"></label>
              <label>开奖最少秒<input v-model.number="cfg.draw_delay_min" type="number" min="0" step=".5"></label>
              <label>开奖最多秒<input v-model.number="cfg.draw_delay_max" type="number" min="0" step=".5"></label>
            </div>
          </section>
          <section v-else-if="group === 'text'" class="card">
            <h3>发布文案</h3>
            <label>抽奖公告<textarea v-model="cfg.announce_template" rows="8"></textarea></label>
            <label>开奖文案<textarea v-model="cfg.result_template" rows="8"></textarea></label>
            <label>人数不足文案<textarea v-model="cfg.empty_template" rows="3"></textarea></label>
            <p class="tip">公告可用 {prize} {winners} {keyword} {duration} {draw_time}；开奖可用 {prize} {participants} {winners} {winner_list}。</p>
          </section>
          <section v-else class="card">
            <h3>参与黑名单</h3>
            <label>用户 ID<textarea v-model="cfg.blacklist_ids" rows="6" placeholder="一行一个或逗号分隔"></textarea></label>
          </section>
          <div class="save"><button class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div>
        </main>
      </div>
      <div v-show="tab === 'monitor'" class="monitor">
        <div class="toolbar"><span>进行中 {{ activities.length }} 场</span><button @click="refresh">刷新</button></div>
        <div v-if="monitorLoading" class="muted">读取中…</div>
        <div v-else-if="!activities.length" class="empty">当前没有进行中的抽奖</div>
        <table v-else>
          <thead><tr><th>编号</th><th>群组</th><th>奖品</th><th>参与</th><th>名额</th><th>关键词</th><th>开奖</th><th></th></tr></thead>
          <tbody><tr v-for="a in activities" :key="a.key">
            <td>#{{ a.lottery_id }}</td><td>{{ a.chat_title }}</td><td>{{ a.prize }}</td>
            <td>{{ a.participants }}</td><td>{{ a.winner_count }}</td><td>{{ a.keyword }}</td><td>{{ a.draw_time }}</td>
            <td><button :disabled="operating" @click="operate('/draw', a)">开奖</button><button class="danger" :disabled="operating" @click="operate('/cancel', a)">取消</button></td>
          </tr></tbody>
        </table>
        <h3 v-if="history.length">最近记录</h3>
        <table v-if="history.length">
          <thead><tr><th>编号</th><th>群组</th><th>奖品</th><th>参与</th><th>中奖者</th><th>状态</th><th>时间</th></tr></thead>
          <tbody><tr v-for="h in history" :key="h.lottery_id + h.time">
            <td>#{{ h.lottery_id }}</td><td>{{ h.chat_title }}</td><td>{{ h.prize }}</td><td>{{ h.participants }}</td>
            <td>{{ h.winner_names || '—' }}</td><td>{{ h.status }}</td><td>{{ h.time }}</td>
          </tr></tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.root{display:flex;flex-direction:column;gap:14px;color:var(--text-primary,#e8ebf0);container-type:inline-size}.tabs{display:flex;gap:6px;border-bottom:1px solid var(--border-light,#2a2e3a)}button{padding:7px 12px;border:1px solid var(--border-light,#2a2e3a);border-radius:7px;background:var(--bg-card,#12141c);color:var(--text-secondary,#b9c0cc);cursor:pointer}.tabs button{border-width:0 0 2px;background:none;border-radius:0}.tabs .on,aside .on{color:var(--accent,#6ea8fe);border-color:var(--accent,#6ea8fe);background:var(--accent-dim,#1e3a5f)}.layout{display:flex;gap:16px;align-items:flex-start}aside{flex:0 0 140px;display:flex;flex-direction:column;gap:5px;padding:10px;border:1px solid var(--border-light,#2a2e3a);border-radius:10px;background:var(--bg-elevated,#1a1d27)}aside button{text-align:left;border:none;background:none}main{flex:1;min-width:0}.card{display:flex;flex-direction:column;gap:13px;padding:16px;border:1px solid var(--border-light,#2a2e3a);border-radius:10px;background:var(--bg-elevated,#1a1d27)}h3{margin:0 0 6px;font-size:15px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 18px}label{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--text-secondary,#b9c0cc)}label:not(.switch){flex-direction:column;align-items:stretch}input,textarea{box-sizing:border-box;width:100%;padding:8px 10px;border:1px solid var(--border-light,#2a2e3a);border-radius:6px;background:var(--bg-card,#12141c);color:var(--text-primary,#e8ebf0);font:inherit}textarea{resize:vertical}.switch input{width:auto}.tip,.muted{font-size:12px;color:var(--text-muted,#7a8291);line-height:1.6}.save{display:flex;justify-content:flex-end;margin-top:12px}.primary{color:var(--accent,#6ea8fe);border-color:var(--accent,#6ea8fe)}.monitor{display:flex;flex-direction:column;gap:14px}.toolbar{display:flex;justify-content:space-between;align-items:center}.empty{text-align:center;padding:48px;color:var(--text-muted,#7a8291)}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px;text-align:left;border-bottom:1px solid var(--border-light,#2a2e3a)}th{font-size:12px;color:var(--text-muted,#7a8291)}td button+button{margin-left:5px}.danger{color:#ff6b6b}.danger:hover{border-color:#ff6b6b}button:disabled{opacity:.5;cursor:not-allowed}@container(max-width:680px){.layout{flex-direction:column}aside{width:100%;box-sizing:border-box;flex-direction:row;flex-wrap:wrap;flex-basis:auto}.grid{grid-template-columns:1fr}.monitor{overflow:auto}}
</style>
