import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,toDisplayString:_toDisplayString,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,vModelSelect:_vModelSelect,vShow:_vShow,createTextVNode:_createTextVNode,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "ep" };
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
const _hoisted_11 = { class: "row" };
const _hoisted_12 = { class: "grid" };
const _hoisted_13 = { class: "row" };
const _hoisted_14 = { class: "row" };
const _hoisted_15 = { class: "row" };
const _hoisted_16 = { class: "grid" };
const _hoisted_17 = { class: "row" };
const _hoisted_18 = { class: "row" };
const _hoisted_19 = { class: "card" };
const _hoisted_20 = { class: "row switch" };
const _hoisted_21 = { class: "row" };
const _hoisted_22 = ["value"];
const _hoisted_23 = { class: "row top" };
const _hoisted_24 = { class: "card" };
const _hoisted_25 = { class: "row" };
const _hoisted_26 = { class: "row" };
const _hoisted_27 = { class: "row" };
const _hoisted_28 = { class: "card" };
const _hoisted_29 = { class: "row" };
const _hoisted_30 = { class: "row" };
const _hoisted_31 = { class: "grid" };
const _hoisted_32 = { class: "row" };
const _hoisted_33 = { class: "row" };
const _hoisted_34 = { class: "row" };
const _hoisted_35 = ["value"];
const _hoisted_36 = { class: "row" };
const _hoisted_37 = { class: "row switch" };
const _hoisted_38 = { class: "card" };
const _hoisted_39 = { class: "row" };
const _hoisted_40 = { class: "row top" };
const _hoisted_41 = { class: "card" };
const _hoisted_42 = { class: "row switch" };
const _hoisted_43 = { class: "row top" };
const _hoisted_44 = { class: "row top" };
const _hoisted_45 = { class: "row top" };
const _hoisted_46 = { class: "row top" };
const _hoisted_47 = { class: "row top" };
const _hoisted_48 = { class: "savebar" };
const _hoisted_49 = ["disabled"];
const _hoisted_50 = ["disabled"];
const _hoisted_51 = { class: "pane" };
const _hoisted_52 = { class: "toolbar" };
const _hoisted_53 = { class: "muted" };
const _hoisted_54 = ["disabled"];
const _hoisted_55 = ["disabled"];
const _hoisted_56 = {
  key: 0,
  class: "muted"
};
const _hoisted_57 = {
  key: 1,
  class: "empty"
};
const _hoisted_58 = {
  key: 2,
  class: "cards"
};
const _hoisted_59 = {
  key: 0,
  class: "rimg-ph"
};
const _hoisted_60 = { class: "rbody" };
const _hoisted_61 = { class: "rname" };
const _hoisted_62 = {
  key: 0,
  class: "rep"
};
const _hoisted_63 = { class: "rmeta" };
const _hoisted_64 = { class: "rtag" };
const _hoisted_65 = { class: "rch" };
const _hoisted_66 = { class: "rtime" };

const {ref,reactive,onMounted} = await importShared('vue');


const TPL_VARS = '{{server_name}} {{status_text}} {{item_name}} {{episode_text}} {{genres}} {{cast}} {{rating}} {{release_date}} {{overview}} {{play_url}} {{tmdb_url}}';


const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

// AWEmbyPush · 配置/管理界面（模块联邦暴露为 ./Config）。
// 平台注入 props { pluginId, host }；host: getConfig/saveConfig/callApi/toast/token。
// 两个页签：配置（左侧 6 分组 + 右侧明细）/ 最近推送（战绩 + 测试推送）。
// 注：Webhook 入站地址由平台在配置弹窗底部独立展示，不在本组件内。
const props = __props;

const DEFAULTS = {
  enable_tmdb: true, tmdb_api_key: '', tmdb_api_domain: 'api.themoviedb.org',
  tmdb_image_domain: 'image.tmdb.org', emby_server_url: '',
  dedup_window: 60, episode_cache_timeout: 30,
  enable_watch_link: false, watch_link_type: 'server', link_redirect_prefix: '',
  tg_bot_token: '', tg_chat_id: '', tg_api_host: '',
  wx_corp_id: '', wx_corp_secret: '', wx_agent_id: '', wx_user_id: '@all',
  wx_msg_type: 'news_notice', wx_proxy_url: '', wx_no_proxy: true,
  bark_server: 'https://api.day.app', bark_keys: '',
  enable_custom_template: false, tg_template: '', wx_title_template: '',
  wx_body_template: '', bark_title_template: '', bark_body_template: '',
};

const GROUPS = [
  { key: 'base', label: '基础' },
  { key: 'watch', label: '观看链接', en: 'enable_watch_link' },
  { key: 'tg', label: 'Telegram' },
  { key: 'wx', label: '企业微信' },
  { key: 'bark', label: 'Bark' },
  { key: 'tpl', label: '自定义模板', en: 'enable_custom_template' },
];
const WATCH_TYPES = [
  { v: 'server', l: 'server（Emby/Jellyfin 直链）' },
  { v: 'forward', l: 'forward（Forward App）' },
  { v: 'infuse', l: 'infuse（Infuse）' },
];
const WX_MSG_TYPES = [
  { v: 'news_notice', l: 'news_notice（卡片）' },
  { v: 'news', l: 'news（图文）' },
];
// 模板可用变量说明（含双大括号，放 JS 常量里避免被 Vue 模板编译器当插值解析）。
const tab = ref('settings');
const group = ref('base');
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const cfg = reactive({ ...DEFAULTS });

const recent = ref([]);
const recentLoading = ref(false);

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

async function testPush() {
  testing.value = true;
  try {
    const r = await props.host.callApi('/test', { method: 'POST', body: {} });
    if (r.ok) props.host.toast.success(r.message || '已发送测试通知');
    else props.host.toast.error(r.message || '测试失败');
  } catch (e) { props.host.toast.error('测试失败：' + (e.message || e)); }
  finally { testing.value = false; }
}

async function loadRecent() {
  recentLoading.value = true;
  try {
    const r = await props.host.callApi('/recent');
    recent.value = r.items || [];
  } catch (e) { props.host.toast.error('读取推送记录失败：' + (e.message || e)); }
  finally { recentLoading.value = false; }
}
async function clearRecent() {
  if (!confirm('清空最近推送记录？')) return
  try {
    await props.host.callApi('/clear', { method: 'POST', body: {} });
    recent.value = [];
    props.host.toast.success('已清空');
  } catch (e) { props.host.toast.error('清空失败：' + (e.message || e)); }
}

function switchTab(t) {
  tab.value = t;
  if (t === 'recent' && !recent.value.length) loadRecent();
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
              class: _normalizeClass(['tab', { on: tab.value === 'recent' }]),
              onClick: _cache[1] || (_cache[1] = $event => (switchTab('recent')))
            }, "📮 最近推送", 2)
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_4, [
            _createElementVNode("aside", _hoisted_5, [
              _cache[30] || (_cache[30] = _createElementVNode("div", { class: "side-title" }, "设置分组", -1)),
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
              (group.value === 'base')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _cache[40] || (_cache[40] = _createElementVNode("h3", { class: "det-title" }, "基础", -1)),
                    _createElementVNode("section", _hoisted_9, [
                      _createElementVNode("label", _hoisted_10, [
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.enable_tmdb) = $event)),
                          type: "checkbox"
                        }, null, 512), [
                          [_vModelCheckbox, cfg.enable_tmdb]
                        ]),
                        _cache[31] || (_cache[31] = _createElementVNode("span", null, "TMDB 元数据增强", -1))
                      ]),
                      (cfg.enable_tmdb)
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                            _createElementVNode("label", _hoisted_11, [
                              _cache[32] || (_cache[32] = _createElementVNode("span", null, "TMDB API Key", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.tmdb_api_key) = $event)),
                                class: "inp",
                                type: "password",
                                placeholder: "留空则不做 TMDB 增强"
                              }, null, 512), [
                                [_vModelText, cfg.tmdb_api_key]
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_12, [
                              _createElementVNode("label", _hoisted_13, [
                                _cache[33] || (_cache[33] = _createElementVNode("span", null, "API 域名", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.tmdb_api_domain) = $event)),
                                  class: "inp"
                                }, null, 512), [
                                  [_vModelText, cfg.tmdb_api_domain]
                                ])
                              ]),
                              _createElementVNode("label", _hoisted_14, [
                                _cache[34] || (_cache[34] = _createElementVNode("span", null, "图片域名", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.tmdb_image_domain) = $event)),
                                  class: "inp"
                                }, null, 512), [
                                  [_vModelText, cfg.tmdb_image_domain]
                                ])
                              ])
                            ])
                          ], 64))
                        : _createCommentVNode("", true),
                      _createElementVNode("label", _hoisted_15, [
                        _cache[35] || (_cache[35] = _createElementVNode("span", null, "Emby 地址", -1)),
                        _withDirectives(_createElementVNode("input", {
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.emby_server_url) = $event)),
                          class: "inp",
                          placeholder: "https://your-emby.com（生成播放链接/图片降级）"
                        }, null, 512), [
                          [_vModelText, cfg.emby_server_url]
                        ])
                      ]),
                      _createElementVNode("div", _hoisted_16, [
                        _createElementVNode("label", _hoisted_17, [
                          _cache[36] || (_cache[36] = _createElementVNode("span", null, "去重窗口", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.dedup_window) = $event)),
                            class: "inp sm",
                            type: "number"
                          }, null, 512), [
                            [
                              _vModelText,
                              cfg.dedup_window,
                              void 0,
                              { number: true }
                            ]
                          ]),
                          _cache[37] || (_cache[37] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                        ]),
                        _createElementVNode("label", _hoisted_18, [
                          _cache[38] || (_cache[38] = _createElementVNode("span", null, "剧集合并等待", -1)),
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.episode_cache_timeout) = $event)),
                            class: "inp sm",
                            type: "number"
                          }, null, 512), [
                            [
                              _vModelText,
                              cfg.episode_cache_timeout,
                              void 0,
                              { number: true }
                            ]
                          ]),
                          _cache[39] || (_cache[39] = _createElementVNode("span", { class: "hint" }, "秒", -1))
                        ])
                      ])
                    ])
                  ], 64))
                : (group.value === 'watch')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[44] || (_cache[44] = _createElementVNode("h3", { class: "det-title" }, "观看链接", -1)),
                      _createElementVNode("section", _hoisted_19, [
                        _createElementVNode("label", _hoisted_20, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.enable_watch_link) = $event)),
                            type: "checkbox"
                          }, null, 512), [
                            [_vModelCheckbox, cfg.enable_watch_link]
                          ]),
                          _cache[41] || (_cache[41] = _createElementVNode("span", null, "生成观看按钮/链接", -1))
                        ]),
                        (cfg.enable_watch_link)
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                              _createElementVNode("label", _hoisted_21, [
                                _cache[42] || (_cache[42] = _createElementVNode("span", null, "播放链接类型", -1)),
                                _withDirectives(_createElementVNode("select", {
                                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.watch_link_type) = $event)),
                                  class: "inp"
                                }, [
                                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(WATCH_TYPES, (o) => {
                                    return _createElementVNode("option", {
                                      key: o.v,
                                      value: o.v
                                    }, _toDisplayString(o.l), 9, _hoisted_22)
                                  }), 64))
                                ], 512), [
                                  [_vModelSelect, cfg.watch_link_type]
                                ])
                              ]),
                              _createElementVNode("label", _hoisted_23, [
                                _cache[43] || (_cache[43] = _createElementVNode("span", null, "非HTTP中转前缀", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.link_redirect_prefix) = $event)),
                                  class: "inp",
                                  rows: "2",
                                  placeholder: "把 infuse:// 等包装成 http 按钮，支持 {url} 占位"
                                }, null, 512), [
                                  [_vModelText, cfg.link_redirect_prefix]
                                ])
                              ])
                            ], 64))
                          : _createCommentVNode("", true)
                      ])
                    ], 64))
                  : (group.value === 'tg')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                        _cache[48] || (_cache[48] = _createElementVNode("h3", { class: "det-title" }, "Telegram", -1)),
                        _createElementVNode("section", _hoisted_24, [
                          _createElementVNode("label", _hoisted_25, [
                            _cache[45] || (_cache[45] = _createElementVNode("span", null, "Bot Token", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.tg_bot_token) = $event)),
                              class: "inp",
                              type: "password",
                              placeholder: "@BotFather 获取，可填平台机器人 token"
                            }, null, 512), [
                              [_vModelText, cfg.tg_bot_token]
                            ])
                          ]),
                          _createElementVNode("label", _hoisted_26, [
                            _cache[46] || (_cache[46] = _createElementVNode("span", null, "Chat ID", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.tg_chat_id) = $event)),
                              class: "inp",
                              placeholder: "目标用户或群组 ID"
                            }, null, 512), [
                              [_vModelText, cfg.tg_chat_id]
                            ])
                          ]),
                          _createElementVNode("label", _hoisted_27, [
                            _cache[47] || (_cache[47] = _createElementVNode("span", null, "API Host", -1)),
                            _withDirectives(_createElementVNode("input", {
                              "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.tg_api_host) = $event)),
                              class: "inp",
                              placeholder: "留空=官方；自建反代可改"
                            }, null, 512), [
                              [_vModelText, cfg.tg_api_host]
                            ])
                          ])
                        ])
                      ], 64))
                    : (group.value === 'wx')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[56] || (_cache[56] = _createElementVNode("h3", { class: "det-title" }, "企业微信", -1)),
                          _createElementVNode("section", _hoisted_28, [
                            _createElementVNode("label", _hoisted_29, [
                              _cache[49] || (_cache[49] = _createElementVNode("span", null, "Corp ID", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.wx_corp_id) = $event)),
                                class: "inp"
                              }, null, 512), [
                                [_vModelText, cfg.wx_corp_id]
                              ])
                            ]),
                            _createElementVNode("label", _hoisted_30, [
                              _cache[50] || (_cache[50] = _createElementVNode("span", null, "Corp Secret", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.wx_corp_secret) = $event)),
                                class: "inp",
                                type: "password"
                              }, null, 512), [
                                [_vModelText, cfg.wx_corp_secret]
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_31, [
                              _createElementVNode("label", _hoisted_32, [
                                _cache[51] || (_cache[51] = _createElementVNode("span", null, "Agent ID", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.wx_agent_id) = $event)),
                                  class: "inp"
                                }, null, 512), [
                                  [_vModelText, cfg.wx_agent_id]
                                ])
                              ]),
                              _createElementVNode("label", _hoisted_33, [
                                _cache[52] || (_cache[52] = _createElementVNode("span", null, "接收用户", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((cfg.wx_user_id) = $event)),
                                  class: "inp",
                                  placeholder: "@all"
                                }, null, 512), [
                                  [_vModelText, cfg.wx_user_id]
                                ])
                              ])
                            ]),
                            _createElementVNode("label", _hoisted_34, [
                              _cache[53] || (_cache[53] = _createElementVNode("span", null, "消息类型", -1)),
                              _withDirectives(_createElementVNode("select", {
                                "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((cfg.wx_msg_type) = $event)),
                                class: "inp"
                              }, [
                                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(WX_MSG_TYPES, (o) => {
                                  return _createElementVNode("option", {
                                    key: o.v,
                                    value: o.v
                                  }, _toDisplayString(o.l), 9, _hoisted_35)
                                }), 64))
                              ], 512), [
                                [_vModelSelect, cfg.wx_msg_type]
                              ])
                            ]),
                            _createElementVNode("label", _hoisted_36, [
                              _cache[54] || (_cache[54] = _createElementVNode("span", null, "API 地址", -1)),
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((cfg.wx_proxy_url) = $event)),
                                class: "inp",
                                placeholder: "留空=官方；自建反代可改"
                              }, null, 512), [
                                [_vModelText, cfg.wx_proxy_url]
                              ])
                            ]),
                            _createElementVNode("label", _hoisted_37, [
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((cfg.wx_no_proxy) = $event)),
                                type: "checkbox"
                              }, null, 512), [
                                [_vModelCheckbox, cfg.wx_no_proxy]
                              ]),
                              _cache[55] || (_cache[55] = _createElementVNode("span", null, "企微请求不走代理", -1))
                            ])
                          ])
                        ], 64))
                      : (group.value === 'bark')
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _cache[59] || (_cache[59] = _createElementVNode("h3", { class: "det-title" }, "Bark", -1)),
                            _createElementVNode("section", _hoisted_38, [
                              _createElementVNode("label", _hoisted_39, [
                                _cache[57] || (_cache[57] = _createElementVNode("span", null, "Bark 服务器", -1)),
                                _withDirectives(_createElementVNode("input", {
                                  "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((cfg.bark_server) = $event)),
                                  class: "inp"
                                }, null, 512), [
                                  [_vModelText, cfg.bark_server]
                                ])
                              ]),
                              _createElementVNode("label", _hoisted_40, [
                                _cache[58] || (_cache[58] = _createElementVNode("span", null, "设备 Key", -1)),
                                _withDirectives(_createElementVNode("textarea", {
                                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((cfg.bark_keys) = $event)),
                                  class: "inp",
                                  rows: "2",
                                  placeholder: "多个 Key 用英文逗号分隔；留空不启用 Bark"
                                }, null, 512), [
                                  [_vModelText, cfg.bark_keys]
                                ])
                              ])
                            ])
                          ], 64))
                        : (group.value === 'tpl')
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
                              _cache[66] || (_cache[66] = _createElementVNode("h3", { class: "det-title" }, "自定义推送模板（测试）", -1)),
                              _createElementVNode("section", _hoisted_41, [
                                _createElementVNode("label", _hoisted_42, [
                                  _withDirectives(_createElementVNode("input", {
                                    "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((cfg.enable_custom_template) = $event)),
                                    type: "checkbox"
                                  }, null, 512), [
                                    [_vModelCheckbox, cfg.enable_custom_template]
                                  ]),
                                  _cache[60] || (_cache[60] = _createElementVNode("span", null, "启用自定义推送模板（测试中，不建议生产）", -1))
                                ]),
                                (cfg.enable_custom_template)
                                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                      _createElementVNode("p", { class: "tip" }, "变量：" + _toDisplayString(TPL_VARS) + "；留空用默认。"),
                                      _createElementVNode("label", _hoisted_43, [
                                        _cache[61] || (_cache[61] = _createElementVNode("span", null, "TG 模板(HTML)", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((cfg.tg_template) = $event)),
                                          class: "inp",
                                          rows: "4"
                                        }, null, 512), [
                                          [_vModelText, cfg.tg_template]
                                        ])
                                      ]),
                                      _createElementVNode("label", _hoisted_44, [
                                        _cache[62] || (_cache[62] = _createElementVNode("span", null, "企微标题", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((cfg.wx_title_template) = $event)),
                                          class: "inp",
                                          rows: "2"
                                        }, null, 512), [
                                          [_vModelText, cfg.wx_title_template]
                                        ])
                                      ]),
                                      _createElementVNode("label", _hoisted_45, [
                                        _cache[63] || (_cache[63] = _createElementVNode("span", null, "企微正文", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((cfg.wx_body_template) = $event)),
                                          class: "inp",
                                          rows: "3"
                                        }, null, 512), [
                                          [_vModelText, cfg.wx_body_template]
                                        ])
                                      ]),
                                      _createElementVNode("label", _hoisted_46, [
                                        _cache[64] || (_cache[64] = _createElementVNode("span", null, "Bark 标题", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((cfg.bark_title_template) = $event)),
                                          class: "inp",
                                          rows: "2"
                                        }, null, 512), [
                                          [_vModelText, cfg.bark_title_template]
                                        ])
                                      ]),
                                      _createElementVNode("label", _hoisted_47, [
                                        _cache[65] || (_cache[65] = _createElementVNode("span", null, "Bark 正文", -1)),
                                        _withDirectives(_createElementVNode("textarea", {
                                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((cfg.bark_body_template) = $event)),
                                          class: "inp",
                                          rows: "3"
                                        }, null, 512), [
                                          [_vModelText, cfg.bark_body_template]
                                        ])
                                      ])
                                    ], 64))
                                  : _createCommentVNode("", true)
                              ])
                            ], 64))
                          : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_48, [
                _createElementVNode("button", {
                  class: "btn",
                  disabled: testing.value,
                  onClick: testPush
                }, _toDisplayString(testing.value ? '发送中…' : '测试推送'), 9, _hoisted_49),
                _createElementVNode("button", {
                  class: "btn primary lg",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_50)
              ])
            ])
          ], 512), [
            [_vShow, tab.value === 'settings']
          ]),
          _withDirectives(_createElementVNode("div", _hoisted_51, [
            _createElementVNode("div", _hoisted_52, [
              _createElementVNode("span", _hoisted_53, "最近 " + _toDisplayString(recent.value.length) + " 条推送", 1),
              _cache[67] || (_cache[67] = _createElementVNode("span", { class: "grow" }, null, -1)),
              _createElementVNode("button", {
                class: "btn",
                disabled: testing.value,
                onClick: testPush
              }, _toDisplayString(testing.value ? '发送中…' : '测试推送'), 9, _hoisted_54),
              _createElementVNode("button", {
                class: "btn",
                onClick: loadRecent
              }, "刷新"),
              _createElementVNode("button", {
                class: "btn danger",
                disabled: !recent.value.length,
                onClick: clearRecent
              }, "清空", 8, _hoisted_55)
            ]),
            (recentLoading.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_56, "加载中…"))
              : (!recent.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_57, [...(_cache[68] || (_cache[68] = [
                    _createTextVNode("暂无推送记录", -1),
                    _createElementVNode("br", null, null, -1),
                    _createElementVNode("span", { class: "muted" }, "Emby/Jellyfin 入库并成功推送后，这里会显示最近 10 条", -1)
                  ]))]))
                : (_openBlock(), _createElementBlock("div", _hoisted_58, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recent.value, (r, i) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: i,
                        class: "rcard"
                      }, [
                        _createElementVNode("div", {
                          class: "rimg",
                          style: _normalizeStyle(r.image_url ? { backgroundImage: `url(${r.image_url})` } : {})
                        }, [
                          (!r.image_url)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_59, _toDisplayString(r.item_type === 'TV' ? '📺' : '🎬'), 1))
                            : _createCommentVNode("", true)
                        ], 4),
                        _createElementVNode("div", _hoisted_60, [
                          _createElementVNode("div", _hoisted_61, _toDisplayString(r.item_name), 1),
                          (r.episode_text)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_62, _toDisplayString(r.episode_text), 1))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_63, [
                            _createElementVNode("span", _hoisted_64, _toDisplayString(r.item_type === 'TV' ? '剧集' : '电影'), 1),
                            _createElementVNode("span", _hoisted_65, _toDisplayString(r.channels || '—'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_66, _toDisplayString(r.time), 1)
                        ])
                      ]))
                    }), 128))
                  ]))
          ], 512), [
            [_vShow, tab.value === 'recent']
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-bf16d1cd"]]);

export { Config as default };
