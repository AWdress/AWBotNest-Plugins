import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelText:_vModelText,withDirectives:_withDirectives,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,vModelCheckbox:_vModelCheckbox,vModelDynamic:_vModelDynamic} = await importShared('vue');


const _hoisted_1 = { class: "movie-monitor-config" };
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
const _hoisted_8 = { class: "fld" };
const _hoisted_9 = { class: "chips" };
const _hoisted_10 = { class: "chip" };
const _hoisted_11 = ["checked"];
const _hoisted_12 = { class: "chip" };
const _hoisted_13 = ["checked"];
const _hoisted_14 = { class: "row switch" };
const _hoisted_15 = { class: "section" };
const _hoisted_16 = { class: "row" };
const _hoisted_17 = { class: "secret-field" };
const _hoisted_18 = ["type"];
const _hoisted_19 = { class: "row" };
const _hoisted_20 = { class: "section" };
const _hoisted_21 = { class: "row" };
const _hoisted_22 = { class: "row" };
const _hoisted_23 = { class: "secret-field" };
const _hoisted_24 = ["type"];
const _hoisted_25 = { class: "row switch" };
const _hoisted_26 = { class: "section" };
const _hoisted_27 = { class: "row" };
const _hoisted_28 = { class: "row" };
const _hoisted_29 = { class: "row switch" };
const _hoisted_30 = { class: "section" };
const _hoisted_31 = { class: "row" };
const _hoisted_32 = { class: "secret-field" };
const _hoisted_33 = ["type"];
const _hoisted_34 = ["disabled"];
const _hoisted_35 = {
  key: 1,
  class: "status"
};
const _hoisted_36 = { class: "card" };
const _hoisted_37 = { class: "kv" };
const _hoisted_38 = { class: "kv" };
const _hoisted_39 = { class: "kv" };
const _hoisted_40 = ["disabled"];
const _hoisted_41 = {
  key: 2,
  class: "logs"
};
const _hoisted_42 = { class: "toolbar" };
const _hoisted_43 = { class: "muted" };
const _hoisted_44 = { class: "tbl" };
const _hoisted_45 = { class: "muted" };
const _hoisted_46 = { class: "tmdb-id" };
const _hoisted_47 = { key: 0 };

const {ref,computed,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { pluginId: { type: String, required: true }, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const cfg = ref({
  monitor_ids: '', media_types: ['movie', 'tv'], only_complete_series: false,
  tmdb_api_key: '', tmdb_language: 'zh-CN',
  emby_url: '', emby_api_key: '', skip_emby_check: false,
  cms_bot_username: '', forward_label: '115 网盘', forward_to_saved: false,
  pan115_cookie: '',
});
const tab = ref('settings');
const saving = ref(false);
const secretVisible = ref({ tmdb_api_key: false, emby_api_key: false, pan115_cookie: false });
const status = ref({});
const testing = ref(false);
const testResult = ref(null);
const logs = ref([]);
const chatNames = ref([]);

const mediaTypes = computed({
  get: () => Array.isArray(cfg.value.media_types) ? cfg.value.media_types : [],
  set: (v) => { cfg.value.media_types = v; },
});

function toggleMedia(type) {
  const arr = mediaTypes.value;
  const i = arr.indexOf(type);
  if (i >= 0) arr.splice(i, 1); else arr.push(type);
}

onMounted(async () => {
  try { const saved = await props.host.getConfig() || {}; for (const field of Object.keys(secretVisible.value)) { if (saved[field] === '********') saved[field] = await props.host.revealSecret(field); } Object.assign(cfg.value, saved); }
  catch (e) { props.host.toast.error('读取配置失败：' + (e.message || e)); }
  await Promise.all([loadStatus(), loadLogs(), loadChatNames()]);
});

async function save() {
  saving.value = true;
  try {
    // 保留旧版运行开关的兼容值；插件整体启停由平台卡片管理。
    await props.host.saveConfig({ ...cfg.value, shareswitch: true });
    await loadChatNames();
    props.host.toast.success('配置已保存');
  } catch (e) {
    props.host.toast.error('保存失败：' + (e.message || e));
  } finally {
    saving.value = false;
  }
}

async function loadChatNames() {
  try {
    const r = await props.host.callApi('/chat_names');
    chatNames.value = r.items || [];
  } catch {}
}

async function loadStatus() {
  try {
    const r = await props.host.callApi('/status');
    status.value = r;
  } catch {}
}

async function testServices() {
  testing.value = true;
  testResult.value = null;
  try {
    const r = await props.host.callApi('/test', { method: 'POST' });
    testResult.value = r;
    loadStatus();
  } catch (e) {
    testResult.value = { ok: false, message: '测试失败：' + e.message };
  } finally {
    testing.value = false;
  }
}

async function loadLogs() {
  try {
    const r = await props.host.callApi('/logs');
    logs.value = r.logs || [];
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
        class: _normalizeClass({ active: tab.value === 'logs' }),
        onClick: _cache[2] || (_cache[2] = $event => (tab.value = 'logs'))
      }, "📝 处理记录", 2)
    ]),
    _createElementVNode("div", _hoisted_3, [
      (tab.value === 'settings')
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[25] || (_cache[25] = _createElementVNode("h3", null, "监控范围", -1)),
              _createElementVNode("label", _hoisted_6, [
                _cache[19] || (_cache[19] = _createElementVNode("span", null, "监控频道/群组", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.value.monitor_ids) = $event)),
                  class: "inp",
                  placeholder: "留空=监控所有会话，多个 ID 用逗号分隔"
                }, null, 512), [
                  [_vModelText, cfg.value.monitor_ids]
                ])
              ]),
              (chatNames.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                    _cache[20] || (_cache[20] = _createElementVNode("span", { class: "chat-label" }, "已识别：", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(chatNames.value, (item) => {
                      return (_openBlock(), _createElementBlock("span", {
                        key: item.id,
                        class: "chat-name"
                      }, _toDisplayString(item.title) + " (" + _toDisplayString(item.id) + ")", 1))
                    }), 128))
                  ]))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_8, [
                _cache[23] || (_cache[23] = _createElementVNode("span", { class: "lbl" }, "转存类型", -1)),
                _createElementVNode("div", _hoisted_9, [
                  _createElementVNode("label", _hoisted_10, [
                    _createElementVNode("input", {
                      type: "checkbox",
                      checked: mediaTypes.value.includes('movie'),
                      onChange: _cache[4] || (_cache[4] = $event => (toggleMedia('movie')))
                    }, null, 40, _hoisted_11),
                    _cache[21] || (_cache[21] = _createTextVNode("电影", -1))
                  ]),
                  _createElementVNode("label", _hoisted_12, [
                    _createElementVNode("input", {
                      type: "checkbox",
                      checked: mediaTypes.value.includes('tv'),
                      onChange: _cache[5] || (_cache[5] = $event => (toggleMedia('tv')))
                    }, null, 40, _hoisted_13),
                    _cache[22] || (_cache[22] = _createTextVNode("电视剧", -1))
                  ])
                ])
              ]),
              _createElementVNode("label", _hoisted_14, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.only_complete_series) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.only_complete_series]
                ]),
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "剧集仅转存完结", -1))
              ])
            ]),
            _createElementVNode("div", _hoisted_15, [
              _cache[29] || (_cache[29] = _createElementVNode("h3", null, "TMDB 配置", -1)),
              _createElementVNode("label", _hoisted_16, [
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "API Key", -1)),
                _createElementVNode("div", _hoisted_17, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.tmdb_api_key) = $event)),
                    type: secretVisible.value.tmdb_api_key ? 'text' : 'password',
                    class: "inp",
                    placeholder: "必填"
                  }, null, 8, _hoisted_18), [
                    [_vModelDynamic, cfg.value.tmdb_api_key]
                  ]),
                  _createElementVNode("button", {
                    type: "button",
                    "aria-label": "显示或隐藏 TMDB API Key",
                    onClick: _cache[8] || (_cache[8] = $event => (secretVisible.value.tmdb_api_key = !secretVisible.value.tmdb_api_key))
                  }, [...(_cache[26] || (_cache[26] = [
                    _createElementVNode("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true"
                    }, [
                      _createElementVNode("path", { d: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" }),
                      _createElementVNode("circle", {
                        cx: "12",
                        cy: "12",
                        r: "3"
                      })
                    ], -1)
                  ]))])
                ])
              ]),
              _createElementVNode("label", _hoisted_19, [
                _cache[28] || (_cache[28] = _createElementVNode("span", null, "语言", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.tmdb_language) = $event)),
                  class: "inp",
                  placeholder: "zh-CN"
                }, null, 512), [
                  [_vModelText, cfg.value.tmdb_language]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_20, [
              _cache[34] || (_cache[34] = _createElementVNode("h3", null, "Emby 配置", -1)),
              _createElementVNode("label", _hoisted_21, [
                _cache[30] || (_cache[30] = _createElementVNode("span", null, "地址", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.emby_url) = $event)),
                  class: "inp",
                  placeholder: "http://emby.local:8096"
                }, null, 512), [
                  [_vModelText, cfg.value.emby_url]
                ])
              ]),
              _createElementVNode("label", _hoisted_22, [
                _cache[32] || (_cache[32] = _createElementVNode("span", null, "API Key", -1)),
                _createElementVNode("div", _hoisted_23, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.value.emby_api_key) = $event)),
                    type: secretVisible.value.emby_api_key ? 'text' : 'password',
                    class: "inp"
                  }, null, 8, _hoisted_24), [
                    [_vModelDynamic, cfg.value.emby_api_key]
                  ]),
                  _createElementVNode("button", {
                    type: "button",
                    "aria-label": "显示或隐藏 Emby API Key",
                    onClick: _cache[12] || (_cache[12] = $event => (secretVisible.value.emby_api_key = !secretVisible.value.emby_api_key))
                  }, [...(_cache[31] || (_cache[31] = [
                    _createElementVNode("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true"
                    }, [
                      _createElementVNode("path", { d: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" }),
                      _createElementVNode("circle", {
                        cx: "12",
                        cy: "12",
                        r: "3"
                      })
                    ], -1)
                  ]))])
                ])
              ]),
              _createElementVNode("label", _hoisted_25, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.value.skip_emby_check) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.skip_emby_check]
                ]),
                _cache[33] || (_cache[33] = _createElementVNode("span", null, "跳过 Emby 查重（直接转发所有链接）", -1))
              ])
            ]),
            _createElementVNode("div", _hoisted_26, [
              _cache[38] || (_cache[38] = _createElementVNode("h3", null, "转发设置", -1)),
              _createElementVNode("label", _hoisted_27, [
                _cache[35] || (_cache[35] = _createElementVNode("span", null, "CMS Bot 用户名", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.value.cms_bot_username) = $event)),
                  class: "inp",
                  placeholder: "如 @cmsbot"
                }, null, 512), [
                  [_vModelText, cfg.value.cms_bot_username]
                ])
              ]),
              _createElementVNode("label", _hoisted_28, [
                _cache[36] || (_cache[36] = _createElementVNode("span", null, "转发标签", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.value.forward_label) = $event)),
                  class: "inp",
                  placeholder: "115 网盘"
                }, null, 512), [
                  [_vModelText, cfg.value.forward_label]
                ])
              ]),
              _createElementVNode("label", _hoisted_29, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.value.forward_to_saved) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.forward_to_saved]
                ]),
                _cache[37] || (_cache[37] = _createElementVNode("span", null, "转发到 Saved Messages（自己的收藏）", -1))
              ])
            ]),
            _createElementVNode("div", _hoisted_30, [
              _cache[41] || (_cache[41] = _createElementVNode("h3", null, "115 网盘配置", -1)),
              _createElementVNode("label", _hoisted_31, [
                _cache[40] || (_cache[40] = _createElementVNode("span", null, "Cookie", -1)),
                _createElementVNode("div", _hoisted_32, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cfg.value.pan115_cookie) = $event)),
                    type: secretVisible.value.pan115_cookie ? 'text' : 'password',
                    class: "inp",
                    placeholder: "可选，用于获取文件名"
                  }, null, 8, _hoisted_33), [
                    [_vModelDynamic, cfg.value.pan115_cookie]
                  ]),
                  _createElementVNode("button", {
                    type: "button",
                    "aria-label": "显示或隐藏 115 Cookie",
                    onClick: _cache[18] || (_cache[18] = $event => (secretVisible.value.pan115_cookie = !secretVisible.value.pan115_cookie))
                  }, [...(_cache[39] || (_cache[39] = [
                    _createElementVNode("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true"
                    }, [
                      _createElementVNode("path", { d: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" }),
                      _createElementVNode("circle", {
                        cx: "12",
                        cy: "12",
                        r: "3"
                      })
                    ], -1)
                  ]))])
                ])
              ])
            ]),
            _createElementVNode("button", {
              onClick: save,
              class: "btn-primary",
              disabled: saving.value
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_34)
          ]))
        : (tab.value === 'status')
          ? (_openBlock(), _createElementBlock("div", _hoisted_35, [
              _createElementVNode("div", _hoisted_36, [
                _cache[45] || (_cache[45] = _createElementVNode("h3", null, "服务状态", -1)),
                _createElementVNode("div", _hoisted_37, [
                  _cache[42] || (_cache[42] = _createElementVNode("span", null, "TMDB API", -1)),
                  _createElementVNode("b", {
                    class: _normalizeClass(status.value.tmdb_ok ? 'ok' : 'err')
                  }, _toDisplayString(status.value.tmdb_status || '未测试'), 3)
                ]),
                _createElementVNode("div", _hoisted_38, [
                  _cache[43] || (_cache[43] = _createElementVNode("span", null, "Emby 连接", -1)),
                  _createElementVNode("b", {
                    class: _normalizeClass(status.value.emby_ok ? 'ok' : 'err')
                  }, _toDisplayString(status.value.emby_status || '未测试'), 3)
                ]),
                _createElementVNode("div", _hoisted_39, [
                  _cache[44] || (_cache[44] = _createElementVNode("span", null, "Emby 库容量", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.emby_items || 0) + " 项", 1)
                ])
              ]),
              _createElementVNode("button", {
                onClick: testServices,
                class: "btn",
                disabled: testing.value
              }, _toDisplayString(testing.value ? '测试中...' : '测试连接'), 9, _hoisted_40),
              (testResult.value)
                ? (_openBlock(), _createElementBlock("p", {
                    key: 0,
                    class: _normalizeClass(["test-result", testResult.value.ok ? 'ok' : 'err'])
                  }, _toDisplayString(testResult.value.message), 3))
                : _createCommentVNode("", true)
            ]))
          : (_openBlock(), _createElementBlock("div", _hoisted_41, [
              _createElementVNode("div", _hoisted_42, [
                _createElementVNode("button", {
                  onClick: loadLogs,
                  class: "btn-sm"
                }, "刷新"),
                _createElementVNode("span", _hoisted_43, "最近 " + _toDisplayString(logs.value.length) + " 条", 1)
              ]),
              _createElementVNode("table", _hoisted_44, [
                _cache[47] || (_cache[47] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", null, "时间"),
                    _createElementVNode("th", null, "频道/群组"),
                    _createElementVNode("th", null, "标题"),
                    _createElementVNode("th", null, "TMDB ID"),
                    _createElementVNode("th", null, "操作")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(logs.value, (log, i) => {
                    return (_openBlock(), _createElementBlock("tr", { key: i }, [
                      _createElementVNode("td", _hoisted_45, _toDisplayString(log.time), 1),
                      _createElementVNode("td", null, _toDisplayString(log.chat_title || log.chat_id || '-'), 1),
                      _createElementVNode("td", null, _toDisplayString(log.title), 1),
                      _createElementVNode("td", null, [
                        _createElementVNode("span", _hoisted_46, _toDisplayString(log.tmdb_id || '-'), 1)
                      ]),
                      _createElementVNode("td", null, [
                        _createElementVNode("span", {
                          class: _normalizeClass('action-' + log.action)
                        }, _toDisplayString(log.action), 3)
                      ])
                    ]))
                  }), 128)),
                  (!logs.value.length)
                    ? (_openBlock(), _createElementBlock("tr", _hoisted_47, [...(_cache[46] || (_cache[46] = [
                        _createElementVNode("td", {
                          colspan: "5",
                          class: "empty"
                        }, "暂无处理记录", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2516431d"]]);

export { Config as default };
