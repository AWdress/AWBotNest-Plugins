import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelText:_vModelText,withDirectives:_withDirectives,vModelCheckbox:_vModelCheckbox,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,renderList:_renderList} = await importShared('vue');


const _hoisted_1 = { class: "bomb-game-config" };
const _hoisted_2 = { class: "tabs" };
const _hoisted_3 = { class: "tab-content" };
const _hoisted_4 = {
  key: 0,
  class: "settings"
};
const _hoisted_5 = { class: "section" };
const _hoisted_6 = { class: "row" };
const _hoisted_7 = { class: "row" };
const _hoisted_8 = { class: "section" };
const _hoisted_9 = { class: "row" };
const _hoisted_10 = { class: "row" };
const _hoisted_11 = { class: "row" };
const _hoisted_12 = { class: "section" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = { class: "row" };
const _hoisted_15 = { class: "row switch" };
const _hoisted_16 = { class: "row indent" };
const _hoisted_17 = { class: "row indent" };
const _hoisted_18 = { class: "row indent" };
const _hoisted_19 = { class: "row indent" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = { class: "section" };
const _hoisted_22 = { class: "row switch" };
const _hoisted_23 = {
  key: 0,
  class: "row"
};
const _hoisted_24 = {
  key: 1,
  class: "row"
};
const _hoisted_25 = { class: "section" };
const _hoisted_26 = { class: "row switch" };
const _hoisted_27 = {
  key: 0,
  class: "row"
};
const _hoisted_28 = ["disabled"];
const _hoisted_29 = {
  key: 1,
  class: "games"
};
const _hoisted_30 = { class: "toolbar" };
const _hoisted_31 = { class: "muted" };
const _hoisted_32 = { class: "tbl" };
const _hoisted_33 = { class: "muted" };
const _hoisted_34 = { class: "gold" };
const _hoisted_35 = { key: 0 };

const {ref,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { api: Object, config: Object },
  setup(__props) {

const props = __props;
const cfg = ref({
  valid_groups: '', monitor_disabled_groups: '', entry_fee: 888, pool_ratio: 50, wait_time: 30,
  default_min: 1, default_max: 100, enable_range_shrink: true,
  shrink_1_5: -10, shrink_6_15: -4, shrink_16_30: -2, shrink_31plus: 2, instant_win_permille: 5,
  auto_delete_enabled: true, auto_delete_delay: 30, no_delete_groups: '',
  require_transfer_confirm: false, transfer_bot_ids: '',
});
const tab = ref('settings');
const saving = ref(false);
const games = ref([]);

onMounted(() => {
  Object.assign(cfg.value, props.config || {});
  loadGames();
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

async function loadGames() {
  try {
    const r = await props.api.get('/games');
    games.value = r.games || [];
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
        class: _normalizeClass({ active: tab.value === 'games' }),
        onClick: _cache[1] || (_cache[1] = $event => (tab.value = 'games'))
      }, "🎮 游戏记录", 2)
    ]),
    _createElementVNode("div", _hoisted_3, [
      (tab.value === 'settings')
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[22] || (_cache[22] = _createElementVNode("h3", null, "群组设置", -1)),
              _createElementVNode("label", _hoisted_6, [
                _cache[20] || (_cache[20] = _createElementVNode("span", null, "允许的群组", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.value.valid_groups) = $event)),
                  class: "inp",
                  placeholder: "留空=不限制，多个 ID 用逗号分隔"
                }, null, 512), [
                  [_vModelText, cfg.value.valid_groups]
                ])
              ]),
              _createElementVNode("label", _hoisted_7, [
                _cache[21] || (_cache[21] = _createElementVNode("span", null, "临时停用的群", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.value.monitor_disabled_groups) = $event)),
                  class: "inp",
                  placeholder: "暂时禁止开启的群 ID"
                }, null, 512), [
                  [_vModelText, cfg.value.monitor_disabled_groups]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_8, [
              _cache[26] || (_cache[26] = _createElementVNode("h3", null, "奖池设置", -1)),
              _createElementVNode("label", _hoisted_9, [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "参与费用(魔力)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.value.entry_fee) = $event)),
                  type: "number",
                  class: "inp",
                  min: "1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.entry_fee,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_10, [
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "中奖者分成(%)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.value.pool_ratio) = $event)),
                  type: "number",
                  class: "inp",
                  min: "10",
                  max: "90"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.pool_ratio,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_11, [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "参与等待时间(秒)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.wait_time) = $event)),
                  type: "number",
                  class: "inp",
                  min: "5"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.wait_time,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_12, [
              _cache[35] || (_cache[35] = _createElementVNode("h3", null, "难度设置", -1)),
              _createElementVNode("label", _hoisted_13, [
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "初始范围下限", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.default_min) = $event)),
                  type: "number",
                  class: "inp"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.default_min,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_14, [
                _cache[28] || (_cache[28] = _createElementVNode("span", null, "初始范围上限", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.value.default_max) = $event)),
                  type: "number",
                  class: "inp"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.default_max,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", _hoisted_15, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.enable_range_shrink) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.enable_range_shrink]
                ]),
                _cache[29] || (_cache[29] = _createElementVNode("span", null, "按距离动态调整范围", -1))
              ]),
              (cfg.value.enable_range_shrink)
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _createElementVNode("label", _hoisted_16, [
                      _cache[30] || (_cache[30] = _createElementVNode("span", null, "距离1-5调整", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.shrink_1_5) = $event)),
                        type: "number",
                        class: "inp"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.shrink_1_5,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ]),
                    _createElementVNode("label", _hoisted_17, [
                      _cache[31] || (_cache[31] = _createElementVNode("span", null, "距离6-15调整", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.value.shrink_6_15) = $event)),
                        type: "number",
                        class: "inp"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.shrink_6_15,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ]),
                    _createElementVNode("label", _hoisted_18, [
                      _cache[32] || (_cache[32] = _createElementVNode("span", null, "距离16-30调整", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.value.shrink_16_30) = $event)),
                        type: "number",
                        class: "inp"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.shrink_16_30,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ]),
                    _createElementVNode("label", _hoisted_19, [
                      _cache[33] || (_cache[33] = _createElementVNode("span", null, "距离31+调整", -1)),
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.value.shrink_31plus) = $event)),
                        type: "number",
                        class: "inp"
                      }, null, 512), [
                        [
                          _vModelText,
                          cfg.value.shrink_31plus,
                          void 0,
                          { number: true }
                        ]
                      ])
                    ])
                  ], 64))
                : _createCommentVNode("", true),
              _createElementVNode("label", _hoisted_20, [
                _cache[34] || (_cache[34] = _createElementVNode("span", null, "一发命中概率(‰)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.value.instant_win_permille) = $event)),
                  type: "number",
                  class: "inp",
                  min: "0",
                  max: "50"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.instant_win_permille,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_21, [
              _cache[39] || (_cache[39] = _createElementVNode("h3", null, "消息设置", -1)),
              _createElementVNode("label", _hoisted_22, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.value.auto_delete_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.auto_delete_enabled]
                ]),
                _cache[36] || (_cache[36] = _createElementVNode("span", null, "自动删除游戏消息", -1))
              ]),
              (cfg.value.auto_delete_enabled)
                ? (_openBlock(), _createElementBlock("label", _hoisted_23, [
                    _cache[37] || (_cache[37] = _createElementVNode("span", null, "删除延迟(秒)", -1)),
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.value.auto_delete_delay) = $event)),
                      type: "number",
                      class: "inp",
                      min: "3"
                    }, null, 512), [
                      [
                        _vModelText,
                        cfg.value.auto_delete_delay,
                        void 0,
                        { number: true }
                      ]
                    ])
                  ]))
                : _createCommentVNode("", true),
              (cfg.value.auto_delete_enabled)
                ? (_openBlock(), _createElementBlock("label", _hoisted_24, [
                    _cache[38] || (_cache[38] = _createElementVNode("span", null, "不删除的群", -1)),
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.value.no_delete_groups) = $event)),
                      class: "inp",
                      placeholder: "群 ID，逗号分隔"
                    }, null, 512), [
                      [_vModelText, cfg.value.no_delete_groups]
                    ])
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_25, [
              _cache[42] || (_cache[42] = _createElementVNode("h3", null, "其他", -1)),
              _createElementVNode("label", _hoisted_26, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((cfg.value.require_transfer_confirm) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.require_transfer_confirm]
                ]),
                _cache[40] || (_cache[40] = _createElementVNode("span", null, "需转账bot确认才算参与", -1))
              ]),
              (cfg.value.require_transfer_confirm)
                ? (_openBlock(), _createElementBlock("label", _hoisted_27, [
                    _cache[41] || (_cache[41] = _createElementVNode("span", null, "转账bot ID", -1)),
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((cfg.value.transfer_bot_ids) = $event)),
                      class: "inp",
                      placeholder: "多个用逗号分隔"
                    }, null, 512), [
                      [_vModelText, cfg.value.transfer_bot_ids]
                    ])
                  ]))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("button", {
              onClick: save,
              class: "btn-primary",
              disabled: saving.value
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_28)
          ]))
        : (_openBlock(), _createElementBlock("div", _hoisted_29, [
            _createElementVNode("div", _hoisted_30, [
              _createElementVNode("button", {
                onClick: loadGames,
                class: "btn-sm"
              }, "刷新"),
              _createElementVNode("span", _hoisted_31, "最近 " + _toDisplayString(games.value.length) + " 场", 1)
            ]),
            _createElementVNode("table", _hoisted_32, [
              _cache[44] || (_cache[44] = _createElementVNode("thead", null, [
                _createElementVNode("tr", null, [
                  _createElementVNode("th", null, "时间"),
                  _createElementVNode("th", null, "群组"),
                  _createElementVNode("th", null, "参与人数"),
                  _createElementVNode("th", null, "奖池"),
                  _createElementVNode("th", null, "中奖者"),
                  _createElementVNode("th", null, "状态")
                ])
              ], -1)),
              _createElementVNode("tbody", null, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(games.value, (g, i) => {
                  return (_openBlock(), _createElementBlock("tr", { key: i }, [
                    _createElementVNode("td", _hoisted_33, _toDisplayString(g.time), 1),
                    _createElementVNode("td", null, _toDisplayString(g.group_name), 1),
                    _createElementVNode("td", null, _toDisplayString(g.players), 1),
                    _createElementVNode("td", _hoisted_34, _toDisplayString(g.pool), 1),
                    _createElementVNode("td", null, _toDisplayString(g.winner || '-'), 1),
                    _createElementVNode("td", null, [
                      _createElementVNode("span", {
                        class: _normalizeClass('status-' + g.status)
                      }, _toDisplayString(g.status), 3)
                    ])
                  ]))
                }), 128)),
                (!games.value.length)
                  ? (_openBlock(), _createElementBlock("tr", _hoisted_35, [...(_cache[43] || (_cache[43] = [
                      _createElementVNode("td", {
                        colspan: "6",
                        class: "empty"
                      }, "暂无游戏记录", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-06624f42"]]);

export { Config as default };
