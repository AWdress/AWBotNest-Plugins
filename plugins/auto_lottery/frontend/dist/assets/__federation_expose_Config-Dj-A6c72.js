import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {vModelText:_vModelText$1,createElementVNode:_createElementVNode$1,withDirectives:_withDirectives$1,toDisplayString:_toDisplayString$1,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,createTextVNode:_createTextVNode$1,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1$1 = { class: "picker" };
const _hoisted_2$1 = { class: "picker-bar" };
const _hoisted_3$1 = { class: "cnt" };
const _hoisted_4$1 = { class: "picker-list" };
const _hoisted_5$1 = ["checked", "onChange"];
const _hoisted_6$1 = { class: "ptitle" };
const _hoisted_7$1 = { class: "pid" };
const _hoisted_8$1 = {
  key: 0,
  class: "pempty"
};
const _hoisted_9$1 = {
  key: 0,
  class: "extra"
};
const _hoisted_10$1 = ["onClick"];
const _hoisted_11$1 = { class: "manual" };

const {ref: ref$1,computed: computed$1} = await importShared('vue');



const _sfc_main$1 = {
  __name: 'ChatPicker',
  props: {
  modelValue: { type: Array, default: () => [] },
  dialogs: { type: Array, default: () => [] }, // [{id, title}]
},
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

// 群组选择器：从账号最近对话（/dialogs）里勾选群，值为群ID数组。
// Vue 模式没有平台内置 chat 选择器，故自带一个（含搜索 + 手动补 ID）。
const props = __props;
const emit = __emit;

const kw = ref$1('');
const manualId = ref$1('');

const selected = computed$1(() => (props.modelValue || []).map(Number));
const filtered = computed$1(() => {
  const k = kw.value.trim().toLowerCase();
  if (!k) return props.dialogs
  return props.dialogs.filter(d =>
    String(d.title || '').toLowerCase().includes(k) || String(d.id).includes(k))
});
// 已选但不在对话列表里的 ID（手动补的 / 已退群的）
const extra = computed$1(() => selected.value.filter(id => !props.dialogs.some(d => Number(d.id) === id)));

function toggle(id) {
  id = Number(id);
  const arr = selected.value.slice();
  const i = arr.indexOf(id);
  if (i >= 0) arr.splice(i, 1);
  else arr.push(id);
  emit('update:modelValue', arr);
}
function addManual() {
  const id = Number(String(manualId.value).trim());
  if (!id) return
  if (!selected.value.includes(id)) emit('update:modelValue', [...selected.value, id]);
  manualId.value = '';
}

return (_ctx, _cache) => {
  return (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
    _createElementVNode$1("div", _hoisted_2$1, [
      _withDirectives$1(_createElementVNode$1("input", {
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((kw).value = $event)),
        class: "pinp",
        placeholder: "搜索群名/ID…"
      }, null, 512), [
        [_vModelText$1, kw.value]
      ]),
      _createElementVNode$1("span", _hoisted_3$1, "已选 " + _toDisplayString$1(selected.value.length), 1)
    ]),
    _createElementVNode$1("div", _hoisted_4$1, [
      (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(filtered.value, (d) => {
        return (_openBlock$1(), _createElementBlock$1("label", {
          key: d.id,
          class: "pchip"
        }, [
          _createElementVNode$1("input", {
            type: "checkbox",
            checked: selected.value.includes(Number(d.id)),
            onChange: $event => (toggle(d.id))
          }, null, 40, _hoisted_5$1),
          _createElementVNode$1("span", _hoisted_6$1, _toDisplayString$1(d.title), 1),
          _createElementVNode$1("span", _hoisted_7$1, _toDisplayString$1(d.id), 1)
        ]))
      }), 128)),
      (!filtered.value.length)
        ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_8$1, "没有匹配的群（可下方手动补 ID）"))
        : _createCommentVNode$1("", true)
    ]),
    (extra.value.length)
      ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_9$1, [
          _cache[2] || (_cache[2] = _createElementVNode$1("span", { class: "extra-l" }, "列表外已选：", -1)),
          (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(extra.value, (id) => {
            return (_openBlock$1(), _createElementBlock$1("span", {
              key: id,
              class: "etag"
            }, [
              _createTextVNode$1(_toDisplayString$1(id), 1),
              _createElementVNode$1("a", {
                class: "ex",
                onClick: $event => (toggle(id))
              }, "×", 8, _hoisted_10$1)
            ]))
          }), 128))
        ]))
      : _createCommentVNode$1("", true),
    _createElementVNode$1("div", _hoisted_11$1, [
      _withDirectives$1(_createElementVNode$1("input", {
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((manualId).value = $event)),
        class: "pinp",
        placeholder: "手动补群ID（如 -1001234567890）",
        onKeyup: _withKeys(addManual, ["enter"])
      }, null, 544), [
        [_vModelText$1, manualId.value]
      ]),
      _createElementVNode$1("button", {
        class: "mbtn",
        type: "button",
        onClick: addManual
      }, "添加")
    ])
  ]))
}
}

};
const ChatPicker = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-5615b698"]]);

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,createVNode:_createVNode,vShow:_vShow,createTextVNode:_createTextVNode,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "al" };
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
const _hoisted_10 = { class: "row switch" };
const _hoisted_11 = { class: "grid" };
const _hoisted_12 = { class: "row" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = { class: "row" };
const _hoisted_15 = { class: "fld" };
const _hoisted_16 = { class: "fld" };
const _hoisted_17 = { class: "card" };
const _hoisted_18 = { class: "row switch" };
const _hoisted_19 = { class: "row switch" };
const _hoisted_20 = { class: "card" };
const _hoisted_21 = { class: "row top" };
const _hoisted_22 = { class: "row switch" };
const _hoisted_23 = { class: "row switch" };
const _hoisted_24 = { class: "card" };
const _hoisted_25 = { class: "row switch" };
const _hoisted_26 = { class: "row switch" };
const _hoisted_27 = { class: "row switch" };
const _hoisted_28 = {
  key: 0,
  class: "row top"
};
const _hoisted_29 = { class: "row switch" };
const _hoisted_30 = {
  key: 1,
  class: "row top"
};
const _hoisted_31 = { class: "row switch" };
const _hoisted_32 = {
  key: 2,
  class: "row"
};
const _hoisted_33 = { class: "card" };
const _hoisted_34 = { class: "row switch" };
const _hoisted_35 = { class: "grid" };
const _hoisted_36 = { class: "row" };
const _hoisted_37 = { class: "row" };
const _hoisted_38 = { class: "row" };
const _hoisted_39 = { class: "row" };
const _hoisted_40 = { class: "row" };
const _hoisted_41 = { class: "row" };
const _hoisted_42 = { class: "row" };
const _hoisted_43 = { class: "row" };
const _hoisted_44 = { class: "row top" };
const _hoisted_45 = { class: "card" };
const _hoisted_46 = { class: "row switch" };
const _hoisted_47 = {
  key: 0,
  class: "row top"
};
const _hoisted_48 = { class: "row switch" };
const _hoisted_49 = {
  key: 1,
  class: "fld"
};
const _hoisted_50 = { class: "row switch" };
const _hoisted_51 = {
  key: 2,
  class: "row top"
};
const _hoisted_52 = { class: "card" };
const _hoisted_53 = { class: "row switch" };
const _hoisted_54 = {
  key: 0,
  class: "row top"
};
const _hoisted_55 = { class: "card" };
const _hoisted_56 = { class: "row switch" };
const _hoisted_57 = { class: "row switch" };
const _hoisted_58 = { class: "row switch" };
const _hoisted_59 = {
  key: 0,
  class: "grid"
};
const _hoisted_60 = { class: "row" };
const _hoisted_61 = { class: "row" };
const _hoisted_62 = { class: "row top" };
const _hoisted_63 = { class: "card" };
const _hoisted_64 = { class: "row switch" };
const _hoisted_65 = {
  key: 0,
  class: "row switch"
};
const _hoisted_66 = { class: "savebar" };
const _hoisted_67 = ["disabled"];
const _hoisted_68 = { class: "pane" };
const _hoisted_69 = { class: "toolbar" };
const _hoisted_70 = { class: "muted" };
const _hoisted_71 = ["disabled"];
const _hoisted_72 = ["disabled"];
const _hoisted_73 = {
  key: 0,
  class: "muted"
};
const _hoisted_74 = {
  key: 0,
  class: "empty"
};
const _hoisted_75 = {
  key: 1,
  class: "tbl"
};
const _hoisted_76 = { class: "mono" };
const _hoisted_77 = { class: "muted" };
const _hoisted_78 = { class: "muted" };
const _hoisted_79 = ["disabled", "onClick"];
const _hoisted_80 = {
  key: 2,
  class: "hist"
};
const _hoisted_81 = { class: "hist-h" };
const _hoisted_82 = { class: "tbl" };
const _hoisted_83 = { class: "mono" };
const _hoisted_84 = { style: {"color":"#6ee7a8"} };
const _hoisted_85 = { class: "muted" };

const {ref,reactive,onMounted,computed} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

// 小菜抽奖 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧分组 + 右侧明细）/ 待发奖（列出待发奖、手动发奖、清空、发奖历史）。
const props = __props;

const DEFAULTS = {
  auto_lottery_enabled: false, lottery_bot_id: '6461022460', auto_lottery_username: '',
  auto_lottery_time: '', lottery_target_groups: [], custom_lottery_groups: [],
  lottery_forward_enabled: false, lottery_forward_first_participant: false,
  prize_list: '', universal_prize_match: false, prize_case_sensitive: false,
  trap_enabled: true, trap_case_sensitive: false, trap_enable_prize_pattern_check: true,
  trap_enable_creator_blacklist: true, trap_enable_participant_check: true,
  trap_max_participants: 1, trap_blacklist_creator_ids: '',
  trap_suspicious_keywords: '脚本,挂机,机器人,外挂,bot,自动,作弊,刷,假人,封禁,封,禁,ban,封号,script,auto,cheat,hack,fake,test,腳本,掛機,機器人,外掛,自動,封號',
  lottery_wait_enabled: false, lottery_participate_wait_min: 25, lottery_participate_wait_max: 65,
  lottery_thank_wait_min: 10, lottery_thank_wait_max: 45, lottery_heimu_wait_min: 20, lottery_heimu_wait_max: 40,
  lottery_negative_wait_min: 10, lottery_negative_wait_max: 60, group_wait_overrides: '',
  lottery_thank_message: false, thank_texts: '感谢{boss}大佬\n{boss}爷，谢谢\n感谢老板，小弟在这',
  username_reply_switch: false, transfer_groups: [],
  lottery_heimu_message: false, heimu_texts: '黑幕\n这也能不中\n下次一定',
  lose_reply_switch: false, negative_texts: '怎么可能啊\n别开玩笑啊\n啊绝对不是\n我是真的\n不要黑我\n？',
  auto_prize_enabled: false, manual_prize_mode: false, prize_send_interval_enabled: true,
  prize_send_interval_min: 2, prize_send_interval_max: 5, prize_send_blacklist: '',
  notify_owner: true, notify_skips: false,
};

const GROUPS = [
  { key: 'lottery', label: '自动抽奖', en: 'auto_lottery_enabled' },
  { key: 'participate', label: '参与方式' },
  { key: 'prize', label: '奖品匹配' },
  { key: 'trap', label: '陷阱检测', en: 'trap_enabled' },
  { key: 'wait', label: '等待时间', en: 'lottery_wait_enabled' },
  { key: 'react', label: '中奖回应' },
  { key: 'negative', label: '负面回复', en: 'lose_reply_switch' },
  { key: 'send', label: '自动发奖', en: 'auto_prize_enabled' },
  { key: 'notify', label: '通知', en: 'notify_owner' },
];

const tab = ref('settings');
const group = ref('lottery');
const loading = ref(true);
const saving = ref(false);
const cfg = reactive({ ...DEFAULTS });
const dialogs = ref([]);

// 待发奖
const pending = ref([]);
const prizeHistory = ref([]);
const pendingLoading = ref(false);
const sending = ref('');

onMounted(async () => {
  try {
    const saved = await props.host.getConfig();
    Object.assign(cfg, DEFAULTS, saved || {});
    // 归一化数组字段（老配置可能是逗号字符串）
    for (const k of ['lottery_target_groups', 'custom_lottery_groups', 'transfer_groups']) {
      if (!Array.isArray(cfg[k])) {
        cfg[k] = String(cfg[k] || '').split(',').map(s => Number(s.trim())).filter(Boolean);
      }
    }
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e));
  } finally {
    loading.value = false;
  }
  try {
    const r = await props.host.callApi('/dialogs');
    dialogs.value = r.items || [];
  } catch (e) { /* 群列表拉取失败不致命，可手动补ID */ }
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

// ── 待发奖 ──
async function loadPending() {
  pendingLoading.value = true;
  try {
    const r = await props.host.callApi('/pending');
    pending.value = r.items || [];
    const h = await props.host.callApi('/history');
    prizeHistory.value = h.items || [];
  } catch (e) {
    props.host.toast.error('读取待发奖失败：' + (e.message || e));
  } finally {
    pendingLoading.value = false;
  }
}
// 发奖在后端是后台任务（避免长耗时超时），返回 started 后延迟刷新待发奖列表。
async function doSend(body, tag) {
  sending.value = tag;
  try {
    const r = await props.host.callApi('/send', { method: 'POST', body });
    if (r.ok) {
      props.host.toast.success(r.message || '已开始发奖');
      setTimeout(loadPending, 6000);
    } else {
      props.host.toast.error(r.message || '发奖失败');
    }
  } catch (e) { props.host.toast.error('发奖失败：' + (e.message || e)); }
  finally { sending.value = ''; }
}
async function sendOne(item) {
  if (!confirm(`给抽奖 ${item.lottery_id.slice(0, 8)} 的 ${item.winners} 位中奖者发奖？`)) return
  await doSend({ lottery_id: item.lottery_id }, item.lottery_id);
}
async function sendAll() {
  if (!pending.value.length) return
  if (!confirm(`给全部 ${pending.value.length} 个待发奖发奖？`)) return
  await doSend({ all: true }, 'all');
}
async function clearPending() {
  if (!confirm('清空待发奖列表？(不影响已发出的奖)')) return
  try {
    await props.host.callApi('/clear', { method: 'POST', body: {} });
    pending.value = [];
    props.host.toast.success('已清空');
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)); }
}

function switchTab(t) {
  tab.value = t;
  if (t === 'prize' && !pending.value.length && !prizeHistory.value.length) loadPending();
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
              class: _normalizeClass(['tab', { on: tab.value === 'prize' }]),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('prize')))
            }, "🎁 待发奖", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", _hoisted_5, [
              _cache[47] || (_cache[47] = _createElementVNode("div", { class: "side-title" }, "设置分组", -1)),
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
              (group.value === 'lottery')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _cache[55] || (_cache[55] = _createElementVNode("h3", { class: "det-title" }, "自动抽奖", -1)),
                    _createElementVNode("section", _hoisted_9, [
                      _createElementVNode("label", _hoisted_10, [
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.auto_lottery_enabled) = $event)),
                          type: "checkbox"
                        }, null, 512), [
                          [_vModelCheckbox, cfg.auto_lottery_enabled]
                        ]),
                        _cache[48] || (_cache[48] = _createElementVNode("span", null, "自动抽奖总开关", -1))
                      ]),
                      (cfg.auto_lottery_enabled)
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                            _createElementVNode("div", _hoisted_11, [
                              _createElementVNode("label", _hoisted_12, [
                                _cache[49] || (_cache[49] = _createElementVNode("span", null, "抽奖机器人ID", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.lottery_bot_id) = $event)),
                                  class: "inp"
                                }, null, 512), [
                                  [_vModelText, cfg.lottery_bot_id]
                                ])
                              ]),
                              _createElementVNode("label", _hoisted_13, [
                                _cache[50] || (_cache[50] = _createElementVNode("span", null, "PT用户名", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.auto_lottery_username) = $event)),
                                  class: "inp",
                                  placeholder: "如 AWdress"
                                }, null, 512), [
                                  [_vModelText, cfg.auto_lottery_username]
                                ])
                              ])
                            ]),
                            _createElementVNode("label", _hoisted_14, [
                              _cache[51] || (_cache[51] = _createElementVNode("span", null, "抽奖时间段", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.auto_lottery_time) = $event)),
                                class: "inp",
                                placeholder: "08:00-11:00,20:00-23:00，留空=全天"
                              }, null, 512), [
                                [_vModelText, cfg.auto_lottery_time]
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_15, [
                              _cache[52] || (_cache[52] = _createElementVNode("span", { class: "lbl" }, "预定义抽奖群组", -1)),
                              _createVNode(ChatPicker, {
                                modelValue: cfg.lottery_target_groups,
                                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.lottery_target_groups) = $event)),
                                dialogs: dialogs.value
                              }, null, 8, ["modelValue", "dialogs"])
                            ]),
                            _createElementVNode("div", _hoisted_16, [
                              _cache[53] || (_cache[53] = _createElementVNode("span", { class: "lbl" }, "自定义抽奖群组", -1)),
                              _createVNode(ChatPicker, {
                                modelValue: cfg.custom_lottery_groups,
                                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.custom_lottery_groups) = $event)),
                                dialogs: dialogs.value
                              }, null, 8, ["modelValue", "dialogs"])
                            ]),
                            _cache[54] || (_cache[54] = _createElementVNode("p", { class: "tip" }, "两组群合并去重后生效；都留空 = 不参与任何群。", -1))
                          ], 64))
                        : _createCommentVNode("", true)
                    ])
                  ], 64))
                : (group.value === 'participate')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[59] || (_cache[59] = _createElementVNode("h3", { class: "det-title" }, "参与方式", -1)),
                      _createElementVNode("section", _hoisted_17, [
                        _createElementVNode("label", _hoisted_18, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.lottery_forward_enabled) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.lottery_forward_enabled]
                          ]),
                          _cache[56] || (_cache[56] = _createElementVNode("span", null, "转发原始抽奖消息参与（关闭则直接发文本关键词）", -1))
                        ]),
                        _createElementVNode("label", _hoisted_19, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.lottery_forward_first_participant) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.lottery_forward_first_participant]
                          ]),
                          _cache[57] || (_cache[57] = _createElementVNode("span", null, "转发第一个参与者（最多等30秒，超时降级）", -1))
                        ]),
                        _cache[58] || (_cache[58] = _createElementVNode("p", { class: "tip" }, "优先级：特殊格式(@、/)→转发原消息 > 转发第一参与者 > 转发原消息 > 直接发文本。", -1))
                      ])
                    ], 64))
                  : (group.value === 'prize')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                        _cache[63] || (_cache[63] = _createElementVNode("h3", { class: "det-title" }, "奖品匹配", -1)),
                        _createElementVNode("section", _hoisted_20, [
                          _createElementVNode("label", _hoisted_21, [
                            _cache[60] || (_cache[60] = _createElementVNode("span", null, "奖品列表", -1)),
                            _withDirectives(_createElementVNode("textarea", {
                              "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.prize_list) = $event)),
                              class: "inp",
                              rows: "4",
                              placeholder: "每行 群组ID|奖品1,奖品2\n例：-1001234567890|魔力,积分"
                            }, null, 512), [
                              [_vModelText, cfg.prize_list]
                            ])
                          ]),
                          _createElementVNode("label", _hoisted_22, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.universal_prize_match) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.universal_prize_match]
                            ]),
                            _cache[61] || (_cache[61] = _createElementVNode("span", null, "通用奖品匹配（所有群共用全部关键词；关闭=精确模式，建议关闭）", -1))
                          ]),
                          _createElementVNode("label", _hoisted_23, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.prize_case_sensitive) = $event)),
                              type: "checkbox"
                            }, null, 512), [
                              [_vModelCheckbox, cfg.prize_case_sensitive]
                            ]),
                            _cache[62] || (_cache[62] = _createElementVNode("span", null, "奖品关键词区分大小写", -1))
                          ])
                        ])
                      ], 64))
                    : (group.value === 'trap')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[73] || (_cache[73] = _createElementVNode("h3", { class: "det-title" }, "陷阱检测", -1)),
                          _createElementVNode("section", _hoisted_24, [
                            _createElementVNode("label", _hoisted_25, [
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.trap_enabled) = $event)),
                                type: "checkbox"
                              }, null, 512), [
                                [_vModelCheckbox, cfg.trap_enabled]
                              ]),
                              _cache[64] || (_cache[64] = _createElementVNode("span", null, "启用陷阱抽奖检测（命中任一特征则跳过）", -1))
                            ]),
                            (cfg.trap_enabled)
                              ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                  _createElementVNode("label", _hoisted_26, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.trap_case_sensitive) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.trap_case_sensitive]
                                    ]),
                                    _cache[65] || (_cache[65] = _createElementVNode("span", null, "陷阱关键词区分大小写", -1))
                                  ]),
                                  _createElementVNode("label", _hoisted_27, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.trap_enable_prize_pattern_check) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.trap_enable_prize_pattern_check]
                                    ]),
                                    _cache[66] || (_cache[66] = _createElementVNode("span", null, "启用关键词检测", -1))
                                  ]),
                                  (cfg.trap_enable_prize_pattern_check)
                                    ? (_openBlock(), _createElementBlock("label", _hoisted_28, [
                                        _cache[67] || (_cache[67] = _createElementVNode("span", null, "可疑关键词", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.trap_suspicious_keywords) = $event)),
                                          class: "inp",
                                          rows: "3",
                                          placeholder: "逗号或换行分隔"
                                        }, null, 512), [
                                          [_vModelText, cfg.trap_suspicious_keywords]
                                        ])
                                      ]))
                                    : _createCommentVNode("", true),
                                  _createElementVNode("label", _hoisted_29, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.trap_enable_creator_blacklist) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.trap_enable_creator_blacklist]
                                    ]),
                                    _cache[68] || (_cache[68] = _createElementVNode("span", null, "启用创建者黑名单", -1))
                                  ]),
                                  (cfg.trap_enable_creator_blacklist)
                                    ? (_openBlock(), _createElementBlock("label", _hoisted_30, [
                                        _cache[69] || (_cache[69] = _createElementVNode("span", null, "创建者黑名单", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((cfg.trap_blacklist_creator_ids) = $event)),
                                          class: "inp",
                                          rows: "2",
                                          placeholder: "逗号或换行分隔的用户ID"
                                        }, null, 512), [
                                          [_vModelText, cfg.trap_blacklist_creator_ids]
                                        ])
                                      ]))
                                    : _createCommentVNode("", true),
                                  _createElementVNode("label", _hoisted_31, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((cfg.trap_enable_participant_check) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.trap_enable_participant_check]
                                    ]),
                                    _cache[70] || (_cache[70] = _createElementVNode("span", null, "启用参与人数检测", -1))
                                  ]),
                                  (cfg.trap_enable_participant_check)
                                    ? (_openBlock(), _createElementBlock("label", _hoisted_32, [
                                        _cache[71] || (_cache[71] = _createElementVNode("span", null, "人数阈值", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((cfg.trap_max_participants) = $event)),
                                          class: "inp sm",
                                          type: "number",
                                          min: "1",
                                          max: "1000"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.trap_max_participants,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[72] || (_cache[72] = _createElementVNode("span", { class: "hint" }, "参与人数 ≤ 此值视为陷阱（=1 即只拦单人抽奖）", -1))
                                      ]))
                                    : _createCommentVNode("", true)
                                ], 64))
                              : _createCommentVNode("", true)
                          ])
                        ], 64))
                      : (group.value === 'wait')
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _cache[92] || (_cache[92] = _createElementVNode("h3", { class: "det-title" }, "抽奖等待时间", -1)),
                            _createElementVNode("section", _hoisted_33, [
                              _createElementVNode("label", _hoisted_34, [
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((cfg.lottery_wait_enabled) = $event)),
                                  type: "checkbox"
                                }, null, 512), [
                                  [_vModelCheckbox, cfg.lottery_wait_enabled]
                                ]),
                                _cache[74] || (_cache[74] = _createElementVNode("span", null, "抽奖等待时间总开关（关闭则相关动作立即执行）", -1))
                              ]),
                              (cfg.lottery_wait_enabled)
                                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                    _createElementVNode("div", _hoisted_35, [
                                      _createElementVNode("label", _hoisted_36, [
                                        _cache[75] || (_cache[75] = _createElementVNode("span", null, "参与前(最小)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((cfg.lottery_participate_wait_min) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_participate_wait_min,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[76] || (_cache[76] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_37, [
                                        _cache[77] || (_cache[77] = _createElementVNode("span", null, "参与前(最大)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((cfg.lottery_participate_wait_max) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_participate_wait_max,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[78] || (_cache[78] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_38, [
                                        _cache[79] || (_cache[79] = _createElementVNode("span", null, "感谢(最小)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((cfg.lottery_thank_wait_min) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_thank_wait_min,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[80] || (_cache[80] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_39, [
                                        _cache[81] || (_cache[81] = _createElementVNode("span", null, "感谢(最大)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((cfg.lottery_thank_wait_max) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_thank_wait_max,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[82] || (_cache[82] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_40, [
                                        _cache[83] || (_cache[83] = _createElementVNode("span", null, "黑幕(最小)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((cfg.lottery_heimu_wait_min) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_heimu_wait_min,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[84] || (_cache[84] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_41, [
                                        _cache[85] || (_cache[85] = _createElementVNode("span", null, "黑幕(最大)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((cfg.lottery_heimu_wait_max) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_heimu_wait_max,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[86] || (_cache[86] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_42, [
                                        _cache[87] || (_cache[87] = _createElementVNode("span", null, "负面(最小)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((cfg.lottery_negative_wait_min) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_negative_wait_min,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[88] || (_cache[88] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ]),
                                      _createElementVNode("label", _hoisted_43, [
                                        _cache[89] || (_cache[89] = _createElementVNode("span", null, "负面(最大)", -1)),
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((cfg.lottery_negative_wait_max) = $event)),
                                          class: "inp sm",
                                          type: "number"
                                        }, null, 512), [
                                          [
                                            _vModelText,
                                            cfg.lottery_negative_wait_max,
                                            void 0,
                                            { number: true }
                                          ]
                                        ]),
                                        _cache[90] || (_cache[90] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                      ])
                                    ]),
                                    _createElementVNode("label", _hoisted_44, [
                                      _cache[91] || (_cache[91] = _createElementVNode("span", null, "按群专属等待", -1)),
                                      _withDirectives(_createElementVNode("textarea", {
                                        "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((cfg.group_wait_overrides) = $event)),
                                        class: "inp",
                                        rows: "2",
                                        placeholder: "每行 群组ID|最小秒|最大秒\n例：-1001234567890|30|90"
                                      }, null, 512), [
                                        [_vModelText, cfg.group_wait_overrides]
                                      ])
                                    ])
                                  ], 64))
                                : _createCommentVNode("", true)
                            ])
                          ], 64))
                        : (group.value === 'react')
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
                              _cache[99] || (_cache[99] = _createElementVNode("h3", { class: "det-title" }, "中奖回应", -1)),
                              _createElementVNode("section", _hoisted_45, [
                                _createElementVNode("label", _hoisted_46, [
                                  _withDirectives(_createElementVNode("input", {
                                    "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((cfg.lottery_thank_message) = $event)),
                                    type: "checkbox"
                                  }, null, 512), [
                                    [_vModelCheckbox, cfg.lottery_thank_message]
                                  ]),
                                  _cache[93] || (_cache[93] = _createElementVNode("span", null, "中奖后发感谢消息", -1))
                                ]),
                                (cfg.lottery_thank_message)
                                  ? (_openBlock(), _createElementBlock("label", _hoisted_47, [
                                      _cache[94] || (_cache[94] = _createElementVNode("span", null, "感谢文案", -1)),
                                      _withDirectives(_createElementVNode("textarea", {
                                        "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((cfg.thank_texts) = $event)),
                                        class: "inp",
                                        rows: "3",
                                        placeholder: "每行一条随机选，{boss}=创建者名字"
                                      }, null, 512), [
                                        [_vModelText, cfg.thank_texts]
                                      ])
                                    ]))
                                  : _createCommentVNode("", true),
                                _createElementVNode("label", _hoisted_48, [
                                  _withDirectives(_createElementVNode("input", {
                                    "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((cfg.username_reply_switch) = $event)),
                                    type: "checkbox"
                                  }, null, 512), [
                                    [_vModelCheckbox, cfg.username_reply_switch]
                                  ]),
                                  _cache[95] || (_cache[95] = _createElementVNode("span", null, "中奖回复用户名（无转账功能的群，需填上方 PT用户名）", -1))
                                ]),
                                (cfg.username_reply_switch)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_49, [
                                      _cache[96] || (_cache[96] = _createElementVNode("span", { class: "lbl" }, "转账群组（免回用户名）", -1)),
                                      _createVNode(ChatPicker, {
                                        modelValue: cfg.transfer_groups,
                                        "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => ((cfg.transfer_groups) = $event)),
                                        dialogs: dialogs.value
                                      }, null, 8, ["modelValue", "dialogs"])
                                    ]))
                                  : _createCommentVNode("", true),
                                _createElementVNode("label", _hoisted_50, [
                                  _withDirectives(_createElementVNode("input", {
                                    "onUpdate:modelValue": _cache[35] || (_cache[35] = $event => ((cfg.lottery_heimu_message) = $event)),
                                    type: "checkbox"
                                  }, null, 512), [
                                    [_vModelCheckbox, cfg.lottery_heimu_message]
                                  ]),
                                  _cache[97] || (_cache[97] = _createElementVNode("span", null, "未中奖发黑幕消息", -1))
                                ]),
                                (cfg.lottery_heimu_message)
                                  ? (_openBlock(), _createElementBlock("label", _hoisted_51, [
                                      _cache[98] || (_cache[98] = _createElementVNode("span", null, "黑幕文案", -1)),
                                      _withDirectives(_createElementVNode("textarea", {
                                        "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => ((cfg.heimu_texts) = $event)),
                                        class: "inp",
                                        rows: "3",
                                        placeholder: "每行一条随机选"
                                      }, null, 512), [
                                        [_vModelText, cfg.heimu_texts]
                                      ])
                                    ]))
                                  : _createCommentVNode("", true)
                              ])
                            ], 64))
                          : (group.value === 'negative')
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 6 }, [
                                _cache[102] || (_cache[102] = _createElementVNode("h3", { class: "det-title" }, "负面回复（被质疑是机器人）", -1)),
                                _createElementVNode("section", _hoisted_52, [
                                  _createElementVNode("label", _hoisted_53, [
                                    _withDirectives(_createElementVNode("input", {
                                      "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((cfg.lose_reply_switch) = $event)),
                                      type: "checkbox"
                                    }, null, 512), [
                                      [_vModelCheckbox, cfg.lose_reply_switch]
                                    ]),
                                    _cache[100] || (_cache[100] = _createElementVNode("span", null, "负面回复开关（有人回你说机器人/脚本等时随机反驳）", -1))
                                  ]),
                                  (cfg.lose_reply_switch)
                                    ? (_openBlock(), _createElementBlock("label", _hoisted_54, [
                                        _cache[101] || (_cache[101] = _createElementVNode("span", null, "反驳文案", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((cfg.negative_texts) = $event)),
                                          class: "inp",
                                          rows: "3",
                                          placeholder: "每行一条随机选"
                                        }, null, 512), [
                                          [_vModelText, cfg.negative_texts]
                                        ])
                                      ]))
                                    : _createCommentVNode("", true)
                                ])
                              ], 64))
                            : (group.value === 'send')
                              ? (_openBlock(), _createElementBlock(_Fragment, { key: 7 }, [
                                  _cache[111] || (_cache[111] = _createElementVNode("h3", { class: "det-title" }, "自动发奖", -1)),
                                  _createElementVNode("section", _hoisted_55, [
                                    _createElementVNode("label", _hoisted_56, [
                                      _withDirectives(_createElementVNode("input", {
                                        "onUpdate:modelValue": _cache[39] || (_cache[39] = $event => ((cfg.auto_prize_enabled) = $event)),
                                        type: "checkbox"
                                      }, null, 512), [
                                        [_vModelCheckbox, cfg.auto_prize_enabled]
                                      ]),
                                      _cache[103] || (_cache[103] = _createElementVNode("span", null, "自动发奖功能总开关（开启才记录自己发起的抽奖中奖者）", -1))
                                    ]),
                                    (cfg.auto_prize_enabled)
                                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                          _createElementVNode("label", _hoisted_57, [
                                            _withDirectives(_createElementVNode("input", {
                                              "onUpdate:modelValue": _cache[40] || (_cache[40] = $event => ((cfg.manual_prize_mode) = $event)),
                                              type: "checkbox"
                                            }, null, 512), [
                                              [_vModelCheckbox, cfg.manual_prize_mode]
                                            ]),
                                            _cache[104] || (_cache[104] = _createElementVNode("span", null, "手动发奖模式（只记录，用「待发奖」页或 .sendprize 发）", -1))
                                          ]),
                                          _createElementVNode("label", _hoisted_58, [
                                            _withDirectives(_createElementVNode("input", {
                                              "onUpdate:modelValue": _cache[41] || (_cache[41] = $event => ((cfg.prize_send_interval_enabled) = $event)),
                                              type: "checkbox"
                                            }, null, 512), [
                                              [_vModelCheckbox, cfg.prize_send_interval_enabled]
                                            ]),
                                            _cache[105] || (_cache[105] = _createElementVNode("span", null, "发奖间隔（每次发奖后随机等待，建议开启）", -1))
                                          ]),
                                          (cfg.prize_send_interval_enabled)
                                            ? (_openBlock(), _createElementBlock("div", _hoisted_59, [
                                                _createElementVNode("label", _hoisted_60, [
                                                  _cache[106] || (_cache[106] = _createElementVNode("span", null, "间隔(最小)", -1)),
                                                  _withDirectives(_createElementVNode("input", {
                                                    "onUpdate:modelValue": _cache[42] || (_cache[42] = $event => ((cfg.prize_send_interval_min) = $event)),
                                                    class: "inp sm",
                                                    type: "number"
                                                  }, null, 512), [
                                                    [
                                                      _vModelText,
                                                      cfg.prize_send_interval_min,
                                                      void 0,
                                                      { number: true }
                                                    ]
                                                  ]),
                                                  _cache[107] || (_cache[107] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                                ]),
                                                _createElementVNode("label", _hoisted_61, [
                                                  _cache[108] || (_cache[108] = _createElementVNode("span", null, "间隔(最大)", -1)),
                                                  _withDirectives(_createElementVNode("input", {
                                                    "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((cfg.prize_send_interval_max) = $event)),
                                                    class: "inp sm",
                                                    type: "number"
                                                  }, null, 512), [
                                                    [
                                                      _vModelText,
                                                      cfg.prize_send_interval_max,
                                                      void 0,
                                                      { number: true }
                                                    ]
                                                  ]),
                                                  _cache[109] || (_cache[109] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                                                ])
                                              ]))
                                            : _createCommentVNode("", true),
                                          _createElementVNode("label", _hoisted_62, [
                                            _cache[110] || (_cache[110] = _createElementVNode("span", null, "发奖黑名单", -1)),
                                            _withDirectives(_createElementVNode("textarea", {
                                              "onUpdate:modelValue": _cache[44] || (_cache[44] = $event => ((cfg.prize_send_blacklist) = $event)),
                                              class: "inp",
                                              rows: "2",
                                              placeholder: "逗号或换行分隔的用户ID，这些中奖者不发奖"
                                            }, null, 512), [
                                              [_vModelText, cfg.prize_send_blacklist]
                                            ])
                                          ])
                                        ], 64))
                                      : _createCommentVNode("", true)
                                  ])
                                ], 64))
                              : (group.value === 'notify')
                                ? (_openBlock(), _createElementBlock(_Fragment, { key: 8 }, [
                                    _cache[114] || (_cache[114] = _createElementVNode("h3", { class: "det-title" }, "通知", -1)),
                                    _createElementVNode("section", _hoisted_63, [
                                      _createElementVNode("label", _hoisted_64, [
                                        _withDirectives(_createElementVNode("input", {
                                          "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((cfg.notify_owner) = $event)),
                                          type: "checkbox"
                                        }, null, 512), [
                                          [_vModelCheckbox, cfg.notify_owner]
                                        ]),
                                        _cache[112] || (_cache[112] = _createElementVNode("span", null, "关键事件通知我（参与成功/中奖/发奖完成）", -1))
                                      ]),
                                      (cfg.notify_owner)
                                        ? (_openBlock(), _createElementBlock("label", _hoisted_65, [
                                            _withDirectives(_createElementVNode("input", {
                                              "onUpdate:modelValue": _cache[46] || (_cache[46] = $event => ((cfg.notify_skips) = $event)),
                                              type: "checkbox"
                                            }, null, 512), [
                                              [_vModelCheckbox, cfg.notify_skips]
                                            ]),
                                            _cache[113] || (_cache[113] = _createElementVNode("span", null, "通知跳过原因（奖品不符/陷阱/不在时间段等，较吵）", -1))
                                          ]))
                                        : _createCommentVNode("", true)
                                    ])
                                  ], 64))
                                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_66, [
                _createElementVNode("button", {
                  class: "btn primary lg",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_67)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_68, [
            _createElementVNode("div", _hoisted_69, [
              _createElementVNode("span", _hoisted_70, "待发奖 " + _toDisplayString(pending.value.length) + " 个", 1),
              _cache[115] || (_cache[115] = _createElementVNode("span", { class: "grow" }, null, -1)),
              _createElementVNode("button", {
                class: "btn",
                onClick: loadPending
              }, "刷新"),
              _createElementVNode("button", {
                class: "btn primary",
                disabled: !pending.value.length || sending.value,
                onClick: sendAll
              }, _toDisplayString(sending.value === 'all' ? '发奖中…' : '全部发奖'), 9, _hoisted_71),
              _createElementVNode("button", {
                class: "btn danger",
                disabled: !pending.value.length,
                onClick: clearPending
              }, "清空", 8, _hoisted_72)
            ]),
            (pendingLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_73, "加载中…"))
              : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  (!pending.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_74, [...(_cache[116] || (_cache[116] = [
                        _createTextVNode("暂无待发奖", -1),
                        _createElementVNode("br", null, null, -1),
                        _createElementVNode("span", { class: "muted" }, "开启「自动发奖」并用「手动发奖模式」后，自己发起的抽奖中奖者会记录在这里", -1)
                      ]))]))
                    : (_openBlock(), _createElementBlock("table", _hoisted_75, [
                        _cache[117] || (_cache[117] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "抽奖ID"),
                            _createElementVNode("th", null, "群"),
                            _createElementVNode("th", null, "奖品"),
                            _createElementVNode("th", null, "中奖人数"),
                            _createElementVNode("th", null, "时间"),
                            _createElementVNode("th")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pending.value, (p) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: p.lottery_id
                            }, [
                              _createElementVNode("td", _hoisted_76, "#" + _toDisplayString(p.lottery_id.slice(0, 8)), 1),
                              _createElementVNode("td", null, _toDisplayString(p.chat_title || '—'), 1),
                              _createElementVNode("td", _hoisted_77, _toDisplayString(p.prize || '—'), 1),
                              _createElementVNode("td", null, _toDisplayString(p.winners), 1),
                              _createElementVNode("td", _hoisted_78, _toDisplayString(p.time || '—'), 1),
                              _createElementVNode("td", null, [
                                _createElementVNode("button", {
                                  class: "btn xs",
                                  disabled: sending.value,
                                  onClick: $event => (sendOne(p))
                                }, _toDisplayString(sending.value === p.lottery_id ? '发奖中…' : '发奖'), 9, _hoisted_79)
                              ])
                            ]))
                          }), 128))
                        ])
                      ])),
                  (prizeHistory.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_80, [
                        _createElementVNode("div", _hoisted_81, "发奖历史（最近 " + _toDisplayString(prizeHistory.value.length) + " 条）", 1),
                        _createElementVNode("table", _hoisted_82, [
                          _cache[118] || (_cache[118] = _createElementVNode("thead", null, [
                            _createElementVNode("tr", null, [
                              _createElementVNode("th", null, "抽奖ID"),
                              _createElementVNode("th", null, "中奖"),
                              _createElementVNode("th", null, "成功"),
                              _createElementVNode("th", null, "失败"),
                              _createElementVNode("th", null, "时间")
                            ])
                          ], -1)),
                          _createElementVNode("tbody", null, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(prizeHistory.value, (h, i) => {
                              return (_openBlock(), _createElementBlock("tr", { key: i }, [
                                _createElementVNode("td", _hoisted_83, "#" + _toDisplayString(String(h.lottery_id || '').slice(0, 8)), 1),
                                _createElementVNode("td", null, _toDisplayString(h.total), 1),
                                _createElementVNode("td", _hoisted_84, _toDisplayString(h.success), 1),
                                _createElementVNode("td", {
                                  style: _normalizeStyle({ color: h.failed ? '#ff6b6b' : '' })
                                }, _toDisplayString(h.failed), 5),
                                _createElementVNode("td", _hoisted_85, _toDisplayString(h.time || '—'), 1)
                              ]))
                            }), 128))
                          ])
                        ])
                      ]))
                    : _createCommentVNode("", true)
                ], 64))
          ], 512), [
            [_vShow, tab.value === 'prize']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-86262419"]]);

export { Config as default };
