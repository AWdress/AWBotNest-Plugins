import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,vModelText:_vModelText,vModelSelect:_vModelSelect,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = ["aria-busy"];
const _hoisted_2 = { class: "masthead" };
const _hoisted_3 = ["disabled"];
const _hoisted_4 = { class: "status-strip" };
const _hoisted_5 = { class: "master" };
const _hoisted_6 = { class: "workspace" };
const _hoisted_7 = { class: "rules-pane" };
const _hoisted_8 = {
  key: 0,
  class: "empty"
};
const _hoisted_9 = {
  key: 1,
  class: "rule-list"
};
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "order" };
const _hoisted_12 = { class: "summary-copy" };
const _hoisted_13 = { class: "chevron" };
const _hoisted_14 = {
  key: 0,
  class: "editor"
};
const _hoisted_15 = { class: "field-grid" };
const _hoisted_16 = ["onUpdate:modelValue"];
const _hoisted_17 = ["onUpdate:modelValue", "disabled"];
const _hoisted_18 = ["onUpdate:modelValue"];
const _hoisted_19 = ["onUpdate:modelValue"];
const _hoisted_20 = ["onUpdate:modelValue"];
const _hoisted_21 = { class: "check" };
const _hoisted_22 = ["onUpdate:modelValue"];
const _hoisted_23 = { key: 0 };
const _hoisted_24 = ["onUpdate:modelValue"];
const _hoisted_25 = { class: "field-grid" };
const _hoisted_26 = ["onUpdate:modelValue"];
const _hoisted_27 = ["onUpdate:modelValue"];
const _hoisted_28 = { class: "option-row" };
const _hoisted_29 = { class: "check" };
const _hoisted_30 = ["onUpdate:modelValue"];
const _hoisted_31 = { class: "check" };
const _hoisted_32 = ["onUpdate:modelValue"];
const _hoisted_33 = { class: "field-grid" };
const _hoisted_34 = ["onUpdate:modelValue"];
const _hoisted_35 = ["onUpdate:modelValue"];
const _hoisted_36 = { class: "rule-actions" };
const _hoisted_37 = ["onClick", "disabled"];
const _hoisted_38 = ["onClick", "disabled"];
const _hoisted_39 = ["onClick"];
const _hoisted_40 = ["onClick"];
const _hoisted_41 = { class: "settings-pane" };
const _hoisted_42 = ["value"];
const _hoisted_43 = { class: "check" };
const _hoisted_44 = { class: "note" };

const {computed,onMounted,reactive,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { pluginId: String, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const cfg = reactive({ enabled: true, midnight_reset: false, leaderboard_enabled: true, rules_text: [], chat_ids: [], delete_after: 0, blacklist_ids: '', leaderboard_command: '.羊毛榜', leaderboard_size: 10 });
const loading = ref(true);
const saving = ref(false);
const openRule = ref(0);

const activeRules = computed(() => cfg.rules_text.filter(rule => rule.reply?.trim() && Number(rule.trigger_chance) > 0).length);
const leaderboardRuleCount = computed(() => cfg.rules_text.filter(rule => rule.count_for_leaderboard !== false).length);
const scopeText = computed(() => Array.isArray(cfg.chat_ids) && cfg.chat_ids.length ? `${cfg.chat_ids.length} 个群组` : '全部群组');

function normalizeRule(rule = {}) {
  return { keyword: String(rule.keyword || ''), reply: String(rule.reply || ''), match_type: ['exact', 'contains'].includes(rule.match_type) ? rule.match_type : 'contains', trigger_mode: ['any', 'reply_to_me'].includes(rule.trigger_mode) ? rule.trigger_mode : 'any', trigger_chance: Math.max(0, Math.min(100, Number(rule.trigger_chance ?? 100))), cooldown_hours: Math.max(0, Number(rule.cooldown_hours ?? 24) || 0), cooldown_notify: rule.cooldown_notify !== false, reset_at_midnight: rule.reset_at_midnight === true, count_for_leaderboard: rule.count_for_leaderboard !== false, fun_reply_chance: Math.max(0, Math.min(100, Number(rule.fun_reply_chance) || 0)), fun_replies: Array.isArray(rule.fun_replies) ? rule.fun_replies.join('\n---\n') : String(rule.fun_replies || ''), extra_reply_enabled: rule.extra_reply_enabled === true, extra_reply: String(rule.extra_reply ?? '叮！恭喜你喜提特等奖掉落。') }
}
function addRule() { cfg.rules_text.push(normalizeRule()); openRule.value = cfg.rules_text.length - 1; }
function duplicateRule(index) { cfg.rules_text.splice(index + 1, 0, normalizeRule(cfg.rules_text[index])); openRule.value = index + 1; }
function removeRule(index) { cfg.rules_text.splice(index, 1); openRule.value = Math.min(openRule.value, cfg.rules_text.length - 1); }
function move(index, delta) { const next = index + delta; if (next < 0 || next >= cfg.rules_text.length) return; const [rule] = cfg.rules_text.splice(index, 1); cfg.rules_text.splice(next, 0, rule); openRule.value = next; }

async function save() {
  const invalid = cfg.rules_text.findIndex(rule => !rule.reply.trim());
  if (invalid >= 0) { openRule.value = invalid; props.host.toast.error(`第 ${invalid + 1} 条规则需要填写回复内容`); return }
  const keys = cfg.rules_text.map(rule => rule.keyword.trim()).filter(Boolean);
  if (new Set(keys).size !== keys.length) { props.host.toast.error('关键词不能重复'); return }
  const missingFun = cfg.rules_text.findIndex(rule => rule.fun_reply_chance > 0 && !rule.fun_replies.trim());
  if (missingFun >= 0) { openRule.value = missingFun; props.host.toast.error(`第 ${missingFun + 1} 条规则设置了趣味概率，请至少填写一条趣味文字`); return }
  const missingExtra = cfg.rules_text.findIndex(rule => rule.extra_reply_enabled && !rule.extra_reply.trim());
  if (missingExtra >= 0) { openRule.value = missingExtra; props.host.toast.error(`第 ${missingExtra + 1} 条规则已开启追加回复，请填写追加回复内容`); return }
  saving.value = true;
  try {
    cfg.rules_text = cfg.rules_text.map(normalizeRule);
    cfg.delete_after = Math.max(0, Math.min(3600, Math.trunc(Number(cfg.delete_after) || 0)));
    cfg.leaderboard_size = Math.max(3, Math.min(30, Math.trunc(Number(cfg.leaderboard_size) || 10)));
    await props.host.saveConfig({ ...cfg });
    props.host.toast.success('聊天互动助手配置已保存');
  } catch (error) { props.host.toast.error(error.message || String(error)); }
  finally { saving.value = false; }
}

onMounted(async () => {
  try {
    const saved = await props.host.getConfig();
    Object.assign(cfg, saved || {});
    const fallbackMatch = ['exact', 'contains'].includes(saved?.match_type) ? saved.match_type : 'contains';
    const fallbackCooldown = Number(saved?.cooldown_hours ?? 24) || 24;
    const fallbackMidnight = saved?.midnight_reset === true;
    cfg.rules_text = Array.isArray(saved?.rules_text) ? saved.rules_text.map(rule => normalizeRule({ match_type: fallbackMatch, cooldown_hours: fallbackCooldown, reset_at_midnight: fallbackMidnight, ...rule })) : [];
  } catch (error) { props.host.toast.error(error.message || String(error)); }
  finally { loading.value = false; }
});

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("main", {
    class: "surface",
    "aria-busy": loading.value
  }, [
    _createElementVNode("header", _hoisted_2, [
      _cache[7] || (_cache[7] = _createElementVNode("div", null, [
        _createElementVNode("h2", null, "聊天互动助手"),
        _createElementVNode("p", null, "无需关键词也能按概率参与群聊，每条规则独立控制触发与冷却。")
      ], -1)),
      _createElementVNode("button", {
        class: "save",
        disabled: loading.value || saving.value,
        onClick: save
      }, _toDisplayString(saving.value ? '保存中…' : '保存并应用'), 9, _hoisted_3)
    ]),
    _createElementVNode("section", _hoisted_4, [
      _createElementVNode("label", _hoisted_5, [
        _withDirectives(_createElementVNode("input", {
          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.enabled) = $event)),
          type: "checkbox"
        }, null, 512), [
          [_vModelCheckbox, cfg.enabled]
        ]),
        _createElementVNode("span", null, [
          _createElementVNode("b", null, _toDisplayString(cfg.enabled ? '互动已启用' : '互动已暂停'), 1),
          _cache[8] || (_cache[8] = _createElementVNode("small", null, "关闭后保留规则与统计", -1))
        ])
      ]),
      _createElementVNode("dl", null, [
        _createElementVNode("div", null, [
          _cache[9] || (_cache[9] = _createElementVNode("dt", null, "有效规则", -1)),
          _createElementVNode("dd", null, _toDisplayString(activeRules.value), 1)
        ]),
        _createElementVNode("div", null, [
          _cache[10] || (_cache[10] = _createElementVNode("dt", null, "生效范围", -1)),
          _createElementVNode("dd", null, _toDisplayString(scopeText.value), 1)
        ]),
        _createElementVNode("div", null, [
          _cache[11] || (_cache[11] = _createElementVNode("dt", null, "回复清理", -1)),
          _createElementVNode("dd", null, _toDisplayString(cfg.delete_after ? `${cfg.delete_after} 秒` : '不删除'), 1)
        ])
      ])
    ]),
    _createElementVNode("div", _hoisted_6, [
      _createElementVNode("section", _hoisted_7, [
        _createElementVNode("div", { class: "section-head" }, [
          _cache[12] || (_cache[12] = _createElementVNode("div", null, [
            _createElementVNode("h3", null, "互动规则"),
            _createElementVNode("p", null, "从上到下判断；概率未命中时继续尝试下一条规则。")
          ], -1)),
          _createElementVNode("button", {
            class: "add",
            onClick: addRule
          }, "新增规则")
        ]),
        (!cfg.rules_text.length)
          ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
              _cache[13] || (_cache[13] = _createElementVNode("strong", null, "还没有规则", -1)),
              _cache[14] || (_cache[14] = _createElementVNode("p", null, "新增第一条规则，设置回复内容、触发概率与独立冷却。", -1)),
              _createElementVNode("button", {
                class: "add",
                onClick: addRule
              }, "创建第一条规则")
            ]))
          : (_openBlock(), _createElementBlock("ol", _hoisted_9, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cfg.rules_text, (rule, index) => {
                return (_openBlock(), _createElementBlock("li", {
                  key: index,
                  class: _normalizeClass({ open: openRule.value === index })
                }, [
                  _createElementVNode("button", {
                    class: "rule-summary",
                    onClick: $event => (openRule.value = openRule.value === index ? -1 : index)
                  }, [
                    _createElementVNode("span", _hoisted_11, _toDisplayString(String(index + 1).padStart(2, '0')), 1),
                    _createElementVNode("span", _hoisted_12, [
                      _createElementVNode("b", null, _toDisplayString(rule.keyword || '任意消息'), 1),
                      _createElementVNode("small", null, _toDisplayString(rule.keyword ? (rule.match_type === 'exact' ? '完全匹配' : '包含匹配') : '无需关键词') + " · " + _toDisplayString(rule.trigger_chance) + "% 触发 · " + _toDisplayString(rule.trigger_mode === 'reply_to_me' ? '需回复我的消息' : '普通消息') + " · " + _toDisplayString(rule.cooldown_hours ? (rule.reset_at_midnight ? '每日零点重置' : `${rule.cooldown_hours} 小时冷却`) : '无冷却') + _toDisplayString(rule.extra_reply_enabled ? ' · 追加回复' : '') + _toDisplayString(rule.fun_reply_chance ? ` · ${rule.fun_reply_chance}% 彩蛋` : ''), 1)
                    ]),
                    _createElementVNode("span", _hoisted_13, _toDisplayString(openRule.value === index ? '收起' : '编辑'), 1)
                  ], 8, _hoisted_10),
                  (openRule.value === index)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
                        _createElementVNode("div", _hoisted_15, [
                          _createElementVNode("label", null, [
                            _cache[15] || (_cache[15] = _createElementVNode("span", null, "关键词（可选）", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": $event => ((rule.keyword) = $event),
                              placeholder: "留空则匹配任意消息"
                            }, null, 8, _hoisted_16), [
                              [_vModelText, rule.keyword]
                            ]),
                            _cache[16] || (_cache[16] = _createElementVNode("small", { class: "field-help" }, "不填写关键词时，每条群消息都会进入概率判断。", -1))
                          ]),
                          _createElementVNode("label", null, [
                            _cache[18] || (_cache[18] = _createElementVNode("span", null, "匹配方式", -1)),
                            _withDirectives(_createElementVNode("select", {
                              "onUpdate:modelValue": $event => ((rule.match_type) = $event),
                              disabled: !rule.keyword.trim()
                            }, [...(_cache[17] || (_cache[17] = [
                              _createElementVNode("option", { value: "contains" }, "消息包含关键词", -1),
                              _createElementVNode("option", { value: "exact" }, "消息完全等于关键词", -1)
                            ]))], 8, _hoisted_17), [
                              [_vModelSelect, rule.match_type]
                            ])
                          ])
                        ]),
                        _createElementVNode("label", null, [
                          _cache[19] || (_cache[19] = _createElementVNode("span", null, "触发概率（%）", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": $event => ((rule.trigger_chance) = $event),
                            type: "number",
                            min: "0",
                            max: "100",
                            step: "1"
                          }, null, 8, _hoisted_18), [
                            [
                              _vModelText,
                              rule.trigger_chance,
                              void 0,
                              { number: true }
                            ]
                          ]),
                          _cache[20] || (_cache[20] = _createElementVNode("small", { class: "field-help" }, "100 表示每次满足条件都触发，0 表示暂停此规则。", -1))
                        ]),
                        _createElementVNode("label", null, [
                          _cache[22] || (_cache[22] = _createElementVNode("span", null, "触发方式", -1)),
                          _withDirectives(_createElementVNode("select", {
                            "onUpdate:modelValue": $event => ((rule.trigger_mode) = $event)
                          }, [...(_cache[21] || (_cache[21] = [
                            _createElementVNode("option", { value: "any" }, "普通消息（不要求回复我）", -1),
                            _createElementVNode("option", { value: "reply_to_me" }, "回复我的消息才触发", -1)
                          ]))], 8, _hoisted_19), [
                            [_vModelSelect, rule.trigger_mode]
                          ]),
                          _cache[23] || (_cache[23] = _createElementVNode("small", { class: "field-help" }, "选择“回复我的消息”后，只有别人回复本账号发出的消息且满足关键词条件时才执行。", -1))
                        ]),
                        _createElementVNode("label", null, [
                          _cache[24] || (_cache[24] = _createElementVNode("span", null, "回复内容", -1)),
                          _withDirectives(_createElementVNode("textarea", {
                            "onUpdate:modelValue": $event => ((rule.reply) = $event),
                            rows: "4",
                            placeholder: "支持 {uname}、{uid} 和 10-100 随机数"
                          }, null, 8, _hoisted_20), [
                            [_vModelText, rule.reply]
                          ])
                        ]),
                        _createElementVNode("label", _hoisted_21, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": $event => ((rule.extra_reply_enabled) = $event),
                            type: "checkbox"
                          }, null, 8, _hoisted_22), [
                            [_vModelCheckbox, rule.extra_reply_enabled]
                          ]),
                          _cache[25] || (_cache[25] = _createElementVNode("span", null, "发送一条追加回复", -1))
                        ]),
                        (rule.extra_reply_enabled)
                          ? (_openBlock(), _createElementBlock("label", _hoisted_23, [
                              _cache[26] || (_cache[26] = _createElementVNode("span", null, "追加回复内容", -1)),
                              _withDirectives(_createElementVNode("textarea", {
                                "onUpdate:modelValue": $event => ((rule.extra_reply) = $event),
                                rows: "3",
                                placeholder: "叮！恭喜你喜提特等奖掉落。"
                              }, null, 8, _hoisted_24), [
                                [_vModelText, rule.extra_reply]
                              ]),
                              _cache[27] || (_cache[27] = _createElementVNode("small", { class: "field-help" }, "标准回复发出后，再单独发送此消息；同样支持 {uname}、{uid} 和随机数。", -1))
                            ]))
                          : _createCommentVNode("", true),
                        _createElementVNode("div", _hoisted_25, [
                          _createElementVNode("label", null, [
                            _cache[28] || (_cache[28] = _createElementVNode("span", null, "此规则冷却（小时）", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": $event => ((rule.cooldown_hours) = $event),
                              type: "number",
                              min: "0",
                              max: "720",
                              step: "0.5"
                            }, null, 8, _hoisted_26), [
                              [
                                _vModelText,
                                rule.cooldown_hours,
                                void 0,
                                { number: true }
                              ]
                            ])
                          ]),
                          _createElementVNode("label", null, [
                            _cache[30] || (_cache[30] = _createElementVNode("span", null, "冷却计算方式", -1)),
                            _withDirectives(_createElementVNode("select", {
                              "onUpdate:modelValue": $event => ((rule.reset_at_midnight) = $event)
                            }, [...(_cache[29] || (_cache[29] = [
                              _createElementVNode("option", { value: false }, "按小时滚动计算", -1),
                              _createElementVNode("option", { value: true }, "每天零点重置", -1)
                            ]))], 8, _hoisted_27), [
                              [_vModelSelect, rule.reset_at_midnight]
                            ])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_28, [
                          _createElementVNode("label", _hoisted_29, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": $event => ((rule.cooldown_notify) = $event),
                              type: "checkbox"
                            }, null, 8, _hoisted_30), [
                              [_vModelCheckbox, rule.cooldown_notify]
                            ]),
                            _cache[31] || (_cache[31] = _createElementVNode("span", null, "冷却中回复剩余时间", -1))
                          ]),
                          _createElementVNode("label", _hoisted_31, [
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": $event => ((rule.count_for_leaderboard) = $event),
                              type: "checkbox"
                            }, null, 8, _hoisted_32), [
                              [_vModelCheckbox, rule.count_for_leaderboard]
                            ]),
                            _cache[32] || (_cache[32] = _createElementVNode("span", null, "命中后计入羊毛榜", -1))
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_33, [
                          _createElementVNode("label", null, [
                            _cache[33] || (_cache[33] = _createElementVNode("span", null, "趣味文字概率（%）", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": $event => ((rule.fun_reply_chance) = $event),
                              type: "number",
                              min: "0",
                              max: "100",
                              step: "1"
                            }, null, 8, _hoisted_34), [
                              [
                                _vModelText,
                                rule.fun_reply_chance,
                                void 0,
                                { number: true }
                              ]
                            ]),
                            _cache[34] || (_cache[34] = _createElementVNode("small", { class: "field-help" }, "设为 0 表示始终发送标准回复。", -1))
                          ]),
                          _createElementVNode("label", null, [
                            _cache[35] || (_cache[35] = _createElementVNode("span", null, "趣味回复文案", -1)),
                            _withDirectives(_createElementVNode("textarea", {
                              "onUpdate:modelValue": $event => ((rule.fun_replies) = $event),
                              rows: "7",
                              placeholder: "【系统提示】：该 NPC 暂无掉落物。\n建议获取途径：\n\n1、日常任务：老实做种；\n\n2、隐藏副本：去隔壁群乞讨。"
                            }, null, 8, _hoisted_35), [
                              [_vModelText, rule.fun_replies]
                            ]),
                            _cache[36] || (_cache[36] = _createElementVNode("small", { class: "field-help" }, "一整段会完整发送并保留换行；配置多条随机文案时，用单独一行 --- 分隔。", -1))
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_36, [
                          _createElementVNode("button", {
                            onClick: $event => (move(index,-1)),
                            disabled: index===0
                          }, "上移", 8, _hoisted_37),
                          _createElementVNode("button", {
                            onClick: $event => (move(index,1)),
                            disabled: index===cfg.rules_text.length-1
                          }, "下移", 8, _hoisted_38),
                          _createElementVNode("button", {
                            onClick: $event => (duplicateRule(index))
                          }, "复制", 8, _hoisted_39),
                          _createElementVNode("button", {
                            class: "remove",
                            onClick: $event => (removeRule(index))
                          }, "删除", 8, _hoisted_40)
                        ])
                      ]))
                    : _createCommentVNode("", true)
                ], 2))
              }), 128))
            ]))
      ]),
      _createElementVNode("aside", _hoisted_41, [
        _createElementVNode("section", null, [
          _cache[40] || (_cache[40] = _createElementVNode("h3", null, "范围与清理", -1)),
          _createElementVNode("label", null, [
            _cache[37] || (_cache[37] = _createElementVNode("span", null, "生效群组 ID", -1)),
            _createElementVNode("textarea", {
              value: Array.isArray(cfg.chat_ids) ? cfg.chat_ids.join('\n') : cfg.chat_ids,
              onInput: _cache[1] || (_cache[1] = $event => (cfg.chat_ids=$event.target.value.split(/[\s,]+/).filter(Boolean))),
              rows: "4",
              placeholder: "留空表示全部群组"
            }, null, 40, _hoisted_42)
          ]),
          _createElementVNode("label", null, [
            _cache[38] || (_cache[38] = _createElementVNode("span", null, "回复自动删除（秒）", -1)),
            _withDirectives(_createElementVNode("input", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.delete_after) = $event)),
              type: "number",
              min: "0",
              max: "3600"
            }, null, 512), [
              [
                _vModelText,
                cfg.delete_after,
                void 0,
                { number: true }
              ]
            ])
          ]),
          _createElementVNode("label", null, [
            _cache[39] || (_cache[39] = _createElementVNode("span", null, "屏蔽用户 ID", -1)),
            _withDirectives(_createElementVNode("textarea", {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.blacklist_ids) = $event)),
              rows: "3",
              placeholder: "逗号或换行分隔"
            }, null, 512), [
              [_vModelText, cfg.blacklist_ids]
            ])
          ])
        ]),
        _createElementVNode("section", null, [
          _cache[44] || (_cache[44] = _createElementVNode("h3", null, "薅羊毛排行榜", -1)),
          _createElementVNode("label", _hoisted_43, [
            _withDirectives(_createElementVNode("input", {
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.leaderboard_enabled) = $event)),
              type: "checkbox"
            }, null, 512), [
              [_vModelCheckbox, cfg.leaderboard_enabled]
            ]),
            _cache[41] || (_cache[41] = _createElementVNode("span", null, "启用排行榜", -1))
          ]),
          (cfg.leaderboard_enabled)
            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createElementVNode("label", null, [
                  _cache[42] || (_cache[42] = _createElementVNode("span", null, "本人查询命令", -1)),
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.leaderboard_command) = $event))
                  }, null, 512), [
                    [_vModelText, cfg.leaderboard_command]
                  ])
                ]),
                _createElementVNode("label", null, [
                  _cache[43] || (_cache[43] = _createElementVNode("span", null, "显示人数", -1)),
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.leaderboard_size) = $event)),
                    type: "number",
                    min: "3",
                    max: "30"
                  }, null, 512), [
                    [
                      _vModelText,
                      cfg.leaderboard_size,
                      void 0,
                      { number: true }
                    ]
                  ])
                ]),
                _createElementVNode("p", _hoisted_44, "当前有 " + _toDisplayString(leaderboardRuleCount.value) + " 条规则计入榜单，可在各规则中单独开关。Premium 使用富文本表格，普通账号自动回退文本。", 1)
              ], 64))
            : _createCommentVNode("", true)
        ])
      ])
    ])
  ], 8, _hoisted_1))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-8dd19fa4"]]);

export { Config as default };
