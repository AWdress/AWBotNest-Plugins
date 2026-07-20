import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


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
const _hoisted_9 = { class: "section" };
const _hoisted_10 = { class: "row switch" };
const _hoisted_11 = {
  key: 0,
  class: "muted"
};
const _hoisted_12 = { class: "section" };
const _hoisted_13 = { class: "row switch" };
const _hoisted_14 = {
  key: 0,
  class: "row"
};
const _hoisted_15 = { class: "section" };
const _hoisted_16 = { class: "row" };
const _hoisted_17 = { class: "row" };
const _hoisted_18 = { class: "section" };
const _hoisted_19 = { class: "row" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = ["disabled"];
const _hoisted_22 = {
  key: 1,
  class: "status"
};
const _hoisted_23 = { class: "card" };
const _hoisted_24 = { class: "kv" };
const _hoisted_25 = { class: "kv" };
const _hoisted_26 = { class: "kv" };
const _hoisted_27 = { class: "kv" };
const _hoisted_28 = { class: "kv" };
const _hoisted_29 = {
  key: 2,
  class: "topics"
};
const _hoisted_30 = { class: "toolbar" };
const _hoisted_31 = { class: "muted" };
const _hoisted_32 = { class: "tbl" };
const _hoisted_33 = { class: "muted" };
const _hoisted_34 = { class: "muted" };
const _hoisted_35 = { class: "muted" };
const _hoisted_36 = { key: 0 };

const {ref,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { api: Object, config: Object },
  setup(__props) {

const props = __props;
const cfg = ref({
  enabled: false, bot_token: '', group_id: '',
  captcha_enabled: true,
  spam_enabled: true, spam_keywords: '',
  rate_limit_window: 10, rate_limit_count: 5,
  menu_auto_delete: 60, media_group_delay: 2.0,
});
const tab = ref('settings');
const saving = ref(false);
const status = ref({});
const topics = ref([]);

onMounted(() => {
  Object.assign(cfg.value, props.config || {});
  loadStatus();
  loadTopics();
  setInterval(loadStatus, 10000);
});

async function save() {
  saving.value = true;
  try {
    await props.api.post('/update_config', cfg.value);
    saving.value = false;
  } catch (e) {
    alert('保存失败：' + e.message);
    saving.value = false;
  }
}

async function loadStatus() {
  try {
    const r = await props.api.get('/status');
    status.value = r;
  } catch {}
}

async function loadTopics() {
  try {
    const r = await props.api.get('/topics');
    topics.value = r.topics || [];
  } catch {}
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
              _cache[16] || (_cache[16] = _createElementVNode("h3", null, "基本设置", -1)),
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
                _cache[14] || (_cache[14] = _createElementVNode("span", null, "Bot Token", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.value.bot_token) = $event)),
                  type: "password",
                  class: "inp",
                  placeholder: "从 @BotFather 获取"
                }, null, 512), [
                  [_vModelText, cfg.value.bot_token]
                ])
              ]),
              _createElementVNode("label", _hoisted_8, [
                _cache[15] || (_cache[15] = _createElementVNode("span", null, "话题群组 ID", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.value.group_id) = $event)),
                  class: "inp",
                  placeholder: "负数，如 -1001234567890"
                }, null, 512), [
                  [_vModelText, cfg.value.group_id]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_9, [
              _cache[18] || (_cache[18] = _createElementVNode("h3", null, "人机验证", -1)),
              _createElementVNode("label", _hoisted_10, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.captcha_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.captcha_enabled]
                ]),
                _cache[17] || (_cache[17] = _createElementVNode("span", null, "启用人机验证", -1))
              ]),
              (cfg.value.captcha_enabled)
                ? (_openBlock(), _createElementBlock("p", _hoisted_11, "插件会为每位待验证用户随机生成一道简单算术题。"))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_12, [
              _cache[21] || (_cache[21] = _createElementVNode("h3", null, "广告过滤", -1)),
              _createElementVNode("label", _hoisted_13, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.spam_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.spam_enabled]
                ]),
                _cache[19] || (_cache[19] = _createElementVNode("span", null, "启用广告过滤", -1))
              ]),
              (cfg.value.spam_enabled)
                ? (_openBlock(), _createElementBlock("label", _hoisted_14, [
                    _cache[20] || (_cache[20] = _createElementVNode("span", null, "关键词", -1)),
                    _withDirectives(_createElementVNode("textarea", {
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.value.spam_keywords) = $event)),
                      class: "inp",
                      rows: "3",
                      placeholder: "多个关键词用逗号分隔"
                    }, null, 512), [
                      [_vModelText, cfg.value.spam_keywords]
                    ])
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_15, [
              _cache[24] || (_cache[24] = _createElementVNode("h3", null, "限流设置", -1)),
              _createElementVNode("label", _hoisted_16, [
                _cache[22] || (_cache[22] = _createElementVNode("span", null, "时间窗口(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.rate_limit_window) = $event)),
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
              _createElementVNode("label", _hoisted_17, [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "窗口内最大消息数", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.rate_limit_count) = $event)),
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
            _createElementVNode("div", _hoisted_18, [
              _cache[27] || (_cache[27] = _createElementVNode("h3", null, "其他", -1)),
              _createElementVNode("label", _hoisted_19, [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "菜单自动删除(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.value.menu_auto_delete) = $event)),
                  type: "number",
                  class: "inp",
                  min: "10"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.menu_auto_delete,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_20, [
                _cache[26] || (_cache[26] = _createElementVNode("span", null, "媒体组聚合延迟(秒)", -1)),
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
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_21)
          ]))
        : (tab.value === 'status')
          ? (_openBlock(), _createElementBlock("div", _hoisted_22, [
              _createElementVNode("div", _hoisted_23, [
                _cache[33] || (_cache[33] = _createElementVNode("h3", null, "服务状态", -1)),
                _createElementVNode("div", _hoisted_24, [
                  _cache[28] || (_cache[28] = _createElementVNode("span", null, "Bot 状态", -1)),
                  _createElementVNode("b", {
                    class: _normalizeClass(status.value.bot_running ? 'ok' : 'err')
                  }, _toDisplayString(status.value.bot_status || '未运行'), 3)
                ]),
                _createElementVNode("div", _hoisted_25, [
                  _cache[29] || (_cache[29] = _createElementVNode("span", null, "话题群组", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.group_title || '-'), 1)
                ]),
                _createElementVNode("div", _hoisted_26, [
                  _cache[30] || (_cache[30] = _createElementVNode("span", null, "活跃用户数", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.active_users || 0), 1)
                ]),
                _createElementVNode("div", _hoisted_27, [
                  _cache[31] || (_cache[31] = _createElementVNode("span", null, "总话题数", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.total_topics || 0), 1)
                ]),
                _createElementVNode("div", _hoisted_28, [
                  _cache[32] || (_cache[32] = _createElementVNode("span", null, "黑名单用户", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.banned_users || 0), 1)
                ])
              ])
            ]))
          : (_openBlock(), _createElementBlock("div", _hoisted_29, [
              _createElementVNode("div", _hoisted_30, [
                _createElementVNode("button", {
                  onClick: loadTopics,
                  class: "btn-sm"
                }, "刷新"),
                _createElementVNode("span", _hoisted_31, "共 " + _toDisplayString(topics.value.length) + " 个话题", 1)
              ]),
              _createElementVNode("table", _hoisted_32, [
                _cache[35] || (_cache[35] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", null, "用户名"),
                    _createElementVNode("th", null, "用户 ID"),
                    _createElementVNode("th", null, "话题 ID"),
                    _createElementVNode("th", null, "最后活跃"),
                    _createElementVNode("th", null, "状态")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(topics.value, (t, i) => {
                    return (_openBlock(), _createElementBlock("tr", { key: i }, [
                      _createElementVNode("td", null, [
                        _createElementVNode("b", null, _toDisplayString(t.name), 1)
                      ]),
                      _createElementVNode("td", _hoisted_33, _toDisplayString(t.user_id), 1),
                      _createElementVNode("td", _hoisted_34, _toDisplayString(t.topic_id), 1),
                      _createElementVNode("td", _hoisted_35, _toDisplayString(t.last_active), 1),
                      _createElementVNode("td", null, [
                        _createElementVNode("span", {
                          class: _normalizeClass('status-' + t.status)
                        }, _toDisplayString(t.status), 3)
                      ])
                    ]))
                  }), 128)),
                  (!topics.value.length)
                    ? (_openBlock(), _createElementBlock("tr", _hoisted_36, [...(_cache[34] || (_cache[34] = [
                        _createElementVNode("td", {
                          colspan: "5",
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d37dd354"]]);

export { Config as default };
