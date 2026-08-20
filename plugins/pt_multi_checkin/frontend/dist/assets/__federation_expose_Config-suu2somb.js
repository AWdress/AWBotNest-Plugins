import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,normalizeStyle:_normalizeStyle,openBlock:_openBlock,createElementBlock:_createElementBlock,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,createTextVNode:_createTextVNode,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = {
  key: 0,
  class: "console"
};
const _hoisted_2 = { class: "mast" };
const _hoisted_3 = { class: "mast-actions" };
const _hoisted_4 = ["disabled"];
const _hoisted_5 = ["disabled"];
const _hoisted_6 = {
  key: 0,
  class: "runline",
  "aria-live": "polite"
};
const _hoisted_7 = { class: "run-copy" };
const _hoisted_8 = { class: "bar" };
const _hoisted_9 = { class: "settings" };
const _hoisted_10 = { class: "switch" };
const _hoisted_11 = { class: "switch" };
const _hoisted_12 = { class: "switch" };
const _hoisted_13 = { class: "time" };
const _hoisted_14 = { class: "section-head" };
const _hoisted_15 = ["disabled"];
const _hoisted_16 = { class: "site-list" };
const _hoisted_17 = { class: "group-head" };
const _hoisted_18 = ["onClick"];
const _hoisted_19 = ["value"];
const _hoisted_20 = { class: "site-name" };
const _hoisted_21 = { class: "section-head history-head" };
const _hoisted_22 = ["disabled"];
const _hoisted_23 = {
  key: 1,
  class: "history"
};
const _hoisted_24 = {
  key: 2,
  class: "empty"
};
const _hoisted_25 = {
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
const status = reactive({ running: false, current: '', completed: 0, total: 0, finished_at: '' });
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
    _createCommentVNode(" Design contract: PT-SIGNIN-OPERATE-2. Dense operations console with restrained blue accent, flat grouped rows, visible progress and practical controls. Avoid decorative gradients, card grids, oversized headings, pill-heavy styling, hidden critical state, and manual credential fields. "),
    (!loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
          _createElementVNode("header", _hoisted_2, [
            _createElementVNode("div", null, [
              _cache[8] || (_cache[8] = _createElementVNode("p", { class: "eyebrow" }, "PT AUTOMATION", -1)),
              _cache[9] || (_cache[9] = _createElementVNode("h2", null, "签到控制台", -1)),
              _createElementVNode("p", null, "统一使用平台同步 Cookie · " + _toDisplayString(config.selected_sites.length) + " / " + _toDisplayString(sites.value.length) + " 个站点已启用", 1)
            ]),
            _createElementVNode("div", _hoisted_3, [
              _createElementVNode("button", {
                class: "secondary",
                disabled: checking.value,
                onClick: checkCookies
              }, _toDisplayString(checking.value ? '检查中…' : '检查 Cookie'), 9, _hoisted_4),
              _createElementVNode("button", {
                class: "primary",
                disabled: status.running || !config.selected_sites.length,
                onClick: run
              }, _toDisplayString(status.running ? '签到进行中' : '立即签到'), 9, _hoisted_5)
            ])
          ]),
          (status.running || status.finished_at)
            ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                _createElementVNode("div", _hoisted_7, [
                  _createElementVNode("b", null, _toDisplayString(status.running ? `正在处理 ${status.current}` : '最近任务已完成'), 1),
                  _createElementVNode("span", null, _toDisplayString(status.completed) + " / " + _toDisplayString(status.total) + " · " + _toDisplayString(progress.value) + "%", 1)
                ]),
                _createElementVNode("div", _hoisted_8, [
                  _createElementVNode("i", {
                    style: _normalizeStyle({ width: `${progress.value}%` })
                  }, null, 4)
                ])
              ]))
            : _createCommentVNode("", true),
          _createElementVNode("section", _hoisted_9, [
            _createElementVNode("label", _hoisted_10, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.auto_checkin) = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, config.auto_checkin]
              ]),
              _cache[10] || (_cache[10] = _createElementVNode("span", null, "每日自动签到", -1))
            ]),
            _createElementVNode("label", _hoisted_11, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.notify_result) = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, config.notify_result]
              ]),
              _cache[11] || (_cache[11] = _createElementVNode("span", null, "推送签到结果", -1))
            ]),
            _createElementVNode("label", _hoisted_12, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.headless) = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, config.headless]
              ]),
              _cache[12] || (_cache[12] = _createElementVNode("span", null, "后台浏览器", -1))
            ]),
            _createElementVNode("label", null, [
              _cache[14] || (_cache[14] = _createTextVNode("执行时间 ", -1)),
              _createElementVNode("span", _hoisted_13, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.checkin_hour) = $event)),
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
                _cache[13] || (_cache[13] = _createTextVNode(":", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.checkin_minute) = $event)),
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
              _cache[15] || (_cache[15] = _createTextVNode("失败重试 ", -1)),
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
              _cache[16] || (_cache[16] = _createTextVNode("间隔（秒） ", -1)),
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
              ])
            ])
          ]),
          _createElementVNode("div", _hoisted_14, [
            _cache[17] || (_cache[17] = _createElementVNode("div", null, [
              _createElementVNode("h3", null, "站点范围"),
              _createElementVNode("p", null, "交互验证站会在无法安全识别时明确提示，不会随机提交。")
            ], -1)),
            _createElementVNode("button", {
              class: "secondary",
              disabled: saving.value,
              onClick: save
            }, _toDisplayString(saving.value ? '保存中…' : '保存配置'), 9, _hoisted_15)
          ]),
          _createElementVNode("section", _hoisted_16, [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(groups.value, ([group, items]) => {
              return (_openBlock(), _createElementBlock("div", {
                key: group,
                class: "site-group"
              }, [
                _createElementVNode("div", _hoisted_17, [
                  _createElementVNode("b", null, _toDisplayString(group), 1),
                  _createElementVNode("button", {
                    onClick: $event => (toggleGroup(items, !items.every(site => config.selected_sites.includes(site.key))))
                  }, _toDisplayString(items.every(site => config.selected_sites.includes(site.key)) ? '取消全选' : '全选'), 9, _hoisted_18)
                ]),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(items, (site) => {
                  return (_openBlock(), _createElementBlock("label", {
                    key: site.key,
                    class: "site-row"
                  }, [
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.selected_sites) = $event)),
                      type: "checkbox",
                      value: site.key
                    }, null, 8, _hoisted_19), [
                      [_vModelCheckbox, config.selected_sites]
                    ]),
                    _createElementVNode("span", _hoisted_20, [
                      _createTextVNode(_toDisplayString(site.name), 1),
                      _createElementVNode("small", null, _toDisplayString(site.domain), 1)
                    ]),
                    (cookieState[site.key])
                      ? (_openBlock(), _createElementBlock("span", {
                          key: 0,
                          class: _normalizeClass(['cookie', cookieState[site.key].ok ? 'good' : 'bad'])
                        }, _toDisplayString(cookieState[site.key].ok ? 'Cookie 可用' : 'Cookie 缺失'), 3))
                      : _createCommentVNode("", true)
                  ]))
                }), 128))
              ]))
            }), 128))
          ]),
          _createElementVNode("div", _hoisted_21, [
            _cache[18] || (_cache[18] = _createElementVNode("div", null, [
              _createElementVNode("h3", null, "最近记录"),
              _createElementVNode("p", null, "最多保留 30 次运行结果。")
            ], -1)),
            _createElementVNode("button", {
              class: "text-button",
              disabled: !history.value.length,
              onClick: clearHistory
            }, "清空", 8, _hoisted_22)
          ]),
          (history.value.length)
            ? (_openBlock(), _createElementBlock("section", _hoisted_23, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item) => {
                  return (_openBlock(), _createElementBlock("details", {
                    key: item.time
                  }, [
                    _createElementVNode("summary", null, [
                      _createElementVNode("span", {
                        class: _normalizeClass(['dot', item.ok ? 'good' : 'bad'])
                      }, null, 2),
                      _createElementVNode("b", null, _toDisplayString(item.summary), 1),
                      _createElementVNode("time", null, _toDisplayString(item.time), 1)
                    ]),
                    _createElementVNode("ul", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.sites, (site) => {
                        return (_openBlock(), _createElementBlock("li", {
                          key: site.key || site.site
                        }, [
                          _createElementVNode("span", null, _toDisplayString(site.site), 1),
                          _createElementVNode("em", {
                            class: _normalizeClass(site.ok ? 'good' : 'bad')
                          }, _toDisplayString(site.message), 3)
                        ]))
                      }), 128))
                    ])
                  ]))
                }), 128))
              ]))
            : (_openBlock(), _createElementBlock("p", _hoisted_24, "还没有签到记录。"))
        ]))
      : (_openBlock(), _createElementBlock("div", _hoisted_25, "正在读取签到配置…"))
  ], 64))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ae9f3dd9"]]);

export { Config as default };
