import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,vShow:_vShow,createTextVNode:_createTextVNode} = await importShared('vue');


const _hoisted_1 = { class: "rp" };
const _hoisted_2 = {
  key: 0,
  class: "muted"
};
const _hoisted_3 = { class: "tabs" };
const _hoisted_4 = { class: "layout" };
const _hoisted_5 = { class: "sidebar" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "detail" };
const _hoisted_8 = { class: "card" };
const _hoisted_9 = { class: "row switch" };
const _hoisted_10 = { class: "card" };
const _hoisted_11 = { class: "row" };
const _hoisted_12 = { class: "row" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = { class: "card" };
const _hoisted_15 = { class: "row" };
const _hoisted_16 = { class: "row switch" };
const _hoisted_17 = { class: "card" };
const _hoisted_18 = { class: "grid" };
const _hoisted_19 = { class: "row" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = { class: "row" };
const _hoisted_22 = { class: "row" };
const _hoisted_23 = { class: "card" };
const _hoisted_24 = { class: "row" };
const _hoisted_25 = { class: "row top" };
const _hoisted_26 = { class: "card" };
const _hoisted_27 = { class: "row top" };
const _hoisted_28 = { class: "savebar" };
const _hoisted_29 = ["disabled"];
const _hoisted_30 = { class: "pane" };
const _hoisted_31 = { class: "toolbar" };
const _hoisted_32 = { class: "muted" };
const _hoisted_33 = {
  key: 0,
  class: "muted"
};
const _hoisted_34 = {
  key: 0,
  class: "empty"
};
const _hoisted_35 = {
  key: 1,
  class: "tbl"
};
const _hoisted_36 = { class: "mono" };
const _hoisted_37 = { class: "muted" };
const _hoisted_38 = { class: "mono" };
const _hoisted_39 = ["disabled", "onClick"];
const _hoisted_40 = {
  key: 2,
  class: "hist"
};
const _hoisted_41 = { class: "hist-h" };
const _hoisted_42 = { class: "tbl" };
const _hoisted_43 = { class: "mono" };
const _hoisted_44 = { class: "muted" };
const _hoisted_45 = { style: {"color":"#6ee7a8"} };
const _hoisted_46 = { class: "muted" };

const {ref,reactive,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

// 发红包 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 红包监控（进行中活动、可手动结束、战绩历史）。
const props = __props;

const DEFAULTS = {
  enabled: true, create_word: '创建红包', status_word: '红包状态', end_word: '结束红包',
  code_length: 4, rotate_code: false,
  max_amount: 0, max_count: 0, activity_timeout_minutes: 30, end_delete_delay: 10,
  transfer_prefix: '+', congrats_text: '恭喜 {name} 抢到 {amount} 魔力！',
  blacklist_ids: '',
};

const GROUPS = [
  { key: 'main', label: '总开关' },
  { key: 'command', label: '命令' },
  { key: 'captcha', label: '验证码' },
  { key: 'limit', label: '限制' },
  { key: 'send', label: '发放与文案' },
  { key: 'block', label: '屏蔽' },
];

const tab = ref('settings');
const group = ref('main');
const loading = ref(true);
const saving = ref(false);
const cfg = reactive({ ...DEFAULTS });

// 红包监控
const activities = ref([]);
const history = ref([]);
const monLoading = ref(false);
const ending = ref('');

onMounted(async () => {
  try {
    const saved = await props.host.getConfig();
    Object.assign(cfg, DEFAULTS, saved || {});
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e));
  } finally {
    loading.value = false;
  }
});

async function save() {
  saving.value = true;
  try {
    await props.host.saveConfig({ ...cfg });
    props.host.toast.success('配置已保存');
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e));
  } finally {
    saving.value = false;
  }
}

// ── 监控 ──
async function loadMonitor() {
  monLoading.value = true;
  try {
    const a = await props.host.callApi('/activities');
    activities.value = a.items || [];
    const h = await props.host.callApi('/history');
    history.value = h.items || [];
  } catch (e) {
    props.host.toast.error('读取红包活动失败：' + (e.message || e));
  } finally {
    monLoading.value = false;
  }
}
async function endOne(item) {
  if (!confirm(`提前结束红包 #${item.rp_id}？剩余 ${item.remaining_count} 个未抢的将不再发放。`)) return
  ending.value = item.key;
  try {
    const r = await props.host.callApi('/end', { method: 'POST', body: { key: item.key } });
    if (r.ok) { props.host.toast.success(r.message || '已结束'); await loadMonitor(); }
    else props.host.toast.error(r.message || '结束失败');
  } catch (e) { props.host.toast.error('结束失败：' + (e.message || e)); }
  finally { ending.value = ''; }
}

function switchTab(t) {
  tab.value = t;
  if (t === 'monitor') loadMonitor();
}

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, "加载配置…"))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("button", {
              class: _normalizeClass(['tab', { on: tab.value === 'settings' }]),
              onClick: _cache[0] || (_cache[0] = $event => (switchTab('settings')))
            }, "⚙ 配置", 2),
            _createElementVNode("button", {
              class: _normalizeClass(['tab', { on: tab.value === 'monitor' }]),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('monitor')))
            }, "🧧 红包监控", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", _hoisted_5, [
              _cache[15] || (_cache[15] = _createElementVNode("div", { class: "side-title" }, "设置分组", -1)),
              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(GROUPS, (g) => {
                return _createElementVNode("button", {
                  key: g.key,
                  class: _normalizeClass(['side-item', { on: group.value === g.key }]),
                  onClick: $event => (group.value = g.key)
                }, [
                  _createElementVNode("span", null, _toDisplayString(g.label), 1)
                ], 10, _hoisted_6)
              }), 64))
            ]),
            _createElementVNode("div", _hoisted_7, [
              (group.value === 'main')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _cache[17] || (_cache[17] = _createElementVNode("h3", { class: "det-title" }, "总开关", -1)),
                    _createElementVNode("section", _hoisted_8, [
                      _createElementVNode("label", _hoisted_9, [
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.enabled) = $event)),
                          type: "checkbox"
                        }, null, 512), [
                          [_vModelCheckbox, cfg.enabled]
                        ]),
                        _cache[16] || (_cache[16] = _createElementVNode("span", null, "启用发红包（关闭后不响应发红包命令）", -1))
                      ])
                    ])
                  ], 64))
                : (group.value === 'command')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[22] || (_cache[22] = _createElementVNode("h3", { class: "det-title" }, "命令词", -1)),
                      _createElementVNode("section", _hoisted_10, [
                        _createElementVNode("label", _hoisted_11, [
                          _cache[18] || (_cache[18] = _createElementVNode("span", null, "创建命令词", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.create_word) = $event)),
                            class: "inp"
                          }, null, 512), [
                            [_vModelText, cfg.create_word]
                          ])
                        ]),
                        _cache[21] || (_cache[21] = _createElementVNode("p", { class: "tip" }, "格式 `创建命令词 总额 个数`（随机验证码），或 `创建命令词 总额 个数 自定义口令`（口令做前缀+随机防挂码，一起渲染成图片）。命令发出后自动秒删。", -1)),
                        _createElementVNode("label", _hoisted_12, [
                          _cache[19] || (_cache[19] = _createElementVNode("span", null, "查看状态词", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.status_word) = $event)),
                            class: "inp"
                          }, null, 512), [
                            [_vModelText, cfg.status_word]
                          ])
                        ]),
                        _createElementVNode("label", _hoisted_13, [
                          _cache[20] || (_cache[20] = _createElementVNode("span", null, "结束命令词", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.end_word) = $event)),
                            class: "inp"
                          }, null, 512), [
                            [_vModelText, cfg.end_word]
                          ])
                        ])
                      ])
                    ], 64))
                  : (group.value === 'captcha')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                        _cache[26] || (_cache[26] = _createElementVNode("h3", { class: "det-title" }, "验证码", -1)),
                        _createElementVNode("section", _hoisted_14, [
                          _createElementVNode("label", _hoisted_15, [
                            _cache[23] || (_cache[23] = _createElementVNode("span", null, "验证码位数", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.code_length) = $event)),
                              class: "inp sm",
                              type: "number",
                              min: "4",
                              max: "8"
                            }, null, 512), [
                              [
                                _vModelText,
                                cfg.code_length,
                                void 0,
                                { number: true }
                              ]
                            ]),
                            _cache[24] || (_cache[24] = _createElementVNode("span", { class: "hint" }, "4-8，去混淆字符集，不区分大小写", -1))
                          ]),
                          _createElementVNode("label", _hoisted_16, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.rotate_code) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.rotate_code]
                            ]),
                            _cache[25] || (_cache[25] = _createElementVNode("span", null, "每抢一个换验证码（旧码立即失效，防复制粘贴）", -1))
                          ])
                        ])
                      ], 64))
                    : (group.value === 'limit')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[35] || (_cache[35] = _createElementVNode("h3", { class: "det-title" }, "限制", -1)),
                          _createElementVNode("section", _hoisted_17, [
                            _createElementVNode("div", _hoisted_18, [
                              _createElementVNode("label", _hoisted_19, [
                                _cache[27] || (_cache[27] = _createElementVNode("span", null, "总额上限", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.max_amount) = $event)),
                                  class: "inp sm",
                                  type: "number",
                                  min: "0"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.max_amount,
                                    void 0,
                                    { number: true }
                                  ]
                                ]),
                                _cache[28] || (_cache[28] = _createElementVNode("span", { class: "hint" }, "魔力，0=不限", -1))
                              ]),
                              _createElementVNode("label", _hoisted_20, [
                                _cache[29] || (_cache[29] = _createElementVNode("span", null, "个数上限", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.max_count) = $event)),
                                  class: "inp sm",
                                  type: "number",
                                  min: "0"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.max_count,
                                    void 0,
                                    { number: true }
                                  ]
                                ]),
                                _cache[30] || (_cache[30] = _createElementVNode("span", { class: "hint" }, "0=不限", -1))
                              ]),
                              _createElementVNode("label", _hoisted_21, [
                                _cache[31] || (_cache[31] = _createElementVNode("span", null, "活动超时", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.activity_timeout_minutes) = $event)),
                                  class: "inp sm",
                                  type: "number",
                                  min: "1",
                                  max: "240"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.activity_timeout_minutes,
                                    void 0,
                                    { number: true }
                                  ]
                                ]),
                                _cache[32] || (_cache[32] = _createElementVNode("span", { class: "hint" }, "分钟，无人抢完则自动结算", -1))
                              ]),
                              _createElementVNode("label", _hoisted_22, [
                                _cache[33] || (_cache[33] = _createElementVNode("span", null, "结束后删消息", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.end_delete_delay) = $event)),
                                  class: "inp sm",
                                  type: "number",
                                  min: "0",
                                  max: "600"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.end_delete_delay,
                                    void 0,
                                    { number: true }
                                  ]
                                ]),
                                _cache[34] || (_cache[34] = _createElementVNode("span", { class: "hint" }, "秒，0=不删", -1))
                              ])
                            ])
                          ])
                        ], 64))
                      : (group.value === 'send')
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _cache[39] || (_cache[39] = _createElementVNode("h3", { class: "det-title" }, "发放与文案", -1)),
                            _createElementVNode("section", _hoisted_23, [
                              _createElementVNode("label", _hoisted_24, [
                                _cache[36] || (_cache[36] = _createElementVNode("span", null, "转账金额前缀", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.transfer_prefix) = $event)),
                                  class: "inp sm"
                                }, null, 512), [
                                  [_vModelText, cfg.transfer_prefix]
                                ]),
                                _cache[37] || (_cache[37] = _createElementVNode("span", { class: "hint" }, "群转账bot据此打款，默认 +", -1))
                              ]),
                              _createElementVNode("label", _hoisted_25, [
                                _cache[38] || (_cache[38] = _createElementVNode("span", null, "祝贺文案", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.congrats_text) = $event)),
                                  class: "inp",
                                  rows: "2",
                                  placeholder: "可用 {name} {amount} {id} 占位"
                                }, null, 512), [
                                  [_vModelText, cfg.congrats_text]
                                ])
                              ])
                            ])
                          ], 64))
                        : (group.value === 'block')
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
                              _cache[41] || (_cache[41] = _createElementVNode("h3", { class: "det-title" }, "屏蔽", -1)),
                              _createElementVNode("section", _hoisted_26, [
                                _createElementVNode("label", _hoisted_27, [
                                  _cache[40] || (_cache[40] = _createElementVNode("span", null, "屏蔽用户ID", -1)),
                                  _withDirectives(_createElementVNode("textarea", {
                                    "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.blacklist_ids) = $event)),
                                    class: "inp",
                                    rows: "3",
                                    placeholder: "一行一个或逗号分隔的用户ID，这些用户参与不计入、不发放"
                                  }, null, 512), [
                                    [_vModelText, cfg.blacklist_ids]
                                  ])
                                ])
                              ])
                            ], 64))
                          : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_28, [
                _createElementVNode("button", {
                  class: "btn primary lg",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_29)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_30, [
            _createElementVNode("div", _hoisted_31, [
              _createElementVNode("span", _hoisted_32, "进行中 " + _toDisplayString(activities.value.length) + " 个", 1),
              _cache[42] || (_cache[42] = _createElementVNode("span", { class: "grow" }, null, -1)),
              _createElementVNode("button", {
                class: "btn",
                onClick: loadMonitor
              }, "刷新")
            ]),
            (monLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_33, "加载中…"))
              : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  (!activities.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_34, [...(_cache[43] || (_cache[43] = [
                        _createTextVNode("当前没有进行中的红包", -1),
                        _createElementVNode("br", null, null, -1),
                        _createElementVNode("span", { class: "muted" }, "在群里用创建命令词发红包后会显示在这里", -1)
                      ]))]))
                    : (_openBlock(), _createElementBlock("table", _hoisted_35, [
                        _cache[44] || (_cache[44] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "编号"),
                            _createElementVNode("th", null, "群"),
                            _createElementVNode("th", null, "总额"),
                            _createElementVNode("th", null, "进度"),
                            _createElementVNode("th", null, "剩余金额"),
                            _createElementVNode("th", null, "已参与"),
                            _createElementVNode("th", null, "口令"),
                            _createElementVNode("th")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(activities.value, (a) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: a.key
                            }, [
                              _createElementVNode("td", _hoisted_36, "#" + _toDisplayString(a.rp_id), 1),
                              _createElementVNode("td", null, _toDisplayString(a.chat_title || a.chat_id), 1),
                              _createElementVNode("td", null, _toDisplayString(a.total_amount), 1),
                              _createElementVNode("td", null, _toDisplayString(a.packet_count - a.remaining_count) + "/" + _toDisplayString(a.packet_count), 1),
                              _createElementVNode("td", _hoisted_37, _toDisplayString(a.remaining_amount), 1),
                              _createElementVNode("td", null, _toDisplayString(a.participants), 1),
                              _createElementVNode("td", _hoisted_38, _toDisplayString(a.keyword), 1),
                              _createElementVNode("td", null, [
                                _createElementVNode("button", {
                                  class: "btn xs danger",
                                  disabled: ending.value,
                                  onClick: $event => (endOne(a))
                                }, _toDisplayString(ending.value === a.key ? '结束中…' : '结束'), 9, _hoisted_39)
                              ])
                            ]))
                          }), 128))
                        ])
                      ])),
                  (history.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_40, [
                        _createElementVNode("div", _hoisted_41, "红包战绩（最近 " + _toDisplayString(history.value.length) + " 条）", 1),
                        _createElementVNode("table", _hoisted_42, [
                          _cache[45] || (_cache[45] = _createElementVNode("thead", null, [
                            _createElementVNode("tr", null, [
                              _createElementVNode("th", null, "编号"),
                              _createElementVNode("th", null, "群"),
                              _createElementVNode("th", null, "总额"),
                              _createElementVNode("th", null, "个数"),
                              _createElementVNode("th", null, "参与"),
                              _createElementVNode("th", null, "发放"),
                              _createElementVNode("th", null, "时间")
                            ])
                          ], -1)),
                          _createElementVNode("tbody", null, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (h, i) => {
                              return (_openBlock(), _createElementBlock("tr", { key: i }, [
                                _createElementVNode("td", _hoisted_43, "#" + _toDisplayString(h.rp_id), 1),
                                _createElementVNode("td", _hoisted_44, _toDisplayString(h.chat_id), 1),
                                _createElementVNode("td", null, _toDisplayString(h.total_amount), 1),
                                _createElementVNode("td", null, _toDisplayString(h.packet_count), 1),
                                _createElementVNode("td", null, _toDisplayString(h.participants), 1),
                                _createElementVNode("td", _hoisted_45, _toDisplayString(h.distributed), 1),
                                _createElementVNode("td", _hoisted_46, _toDisplayString(h.time || '—'), 1)
                              ]))
                            }), 128))
                          ])
                        ])
                      ]))
                    : _createCommentVNode("", true)
                ], 64))
          ], 512), [
            [_vShow, tab.value === 'monitor']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c19ca658"]]);

export { Config as default };
