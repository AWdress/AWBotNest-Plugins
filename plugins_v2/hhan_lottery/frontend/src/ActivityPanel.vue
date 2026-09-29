<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({ pluginId: String, host: { type: Object, required: true } })
const cfg = reactive({
  auto_grab_random_packet: false,
  auto_join_official_lottery: false,
  random_packet_delay_min: 1,
  random_packet_delay_max: 5,
})
const loading = ref(true)
const saving = ref(false)
const enabledCount = computed(() => Number(cfg.auto_grab_random_packet) + Number(cfg.auto_join_official_lottery))

async function save() {
  saving.value = true
  try {
    cfg.random_packet_delay_min = Math.max(0, Math.min(Number(cfg.random_packet_delay_min) || 0, 3600))
    cfg.random_packet_delay_max = Math.max(0, Math.min(Number(cfg.random_packet_delay_max) || 0, 3600))
    if (cfg.random_packet_delay_min > cfg.random_packet_delay_max) {
      ;[cfg.random_packet_delay_min, cfg.random_packet_delay_max] = [cfg.random_packet_delay_max, cfg.random_packet_delay_min]
    }
    await props.host.saveConfig({ ...cfg })
    props.host.toast.success('红包抽奖配置已保存')
  } catch (error) {
    props.host.toast.error('保存失败：' + (error.message || error))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    Object.assign(cfg, await props.host.getConfig() || {})
  } catch (error) {
    props.host.toast.error('读取配置失败：' + (error.message || error))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="activity-panel">
    <div v-if="loading" class="loading" role="status">正在读取配置…</div>
    <template v-else>
      <header>
        <div>
          <h2>抢红包与抽奖</h2>
          <p>自动识别 HHanClub 官方机器人发布的口令活动，并使用当前 Telegram 账号参与。</p>
        </div>
        <span class="status" :class="{ on: enabledCount > 0 }">{{ enabledCount ? `已启用 ${enabledCount} 项` : '全部关闭' }}</span>
      </header>

      <div class="layout">
        <section class="settings">
          <div class="section-head">
            <div><h3>自动参与</h3><p>两个功能相互独立，默认均为关闭。</p></div>
            <button class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存设置' }}</button>
          </div>

          <label class="switch-row">
            <span><b>自动抢红包</b><small>支持“普通红包”和“随机红包”，提取完整领取口令后发送</small></span>
            <input v-model="cfg.auto_grab_random_packet" type="checkbox" role="switch">
          </label>
          <label class="switch-row">
            <span><b>自动参加抽奖</b><small>只参加状态为“进行中”的抽奖，提取活动原始口令后发送</small></span>
            <input v-model="cfg.auto_join_official_lottery" type="checkbox" role="switch">
          </label>

          <div class="delay-fields">
            <label><span>最短等待</span><div><input v-model.number="cfg.random_packet_delay_min" type="number" min="0" max="3600" step="0.5"><em>秒</em></div></label>
            <label><span>最长等待</span><div><input v-model.number="cfg.random_packet_delay_max" type="number" min="0" max="3600" step="0.5"><em>秒</em></div></label>
          </div>
        </section>

        <aside class="guide">
          <h3>识别规则</h3>
          <ul>
            <li>仅接受官方机器人 8780479105 的直接消息或 Telegram 原生转发消息</li>
            <li>不会根据正文中的机器人名称判断，避免伪造活动误触发</li>
            <li>已领完、已过期红包和非进行中抽奖会自动跳过</li>
            <li>同一账号在同一群的同一活动只参与一次，消息编辑不会重复参与</li>
          </ul>
          <p class="note">等待时间同时用于红包和抽奖。设置为 0 可立即发送口令。</p>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.activity-panel { --line:#293a50; --muted:#9aacc2; color:#e9f0f9; font-family:"Microsoft YaHei",system-ui,sans-serif; }
.loading { padding:42px; text-align:center; color:var(--muted); }
header,.section-head,.switch-row { display:flex; align-items:center; justify-content:space-between; gap:18px; }
header { align-items:flex-start; margin-bottom:18px; }
h2 { margin:0 0 6px; color:#f5f8fc; font-size:25px; }
h3 { margin:0 0 5px; font-size:14px; }
header p,.section-head p { max-width:68ch; margin:0; color:var(--muted); font-size:13px; line-height:1.6; }
.status { flex:0 0 auto; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:#a9b8ca; background:#111c2b; font-size:12px; }
.status.on { border-color:#246b55; color:#78dfb6; background:#10251f; }
.layout { display:grid; grid-template-columns:minmax(360px,1.25fr) minmax(270px,.75fr); gap:14px; }
.settings,.guide { min-width:0; padding:19px; border:1px solid var(--line); border-radius:14px; background:#111c2b; }
button { min-height:38px; padding:0 14px; border:1px solid #287de7; border-radius:9px; color:#fff; background:#287de7; font:inherit; font-weight:650; cursor:pointer; }
button:hover:not(:disabled) { background:#3489ef; }
button:focus-visible,input:focus-visible { outline:2px solid #78b7ff; outline-offset:2px; }
button:disabled { opacity:.55; cursor:not-allowed; }
.switch-row { padding:16px 0; border-bottom:1px solid #223248; }
.switch-row span { display:grid; min-width:0; gap:4px; }
.switch-row b { font-size:13px; }
.switch-row small { color:var(--muted); line-height:1.5; overflow-wrap:anywhere; }
.switch-row input { flex:0 0 auto; }
.delay-fields { display:grid; grid-template-columns:1fr 1fr; gap:13px; margin-top:16px; }
.delay-fields label { display:grid; min-width:0; gap:7px; color:#b4c2d3; font-size:12px; }
.delay-fields label>div { display:flex; align-items:center; }
input[type=number] { width:100%; min-width:0; box-sizing:border-box; padding:9px 42px 9px 10px; border:1px solid #344861; border-radius:8px; color:#edf4fc; background:#0d1725; font:inherit; }
em { margin-left:-31px; color:#8294aa; font-style:normal; font-size:11px; pointer-events:none; }
.guide ul { padding-inline-start:19px; margin:15px 0; color:#a9b8ca; font-size:12px; line-height:1.85; }
.note { margin:0; padding:11px 12px; border-radius:9px; color:#9fc5f5; background:#0c1827; font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
@media(max-width:720px){ header{display:block}.status{display:inline-block;margin-top:12px}.layout{grid-template-columns:1fr}.section-head{align-items:flex-start}.section-head button{flex:0 0 auto}.delay-fields{grid-template-columns:1fr}input[type=number]{font-size:16px} }
</style>
