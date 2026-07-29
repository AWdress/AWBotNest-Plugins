import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,createTextVNode:_createTextVNode,vModelText:_vModelText,vShow:_vShow} = await importShared('vue');


const _hoisted_1 = { class: "root" };
const _hoisted_2 = {
  key: 0,
  class: "muted"
};
const _hoisted_3 = { class: "tabs" };
const _hoisted_4 = { class: "layout" };
const _hoisted_5 = ["onClick"];
const _hoisted_6 = {
  key: 0,
  class: "card"
};
const _hoisted_7 = { class: "switch" };
const _hoisted_8 = { class: "switch" };
const _hoisted_9 = { class: "grid" };
const _hoisted_10 = {
  key: 1,
  class: "card"
};
const _hoisted_11 = { class: "grid" };
const _hoisted_12 = { class: "switch" };
const _hoisted_13 = { class: "tip" };
const _hoisted_14 = {
  key: 2,
  class: "card"
};
const _hoisted_15 = { class: "switch" };
const _hoisted_16 = { class: "grid" };
const _hoisted_17 = {
  key: 3,
  class: "card"
};
const _hoisted_18 = { class: "switch" };
const _hoisted_19 = { class: "switch" };
const _hoisted_20 = {
  key: 4,
  class: "card"
};
const _hoisted_21 = { class: "grid" };
const _hoisted_22 = {
  key: 5,
  class: "card"
};
const _hoisted_23 = {
  key: 6,
  class: "card"
};
const _hoisted_24 = { class: "save" };
const _hoisted_25 = ["disabled"];
const _hoisted_26 = { class: "monitor" };
const _hoisted_27 = { class: "toolbar" };
const _hoisted_28 = {
  key: 0,
  class: "muted"
};
const _hoisted_29 = {
  key: 1,
  class: "empty"
};
const _hoisted_30 = { key: 2 };
const _hoisted_31 = ["disabled", "onClick"];
const _hoisted_32 = ["disabled", "onClick"];
const _hoisted_33 = { key: 3 };
const _hoisted_34 = { key: 4 };

const {onMounted,reactive,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

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
};
const groups = [
  ['basic', '基本设置'], ['commands', '群内命令'], ['award', '自动发奖'], ['rules', '参与规则'],
  ['human', '人形行为'], ['text', '发布文案'], ['block', '黑名单'],
];
const cfg = reactive({ ...DEFAULTS });
const tab = ref('settings');
const group = ref('basic');
const loading = ref(true);
const saving = ref(false);
const monitorLoading = ref(false);
const activities = ref([]);
const history = ref([]);
const operating = ref('');

onMounted(async () => {
  try { Object.assign(cfg, DEFAULTS, await props.host.getConfig() || {}); }
  catch (e) { props.host.toast.error('读取配置失败：' + (e.message || e)); }
  finally { loading.value = false; }
});
async function save() {
  saving.value = true;
  try { await props.host.saveConfig({ ...cfg }); props.host.toast.success('配置已保存'); }
  catch (e) { props.host.toast.error('保存失败：' + (e.message || e)); }
  finally { saving.value = false; }
}
async function refresh() {
  monitorLoading.value = true;
  try {
    activities.value = (await props.host.callApi('/activities')).items || [];
    history.value = (await props.host.callApi('/history')).items || [];
  } catch (e) { props.host.toast.error('读取活动失败：' + (e.message || e)); }
  finally { monitorLoading.value = false; }
}
async function operate(path, item) {
  const action = path === '/draw' ? '提前开奖' : '取消';
  if (!confirm(`${action}抽奖 #${item.lottery_id}？`)) return
  operating.value = item.key;
  try {
    const result = await props.host.callApi(path, { method: 'POST', body: { key: item.key } });
    result.ok ? props.host.toast.success(result.message || '操作成功') : props.host.toast.error(result.message || '操作失败');
    await refresh();
  } catch (e) { props.host.toast.error('操作失败：' + (e.message || e)); }
  finally { operating.value = ''; }
}
function switchTab(value) { tab.value = value; if (value === 'monitor') refresh(); }

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, "加载配置…"))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("button", {
              class: _normalizeClass({ on: tab.value === 'settings' }),
              onClick: _cache[0] || (_cache[0] = $event => (switchTab('settings')))
            }, "⚙ 配置", 2),
            _createElementVNode("button", {
              class: _normalizeClass({ on: tab.value === 'monitor' }),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('monitor')))
            }, "🎟 抽奖管理", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", null, [
              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(groups, (g) => {
                return _createElementVNode("button", {
                  key: g[0],
                  class: _normalizeClass({ on: group.value === g[0] }),
                  onClick: $event => (group.value = g[0])
                }, _toDisplayString(g[1]), 11, _hoisted_5)
              }), 64))
            ]),
            _createElementVNode("main", null, [
              (group.value === 'basic')
                ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                    _cache[38] || (_cache[38] = _createElementVNode("h3", null, "基本设置", -1)),
                    _createElementVNode("label", _hoisted_7, [
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.enabled) = $event)),
                        type: "checkbox"
                      }, null, 512), [
                        [_vModelCheckbox, cfg.enabled]
                      ]),
                      _cache[30] || (_cache[30] = _createTextVNode("启用幸运抽奖", -1))
                    ]),
                    _createElementVNode("label", _hoisted_8, [
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.notify_owner) = $event)),
                        type: "checkbox"
                      }, null, 512), [
                        [_vModelCheckbox, cfg.notify_owner]
                      ]),
                      _cache[31] || (_cache[31] = _createTextVNode("开奖结果通知我", -1))
                    ]),
                    _createElementVNode("div", _hoisted_9, [
                      _createElementVNode("label", null, [
                        _cache[32] || (_cache[32] = _createTextVNode("默认参与词", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.default_keyword) = $event))
                        }, null, 512), [
                          [_vModelText, cfg.default_keyword]
                        ])
                      ]),
                      _createElementVNode("label", null, [
                        _cache[33] || (_cache[33] = _createTextVNode("默认持续分钟", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.default_duration) = $event)),
                          type: "number",
                          min: "1"
                        }, null, 512), [
                          [
                            _vModelText,
                            cfg.default_duration,
                            void 0,
                            { number: true }
                          ]
                        ])
                      ]),
                      _createElementVNode("label", null, [
                        _cache[34] || (_cache[34] = _createTextVNode("默认中奖人数", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.default_winners) = $event)),
                          type: "number",
                          min: "1"
                        }, null, 512), [
                          [
                            _vModelText,
                            cfg.default_winners,
                            void 0,
                            { number: true }
                          ]
                        ])
                      ]),
                      _createElementVNode("label", null, [
                        _cache[35] || (_cache[35] = _createTextVNode("最低参与人数", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.min_participants) = $event)),
                          type: "number",
                          min: "1"
                        }, null, 512), [
                          [
                            _vModelText,
                            cfg.min_participants,
                            void 0,
                            { number: true }
                          ]
                        ])
                      ]),
                      _createElementVNode("label", null, [
                        _cache[36] || (_cache[36] = _createTextVNode("最长持续分钟", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.max_duration) = $event)),
                          type: "number",
                          min: "1"
                        }, null, 512), [
                          [
                            _vModelText,
                            cfg.max_duration,
                            void 0,
                            { number: true }
                          ]
                        ])
                      ]),
                      _createElementVNode("label", null, [
                        _cache[37] || (_cache[37] = _createTextVNode("最大中奖人数", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.max_winners) = $event)),
                          type: "number",
                          min: "1"
                        }, null, 512), [
                          [
                            _vModelText,
                            cfg.max_winners,
                            void 0,
                            { number: true }
                          ]
                        ])
                      ])
                    ])
                  ]))
                : (group.value === 'commands')
                  ? (_openBlock(), _createElementBlock("section", _hoisted_10, [
                      _cache[45] || (_cache[45] = _createElementVNode("h3", null, "群内命令", -1)),
                      _createElementVNode("div", _hoisted_11, [
                        _createElementVNode("label", null, [
                          _cache[39] || (_cache[39] = _createTextVNode("创建抽奖", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.create_word) = $event))
                          }, null, 512), [
                            [_vModelText, cfg.create_word]
                          ])
                        ]),
                        _createElementVNode("label", null, [
                          _cache[40] || (_cache[40] = _createTextVNode("查看状态", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.status_word) = $event))
                          }, null, 512), [
                            [_vModelText, cfg.status_word]
                          ])
                        ]),
                        _createElementVNode("label", null, [
                          _cache[41] || (_cache[41] = _createTextVNode("提前开奖", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.draw_word) = $event))
                          }, null, 512), [
                            [_vModelText, cfg.draw_word]
                          ])
                        ]),
                        _createElementVNode("label", null, [
                          _cache[42] || (_cache[42] = _createTextVNode("取消抽奖", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.cancel_word) = $event))
                          }, null, 512), [
                            [_vModelText, cfg.cancel_word]
                          ])
                        ])
                      ]),
                      _createElementVNode("label", _hoisted_12, [
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.delete_commands) = $event)),
                          type: "checkbox"
                        }, null, 512), [
                          [_vModelCheckbox, cfg.delete_commands]
                        ]),
                        _cache[43] || (_cache[43] = _createTextVNode("执行后删除我的命令消息", -1))
                      ]),
                      _createElementVNode("p", _hoisted_13, [
                        _createTextVNode("格式：" + _toDisplayString(cfg.create_word) + " 奖品 | 中奖人数 | 持续分钟 | 参与关键词 | 每人奖励", 1),
                        _cache[44] || (_cache[44] = _createElementVNode("br", null, null, -1)),
                        _createTextVNode("最后一项可省略，插件会从奖品名称提取数字。示例：" + _toDisplayString(cfg.create_word) + " 1000魔力 | 3 | 10 | 冲鸭", 1)
                      ])
                    ]))
                  : (group.value === 'award')
                    ? (_openBlock(), _createElementBlock("section", _hoisted_14, [
                        _cache[50] || (_cache[50] = _createElementVNode("h3", null, "自动发奖", -1)),
                        _createElementVNode("label", _hoisted_15, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.auto_award) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.auto_award]
                          ]),
                          _cache[46] || (_cache[46] = _createTextVNode("开奖后自动给中奖者发奖", -1))
                        ]),
                        _createElementVNode("label", null, [
                          _cache[47] || (_cache[47] = _createTextVNode("发奖命令模板", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.award_command) = $event)),
                            placeholder: "+{amount}"
                          }, null, 512), [
                            [_vModelText, cfg.award_command]
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_16, [
                          _createElementVNode("label", null, [
                            _cache[48] || (_cache[48] = _createTextVNode("逐人间隔最少秒", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.award_delay_min) = $event)),
                              type: "number",
                              min: "0",
                              step: ".5"
                            }, null, 512), [
                              [
                                _vModelText,
                                cfg.award_delay_min,
                                void 0,
                                { number: true }
                              ]
                            ])
                          ]),
                          _createElementVNode("label", null, [
                            _cache[49] || (_cache[49] = _createTextVNode("逐人间隔最多秒", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((cfg.award_delay_max) = $event)),
                              type: "number",
                              min: "0",
                              step: ".5"
                            }, null, 512), [
                              [
                                _vModelText,
                                cfg.award_delay_max,
                                void 0,
                                { number: true }
                              ]
                            ])
                          ])
                        ]),
                        _cache[51] || (_cache[51] = _createElementVNode("p", { class: "tip" }, "默认回复中奖者的参与消息发送“+金额”，供群转账 Bot 打款。模板可用 {amount} {prize} {lottery_id}。", -1))
                      ]))
                    : (group.value === 'rules')
                      ? (_openBlock(), _createElementBlock("section", _hoisted_17, [
                          _cache[55] || (_cache[55] = _createElementVNode("h3", null, "参与规则", -1)),
                          _createElementVNode("label", _hoisted_18, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((cfg.allow_creator) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.allow_creator]
                            ]),
                            _cache[52] || (_cache[52] = _createTextVNode("允许创建者参与", -1))
                          ]),
                          _createElementVNode("label", _hoisted_19, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((cfg.require_reply) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.require_reply]
                            ]),
                            _cache[53] || (_cache[53] = _createTextVNode("必须回复抽奖公告才计入", -1))
                          ]),
                          _createElementVNode("label", null, [
                            _cache[54] || (_cache[54] = _createTextVNode("每 N 人播报一次（0=关闭）", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((cfg.progress_every) = $event)),
                              type: "number",
                              min: "0"
                            }, null, 512), [
                              [
                                _vModelText,
                                cfg.progress_every,
                                void 0,
                                { number: true }
                              ]
                            ])
                          ])
                        ]))
                      : (group.value === 'human')
                        ? (_openBlock(), _createElementBlock("section", _hoisted_20, [
                            _cache[60] || (_cache[60] = _createElementVNode("h3", null, "人形随机延迟", -1)),
                            _createElementVNode("div", _hoisted_21, [
                              _createElementVNode("label", null, [
                                _cache[56] || (_cache[56] = _createTextVNode("发布最少秒", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((cfg.announce_delay_min) = $event)),
                                  type: "number",
                                  min: "0",
                                  step: ".5"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.announce_delay_min,
                                    void 0,
                                    { number: true }
                                  ]
                                ])
                              ]),
                              _createElementVNode("label", null, [
                                _cache[57] || (_cache[57] = _createTextVNode("发布最多秒", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((cfg.announce_delay_max) = $event)),
                                  type: "number",
                                  min: "0",
                                  step: ".5"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.announce_delay_max,
                                    void 0,
                                    { number: true }
                                  ]
                                ])
                              ]),
                              _createElementVNode("label", null, [
                                _cache[58] || (_cache[58] = _createTextVNode("开奖最少秒", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((cfg.draw_delay_min) = $event)),
                                  type: "number",
                                  min: "0",
                                  step: ".5"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.draw_delay_min,
                                    void 0,
                                    { number: true }
                                  ]
                                ])
                              ]),
                              _createElementVNode("label", null, [
                                _cache[59] || (_cache[59] = _createTextVNode("开奖最多秒", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((cfg.draw_delay_max) = $event)),
                                  type: "number",
                                  min: "0",
                                  step: ".5"
                                }, null, 512), [
                                  [
                                    _vModelText,
                                    cfg.draw_delay_max,
                                    void 0,
                                    { number: true }
                                  ]
                                ])
                              ])
                            ])
                          ]))
                        : (group.value === 'text')
                          ? (_openBlock(), _createElementBlock("section", _hoisted_22, [
                              _cache[64] || (_cache[64] = _createElementVNode("h3", null, "发布文案", -1)),
                              _createElementVNode("label", null, [
                                _cache[61] || (_cache[61] = _createTextVNode("抽奖公告", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((cfg.announce_template) = $event)),
                                  rows: "8"
                                }, null, 512), [
                                  [_vModelText, cfg.announce_template]
                                ])
                              ]),
                              _createElementVNode("label", null, [
                                _cache[62] || (_cache[62] = _createTextVNode("开奖文案", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((cfg.result_template) = $event)),
                                  rows: "8"
                                }, null, 512), [
                                  [_vModelText, cfg.result_template]
                                ])
                              ]),
                              _createElementVNode("label", null, [
                                _cache[63] || (_cache[63] = _createTextVNode("人数不足文案", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((cfg.empty_template) = $event)),
                                  rows: "3"
                                }, null, 512), [
                                  [_vModelText, cfg.empty_template]
                                ])
                              ]),
                              _cache[65] || (_cache[65] = _createElementVNode("p", { class: "tip" }, "公告可用 {prize} {winners} {keyword} {duration} {draw_time}；开奖可用 {prize} {participants} {winners} {winner_list}。", -1))
                            ]))
                          : (_openBlock(), _createElementBlock("section", _hoisted_23, [
                              _cache[67] || (_cache[67] = _createElementVNode("h3", null, "参与黑名单", -1)),
                              _createElementVNode("label", null, [
                                _cache[66] || (_cache[66] = _createTextVNode("用户 ID", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((cfg.blacklist_ids) = $event)),
                                  rows: "6",
                                  placeholder: "一行一个或逗号分隔"
                                }, null, 512), [
                                  [_vModelText, cfg.blacklist_ids]
                                ])
                              ])
                            ])),
              _createElementVNode("div", _hoisted_24, [
                _createElementVNode("button", {
                  class: "primary",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_25)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_26, [
            _createElementVNode("div", _hoisted_27, [
              _createElementVNode("span", null, "进行中 " + _toDisplayString(activities.value.length) + " 场", 1),
              _createElementVNode("button", { onClick: refresh }, "刷新")
            ]),
            (monitorLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_28, "读取中…"))
              : (!activities.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_29, "当前没有进行中的抽奖"))
                : (_openBlock(), _createElementBlock("table", _hoisted_30, [
                    _cache[68] || (_cache[68] = _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _createElementVNode("th", null, "编号"),
                        _createElementVNode("th", null, "群组"),
                        _createElementVNode("th", null, "奖品"),
                        _createElementVNode("th", null, "参与"),
                        _createElementVNode("th", null, "名额"),
                        _createElementVNode("th", null, "关键词"),
                        _createElementVNode("th", null, "开奖"),
                        _createElementVNode("th")
                      ])
                    ], -1)),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(activities.value, (a) => {
                        return (_openBlock(), _createElementBlock("tr", {
                          key: a.key
                        }, [
                          _createElementVNode("td", null, "#" + _toDisplayString(a.lottery_id), 1),
                          _createElementVNode("td", null, _toDisplayString(a.chat_title), 1),
                          _createElementVNode("td", null, _toDisplayString(a.prize), 1),
                          _createElementVNode("td", null, _toDisplayString(a.participants), 1),
                          _createElementVNode("td", null, _toDisplayString(a.winner_count), 1),
                          _createElementVNode("td", null, _toDisplayString(a.keyword), 1),
                          _createElementVNode("td", null, _toDisplayString(a.draw_time), 1),
                          _createElementVNode("td", null, [
                            _createElementVNode("button", {
                              disabled: operating.value,
                              onClick: $event => (operate('/draw', a))
                            }, "开奖", 8, _hoisted_31),
                            _createElementVNode("button", {
                              class: "danger",
                              disabled: operating.value,
                              onClick: $event => (operate('/cancel', a))
                            }, "取消", 8, _hoisted_32)
                          ])
                        ]))
                      }), 128))
                    ])
                  ])),
            (history.value.length)
              ? (_openBlock(), _createElementBlock("h3", _hoisted_33, "最近记录"))
              : _createCommentVNode("", true),
            (history.value.length)
              ? (_openBlock(), _createElementBlock("table", _hoisted_34, [
                  _cache[69] || (_cache[69] = _createElementVNode("thead", null, [
                    _createElementVNode("tr", null, [
                      _createElementVNode("th", null, "编号"),
                      _createElementVNode("th", null, "群组"),
                      _createElementVNode("th", null, "奖品"),
                      _createElementVNode("th", null, "参与"),
                      _createElementVNode("th", null, "中奖者"),
                      _createElementVNode("th", null, "状态"),
                      _createElementVNode("th", null, "时间")
                    ])
                  ], -1)),
                  _createElementVNode("tbody", null, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (h) => {
                      return (_openBlock(), _createElementBlock("tr", {
                        key: h.lottery_id + h.time
                      }, [
                        _createElementVNode("td", null, "#" + _toDisplayString(h.lottery_id), 1),
                        _createElementVNode("td", null, _toDisplayString(h.chat_title), 1),
                        _createElementVNode("td", null, _toDisplayString(h.prize), 1),
                        _createElementVNode("td", null, _toDisplayString(h.participants), 1),
                        _createElementVNode("td", null, _toDisplayString(h.winner_names || '—'), 1),
                        _createElementVNode("td", null, _toDisplayString(h.status), 1),
                        _createElementVNode("td", null, _toDisplayString(h.time), 1)
                      ]))
                    }), 128))
                  ])
                ]))
              : _createCommentVNode("", true)
          ], 512), [
            [_vShow, tab.value === 'monitor']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d7b3ce0f"]]);

export { Config as default };
