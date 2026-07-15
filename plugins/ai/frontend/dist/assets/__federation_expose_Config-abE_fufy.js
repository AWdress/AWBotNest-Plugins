import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,vModelText:_vModelText,withDirectives:_withDirectives,vModelCheckbox:_vModelCheckbox,vShow:_vShow,createTextVNode:_createTextVNode,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "ai" };
const _hoisted_2 = {
  key: 0,
  class: "muted"
};
const _hoisted_3 = { class: "tabs" };
const _hoisted_4 = { class: "layout" };
const _hoisted_5 = { class: "sidebar" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = {
  key: 0,
  class: "dot"
};
const _hoisted_8 = { class: "detail" };
const _hoisted_9 = { class: "card" };
const _hoisted_10 = { class: "row" };
const _hoisted_11 = { class: "row" };
const _hoisted_12 = { class: "row" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = ["disabled"];
const _hoisted_15 = { class: "card" };
const _hoisted_16 = { class: "row switch" };
const _hoisted_17 = { class: "row switch" };
const _hoisted_18 = {
  key: 0,
  class: "row top"
};
const _hoisted_19 = { class: "row top" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = { class: "card" };
const _hoisted_22 = { class: "row switch" };
const _hoisted_23 = { class: "row top" };
const _hoisted_24 = { class: "grid" };
const _hoisted_25 = { class: "row" };
const _hoisted_26 = { class: "row" };
const _hoisted_27 = { class: "card" };
const _hoisted_28 = { class: "row switch" };
const _hoisted_29 = { class: "row switch" };
const _hoisted_30 = {
  key: 0,
  class: "row top"
};
const _hoisted_31 = { class: "card" };
const _hoisted_32 = { class: "row top" };
const _hoisted_33 = { class: "savebar" };
const _hoisted_34 = ["disabled"];
const _hoisted_35 = { class: "pane" };
const _hoisted_36 = { class: "toolbar" };
const _hoisted_37 = { class: "muted" };
const _hoisted_38 = ["disabled"];
const _hoisted_39 = {
  key: 0,
  class: "muted"
};
const _hoisted_40 = {
  key: 1,
  class: "empty"
};
const _hoisted_41 = {
  key: 2,
  class: "mem-layout"
};
const _hoisted_42 = { class: "mem-list" };
const _hoisted_43 = ["onClick"];
const _hoisted_44 = { class: "mem-h" };
const _hoisted_45 = { class: "mem-type" };
const _hoisted_46 = { class: "mem-id" };
const _hoisted_47 = { class: "mem-last" };
const _hoisted_48 = { class: "mem-meta" };
const _hoisted_49 = ["onClick"];
const _hoisted_50 = { class: "mem-detail" };
const _hoisted_51 = {
  key: 0,
  class: "muted center"
};
const _hoisted_52 = {
  key: 1,
  class: "muted"
};
const _hoisted_53 = {
  key: 2,
  class: "chat"
};
const _hoisted_54 = { class: "bubble-role" };
const _hoisted_55 = { class: "bubble-text" };

const {ref,reactive,onMounted,computed} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

// AI 助手 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 对话记忆（查看、清空各会话历史）。
const props = __props;

const DEFAULTS = {
  api_key: '', base_url: '', model: 'gpt-3.5-turbo',
  enable_private_chat: true, enable_group_chat: true, group_chat_ids: '',
  system_prompt: (
    '# Role\n你是一个相处了很久的普通网友。\n\n' +
    '# Rules\n' +
    '1. 语气口语化、随性、接地气，就像在微信或QQ上聊天。\n' +
    '2. 每次回复必须精简，严禁长篇大论。\n' +
    '3. 绝对不能超过 20 个字。\n' +
    '4. 绝对不要在回复中模仿、复述或带入用户的动作动作。\n' +
    '5. 偶尔可以在句末加一个合适的 emoji（如 😂、🤷‍♂️、👀），不要过多。'
  ),
  max_history: 10,
  enable_proactive: false, proactive_chat_ids: '',
  proactive_min_minutes: 60, proactive_max_minutes: 180,
  enable_explain_command: true, enable_explain_prompt: false,
  explain_prompt: (
    '你是一个群聊消息解读助手。请根据用户【回复的消息内容】进行解释与答疑，简明清晰。\n' +
    '输出结构：\n1) 这句话/这段话的主要意思\n2) 语气/态度\n3) 可能的隐含信息（没有就写\'无\'）\n\n' +
    '需要解释的消息内容：{content}'
  ),
  white_list_chats: '',
};

const GROUPS = [
  { key: 'api', label: '接口' },
  { key: 'human', label: '人形回复', en: 'enable_private_chat' },
  { key: 'proactive', label: '主动搭话', en: 'enable_proactive' },
  { key: 'explain', label: '解释命令', en: 'enable_explain_command' },
  { key: 'scope', label: '范围' },
];

const tab = ref('settings');
const group = ref('api');
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const cfg = reactive({ ...DEFAULTS });

// 对话记忆
const histories = ref([]);
const proactiveNext = ref('');
const histLoading = ref(false);
const activeChat = ref(null);
const chatMessages = ref([]);
const msgLoading = ref(false);

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

async function testConn() {
  testing.value = true;
  try {
    const r = await props.host.callApi('/test', { method: 'POST', body: {} });
    if (r.ok) props.host.toast.success('连接正常 ✅ ' + (r.model || ''));
    else props.host.toast.error('连接失败：' + (r.message || '未知'));
  } catch (e) {
    props.host.toast.error('连接失败：' + (e.message || e));
  } finally {
    testing.value = false;
  }
}

// ── 对话记忆 ──
async function loadHistories() {
  histLoading.value = true;
  try {
    const r = await props.host.callApi('/histories');
    histories.value = r.items || [];
    proactiveNext.value = r.proactive_next || '';
  } catch (e) {
    props.host.toast.error('读取会话列表失败：' + (e.message || e));
  } finally {
    histLoading.value = false;
  }
}
async function openChat(h) {
  activeChat.value = h;
  msgLoading.value = true;
  chatMessages.value = [];
  try {
    const r = await props.host.callApi('/history?chat_id=' + encodeURIComponent(h.chat_id));
    chatMessages.value = r.messages || [];
  } catch (e) {
    props.host.toast.error('读取会话历史失败：' + (e.message || e));
  } finally {
    msgLoading.value = false;
  }
}
async function clearChat(h) {
  if (!confirm(`清空会话 ${h.chat_id} 的对话记忆？`)) return
  try {
    await props.host.callApi('/history/clear', { method: 'POST', body: { chat_id: h.chat_id } });
    histories.value = histories.value.filter(x => x.chat_id !== h.chat_id);
    if (activeChat.value && activeChat.value.chat_id === h.chat_id) {
      activeChat.value = null;
      chatMessages.value = [];
    }
    props.host.toast.success('已清空');
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)); }
}
async function clearAll() {
  if (!confirm('清空全部会话的对话记忆？')) return
  try {
    await props.host.callApi('/history/clear', { method: 'POST', body: { all: true } });
    histories.value = [];
    activeChat.value = null;
    chatMessages.value = [];
    props.host.toast.success('已清空全部');
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)); }
}

function switchTab(t) {
  tab.value = t;
  if (t === 'memory' && !histories.value.length) loadHistories();
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
              class: _normalizeClass(['tab', { on: tab.value === 'memory' }]),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('memory')))
            }, "💬 对话记忆", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", _hoisted_5, [
              _cache[18] || (_cache[18] = _createElementVNode("div", { class: "side-title" }, "设置分组", -1)),
              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(GROUPS, (g) => {
                return _createElementVNode("button", {
                  key: g.key,
                  class: _normalizeClass(['side-item', { on: group.value === g.key }]),
                  onClick: $event => (group.value = g.key)
                }, [
                  _createElementVNode("span", null, _toDisplayString(g.label), 1),
                  (g.en && cfg[g.en])
                    ? (_openBlock(), _createElementBlock("span", _hoisted_7))
                    : _createCommentVNode("", true)
                ], 10, _hoisted_6)
              }), 64))
            ]),
            _createElementVNode("div", _hoisted_8, [
              (group.value === 'api')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _cache[22] || (_cache[22] = _createElementVNode("h3", { class: "det-title" }, "OpenAI 兼容接口", -1)),
                    _createElementVNode("section", _hoisted_9, [
                      _createElementVNode("label", _hoisted_10, [
                        _cache[19] || (_cache[19] = _createElementVNode("span", null, "API Key", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.api_key) = $event)),
                          class: "inp",
                          type: "password",
                          placeholder: "接口密钥"
                        }, null, 512), [
                          [_vModelText, cfg.api_key]
                        ])
                      ]),
                      _createElementVNode("label", _hoisted_11, [
                        _cache[20] || (_cache[20] = _createElementVNode("span", null, "接口地址", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.base_url) = $event)),
                          class: "inp",
                          placeholder: "https://api.openai.com/v1（留空用官方默认）"
                        }, null, 512), [
                          [_vModelText, cfg.base_url]
                        ])
                      ]),
                      _createElementVNode("label", _hoisted_12, [
                        _cache[21] || (_cache[21] = _createElementVNode("span", null, "模型", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.model) = $event)),
                          class: "inp",
                          placeholder: "gpt-4o-mini / gpt-3.5-turbo 等"
                        }, null, 512), [
                          [_vModelText, cfg.model]
                        ])
                      ]),
                      _createElementVNode("div", _hoisted_13, [
                        _createElementVNode("button", {
                          class: "btn",
                          disabled: testing.value,
                          onClick: testConn
                        }, _toDisplayString(testing.value ? '测试中…' : '测试连接'), 9, _hoisted_14)
                      ])
                    ])
                  ], 64))
                : (group.value === 'human')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[29] || (_cache[29] = _createElementVNode("h3", { class: "det-title" }, "人形回复", -1)),
                      _createElementVNode("section", _hoisted_15, [
                        _createElementVNode("label", _hoisted_16, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.enable_private_chat) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.enable_private_chat]
                          ]),
                          _cache[23] || (_cache[23] = _createElementVNode("span", null, "私聊回复（私聊里直接对话）", -1))
                        ]),
                        _createElementVNode("label", _hoisted_17, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.enable_group_chat) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.enable_group_chat]
                          ]),
                          _cache[24] || (_cache[24] = _createElementVNode("span", null, "群聊回复（群里 @你 或回复你的消息时对话）", -1))
                        ]),
                        (cfg.enable_group_chat)
                          ? (_openBlock(), _createElementBlock("label", _hoisted_18, [
                              _cache[25] || (_cache[25] = _createElementVNode("span", null, "生效群组", -1)),
                              _withDirectives(_createElementVNode("textarea", {
                                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.group_chat_ids) = $event)),
                                class: "inp",
                                rows: "2",
                                placeholder: "群ID逗号分隔，留空=所有群"
                              }, null, 512), [
                                [_vModelText, cfg.group_chat_ids]
                              ])
                            ]))
                          : _createCommentVNode("", true),
                        _createElementVNode("label", _hoisted_19, [
                          _cache[26] || (_cache[26] = _createElementVNode("span", null, "人设", -1)),
                          _withDirectives(_createElementVNode("textarea", {
                            "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.system_prompt) = $event)),
                            class: "inp",
                            rows: "8",
                            placeholder: "系统提示词"
                          }, null, 512), [
                            [_vModelText, cfg.system_prompt]
                          ])
                        ]),
                        _createElementVNode("label", _hoisted_20, [
                          _cache[27] || (_cache[27] = _createElementVNode("span", null, "记忆轮数", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.max_history) = $event)),
                            class: "inp sm",
                            type: "number",
                            min: "0",
                            max: "40"
                          }, null, 512), [
                            [
                              _vModelText,
                              cfg.max_history,
                              void 0,
                              { number: true }
                            ]
                          ]),
                          _cache[28] || (_cache[28] = _createElementVNode("span", { class: "hint" }, "每会话保留多少条历史，0=不记忆", -1))
                        ])
                      ])
                    ], 64))
                  : (group.value === 'proactive')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                        _cache[37] || (_cache[37] = _createElementVNode("h3", { class: "det-title" }, "随机主动搭话", -1)),
                        _createElementVNode("section", _hoisted_21, [
                          _createElementVNode("label", _hoisted_22, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.enable_proactive) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.enable_proactive]
                            ]),
                            _cache[30] || (_cache[30] = _createElementVNode("span", null, "开启随机主动搭话", -1))
                          ]),
                          _cache[36] || (_cache[36] = _createElementVNode("p", { class: "tip" }, "在下方群组里每隔随机时间挑一条群友近期消息主动接话开启话题；群友回复你后走人形对话续聊（需「群聊回复」开着）。", -1)),
                          (cfg.enable_proactive)
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                _createElementVNode("label", _hoisted_23, [
                                  _cache[31] || (_cache[31] = _createElementVNode("span", null, "搭话群组", -1)),
                                  _withDirectives(_createElementVNode("textarea", {
                                    "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.proactive_chat_ids) = $event)),
                                    class: "inp",
                                    rows: "2",
                                    placeholder: "群ID逗号分隔，必填"
                                  }, null, 512), [
                                    [_vModelText, cfg.proactive_chat_ids]
                                  ])
                                ]),
                                _createElementVNode("div", _hoisted_24, [
                                  _createElementVNode("label", _hoisted_25, [
                                    _cache[32] || (_cache[32] = _createElementVNode("span", null, "间隔最小", -1)),
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.proactive_min_minutes) = $event)),
                                      class: "inp sm",
                                      type: "number",
                                      min: "5",
                                      max: "720"
                                    }, null, 512), [
                                      [
                                        _vModelText,
                                        cfg.proactive_min_minutes,
                                        void 0,
                                        { number: true }
                                      ]
                                    ]),
                                    _cache[33] || (_cache[33] = _createElementVNode("span", { class: "hint" }, "分钟", -1))
                                  ]),
                                  _createElementVNode("label", _hoisted_26, [
                                    _cache[34] || (_cache[34] = _createElementVNode("span", null, "间隔最大", -1)),
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.proactive_max_minutes) = $event)),
                                      class: "inp sm",
                                      type: "number",
                                      min: "5",
                                      max: "1440"
                                    }, null, 512), [
                                      [
                                        _vModelText,
                                        cfg.proactive_max_minutes,
                                        void 0,
                                        { number: true }
                                      ]
                                    ]),
                                    _cache[35] || (_cache[35] = _createElementVNode("span", { class: "hint" }, "分钟", -1))
                                  ])
                                ])
                              ], 64))
                            : _createCommentVNode("", true)
                        ])
                      ], 64))
                    : (group.value === 'explain')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[42] || (_cache[42] = _createElementVNode("h3", { class: "det-title" }, "/ai 解释命令", -1)),
                          _createElementVNode("section", _hoisted_27, [
                            _createElementVNode("label", _hoisted_28, [
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.enable_explain_command) = $event)),
                                type: "checkbox"
                              }, null, 512), [
                                [_vModelCheckbox, cfg.enable_explain_command]
                              ]),
                              _cache[38] || (_cache[38] = _createElementVNode("span", null, "启用 /ai 解释命令", -1))
                            ]),
                            _cache[41] || (_cache[41] = _createElementVNode("p", { class: "tip" }, "回复一条消息（或图片）再发 /ai，让 AI 解释/解答（单次，无记忆）。", -1)),
                            (cfg.enable_explain_command)
                              ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                  _createElementVNode("label", _hoisted_29, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.enable_explain_prompt) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.enable_explain_prompt]
                                    ]),
                                    _cache[39] || (_cache[39] = _createElementVNode("span", null, "用解释模板（否则直接把内容丢给 AI）", -1))
                                  ]),
                                  (cfg.enable_explain_prompt)
                                    ? (_openBlock(), _createElementBlock("label", _hoisted_30, [
                                        _cache[40] || (_cache[40] = _createElementVNode("span", null, "解释模板", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.explain_prompt) = $event)),
                                          class: "inp",
                                          rows: "6",
                                          placeholder: "用 {content} 占位被解释的内容"
                                        }, null, 512), [
                                          [_vModelText, cfg.explain_prompt]
                                        ])
                                      ]))
                                    : _createCommentVNode("", true)
                                ], 64))
                              : _createCommentVNode("", true)
                          ])
                        ], 64))
                      : (group.value === 'scope')
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _cache[44] || (_cache[44] = _createElementVNode("h3", { class: "det-title" }, "生效范围", -1)),
                            _createElementVNode("section", _hoisted_31, [
                              _createElementVNode("label", _hoisted_32, [
                                _cache[43] || (_cache[43] = _createElementVNode("span", null, "会话白名单", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.white_list_chats) = $event)),
                                  class: "inp",
                                  rows: "2",
                                  placeholder: "会话ID逗号分隔，留空=所有会话"
                                }, null, 512), [
                                  [_vModelText, cfg.white_list_chats]
                                ])
                              ])
                            ])
                          ], 64))
                        : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_33, [
                _createElementVNode("button", {
                  class: "btn primary lg",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_34)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_35, [
            _createElementVNode("div", _hoisted_36, [
              _createElementVNode("span", _hoisted_37, "下次主动搭话：" + _toDisplayString(proactiveNext.value || '—'), 1),
              _cache[45] || (_cache[45] = _createElementVNode("span", { class: "grow" }, null, -1)),
              _createElementVNode("button", {
                class: "btn",
                onClick: loadHistories
              }, "刷新"),
              _createElementVNode("button", {
                class: "btn danger",
                disabled: !histories.value.length,
                onClick: clearAll
              }, "全部清空", 8, _hoisted_38)
            ]),
            (histLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_39, "加载中…"))
              : (!histories.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_40, [...(_cache[46] || (_cache[46] = [
                    _createTextVNode("暂无对话记忆", -1),
                    _createElementVNode("br", null, null, -1),
                    _createElementVNode("span", { class: "muted" }, "私聊/群@你对话后会在这里记录会话记忆", -1)
                  ]))]))
                : (_openBlock(), _createElementBlock("div", _hoisted_41, [
                    _createElementVNode("div", _hoisted_42, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(histories.value, (h) => {
                        return (_openBlock(), _createElementBlock("button", {
                          key: h.chat_id,
                          class: _normalizeClass(['mem-item', { on: activeChat.value && activeChat.value.chat_id === h.chat_id }]),
                          onClick: $event => (openChat(h))
                        }, [
                          _createElementVNode("div", _hoisted_44, [
                            _createElementVNode("span", _hoisted_45, _toDisplayString(h.is_private ? '私聊' : '群'), 1),
                            _createElementVNode("span", _hoisted_46, _toDisplayString(h.chat_id), 1)
                          ]),
                          _createElementVNode("div", _hoisted_47, _toDisplayString(h.last || '—'), 1),
                          _createElementVNode("div", _hoisted_48, [
                            _createTextVNode(_toDisplayString(h.count) + " 条 · ", 1),
                            _createElementVNode("a", {
                              class: "lnk",
                              onClick: _withModifiers($event => (clearChat(h)), ["stop"])
                            }, "清空", 8, _hoisted_49)
                          ])
                        ], 10, _hoisted_43))
                      }), 128))
                    ]),
                    _createElementVNode("div", _hoisted_50, [
                      (!activeChat.value)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_51, "← 选择一个会话查看历史"))
                        : (msgLoading.value)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_52, "加载中…"))
                          : (_openBlock(), _createElementBlock("div", _hoisted_53, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(chatMessages.value, (m, i) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: i,
                                  class: _normalizeClass(['bubble', m.role])
                                }, [
                                  _createElementVNode("div", _hoisted_54, _toDisplayString(m.role === 'user' ? '对方' : '我'), 1),
                                  _createElementVNode("div", _hoisted_55, _toDisplayString(m.content), 1)
                                ], 2))
                              }), 128))
                            ]))
                    ])
                  ]))
          ], 512), [
            [_vShow, tab.value === 'memory']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c746a841"]]);

export { Config as default };
