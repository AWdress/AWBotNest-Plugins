import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,Fragment:_Fragment,normalizeStyle:_normalizeStyle,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,renderList:_renderList} = await importShared('vue');


const _hoisted_1 = { class: "read-panel" };
const _hoisted_2 = {
  key: 0,
  class: "skeleton",
  "aria-label": "正在加载"
};
const _hoisted_3 = { class: "header" };
const _hoisted_4 = { class: "title-wrap" };
const _hoisted_5 = ["innerHTML"];
const _hoisted_6 = {
  class: "run-area",
  "aria-labelledby": "run-heading"
};
const _hoisted_7 = { class: "run-copy" };
const _hoisted_8 = { class: "meta" };
const _hoisted_9 = { class: "actions" };
const _hoisted_10 = ["disabled"];
const _hoisted_11 = ["innerHTML"];
const _hoisted_12 = ["disabled"];
const _hoisted_13 = ["innerHTML"];
const _hoisted_14 = ["disabled"];
const _hoisted_15 = ["innerHTML"];
const _hoisted_16 = ["aria-valuenow"];
const _hoisted_17 = { class: "content-grid" };
const _hoisted_18 = {
  class: "settings",
  "aria-labelledby": "settings-heading"
};
const _hoisted_19 = { class: "section-head" };
const _hoisted_20 = ["disabled"];
const _hoisted_21 = { class: "toggle-row" };
const _hoisted_22 = { class: "toggle-row" };
const _hoisted_23 = { class: "field-grid" };
const _hoisted_24 = { class: "input-unit" };
const _hoisted_25 = { class: "input-unit" };
const _hoisted_26 = {
  class: "history-area",
  "aria-labelledby": "history-heading"
};
const _hoisted_27 = { class: "section-head" };
const _hoisted_28 = { class: "head-actions" };
const _hoisted_29 = ["innerHTML"];
const _hoisted_30 = ["disabled"];
const _hoisted_31 = ["innerHTML"];
const _hoisted_32 = {
  key: 0,
  class: "empty"
};
const _hoisted_33 = ["innerHTML"];
const _hoisted_34 = {
  key: 1,
  class: "history-list"
};
const _hoisted_35 = { class: "history-meta" };

const {computed,onBeforeUnmount,onMounted,reactive,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const cfg = reactive({ enabled: true, notify_result: true, page_delay: 1, max_pages: 200 });
const status = ref({
  running: false, phase: 'idle', message: '正在读取状态…', current_page: 0,
  total_pages: 0, processed: 0, started_at: '', finished_at: '', stop_requested: false,
});
const history = ref([]);
const loading = ref(true);
const saving = ref(false);
const starting = ref(false);
const stopping = ref(false);
const checking = ref(false);
const clearing = ref(false);
let timer = null;

const phaseLabel = computed(() => ({
  idle: '待运行', checking: '检查登录', searching: '查找未读', processing: '处理中',
  completed: '已完成', stopped: '已停止', failed: '运行失败',
}[status.value.phase] || '待运行'));

const progress = computed(() => {
  const total = Number(status.value.total_pages || 0);
  const current = Number(status.value.current_page || 0);
  if (!total) return 0
  return Math.max(0, Math.min(100, Math.round(current / total * 100)))
});

const statusTone = computed(() => {
  if (status.value.running) return 'active'
  if (status.value.phase === 'failed') return 'danger'
  if (status.value.phase === 'completed') return 'success'
  return 'neutral'
});

function iconPath(name) {
  const paths = {
    inbox: '<path d="M4 5.5h16v13H4z"/><path d="M4 14h4l2 2h4l2-2h4"/>',
    play: '<path d="m8 5 11 7-11 7z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
    shield: '<path d="M12 3 5.5 5.8v5.1c0 4.3 2.8 7.8 6.5 9.1 3.7-1.3 6.5-4.8 6.5-9.1V5.8z"/><path d="m9 12 2 2 4-4"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.3-2.4L20 9M4 15l2.6 2.4A7 7 0 0 0 17.9 15"/>',
  };
  return paths[name] || ''
}

async function loadStatus() {
  try { status.value = await props.host.callApi('/status'); }
  catch (error) { /* 轮询失败不打断用户 */ }
}

async function loadHistory() {
  try { history.value = (await props.host.callApi('/history')).items || []; }
  catch (error) { props.host.toast.error('读取运行记录失败：' + (error.message || error)); }
}

async function save() {
  saving.value = true;
  try {
    cfg.page_delay = Math.max(0.2, Math.min(Number(cfg.page_delay) || 1, 10));
    cfg.max_pages = Math.max(1, Math.min(Number(cfg.max_pages) || 200, 1000));
    await props.host.saveConfig({ ...cfg });
    props.host.toast.success('配置已保存');
  } catch (error) {
    props.host.toast.error('保存失败：' + (error.message || error));
  } finally { saving.value = false; }
}

async function run() {
  starting.value = true;
  try {
    await props.host.saveConfig({ ...cfg });
    const result = await props.host.callApi('/run', { method: 'POST', body: {} });
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
    await loadStatus();
  } catch (error) {
    props.host.toast.error('启动失败：' + (error.message || error));
  } finally { starting.value = false; }
}

async function stop() {
  stopping.value = true;
  try {
    const result = await props.host.callApi('/stop', { method: 'POST', body: {} });
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
    await loadStatus();
  } catch (error) {
    props.host.toast.error('停止失败：' + (error.message || error));
  } finally { stopping.value = false; }
}

async function checkCookie() {
  checking.value = true;
  try {
    const result = await props.host.callApi('/cookie/check');
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
  } catch (error) {
    props.host.toast.error('检查失败：' + (error.message || error));
  } finally { checking.value = false; }
}

async function clearHistory() {
  if (!confirm('清空最近运行记录？')) return
  clearing.value = true;
  try {
    const result = await props.host.callApi('/history/clear', { method: 'POST', body: {} });
    history.value = [];
    props.host.toast.success(result.message);
  } catch (error) {
    props.host.toast.error('清空失败：' + (error.message || error));
  } finally { clearing.value = false; }
}

function historyStatus(item) {
  return ({ completed: '完成', stopped: '停止', failed: '失败' }[item.status] || item.status)
}

onMounted(async () => {
  try {
    Object.assign(cfg, await props.host.getConfig() || {});
    await Promise.all([loadStatus(), loadHistory()]);
  } catch (error) {
    props.host.toast.error('读取插件数据失败：' + (error.message || error));
  } finally { loading.value = false; }
  timer = window.setInterval(async () => {
    const wasRunning = status.value.running;
    await loadStatus();
    if (wasRunning && !status.value.running) await loadHistory();
  }, 1500);
});

onBeforeUnmount(() => { if (timer) window.clearInterval(timer); });

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [...(_cache[4] || (_cache[4] = [
          _createElementVNode("span", null, null, -1),
          _createElementVNode("span", null, null, -1),
          _createElementVNode("span", null, null, -1)
        ]))]))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
          _createElementVNode("header", _hoisted_3, [
            _createElementVNode("div", _hoisted_4, [
              (_openBlock(), _createElementBlock("svg", {
                class: "title-icon",
                viewBox: "0 0 24 24",
                "aria-hidden": "true",
                innerHTML: iconPath('inbox')
              }, null, 8, _hoisted_5)),
              _cache[5] || (_cache[5] = _createElementVNode("div", null, [
                _createElementVNode("h2", null, "一键全部已读"),
                _createElementVNode("p", null, "扫描 HHanClub 收件箱，只处理带未读标记的站内信。")
              ], -1))
            ]),
            _createElementVNode("span", {
              class: _normalizeClass(["state", statusTone.value])
            }, [
              _cache[6] || (_cache[6] = _createElementVNode("i", null, null, -1)),
              _createTextVNode(_toDisplayString(phaseLabel.value), 1)
            ], 2)
          ]),
          _createElementVNode("section", _hoisted_6, [
            _createElementVNode("div", _hoisted_7, [
              _cache[7] || (_cache[7] = _createElementVNode("span", {
                id: "run-heading",
                class: "section-label"
              }, "当前任务", -1)),
              _createElementVNode("strong", null, _toDisplayString(status.value.message), 1),
              _createElementVNode("span", _hoisted_8, [
                (status.value.total_pages)
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createTextVNode("第 " + _toDisplayString(status.value.current_page) + "/" + _toDisplayString(status.value.total_pages) + " 页 · ", 1)
                    ], 64))
                  : _createCommentVNode("", true),
                _createTextVNode(" 已处理 " + _toDisplayString(status.value.processed) + " 条 ", 1)
              ])
            ]),
            _createElementVNode("div", _hoisted_9, [
              (!status.value.running)
                ? (_openBlock(), _createElementBlock("button", {
                    key: 0,
                    class: "button primary",
                    disabled: starting.value || !cfg.enabled,
                    onClick: run
                  }, [
                    (_openBlock(), _createElementBlock("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('play')
                    }, null, 8, _hoisted_11)),
                    _createTextVNode(" " + _toDisplayString(starting.value ? '启动中…' : '开始全部已读'), 1)
                  ], 8, _hoisted_10))
                : (_openBlock(), _createElementBlock("button", {
                    key: 1,
                    class: "button danger",
                    disabled: stopping.value || status.value.stop_requested,
                    onClick: stop
                  }, [
                    (_openBlock(), _createElementBlock("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('stop')
                    }, null, 8, _hoisted_13)),
                    _createTextVNode(" " + _toDisplayString(status.value.stop_requested ? '等待停止…' : stopping.value ? '提交中…' : '停止任务'), 1)
                  ], 8, _hoisted_12)),
              _createElementVNode("button", {
                class: "button",
                disabled: checking.value || status.value.running,
                onClick: checkCookie
              }, [
                (_openBlock(), _createElementBlock("svg", {
                  viewBox: "0 0 24 24",
                  "aria-hidden": "true",
                  innerHTML: iconPath('shield')
                }, null, 8, _hoisted_15)),
                _createTextVNode(" " + _toDisplayString(checking.value ? '检查中…' : '检查 Cookie'), 1)
              ], 8, _hoisted_14)
            ]),
            _createElementVNode("div", {
              class: "progress",
              role: "progressbar",
              "aria-valuenow": progress.value,
              "aria-valuemin": "0",
              "aria-valuemax": "100"
            }, [
              _createElementVNode("span", {
                style: _normalizeStyle({ transform: `scaleX(${progress.value / 100})` })
              }, null, 4)
            ], 8, _hoisted_16)
          ]),
          _createElementVNode("div", _hoisted_17, [
            _createElementVNode("section", _hoisted_18, [
              _createElementVNode("div", _hoisted_19, [
                _cache[8] || (_cache[8] = _createElementVNode("div", null, [
                  _createElementVNode("h3", { id: "settings-heading" }, "运行设置"),
                  _createElementVNode("p", null, "开始任务时会先自动保存这些设置。")
                ], -1)),
                _createElementVNode("button", {
                  class: "button compact",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString(saving.value ? '保存中…' : '保存'), 9, _hoisted_20)
              ]),
              _createElementVNode("label", _hoisted_21, [
                _cache[9] || (_cache[9] = _createElementVNode("span", null, [
                  _createElementVNode("b", null, "启用插件"),
                  _createElementVNode("small", null, "关闭后不能启动新任务")
                ], -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.enabled) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox, cfg.enabled]
                ])
              ]),
              _createElementVNode("label", _hoisted_22, [
                _cache[10] || (_cache[10] = _createElementVNode("span", null, [
                  _createElementVNode("b", null, "完成后推送结果"),
                  _createElementVNode("small", null, "通过平台通知渠道发送处理汇总")
                ], -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((cfg.notify_result) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox, cfg.notify_result]
                ])
              ]),
              _createElementVNode("div", _hoisted_23, [
                _createElementVNode("label", null, [
                  _cache[12] || (_cache[12] = _createElementVNode("span", null, "翻页间隔", -1)),
                  _createElementVNode("div", _hoisted_24, [
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.page_delay) = $event)),
                      type: "number",
                      min: "0.2",
                      max: "10",
                      step: "0.1"
                    }, null, 512), [
                      [
                        _vModelText,
                        cfg.page_delay,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[11] || (_cache[11] = _createElementVNode("em", null, "秒", -1))
                  ])
                ]),
                _createElementVNode("label", null, [
                  _cache[14] || (_cache[14] = _createElementVNode("span", null, "最多扫描", -1)),
                  _createElementVNode("div", _hoisted_25, [
                    _withDirectives(_createElementVNode("input", {
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.max_pages) = $event)),
                      type: "number",
                      min: "1",
                      max: "1000"
                    }, null, 512), [
                      [
                        _vModelText,
                        cfg.max_pages,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[13] || (_cache[13] = _createElementVNode("em", null, "页", -1))
                  ])
                ])
              ]),
              _cache[15] || (_cache[15] = _createElementVNode("p", { class: "notice" }, [
                _createTextVNode("任务只勾选页面中使用 "),
                _createElementVNode("code", null, "icon-unread.svg"),
                _createTextVNode(" 标记的消息；进入连续已读区域后自动结束。")
              ], -1))
            ]),
            _createElementVNode("section", _hoisted_26, [
              _createElementVNode("div", _hoisted_27, [
                _cache[16] || (_cache[16] = _createElementVNode("div", null, [
                  _createElementVNode("h3", { id: "history-heading" }, "最近运行"),
                  _createElementVNode("p", null, "保留最近 20 次处理结果。")
                ], -1)),
                _createElementVNode("div", _hoisted_28, [
                  _createElementVNode("button", {
                    class: "icon-button",
                    title: "刷新记录",
                    "aria-label": "刷新记录",
                    onClick: loadHistory
                  }, [
                    (_openBlock(), _createElementBlock("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('refresh')
                    }, null, 8, _hoisted_29))
                  ]),
                  _createElementVNode("button", {
                    class: "icon-button danger-text",
                    title: "清空记录",
                    "aria-label": "清空记录",
                    disabled: clearing.value || !history.value.length,
                    onClick: clearHistory
                  }, [
                    (_openBlock(), _createElementBlock("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('trash')
                    }, null, 8, _hoisted_31))
                  ], 8, _hoisted_30)
                ])
              ]),
              (!history.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_32, [
                    (_openBlock(), _createElementBlock("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('inbox')
                    }, null, 8, _hoisted_33)),
                    _cache[17] || (_cache[17] = _createElementVNode("b", null, "还没有运行记录", -1)),
                    _cache[18] || (_cache[18] = _createElementVNode("span", null, "首次执行后，处理数量和结果会显示在这里。", -1))
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_34, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item, index) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: item.time + index,
                        class: "history-item"
                      }, [
                        _createElementVNode("span", {
                          class: _normalizeClass(["history-status", item.status])
                        }, _toDisplayString(historyStatus(item)), 3),
                        _createElementVNode("div", null, [
                          _createElementVNode("b", null, _toDisplayString(item.processed) + " 条消息", 1),
                          _createElementVNode("span", null, _toDisplayString(item.detail), 1)
                        ]),
                        _createElementVNode("div", _hoisted_35, [
                          _createElementVNode("time", null, _toDisplayString(item.time), 1),
                          _createElementVNode("span", null, _toDisplayString(item.pages) + " 页", 1)
                        ])
                      ]))
                    }), 128))
                  ]))
            ])
          ])
        ], 64))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-57dd015e"]]);

export { Config as default };
