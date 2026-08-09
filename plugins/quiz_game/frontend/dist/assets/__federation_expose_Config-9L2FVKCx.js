import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelText:_vModelText,withDirectives:_withDirectives,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createCommentVNode:_createCommentVNode,vModelSelect:_vModelSelect,vModelCheckbox:_vModelCheckbox} = await importShared('vue');


const _hoisted_1 = { class: "quiz-game-config" };
const _hoisted_2 = { class: "tabs" };
const _hoisted_3 = { class: "tab-content" };
const _hoisted_4 = {
  key: 0,
  class: "settings"
};
const _hoisted_5 = { class: "section" };
const _hoisted_6 = { class: "row" };
const _hoisted_7 = {
  key: 0,
  class: "chat-names"
};
const _hoisted_8 = { class: "section" };
const _hoisted_9 = { class: "row" };
const _hoisted_10 = {
  key: 0,
  class: "tip"
};
const _hoisted_11 = {
  key: 1,
  class: "row"
};
const _hoisted_12 = { class: "section" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = { class: "row switch" };
const _hoisted_15 = { class: "row indent" };
const _hoisted_16 = { class: "row indent" };
const _hoisted_17 = { class: "section" };
const _hoisted_18 = { class: "row" };
const _hoisted_19 = { class: "row" };
const _hoisted_20 = ["disabled"];
const _hoisted_21 = {
  key: 1,
  class: "history"
};
const _hoisted_22 = { class: "toolbar" };
const _hoisted_23 = { class: "muted" };
const _hoisted_24 = { class: "tbl" };
const _hoisted_25 = { class: "muted" };
const _hoisted_26 = { class: "gold" };
const _hoisted_27 = { key: 0 };

const {ref,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

const props = __props;
const cfg = ref({
  valid_groups: '', source: 'ai',
  ai_api_key: '', ai_base_url: '', ai_model: 'gpt-4o-mini',
  tianapi_key: '',
  base_reward: 500, streak_enabled: true, streak_multiplier: 1.5, max_streak: 5,
  timeout: 60, auto_delete_delay: 30,
});
const tab = ref('settings');
const saving = ref(false);
const history = ref([]);
const chatNames = ref([]);

onMounted(async () => {
  try {
    Object.assign(cfg.value, await props.host.getConfig() || {});
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e));
  }
  await Promise.all([loadHistory(), loadChatNames()]);
});

async function save() {
  saving.value = true;
  try {
    await props.host.saveConfig({ ...cfg.value });
    await loadChatNames();
    props.host.toast.success('配置已保存');
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e));
  } finally {
    saving.value = false;
  }
}

async function loadHistory() {
  try {
    const r = await props.host.callApi('/history');
    history.value = r.history || [];
  } catch (e) {
    props.host.toast.error('读取答题记录失败：' + (e.message || e));
  }
}

async function loadChatNames() {
  try {
    const r = await props.host.callApi('/chat_names');
    chatNames.value = r.items || [];
  } catch (e) {
    props.host.toast.error('读取群组名称失败：' + (e.message || e));
  }
}

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'settings' }),
        onClick: _cache[0] || (_cache[0] = $event => (tab.value = 'settings'))
      }, "⚙️ 设置", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'history' }),
        onClick: _cache[1] || (_cache[1] = $event => (tab.value = 'history'))
      }, "📝 答题记录", 2)
    ]),
    _createElementVNode("div", _hoisted_3, [
      (tab.value === 'settings')
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[13] || (_cache[13] = _createElementVNode("h3", null, "群组设置", -1)),
              _createElementVNode("label", _hoisted_6, [
                _cache[11] || (_cache[11] = _createElementVNode("span", null, "允许的群组", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.value.valid_groups) = $event)),
                  class: "inp",
                  placeholder: "留空=不限制，多个 ID 用逗号分隔"
                }, null, 512), [
                  [_vModelText, cfg.value.valid_groups]
                ])
              ]),
              (chatNames.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                    _cache[12] || (_cache[12] = _createElementVNode("span", { class: "chat-label" }, "已识别：", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(chatNames.value, (item) => {
                      return (_openBlock(), _createElementBlock("span", {
                        key: item.id,
                        class: "chat-name"
                      }, _toDisplayString(item.title) + " (" + _toDisplayString(item.id) + ")", 1))
                    }), 128))
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_8, [
              _cache[17] || (_cache[17] = _createElementVNode("h3", null, "出题源", -1)),
              _createElementVNode("label", _hoisted_9, [
                _cache[15] || (_cache[15] = _createElementVNode("span", null, "出题方式", -1)),
                _withDirectives(_createElementVNode("select", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.value.source) = $event)),
                  class: "inp"
                }, [...(_cache[14] || (_cache[14] = [
                  _createElementVNode("option", { value: "ai" }, "AI 模型", -1),
                  _createElementVNode("option", { value: "tianapi" }, "天行数据", -1)
                ]))], 512), [
                  [_vModelSelect, cfg.value.source]
                ])
              ]),
              (cfg.value.source === 'ai')
                ? (_openBlock(), _createElementBlock("p", _hoisted_10, "使用平台统一 AI 服务（在「系统设置→AI 服务」配置）。"))
                : _createCommentVNode("", true),
              (cfg.value.source === 'tianapi')
                ? (_openBlock(), _createElementBlock("label", _hoisted_11, [
                    _cache[16] || (_cache[16] = _createElementVNode("span", null, "天行数据 Key", -1)),
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.value.tianapi_key) = $event)),
                      type: "password",
                      class: "inp"
                    }, null, 512), [
                      [_vModelText, cfg.value.tianapi_key]
                    ])
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_12, [
              _cache[22] || (_cache[22] = _createElementVNode("h3", null, "奖励设置", -1)),
              _createElementVNode("label", _hoisted_13, [
                _cache[18] || (_cache[18] = _createElementVNode("span", null, "基础奖励(魔力)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.value.base_reward) = $event)),
                  type: "number",
                  class: "inp",
                  min: "1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.base_reward,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_14, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.streak_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.streak_enabled]
                ]),
                _cache[19] || (_cache[19] = _createElementVNode("span", null, "启用连胜加成", -1))
              ]),
              (cfg.value.streak_enabled)
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _createElementVNode("label", _hoisted_15, [
                      _cache[20] || (_cache[20] = _createElementVNode("span", null, "连胜倍率", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.streak_multiplier) = $event)),
                        type: "number",
                        class: "inp",
                        min: "1",
                        step: "0.1"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.streak_multiplier,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ]),
                    _createElementVNode("label", _hoisted_16, [
                      _cache[21] || (_cache[21] = _createElementVNode("span", null, "最大连胜", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.value.max_streak) = $event)),
                        type: "number",
                        class: "inp",
                        min: "1"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.max_streak,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ])
                  ], 64))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_17, [
              _cache[25] || (_cache[25] = _createElementVNode("h3", null, "答题规则", -1)),
              _createElementVNode("label", _hoisted_18, [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "答题超时(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.timeout) = $event)),
                  type: "number",
                  class: "inp",
                  min: "10"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.timeout,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_19, [
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "自动删除延迟(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.auto_delete_delay) = $event)),
                  type: "number",
                  class: "inp",
                  min: "0"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.auto_delete_delay,
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
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_20)
          ]))
        : (_openBlock(), _createElementBlock("div", _hoisted_21, [
            _createElementVNode("div", _hoisted_22, [
              _createElementVNode("button", {
                onClick: loadHistory,
                class: "btn-sm"
              }, "刷新"),
              _createElementVNode("span", _hoisted_23, "最近 " + _toDisplayString(history.value.length) + " 条", 1)
            ]),
            _createElementVNode("table", _hoisted_24, [
              _cache[27] || (_cache[27] = _createElementVNode("thead", null, [
                _createElementVNode("tr", null, [
                  _createElementVNode("th", null, "时间"),
                  _createElementVNode("th", null, "群组"),
                  _createElementVNode("th", null, "题目"),
                  _createElementVNode("th", null, "答案"),
                  _createElementVNode("th", null, "回答者"),
                  _createElementVNode("th", null, "奖励")
                ])
              ], -1)),
              _createElementVNode("tbody", null, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (h, i) => {
                  return (_openBlock(), _createElementBlock("tr", { key: i }, [
                    _createElementVNode("td", _hoisted_25, _toDisplayString(h.time), 1),
                    _createElementVNode("td", null, _toDisplayString(h.group), 1),
                    _createElementVNode("td", null, _toDisplayString(h.question), 1),
                    _createElementVNode("td", null, [
                      _createElementVNode("b", null, _toDisplayString(h.answer), 1)
                    ]),
                    _createElementVNode("td", null, _toDisplayString(h.player || '-'), 1),
                    _createElementVNode("td", _hoisted_26, _toDisplayString(h.reward || 0), 1)
                  ]))
                }), 128)),
                (!history.value.length)
                  ? (_openBlock(), _createElementBlock("tr", _hoisted_27, [...(_cache[26] || (_cache[26] = [
                      _createElementVNode("td", {
                        colspan: "6",
                        class: "empty"
                      }, "暂无答题记录", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-eb32992c"]]);

export { Config as default };
