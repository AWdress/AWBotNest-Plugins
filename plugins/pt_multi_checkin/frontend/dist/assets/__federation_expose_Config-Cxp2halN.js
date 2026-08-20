import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle,openBlock:_openBlock,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = {
  key: 0,
  class: "console"
};
const _hoisted_2 = { class: "mast" };
const _hoisted_3 = { class: "title-block" };
const _hoisted_4 = { class: "mast-actions" };
const _hoisted_5 = ["disabled"];
const _hoisted_6 = ["disabled"];
const _hoisted_7 = {
  class: "control-rail",
  "aria-label": "签到设置"
};
const _hoisted_8 = { class: "toggles" };
const _hoisted_9 = { class: "toggle" };
const _hoisted_10 = { class: "toggle" };
const _hoisted_11 = { class: "toggle" };
const _hoisted_12 = { class: "schedule-fields" };
const _hoisted_13 = { class: "time-field" };
const _hoisted_14 = { class: "unit-field" };
const _hoisted_15 = {
  key: 0,
  class: "run-status",
  "aria-live": "polite"
};
const _hoisted_16 = { class: "progress" };
const _hoisted_17 = { class: "sites-panel" };
const _hoisted_18 = { class: "section-head" };
const _hoisted_19 = { class: "section-actions" };
const _hoisted_20 = { class: "group-title" };
const _hoisted_21 = ["onClick"];
const _hoisted_22 = { class: "site-chips" };
const _hoisted_23 = ["value"];
const _hoisted_24 = { class: "site-badge" };
const _hoisted_25 = { class: "site-copy" };
const _hoisted_26 = ["title"];
const _hoisted_27 = { class: "save-bar" };
const _hoisted_28 = ["disabled"];
const _hoisted_29 = { class: "history-panel" };
const _hoisted_30 = { class: "section-head" };
const _hoisted_31 = ["disabled"];
const _hoisted_32 = {
  key: 0,
  class: "history"
};
const _hoisted_33 = {
  key: 1,
  class: "empty"
};
const _hoisted_34 = {
  key: 1,
  class: "loading"
};

const {computed,onBeforeUnmount,onMounted,reactive,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { pluginId: { type: String, required: true }, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const config = reactive({ auto_checkin: true, notify_result: true, headless: true, checkin_hour: 8, checkin_minute: 10, retry_count: 2, retry_interval: 20, tjupt_ai_assist: true, tjupt_confirm_timeout: 300, selected_sites: [] });
const sites = ref([]), history = ref([]), cookieState = reactive({});
const status = reactive({ running: false, current: '', phase: '', message: '', completed: 0, total: 0, finished_at: '' });
const loading = ref(true), saving = ref(false), checking = ref(false);
let timer;
const groups = computed(() => Object.entries(sites.value.reduce((all, site) => ((all[site.group] ||= []).push(site), all), {})));
const progress = computed(() => status.total ? Math.round(status.completed / status.total * 100) : 0);

async function refresh() {
  Object.assign(status, await props.host.callApi('/status'));
  const data = await props.host.callApi('/history'); history.value = data.items || [];
  if (!status.running && timer) { clearInterval(timer); timer = null; }
}
async function load() {
  try {
    const [saved, meta] = await Promise.all([props.host.getConfig(), props.host.callApi('/meta')]);
    Object.assign(config, meta.defaults || {}, saved || {});
    sites.value = meta.sites || [];
    if (!Array.isArray(config.selected_sites)) config.selected_sites = sites.value.map(site => site.key);
    await refresh();
  } catch (error) { props.host.toast.error(`读取失败：${error.message || error}`); }
  finally { loading.value = false; }
}
async function save() {
  saving.value = true;
  try { await props.host.saveConfig({ ...config, selected_sites: [...config.selected_sites] }); props.host.toast.success('配置已保存'); }
  catch (error) { props.host.toast.error(`保存失败：${error.message || error}`); }
  finally { saving.value = false; }
}
async function run() {
  const result = await props.host.callApi('/run', { method: 'POST' });
  result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
  await refresh(); if (!timer) timer = setInterval(refresh, 2500);
}
async function checkCookies() {
  checking.value = true;
  try { const data = await props.host.callApi('/cookies/check'); (data.items || []).forEach(item => { cookieState[item.key] = item; }); props.host.toast[data.ok ? 'success' : 'warning'](data.ok ? '所选站点 Cookie 均可用' : '部分站点 Cookie 不可用'); }
  catch (error) { props.host.toast.error(`检查失败：${error.message || error}`); }
  finally { checking.value = false; }
}
function toggleGroup(items, enabled) { const keys = new Set(config.selected_sites); items.forEach(site => enabled ? keys.add(site.key) : keys.delete(site.key)); config.selected_sites = [...keys]; }
async function clearHistory() { const result = await props.host.callApi('/history/clear', { method: 'POST' }); if (result.ok) { history.value = []; props.host.toast.success(result.message); } }
onMounted(load); onBeforeUnmount(() => timer && clearInterval(timer));

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock(_Fragment, null, [
    _createCommentVNode(" THESIS: Fast PT operations through glanceable controls and tactile checked labels, refusing spreadsheet-like site rows. OWN-WORLD: Ink-blue surfaces, crisp blue selection outlines, compact square checks, quiet cyan status. STORY: Choose sites, confirm platform cookies, save, and run with progress always visible. FIRST VIEWPORT: Title and actions lead; schedule controls sit in one rail; site chips fill grouped fields below. FORM: Compact operator console, seed PT-CHECK-CHIPS-3. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md. "),
    (!loading.value)
      ? (_openBlock(), _createElementBlock("main", _hoisted_1, [
          _createElementVNode("header", _hoisted_2, [
            _createElementVNode("div", _hoisted_3, [
              _cache[12] || (_cache[12] = _createElementVNode("span", {
                class: "brand-mark",
                "aria-hidden": "true"
              }, "PT", -1)),
              _createElementVNode("div", null, [
                _cache[11] || (_cache[11] = _createElementVNode("h2", null, "多站签到", -1)),
                _createElementVNode("p", null, [
                  _cache[10] || (_cache[10] = _createTextVNode("平台 Cookie 自动同步 · 已选择 ", -1)),
                  _createElementVNode("b", null, _toDisplayString(config.selected_sites.length), 1),
                  _createTextVNode(" / " + _toDisplayString(sites.value.length) + " 个站点", 1)
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_4, [
              _createElementVNode("button", {
                class: "button quiet",
                disabled: checking.value,
                onClick: checkCookies
              }, [
                _cache[13] || (_cache[13] = _createElementVNode("span", {
                  class: "button-icon",
                  "aria-hidden": "true"
                }, null, -1)),
                _createTextVNode(_toDisplayString(checking.value ? '正在检查' : '检查 Cookie'), 1)
              ], 8, _hoisted_5),
              _createElementVNode("button", {
                class: "button primary",
                disabled: status.running || !config.selected_sites.length,
                onClick: run
              }, [
                _cache[14] || (_cache[14] = _createElementVNode("span", {
                  class: "play",
                  "aria-hidden": "true"
                }, null, -1)),
                _createTextVNode(_toDisplayString(status.running ? '签到进行中' : '立即签到'), 1)
              ], 8, _hoisted_6)
            ])
          ]),
          _createElementVNode("section", _hoisted_7, [
            _createElementVNode("div", _hoisted_8, [
              _createElementVNode("label", _hoisted_9, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.auto_checkin) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, config.auto_checkin]
                ]),
                _cache[15] || (_cache[15] = _createElementVNode("i", null, null, -1)),
                _cache[16] || (_cache[16] = _createElementVNode("span", null, "自动签到", -1))
              ]),
              _createElementVNode("label", _hoisted_10, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.notify_result) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, config.notify_result]
                ]),
                _cache[17] || (_cache[17] = _createElementVNode("i", null, null, -1)),
                _cache[18] || (_cache[18] = _createElementVNode("span", null, "结果推送", -1))
              ]),
              _createElementVNode("label", _hoisted_11, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.headless) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, config.headless]
                ]),
                _cache[19] || (_cache[19] = _createElementVNode("i", null, null, -1)),
                _cache[20] || (_cache[20] = _createElementVNode("span", null, "浏览器静默运行", -1))
              ])
            ]),
            _createElementVNode("div", _hoisted_12, [
              _createElementVNode("label", null, [
                _cache[22] || (_cache[22] = _createElementVNode("span", null, "每天执行", -1)),
                _createElementVNode("span", _hoisted_13, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.checkin_hour) = $event)),
                    "aria-label": "执行小时",
                    type: "number",
                    min: "0",
                    max: "23"
                  }, null, 512), [
                    [
                      _vModelText,
                      config.checkin_hour,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[21] || (_cache[21] = _createElementVNode("b", null, ":", -1)),
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.checkin_minute) = $event)),
                    "aria-label": "执行分钟",
                    type: "number",
                    min: "0",
                    max: "59"
                  }, null, 512), [
                    [
                      _vModelText,
                      config.checkin_minute,
                      void 0,
                      { number: true }
                    ]
                  ])
                ])
              ]),
              _createElementVNode("label", null, [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "重试次数", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.retry_count) = $event)),
                  type: "number",
                  min: "0",
                  max: "5"
                }, null, 512), [
                  [
                    _vModelText,
                    config.retry_count,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode("label", null, [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "重试间隔", -1)),
                _createElementVNode("span", _hoisted_14, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.retry_interval) = $event)),
                    type: "number",
                    min: "5",
                    max: "300"
                  }, null, 512), [
                    [
                      _vModelText,
                      config.retry_interval,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[24] || (_cache[24] = _createElementVNode("i", null, "秒", -1))
                ])
              ])
            ])
          ]),
          (status.running || status.finished_at)
            ? (_openBlock(), _createElementBlock("section", _hoisted_15, [
                _createElementVNode("span", {
                  class: _normalizeClass(['pulse', { active: status.running }])
                }, null, 2),
                _createElementVNode("div", null, [
                  _createElementVNode("b", null, _toDisplayString(status.running ? `${status.phase} · ${status.current}` : '最近任务已完成'), 1),
                  _createElementVNode("small", null, _toDisplayString(status.message || `${status.completed} / ${status.total} 个站点`), 1)
                ]),
                _createElementVNode("strong", null, _toDisplayString(progress.value) + "%", 1),
                _createElementVNode("div", _hoisted_16, [
                  _createElementVNode("i", {
                    style: _normalizeStyle({ width: `${progress.value}%` })
                  }, null, 4)
                ])
              ]))
            : _createCommentVNode("", true),
          _createElementVNode("section", _hoisted_17, [
            _createElementVNode("div", _hoisted_18, [
              _cache[27] || (_cache[27] = _createElementVNode("div", null, [
                _createElementVNode("h3", null, "选择签到站点"),
                _createElementVNode("p", null, "点击标签即可勾选。除 TJUPT 外，验证码由平台 AI 自动识别。")
              ], -1)),
              _createElementVNode("div", _hoisted_19, [
                _createElementVNode("button", {
                  class: "link-button",
                  onClick: _cache[7] || (_cache[7] = $event => (toggleGroup(sites.value, true)))
                }, "全选"),
                _cache[26] || (_cache[26] = _createElementVNode("span", null, null, -1)),
                _createElementVNode("button", {
                  class: "link-button",
                  onClick: _cache[8] || (_cache[8] = $event => (toggleGroup(sites.value, false)))
                }, "清空")
              ])
            ]),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(groups.value, ([group, items]) => {
              return (_openBlock(), _createElementBlock("div", {
                key: group,
                class: "site-group"
              }, [
                _createElementVNode("div", _hoisted_20, [
                  _createElementVNode("span", null, _toDisplayString(group), 1),
                  _createElementVNode("small", null, _toDisplayString(items.filter(site => config.selected_sites.includes(site.key)).length) + "/" + _toDisplayString(items.length), 1),
                  _createElementVNode("button", {
                    onClick: $event => (toggleGroup(items, !items.every(site => config.selected_sites.includes(site.key))))
                  }, _toDisplayString(items.every(site => config.selected_sites.includes(site.key)) ? '取消本组' : '选择本组'), 9, _hoisted_21)
                ]),
                _createElementVNode("div", _hoisted_22, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(items, (site) => {
                    return (_openBlock(), _createElementBlock("label", {
                      key: site.key,
                      class: _normalizeClass(['site-chip', { selected: config.selected_sites.includes(site.key), checked: cookieState[site.key]?.ok, missing: cookieState[site.key] && !cookieState[site.key].ok }])
                    }, [
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.selected_sites) = $event)),
                        type: "checkbox",
                        value: site.key
                      }, null, 8, _hoisted_23), [
                        [_vModelCheckbox, config.selected_sites]
                      ]),
                      _cache[28] || (_cache[28] = _createElementVNode("span", { class: "checkmark" }, [
                        _createElementVNode("i")
                      ], -1)),
                      _createElementVNode("span", _hoisted_24, _toDisplayString(site.name.slice(0, 2).toUpperCase()), 1),
                      _createElementVNode("span", _hoisted_25, [
                        _createElementVNode("b", null, _toDisplayString(site.name), 1),
                        _createElementVNode("small", null, _toDisplayString(site.domain), 1)
                      ]),
                      (cookieState[site.key])
                        ? (_openBlock(), _createElementBlock("span", {
                            key: 0,
                            class: "cookie-dot",
                            title: cookieState[site.key].message
                          }, null, 8, _hoisted_26))
                        : _createCommentVNode("", true)
                    ], 2))
                  }), 128))
                ])
              ]))
            }), 128)),
            _createElementVNode("footer", _hoisted_27, [
              _cache[29] || (_cache[29] = _createElementVNode("p", null, [
                _createElementVNode("span", {
                  class: "shield",
                  "aria-hidden": "true"
                }),
                _createTextVNode("Cookie 只从平台读取，不会保存在插件配置中。")
              ], -1)),
              _createElementVNode("button", {
                class: "button primary",
                disabled: saving.value,
                onClick: save
              }, _toDisplayString(saving.value ? '正在保存…' : '保存并应用'), 9, _hoisted_28)
            ])
          ]),
          _createElementVNode("section", _hoisted_29, [
            _createElementVNode("div", _hoisted_30, [
              _cache[30] || (_cache[30] = _createElementVNode("div", null, [
                _createElementVNode("h3", null, "最近运行"),
                _createElementVNode("p", null, "保留最近 30 次签到结果。")
              ], -1)),
              _createElementVNode("button", {
                class: "link-button danger",
                disabled: !history.value.length,
                onClick: clearHistory
              }, "清空记录", 8, _hoisted_31)
            ]),
            (history.value.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_32, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item) => {
                    return (_openBlock(), _createElementBlock("details", {
                      key: item.time
                    }, [
                      _createElementVNode("summary", null, [
                        _createElementVNode("span", {
                          class: _normalizeClass(['result-mark', item.ok ? 'success' : 'failed'])
                        }, null, 2),
                        _createElementVNode("b", null, _toDisplayString(item.summary), 1),
                        _createElementVNode("time", null, _toDisplayString(item.time), 1),
                        _cache[31] || (_cache[31] = _createElementVNode("span", { class: "chevron" }, null, -1))
                      ]),
                      _createElementVNode("ul", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.sites, (site) => {
                          return (_openBlock(), _createElementBlock("li", {
                            key: site.key || site.site
                          }, [
                            _createElementVNode("span", null, _toDisplayString(site.site), 1),
                            _createElementVNode("em", {
                              class: _normalizeClass(site.ok ? 'success-text' : 'failed-text')
                            }, _toDisplayString(site.message), 3)
                          ]))
                        }), 128))
                      ])
                    ]))
                  }), 128))
                ]))
              : (_openBlock(), _createElementBlock("div", _hoisted_33, [...(_cache[32] || (_cache[32] = [
                  _createElementVNode("span", { class: "empty-mark" }, null, -1),
                  _createElementVNode("b", null, "等待第一次签到", -1),
                  _createElementVNode("p", null, "运行完成后，站点结果会显示在这里。", -1)
                ]))]))
          ])
        ]))
      : (_openBlock(), _createElementBlock("div", _hoisted_34, "正在读取签到配置…"))
  ], 64))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-f3b2d5f9"]]);

export { Config as default };
