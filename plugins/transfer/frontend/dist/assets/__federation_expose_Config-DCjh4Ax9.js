import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,vModelSelect:_vModelSelect,withDirectives:_withDirectives,vModelText:_vModelText,vModelCheckbox:_vModelCheckbox,vShow:_vShow,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "tf" };
const _hoisted_2 = {
  key: 0,
  class: "muted"
};
const _hoisted_3 = { class: "tabs" };
const _hoisted_4 = { class: "layout" };
const _hoisted_5 = { class: "sidebar" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "detail" };
const _hoisted_8 = { class: "site-h" };
const _hoisted_9 = { class: "site-name" };
const _hoisted_10 = { class: "site-bonus" };
const _hoisted_11 = {
  key: 0,
  class: "site-note"
};
const _hoisted_12 = { class: "chips" };
const _hoisted_13 = ["checked", "onChange"];
const _hoisted_14 = { class: "card" };
const _hoisted_15 = { class: "row" };
const _hoisted_16 = ["value"];
const _hoisted_17 = { class: "row" };
const _hoisted_18 = { class: "row" };
const _hoisted_19 = { class: "card" };
const _hoisted_20 = { class: "grid" };
const _hoisted_21 = { class: "row" };
const _hoisted_22 = { class: "row" };
const _hoisted_23 = { class: "card" };
const _hoisted_24 = { class: "row" };
const _hoisted_25 = ["value"];
const _hoisted_26 = { class: "row switch" };
const _hoisted_27 = { class: "savebar" };
const _hoisted_28 = ["disabled"];
const _hoisted_29 = { class: "pane" };
const _hoisted_30 = { class: "toolbar" };
const _hoisted_31 = {
  key: 0,
  value: ""
};
const _hoisted_32 = ["value"];
const _hoisted_33 = { class: "seg" };
const _hoisted_34 = ["disabled"];
const _hoisted_35 = {
  key: 0,
  class: "muted"
};
const _hoisted_36 = {
  key: 1,
  class: "empty"
};
const _hoisted_37 = {
  key: 2,
  class: "tbl"
};
const _hoisted_38 = { class: "rank" };
const _hoisted_39 = { class: "muted" };
const _hoisted_40 = {
  key: 3,
  class: "hist"
};
const _hoisted_41 = { class: "hist-h" };
const _hoisted_42 = { class: "tbl" };
const _hoisted_43 = { class: "muted" };
const _hoisted_44 = { class: "muted" };

const {ref,reactive,onMounted,computed} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

// 多站点转账 · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（站点开关矩阵 + 排行榜/延迟/进阶）/ 排行榜（查看各站点榜单、最近流水、清空）。
const props = __props;

// 站点（key 对应 config 字段；群组/bot 平台内置写死，这里只开关功能）
const SITES = [
  { key: 'site_audiences', label: 'Audiences', bonus: '爆米花' },
  { key: 'site_hddolby', label: 'HDDolby', bonus: '鲸币' },
  { key: 'site_azusa', label: 'Azusa', bonus: '魔力值' },
  { key: 'site_zm', label: 'ZmPT', bonus: '电力', note: '致谢/榜单自动延后约11秒发出' },
  { key: 'site_springsunday', label: 'SpringSunday', bonus: '茉莉', note: '含两个群' },
  { key: 'site_hdsky', label: 'HDSky', bonus: '银元' },
  { key: 'site_mocktest', label: 'MockTest', bonus: '测试', note: '默认关' },
];
const TOGGLES = [
  { v: 'on', l: '启用' }, { v: 'notify', l: '群内致谢' },
  { v: 'lb_in', l: '打赏榜' }, { v: 'lb_out', l: '赏赐榜' },
];
const RANK_OUTPUTS = [
  { v: 'image', l: '图片（默认）' },
  { v: 'text', l: '文本' },
];
const SSD_MODES = [{ v: 'off', l: '关闭' }, { v: 'once', l: '单次确认' }, { v: '5min', l: '5分钟确认' }];

const DEFAULTS = {
  site_audiences: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hddolby: ['on', 'notify', 'lb_in', 'lb_out'],
  site_azusa: ['on', 'notify', 'lb_in', 'lb_out'],
  site_zm: ['on', 'notify', 'lb_in', 'lb_out'],
  site_springsunday: ['on', 'notify', 'lb_in', 'lb_out'],
  site_hdsky: ['on', 'notify', 'lb_in', 'lb_out'],
  site_mocktest: [],
  rank_output: 'image', rank_size: 10, rank_command: '转账排行',
  notify_delay_min: 0, notify_delay_max: 0,
  ssd_click_mode: 'off', owner_notify: false,
};

const GROUPS = [
  { key: 'sites', label: '站点' },
  { key: 'rank', label: '排行榜' },
  { key: 'delay', label: '致谢延迟' },
  { key: 'adv', label: '进阶' },
];

const tab = ref('settings');
const group = ref('sites');
const loading = ref(true);
const saving = ref(false);
const cfg = reactive({ ...DEFAULTS });

// 排行榜面板
const sites = ref([]);
const lbSite = ref('');
const lbDir = ref('in');
const lbRows = ref([]);
const lbLoading = ref(false);
const recent = ref([]);

onMounted(async () => {
  try {
    const saved = await props.host.getConfig();
    Object.assign(cfg, DEFAULTS, saved || {});
    if (!RANK_OUTPUTS.some(o => o.v === cfg.rank_output)) cfg.rank_output = 'text';
    for (const s of SITES) if (!Array.isArray(cfg[s.key])) cfg[s.key] = [];
  } catch (e) {
    props.host.toast.error('读取配置失败：' + (e.message || e));
  } finally {
    loading.value = false;
  }
});

function has(key, v) { return (cfg[key] || []).includes(v) }
function toggle(key, v) {
  const arr = (cfg[key] || []).slice();
  const i = arr.indexOf(v);
  if (i >= 0) arr.splice(i, 1);
  else arr.push(v);
  cfg[key] = arr;
}

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

// ── 排行榜面板 ──
async function loadSites() {
  try {
    const r = await props.host.callApi('/sites');
    sites.value = r.sites || [];
    if (!lbSite.value && sites.value.length) {
      const withData = sites.value.find(s => s.has_data) || sites.value[0];
      lbSite.value = withData.name;
    }
    await loadLeaderboard();
    await loadRecent();
  } catch (e) {
    props.host.toast.error('读取站点失败：' + (e.message || e));
  }
}
async function loadLeaderboard() {
  if (!lbSite.value) { lbRows.value = []; return }
  lbLoading.value = true;
  try {
    const r = await props.host.callApi(`/leaderboard?site=${encodeURIComponent(lbSite.value)}&dir=${lbDir.value}&limit=${cfg.rank_size || 10}`);
    lbRows.value = r.items || [];
  } catch (e) {
    props.host.toast.error('读取排行榜失败：' + (e.message || e));
  } finally {
    lbLoading.value = false;
  }
}
async function loadRecent() {
  try {
    const r = await props.host.callApi('/recent');
    recent.value = r.items || [];
  } catch (e) { /* 流水拉取失败不致命 */ }
}
const bonusOf = computed(() => {
  const s = sites.value.find(x => x.name === lbSite.value);
  return s ? s.bonus : ''
});
async function resetSite() {
  if (!lbSite.value) return
  if (!confirm(`清空站点「${lbSite.value}」的全部转账记录与排行榜？此操作不可恢复。`)) return
  try {
    await props.host.callApi('/reset', { method: 'POST', body: { site: lbSite.value } });
    lbRows.value = [];
    props.host.toast.success('已清空');
    await loadSites();
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)); }
}
function fmtTime(ts) { return String(ts || '').replace('T', ' ').slice(0, 16) }

function switchTab(t) {
  tab.value = t;
  if (t === 'rank' && !sites.value.length) loadSites();
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
              class: _normalizeClass(['tab', { on: tab.value === 'rank' }]),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('rank')))
            }, "🏆 排行榜", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", _hoisted_5, [
              _cache[12] || (_cache[12] = _createElementVNode("div", { class: "side-title" }, "设置分组", -1)),
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
              (group.value === 'sites')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _cache[13] || (_cache[13] = _createElementVNode("h3", { class: "det-title" }, "站点开关", -1)),
                    _cache[14] || (_cache[14] = _createElementVNode("p", { class: "tip" }, "群组/转账bot 平台内置写死，这里只按站点开关功能：启用=监听记录；群内致谢=收/发后群里回一句；打赏榜/赏赐榜=致谢里附转入/转出排行榜。", -1)),
                    (_openBlock(), _createElementBlock(_Fragment, null, _renderList(SITES, (s) => {
                      return _createElementVNode("section", {
                        key: s.key,
                        class: "card site"
                      }, [
                        _createElementVNode("div", _hoisted_8, [
                          _createElementVNode("span", _hoisted_9, _toDisplayString(s.label), 1),
                          _createElementVNode("span", _hoisted_10, _toDisplayString(s.bonus), 1),
                          (s.note)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_11, _toDisplayString(s.note), 1))
                            : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("div", _hoisted_12, [
                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(TOGGLES, (t) => {
                            return _createElementVNode("label", {
                              key: t.v,
                              class: _normalizeClass(['chip', { on: has(s.key, t.v) }])
                            }, [
                              _createElementVNode("input", {
                                type: "checkbox",
                                checked: has(s.key, t.v),
                                onChange: $event => (toggle(s.key, t.v))
                              }, null, 40, _hoisted_13),
                              _createTextVNode(_toDisplayString(t.l), 1)
                            ], 2)
                          }), 64))
                        ])
                      ])
                    }), 64))
                  ], 64))
                : (group.value === 'rank')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[20] || (_cache[20] = _createElementVNode("h3", { class: "det-title" }, "排行榜", -1)),
                      _createElementVNode("section", _hoisted_14, [
                        _createElementVNode("label", _hoisted_15, [
                          _cache[15] || (_cache[15] = _createElementVNode("span", null, "输出形式", -1)),
                          _withDirectives(_createElementVNode("select", {
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.rank_output) = $event)),
                            class: "inp"
                          }, [
                            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(RANK_OUTPUTS, (o) => {
                              return _createElementVNode("option", {
                                key: o.v,
                                value: o.v
                              }, _toDisplayString(o.l), 9, _hoisted_16)
                            }), 64))
                          ], 512), [
                            [_vModelSelect, cfg.rank_output]
                          ])
                        ]),
                        _cache[18] || (_cache[18] = _createElementVNode("p", { class: "tip" }, "图片生成或发送失败时会自动回退为文本排行榜。", -1)),
                        _createElementVNode("label", _hoisted_17, [
                          _cache[16] || (_cache[16] = _createElementVNode("span", null, "排行榜人数", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.rank_size) = $event)),
                            class: "inp sm",
                            type: "number",
                            min: "3",
                            max: "30"
                          }, null, 512), [
                            [
                              _vModelText,
                              cfg.rank_size,
                              void 0,
                              { number: true }
                            ]
                          ])
                        ]),
                        _createElementVNode("label", _hoisted_18, [
                          _cache[17] || (_cache[17] = _createElementVNode("span", null, "命令词", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.rank_command) = $event)),
                            class: "inp"
                          }, null, 512), [
                            [_vModelText, cfg.rank_command]
                          ])
                        ]),
                        _cache[19] || (_cache[19] = _createElementVNode("p", { class: "tip" }, "在任意聊天发「.命令词 [站点] [in/out]」拉排行榜，如 .转账排行 hdsky in。", -1))
                      ])
                    ], 64))
                  : (group.value === 'delay')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                        _cache[26] || (_cache[26] = _createElementVNode("h3", { class: "det-title" }, "致谢延迟", -1)),
                        _createElementVNode("section", _hoisted_19, [
                          _cache[25] || (_cache[25] = _createElementVNode("p", { class: "tip" }, "记录到转账后等待若干秒再发致谢，模拟人工（0=不等）。", -1)),
                          _createElementVNode("div", _hoisted_20, [
                            _createElementVNode("label", _hoisted_21, [
                              _cache[21] || (_cache[21] = _createElementVNode("span", null, "最小", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.notify_delay_min) = $event)),
                                class: "inp sm",
                                type: "number",
                                min: "0",
                                max: "300"
                              }, null, 512), [
                                [
                                  _vModelText,
                                  cfg.notify_delay_min,
                                  void 0,
                                  { number: true }
                                ]
                              ]),
                              _cache[22] || (_cache[22] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                            ]),
                            _createElementVNode("label", _hoisted_22, [
                              _cache[23] || (_cache[23] = _createElementVNode("span", null, "最大", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.notify_delay_max) = $event)),
                                class: "inp sm",
                                type: "number",
                                min: "0",
                                max: "300"
                              }, null, 512), [
                                [
                                  _vModelText,
                                  cfg.notify_delay_max,
                                  void 0,
                                  { number: true }
                                ]
                              ]),
                              _cache[24] || (_cache[24] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                            ])
                          ])
                        ])
                      ], 64))
                    : (group.value === 'adv')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[30] || (_cache[30] = _createElementVNode("h3", { class: "det-title" }, "进阶", -1)),
                          _createElementVNode("section", _hoisted_23, [
                            _createElementVNode("label", _hoisted_24, [
                              _cache[27] || (_cache[27] = _createElementVNode("span", null, "SSD 大额自动确认", -1)),
                              _withDirectives(_createElementVNode("select", {
                                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.ssd_click_mode) = $event)),
                                class: "inp"
                              }, [
                                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(SSD_MODES, (o) => {
                                  return _createElementVNode("option", {
                                    key: o.v,
                                    value: o.v
                                  }, _toDisplayString(o.l), 9, _hoisted_25)
                                }), 64))
                              ], 512), [
                                [_vModelSelect, cfg.ssd_click_mode]
                              ])
                            ]),
                            _cache[29] || (_cache[29] = _createElementVNode("p", { class: "tip" }, "SpringSunday 大额转账时 bot 会要你点确认按钮，开启后自动点。", -1)),
                            _createElementVNode("label", _hoisted_26, [
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.owner_notify) = $event)),
                                type: "checkbox"
                              }, null, 512), [
                                [_vModelCheckbox, cfg.owner_notify]
                              ]),
                              _cache[28] || (_cache[28] = _createElementVNode("span", null, "每笔转账推送给平台主人", -1))
                            ])
                          ])
                        ], 64))
                      : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_27, [
                _createElementVNode("button", {
                  class: "btn primary lg",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_28)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_29, [
            _createElementVNode("div", _hoisted_30, [
              _withDirectives(_createElementVNode("select", {
                "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((lbSite).value = $event)),
                class: "inp sm2",
                onChange: loadLeaderboard
              }, [
                (!sites.value.length)
                  ? (_openBlock(), _createElementBlock("option", _hoisted_31, "（无数据）"))
                  : _createCommentVNode("", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sites.value, (s) => {
                  return (_openBlock(), _createElementBlock("option", {
                    key: s.name,
                    value: s.name
                  }, _toDisplayString(s.name) + _toDisplayString(s.has_data ? '' : '（空）'), 9, _hoisted_32))
                }), 128))
              ], 544), [
                [_vModelSelect, lbSite.value]
              ]),
              _createElementVNode("div", _hoisted_33, [
                _createElementVNode("button", {
                  class: _normalizeClass(['segbtn', { on: lbDir.value === 'in' }]),
                  onClick: _cache[10] || (_cache[10] = $event => {lbDir.value = 'in'; loadLeaderboard();})
                }, "打赏榜(转入)", 2),
                _createElementVNode("button", {
                  class: _normalizeClass(['segbtn', { on: lbDir.value === 'out' }]),
                  onClick: _cache[11] || (_cache[11] = $event => {lbDir.value = 'out'; loadLeaderboard();})
                }, "赏赐榜(转出)", 2)
              ]),
              _cache[31] || (_cache[31] = _createElementVNode("span", { class: "grow" }, null, -1)),
              _createElementVNode("button", {
                class: "btn",
                onClick: loadSites
              }, "刷新"),
              _createElementVNode("button", {
                class: "btn danger",
                disabled: !lbSite.value,
                onClick: resetSite
              }, "清空该站", 8, _hoisted_34)
            ]),
            (lbLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_35, "加载中…"))
              : (!lbRows.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_36, "该站点暂无" + _toDisplayString(lbDir.value === 'in' ? '转入' : '转出') + "数据", 1))
                : (_openBlock(), _createElementBlock("table", _hoisted_37, [
                    _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _cache[32] || (_cache[32] = _createElementVNode("th", null, "名次", -1)),
                        _cache[33] || (_cache[33] = _createElementVNode("th", null, "用户", -1)),
                        _createElementVNode("th", null, "累计" + _toDisplayString(bonusOf.value), 1),
                        _cache[34] || (_cache[34] = _createElementVNode("th", null, "笔数", -1))
                      ])
                    ]),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(lbRows.value, (r) => {
                        return (_openBlock(), _createElementBlock("tr", {
                          key: r.rank
                        }, [
                          _createElementVNode("td", _hoisted_38, _toDisplayString(r.rank <= 3 ? ['🥇','🥈','🥉'][r.rank-1] : r.rank), 1),
                          _createElementVNode("td", null, _toDisplayString(r.user_name), 1),
                          _createElementVNode("td", null, _toDisplayString(r.total), 1),
                          _createElementVNode("td", _hoisted_39, _toDisplayString(r.count), 1)
                        ]))
                      }), 128))
                    ])
                  ])),
            (recent.value.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_40, [
                  _createElementVNode("div", _hoisted_41, "最近流水（" + _toDisplayString(recent.value.length) + " 条）", 1),
                  _createElementVNode("table", _hoisted_42, [
                    _cache[35] || (_cache[35] = _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _createElementVNode("th", null, "站点"),
                        _createElementVNode("th", null, "方向"),
                        _createElementVNode("th", null, "用户"),
                        _createElementVNode("th", null, "金额"),
                        _createElementVNode("th", null, "时间")
                      ])
                    ], -1)),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recent.value, (r, i) => {
                        return (_openBlock(), _createElementBlock("tr", { key: i }, [
                          _createElementVNode("td", _hoisted_43, _toDisplayString(r.site), 1),
                          _createElementVNode("td", null, [
                            _createElementVNode("span", {
                              style: _normalizeStyle({ color: r.direction === 'in' ? '#6ee7a8' : '#6ea8fe' })
                            }, _toDisplayString(r.direction === 'in' ? '转入' : '转出'), 5)
                          ]),
                          _createElementVNode("td", null, _toDisplayString(r.user_name), 1),
                          _createElementVNode("td", null, _toDisplayString(r.amount), 1),
                          _createElementVNode("td", _hoisted_44, _toDisplayString(fmtTime(r.ts)), 1)
                        ]))
                      }), 128))
                    ])
                  ])
                ]))
              : _createCommentVNode("", true)
          ], 512), [
            [_vShow, tab.value === 'rank']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-97343612"]]);

export { Config as default };
