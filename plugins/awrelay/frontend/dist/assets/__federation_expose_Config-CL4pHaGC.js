import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelSelect:_vModelSelect,toDisplayString:_toDisplayString,vModelText:_vModelText,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "awrelay-config" };
const _hoisted_2 = { class: "tabs" };
const _hoisted_3 = { class: "tab-content" };
const _hoisted_4 = {
  key: 0,
  class: "settings"
};
const _hoisted_5 = { class: "section" };
const _hoisted_6 = { class: "row switch" };
const _hoisted_7 = { class: "row" };
const _hoisted_8 = { class: "row" };
const _hoisted_9 = ["placeholder"];
const _hoisted_10 = { class: "row" };
const _hoisted_11 = ["placeholder"];
const _hoisted_12 = { class: "section" };
const _hoisted_13 = { class: "row switch" };
const _hoisted_14 = {
  key: 0,
  class: "muted"
};
const _hoisted_15 = { class: "section" };
const _hoisted_16 = { class: "row switch" };
const _hoisted_17 = {
  key: 0,
  class: "row"
};
const _hoisted_18 = { class: "section" };
const _hoisted_19 = { class: "row" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = { class: "section" };
const _hoisted_22 = { class: "row" };
const _hoisted_23 = ["disabled"];
const _hoisted_24 = {
  key: 1,
  class: "status"
};
const _hoisted_25 = { class: "card" };
const _hoisted_26 = { class: "kv" };
const _hoisted_27 = { class: "kv" };
const _hoisted_28 = { class: "kv" };
const _hoisted_29 = { class: "kv" };
const _hoisted_30 = { class: "kv" };
const _hoisted_31 = { class: "kv" };
const _hoisted_32 = {
  key: 2,
  class: "topics"
};
const _hoisted_33 = { class: "toolbar" };
const _hoisted_34 = { class: "muted" };
const _hoisted_35 = { class: "tbl" };
const _hoisted_36 = { class: "muted" };
const _hoisted_37 = { class: "muted" };
const _hoisted_38 = { class: "muted" };
const _hoisted_39 = ["onClick"];
const _hoisted_40 = { key: 0 };

const {ref,onMounted,onUnmounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

const props = __props;
const cfg = ref({
  enabled: false, topic_mode: 'group', group_id: '', admin_ids: '',
  captcha_enabled: true,
  spam_enabled: true, spam_keywords: 'USDT,博彩,兼职,t.me/,http://,https://',
  rate_limit_window: 10, rate_limit_count: 5,
  media_group_delay: 2.0,
});
const tab = ref('settings');
const saving = ref(false);
const status = ref({});
const topics = ref([]);

let timer;
onMounted(async () => {
  try {
    Object.assign(cfg.value, await props.host.getConfig() || {});
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e));
  }
  await Promise.all([loadStatus(), loadTopics()]);
  timer = setInterval(loadStatus, 10000);
});
onUnmounted(() => clearInterval(timer));

async function save() {
  saving.value = true;
  try {
    await props.host.saveConfig({ ...cfg.value });
    props.host.toast.success('配置已保存');
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e));
  } finally {
    saving.value = false;
  }
}

async function loadStatus() {
  try {
    const r = await props.host.callApi('/status');
    status.value = r;
  } catch (e) { props.host.toast.error('读取状态失败：' + (e.message || e)); }
}

async function loadTopics() {
  try {
    const r = await props.host.callApi('/topics');
    topics.value = r.topics || [];
  } catch (e) { props.host.toast.error('读取话题失败：' + (e.message || e)); }
}

async function toggleBan(topic) {
  const banned = topic.status !== '已封禁';
  try {
    const result = await props.host.callApi('/ban', { method: 'POST', body: { user_id: topic.user_id, banned } });
    if (!result?.ok) throw new Error(result?.message || '后端未确认操作成功')
    topic.status = banned ? '已封禁' : '正常';
    await loadStatus();
    props.host.toast.success(banned ? '已拉黑用户' : '已解除黑名单');
  } catch (e) { props.host.toast.error('操作失败：' + (e.message || e)); }
}

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'settings' }),
        onClick: _cache[0] || (_cache[0] = $event => (tab.value = 'settings'))
      }, "⚙️ 设置", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'status' }),
        onClick: _cache[1] || (_cache[1] = $event => (tab.value = 'status'))
      }, "📊 运行状态", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'topics' }),
        onClick: _cache[2] || (_cache[2] = $event => (tab.value = 'topics'))
      }, "💬 话题列表", 2)
    ]),
    _createElementVNode("div", _hoisted_3, [
      (tab.value === 'settings')
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[17] || (_cache[17] = _createElementVNode("h3", null, "基本设置", -1)),
              _createElementVNode("label", _hoisted_6, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.value.enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.enabled]
                ]),
                _cache[13] || (_cache[13] = _createElementVNode("span", null, "启用 AWRelay", -1))
              ]),
              _createElementVNode("label", _hoisted_7, [
                _cache[15] || (_cache[15] = _createElementVNode("span", null, "话题模式", -1)),
                _withDirectives(_createElementVNode("select", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.value.topic_mode) = $event)),
                  class: "inp"
                }, [...(_cache[14] || (_cache[14] = [
                  _createElementVNode("option", { value: "group" }, "群组论坛话题", -1),
                  _createElementVNode("option", { value: "bot" }, "Bot 私聊话题", -1)
                ]))], 512), [
                  [_vModelSelect, cfg.value.topic_mode]
                ])
              ]),
              _createElementVNode("label", _hoisted_8, [
                _createElementVNode("span", null, _toDisplayString(cfg.value.topic_mode === 'bot' ? '管理员私聊 ID' : '话题群组 ID'), 1),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.value.group_id) = $event)),
                  class: "inp",
                  placeholder: cfg.value.topic_mode === 'bot' ? '管理员用户 ID，如 123456789' : '超级群组 ID，如 -1001234567890'
                }, null, 8, _hoisted_9), [
                  [_vModelText, cfg.value.group_id]
                ])
              ]),
              _createElementVNode("label", _hoisted_10, [
                _cache[16] || (_cache[16] = _createElementVNode("span", null, "管理员用户 ID", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.admin_ids) = $event)),
                  class: "inp",
                  placeholder: cfg.value.topic_mode === 'bot' ? '建议填写目标管理员 ID，多个用逗号分隔' : '留空允许群内成员，多个 ID 用逗号分隔'
                }, null, 8, _hoisted_11), [
                  [_vModelText, cfg.value.admin_ids]
                ])
              ]),
              _cache[18] || (_cache[18] = _createElementVNode("p", { class: "muted" }, "Bot 私聊模式需要先在 Telegram 中为该 Bot 开启话题，并让目标管理员与 Bot 建立私聊。", -1))
            ]),
            _createElementVNode("div", _hoisted_12, [
              _cache[20] || (_cache[20] = _createElementVNode("h3", null, "人机验证", -1)),
              _createElementVNode("label", _hoisted_13, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.captcha_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.captcha_enabled]
                ]),
                _cache[19] || (_cache[19] = _createElementVNode("span", null, "启用人机验证", -1))
              ]),
              (cfg.value.captcha_enabled)
                ? (_openBlock(), _createElementBlock("p", _hoisted_14, "插件会为每位待验证用户随机生成一道简单算术题。"))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_15, [
              _cache[23] || (_cache[23] = _createElementVNode("h3", null, "广告过滤", -1)),
              _createElementVNode("label", _hoisted_16, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.value.spam_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.spam_enabled]
                ]),
                _cache[21] || (_cache[21] = _createElementVNode("span", null, "启用广告过滤", -1))
              ]),
              (cfg.value.spam_enabled)
                ? (_openBlock(), _createElementBlock("label", _hoisted_17, [
                    _cache[22] || (_cache[22] = _createElementVNode("span", null, "关键词", -1)),
                    _withDirectives(_createElementVNode("textarea", {
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.spam_keywords) = $event)),
                      class: "inp",
                      rows: "3",
                      placeholder: "多个关键词用逗号分隔"
                    }, null, 512), [
                      [_vModelText, cfg.value.spam_keywords]
                    ])
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_18, [
              _cache[26] || (_cache[26] = _createElementVNode("h3", null, "限流设置", -1)),
              _createElementVNode("label", _hoisted_19, [
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "时间窗口(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.rate_limit_window) = $event)),
                  type: "number",
                  class: "inp",
                  min: "1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.rate_limit_window,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_20, [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "窗口内最大消息数", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.value.rate_limit_count) = $event)),
                  type: "number",
                  class: "inp",
                  min: "1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.rate_limit_count,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_21, [
              _cache[28] || (_cache[28] = _createElementVNode("h3", null, "其他", -1)),
              _createElementVNode("label", _hoisted_22, [
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "媒体组聚合延迟(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.value.media_group_delay) = $event)),
                  type: "number",
                  class: "inp",
                  min: "0",
                  step: "0.1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.media_group_delay,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ]),
            _createElementVNode("button", {
              onClick: save,
              class: "btn-primary",
              disabled: saving.value
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_23)
          ]))
        : (tab.value === 'status')
          ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
              _createElementVNode("div", _hoisted_25, [
                _cache[35] || (_cache[35] = _createElementVNode("h3", null, "服务状态", -1)),
                _createElementVNode("div", _hoisted_26, [
                  _cache[29] || (_cache[29] = _createElementVNode("span", null, "Bot 状态", -1)),
                  _createElementVNode("b", {
                    class: _normalizeClass(status.value.bot_running ? 'ok' : 'err')
                  }, _toDisplayString(status.value.bot_status || '未运行'), 3)
                ]),
                _createElementVNode("div", _hoisted_27, [
                  _cache[30] || (_cache[30] = _createElementVNode("span", null, "话题模式", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.topic_mode === 'bot' ? 'Bot 私聊话题' : '群组论坛话题'), 1)
                ]),
                _createElementVNode("div", _hoisted_28, [
                  _cache[31] || (_cache[31] = _createElementVNode("span", null, "目标会话", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.group_title || '-'), 1)
                ]),
                _createElementVNode("div", _hoisted_29, [
                  _cache[32] || (_cache[32] = _createElementVNode("span", null, "活跃用户数", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.active_users || 0), 1)
                ]),
                _createElementVNode("div", _hoisted_30, [
                  _cache[33] || (_cache[33] = _createElementVNode("span", null, "总话题数", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.total_topics || 0), 1)
                ]),
                _createElementVNode("div", _hoisted_31, [
                  _cache[34] || (_cache[34] = _createElementVNode("span", null, "黑名单用户", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.banned_users || 0), 1)
                ])
              ])
            ]))
          : (_openBlock(), _createElementBlock("div", _hoisted_32, [
              _createElementVNode("div", _hoisted_33, [
                _createElementVNode("button", {
                  onClick: loadTopics,
                  class: "btn-sm"
                }, "刷新"),
                _createElementVNode("span", _hoisted_34, "共 " + _toDisplayString(topics.value.length) + " 个话题", 1)
              ]),
              _createElementVNode("table", _hoisted_35, [
                _cache[37] || (_cache[37] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", null, "用户名"),
                    _createElementVNode("th", null, "用户 ID"),
                    _createElementVNode("th", null, "话题 ID"),
                    _createElementVNode("th", null, "最后活跃"),
                    _createElementVNode("th", null, "状态"),
                    _createElementVNode("th", null, "操作")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(topics.value, (t, i) => {
                    return (_openBlock(), _createElementBlock("tr", { key: i }, [
                      _createElementVNode("td", null, [
                        _createElementVNode("b", null, _toDisplayString(t.name), 1)
                      ]),
                      _createElementVNode("td", _hoisted_36, _toDisplayString(t.user_id), 1),
                      _createElementVNode("td", _hoisted_37, _toDisplayString(t.topic_id), 1),
                      _createElementVNode("td", _hoisted_38, _toDisplayString(t.last_active), 1),
                      _createElementVNode("td", null, [
                        _createElementVNode("span", {
                          class: _normalizeClass('status-' + t.status)
                        }, _toDisplayString(t.status), 3)
                      ]),
                      _createElementVNode("td", null, [
                        _createElementVNode("button", {
                          class: "btn-sm",
                          onClick: $event => (toggleBan(t))
                        }, _toDisplayString(t.status === '已封禁' ? '解除' : '拉黑'), 9, _hoisted_39)
                      ])
                    ]))
                  }), 128)),
                  (!topics.value.length)
                    ? (_openBlock(), _createElementBlock("tr", _hoisted_40, [...(_cache[36] || (_cache[36] = [
                        _createElementVNode("td", {
                          colspan: "6",
                          class: "empty"
                        }, "暂无话题", -1)
                      ]))]))
                    : _createCommentVNode("", true)
                ])
              ])
            ]))
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-24b536ab"]]);

export { Config as default };
