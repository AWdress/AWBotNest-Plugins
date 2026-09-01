import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode$4,toDisplayString:_toDisplayString$3,createTextVNode:_createTextVNode$2,normalizeClass:_normalizeClass$4,normalizeStyle:_normalizeStyle$1,renderList:_renderList$1,Fragment:_Fragment$3,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4,vModelCheckbox:_vModelCheckbox$2,withDirectives:_withDirectives$3,vModelSelect:_vModelSelect,vModelText:_vModelText$3} = await importShared('vue');


const _hoisted_1$4 = { class: "panel" };
const _hoisted_2$4 = { class: "progress-card" };
const _hoisted_3$3 = { class: "progress-top" };
const _hoisted_4$3 = { class: "track" };
const _hoisted_5$3 = { class: "live-stats" };
const _hoisted_6$3 = { class: "stats-head" };
const _hoisted_7$3 = { class: "balance-line" };
const _hoisted_8$3 = { key: 0 };
const _hoisted_9$3 = {
  key: 1,
  class: "empty-stat"
};
const _hoisted_10$2 = { class: "stats-head" };
const _hoisted_11$2 = { class: "balance-line" };
const _hoisted_12$2 = { key: 0 };
const _hoisted_13$2 = {
  key: 1,
  class: "empty-stat"
};
const _hoisted_14$1 = { class: "grid" };
const _hoisted_15$1 = { class: "card settings" };
const _hoisted_16$1 = { class: "toggle-row" };
const _hoisted_17$1 = { key: 0 };
const _hoisted_18$1 = { key: 1 };
const _hoisted_19$1 = {
  key: 2,
  class: "mode-note"
};
const _hoisted_20$1 = { class: "check" };
const _hoisted_21$1 = { class: "check" };
const _hoisted_22$1 = { key: 3 };
const _hoisted_23$1 = {
  key: 4,
  class: "mode-note"
};
const _hoisted_24$1 = { class: "check" };
const _hoisted_25$1 = {
  key: 5,
  class: "stop-box"
};
const _hoisted_26$1 = { class: "check" };
const _hoisted_27$1 = { class: "check" };
const _hoisted_28$1 = { class: "check" };
const _hoisted_29$1 = { class: "check" };
const _hoisted_30$1 = { class: "check" };
const _hoisted_31$1 = ["disabled"];
const _hoisted_32$1 = { class: "card result" };
const _hoisted_33$1 = ["disabled"];
const _hoisted_34$1 = ["disabled"];
const _hoisted_35$1 = ["disabled"];
const _hoisted_36$1 = ["disabled"];

const {computed: computed$2,onBeforeUnmount: onBeforeUnmount$1,onMounted: onMounted$3,reactive: reactive$3,ref: ref$4} = await importShared('vue');



const _sfc_main$4 = {
  __name: 'LotteryPanel',
  props: { pluginId: String, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const cfg = reactive$3({ enabled: true, notify_result: true, notify_cookie_error: true, lottery_mode: 'fixed', lottery_count: 10, interval_seconds: 7, reserve_beans: 0, sync_every_draws: 20, auto_clean_lottery_mail: false, stop_on_prize: false, stop_on_vip: true, stop_on_invite: true, stop_on_big_beans: true, big_bean_threshold: 500000, stop_prize_keywords: '', scheduled_stop_enabled: false, scheduled_stop_at: '' });
const status = ref$4({ running: false, completed: 0, target: 0, detail: '', last_prize: '', last_result: '', current_stats: {}, cumulative_stats: {} });
const busy = ref$4('');
const saving = ref$4(false);
let timer;

const progress = computed$2(() => status.value.target ? Math.min(100, Math.round(status.value.completed / status.value.target * 100)) : 0);
const stateText = computed$2(() => status.value.running ? `正在抽奖 ${status.value.completed}/${status.value.target}` : (status.value.detail || '等待开始'));
const currentStats = computed$2(() => status.value.current_stats || {});
const cumulativeStats = computed$2(() => status.value.cumulative_stats || {});
const formatNumber = value => new Intl.NumberFormat('zh-CN').format(Number(value) || 0);
const formatSigned = value => `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`;
const profitTone = value => Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : 'neutral';
const prizeRows = value => Object.entries(value?.prizes || {}).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 20);

async function refresh() { try { status.value = await props.host.callApi('/lottery/status'); } catch (_) {} }
async function save(showToast = true) {
  if (saving.value) return
  saving.value = true;
  try {
    cfg.lottery_mode = ['fixed', 'balance', 'reserve'].includes(cfg.lottery_mode) ? cfg.lottery_mode : 'fixed';
    cfg.lottery_count = Math.max(1, Math.trunc(Number(cfg.lottery_count) || 10));
    cfg.interval_seconds = Math.max(3, Math.min(Number(cfg.interval_seconds) || 7, 30));
    cfg.reserve_beans = Math.max(0, Math.trunc(Number(cfg.reserve_beans) || 0));
    cfg.sync_every_draws = Math.max(1, Math.min(200, Math.trunc(Number(cfg.sync_every_draws) || 20)));
    cfg.big_bean_threshold = Math.max(1, Math.trunc(Number(cfg.big_bean_threshold) || 500000));
    cfg.scheduled_stop_at = String(cfg.scheduled_stop_at || '');
    await props.host.saveConfig({ ...cfg });
    if (showToast) props.host.toast.success('转盘配置已保存');
  } catch (error) {
    if (showToast) props.host.toast.error(error.message || String(error));
    throw error
  } finally {
    saving.value = false;
  }
}
async function action(name, path, method = 'POST') {
  busy.value = name;
  try {
    if (name === 'run') await save(false);
    const result = await props.host.callApi(path, { method, body: method === 'POST' ? {} : undefined })
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message || '操作完成');
    await refresh();
  } catch (error) { props.host.toast.error(error.message || String(error)); }
  finally { busy.value = ''; }
}

onMounted$3(async () => {
  Object.assign(cfg, await props.host.getConfig());
  await refresh();
  timer = setInterval(refresh, 1500);
});
onBeforeUnmount$1(() => clearInterval(timer));

return (_ctx, _cache) => {
  return (_openBlock$4(), _createElementBlock$4("section", _hoisted_1$4, [
    _createElementVNode$4("header", null, [
      _cache[23] || (_cache[23] = _createElementVNode$4("div", null, [
        _createElementVNode$4("p", { class: "eyebrow" }, "HHANCLUB"),
        _createElementVNode$4("h2", null, "幸运转盘"),
        _createElementVNode$4("p", { class: "sub" }, "可指定任意正整数次数，或按当前余额自动抽完。")
      ], -1)),
      _createElementVNode$4("span", {
        class: _normalizeClass$4(["state", { live: status.value.running }])
      }, [
        _cache[22] || (_cache[22] = _createElementVNode$4("i", null, null, -1)),
        _createTextVNode$2(_toDisplayString$3(stateText.value), 1)
      ], 2)
    ]),
    _createElementVNode$4("div", _hoisted_2$4, [
      _createElementVNode$4("div", _hoisted_3$3, [
        _createElementVNode$4("strong", null, [
          _createTextVNode$2(_toDisplayString$3(status.value.completed) + " ", 1),
          _createElementVNode$4("small", null, "/ " + _toDisplayString$3(status.value.target || (cfg.lottery_mode === 'balance' ? '待计算' : cfg.lottery_count)) + " 次", 1)
        ]),
        _createElementVNode$4("span", null, _toDisplayString$3(progress.value) + "%", 1)
      ]),
      _createElementVNode$4("div", _hoisted_4$3, [
        _createElementVNode$4("i", {
          style: _normalizeStyle$1({ width: progress.value + '%' })
        }, null, 4)
      ]),
      _createElementVNode$4("p", null, _toDisplayString$3(status.value.last_prize ? `最近奖品：${status.value.last_prize}` : '开始后这里会实时显示进度与最近奖品。'), 1),
      _createElementVNode$4("div", _hoisted_5$3, [
        _createElementVNode$4("section", null, [
          _createElementVNode$4("div", _hoisted_6$3, [
            _cache[24] || (_cache[24] = _createElementVNode$4("h3", null, "当前任务", -1)),
            _createElementVNode$4("span", null, _toDisplayString$3(formatNumber(currentStats.value.count)) + " 次 · 消耗 " + _toDisplayString$3(formatNumber(currentStats.value.cost)), 1)
          ]),
          _createElementVNode$4("div", _hoisted_7$3, [
            _createElementVNode$4("span", null, "憨豆奖品 " + _toDisplayString$3(formatNumber(currentStats.value.beans)), 1),
            _createElementVNode$4("b", {
              class: _normalizeClass$4(["profit", profitTone(currentStats.value.profit)])
            }, "净盈亏 " + _toDisplayString$3(formatSigned(currentStats.value.profit)), 3)
          ]),
          (prizeRows(currentStats.value).length)
            ? (_openBlock$4(), _createElementBlock$4("ul", _hoisted_8$3, [
                (_openBlock$4(true), _createElementBlock$4(_Fragment$3, null, _renderList$1(prizeRows(currentStats.value), ([name, count]) => {
                  return (_openBlock$4(), _createElementBlock$4("li", { key: name }, [
                    _createElementVNode$4("span", null, _toDisplayString$3(name), 1),
                    _createElementVNode$4("b", null, "× " + _toDisplayString$3(formatNumber(count)), 1)
                  ]))
                }), 128))
              ]))
            : (_openBlock$4(), _createElementBlock$4("p", _hoisted_9$3, "本轮奖品将在这里实时累积。"))
        ]),
        _createElementVNode$4("section", null, [
          _createElementVNode$4("div", _hoisted_10$2, [
            _cache[25] || (_cache[25] = _createElementVNode$4("h3", null, "累计奖品", -1)),
            _createElementVNode$4("span", null, _toDisplayString$3(formatNumber(cumulativeStats.value.count)) + " 次 · 消耗 " + _toDisplayString$3(formatNumber(cumulativeStats.value.cost)), 1)
          ]),
          _createElementVNode$4("div", _hoisted_11$2, [
            _createElementVNode$4("span", null, "憨豆奖品 " + _toDisplayString$3(formatNumber(cumulativeStats.value.beans)), 1),
            _createElementVNode$4("b", {
              class: _normalizeClass$4(["profit", profitTone(cumulativeStats.value.profit)])
            }, "净盈亏 " + _toDisplayString$3(formatSigned(cumulativeStats.value.profit)), 3)
          ]),
          (prizeRows(cumulativeStats.value).length)
            ? (_openBlock$4(), _createElementBlock$4("ul", _hoisted_12$2, [
                (_openBlock$4(true), _createElementBlock$4(_Fragment$3, null, _renderList$1(prizeRows(cumulativeStats.value), ([name, count]) => {
                  return (_openBlock$4(), _createElementBlock$4("li", { key: name }, [
                    _createElementVNode$4("span", null, _toDisplayString$3(name), 1),
                    _createElementVNode$4("b", null, "× " + _toDisplayString$3(formatNumber(count)), 1)
                  ]))
                }), 128))
              ]))
            : (_openBlock$4(), _createElementBlock$4("p", _hoisted_13$2, "完成第一次抽奖后显示累计记录。"))
        ])
      ])
    ]),
    _createElementVNode$4("div", _hoisted_14$1, [
      _createElementVNode$4("div", _hoisted_15$1, [
        _cache[44] || (_cache[44] = _createElementVNode$4("h3", null, "抽奖设置", -1)),
        _createElementVNode$4("label", _hoisted_16$1, [
          _cache[26] || (_cache[26] = _createElementVNode$4("span", null, [
            _createElementVNode$4("b", null, "启用转盘"),
            _createElementVNode$4("small", null, "关闭后不能启动新任务")
          ], -1)),
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.enabled) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.enabled]
          ])
        ]),
        _createElementVNode$4("label", null, [
          _cache[28] || (_cache[28] = _createElementVNode$4("span", null, "抽奖方式", -1)),
          _withDirectives$3(_createElementVNode$4("select", {
            "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((cfg.lottery_mode) = $event))
          }, [...(_cache[27] || (_cache[27] = [
            _createElementVNode$4("option", { value: "fixed" }, "指定次数", -1),
            _createElementVNode$4("option", { value: "balance" }, "按余额抽完", -1),
            _createElementVNode$4("option", { value: "reserve" }, "保留余额抽取", -1)
          ]))], 512), [
            [_vModelSelect, cfg.lottery_mode]
          ])
        ]),
        (cfg.lottery_mode === 'fixed')
          ? (_openBlock$4(), _createElementBlock$4("label", _hoisted_17$1, [
              _cache[29] || (_cache[29] = _createElementVNode$4("span", null, "抽奖次数", -1)),
              _withDirectives$3(_createElementVNode$4("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.lottery_count) = $event)),
                type: "number",
                min: "1",
                step: "1"
              }, null, 512), [
                [
                  _vModelText$3,
                  cfg.lottery_count,
                  void 0,
                  { number: true }
                ]
              ])
            ]))
          : (cfg.lottery_mode === 'reserve')
            ? (_openBlock$4(), _createElementBlock$4("label", _hoisted_18$1, [
                _cache[30] || (_cache[30] = _createElementVNode$4("span", null, "保留憨豆", -1)),
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.reserve_beans) = $event)),
                  type: "number",
                  min: "0",
                  step: "1000"
                }, null, 512), [
                  [
                    _vModelText$3,
                    cfg.reserve_beans,
                    void 0,
                    { number: true }
                  ]
                ])
              ]))
            : (_openBlock$4(), _createElementBlock$4("p", _hoisted_19$1, "启动时读取憨豆余额和单次消耗，自动计算本次可抽次数。")),
        _createElementVNode$4("label", null, [
          _cache[31] || (_cache[31] = _createElementVNode$4("span", null, "抽奖间隔（秒）", -1)),
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.interval_seconds) = $event)),
            type: "number",
            min: "3",
            max: "30"
          }, null, 512), [
            [
              _vModelText$3,
              cfg.interval_seconds,
              void 0,
              { number: true }
            ]
          ])
        ]),
        _createElementVNode$4("label", null, [
          _cache[32] || (_cache[32] = _createElementVNode$4("span", null, "余额校准间隔", -1)),
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.sync_every_draws) = $event)),
            type: "number",
            min: "1",
            max: "200"
          }, null, 512), [
            [
              _vModelText$3,
              cfg.sync_every_draws,
              void 0,
              { number: true }
            ]
          ])
        ]),
        _createElementVNode$4("label", _hoisted_20$1, [
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.auto_clean_lottery_mail) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.auto_clean_lottery_mail]
          ]),
          _cache[33] || (_cache[33] = _createTextVNode$2(" 校准时清理转盘通知", -1))
        ]),
        _createElementVNode$4("label", _hoisted_21$1, [
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.scheduled_stop_enabled) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.scheduled_stop_enabled]
          ]),
          _cache[34] || (_cache[34] = _createTextVNode$2(" 到指定日期时间自动停止", -1))
        ]),
        (cfg.scheduled_stop_enabled)
          ? (_openBlock$4(), _createElementBlock$4("label", _hoisted_22$1, [
              _cache[35] || (_cache[35] = _createElementVNode$4("span", null, "停止日期时间", -1)),
              _withDirectives$3(_createElementVNode$4("input", {
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.scheduled_stop_at) = $event)),
                type: "datetime-local"
              }, null, 512), [
                [_vModelText$3, cfg.scheduled_stop_at]
              ])
            ]))
          : _createCommentVNode$4("", true),
        (cfg.scheduled_stop_enabled)
          ? (_openBlock$4(), _createElementBlock$4("p", _hoisted_23$1, "任务计划会持久化；平台或插件重启后，将继续剩余抽奖并在此时间停止。"))
          : _createCommentVNode$4("", true),
        _createElementVNode$4("label", _hoisted_24$1, [
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.stop_on_prize) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.stop_on_prize]
          ]),
          _cache[36] || (_cache[36] = _createTextVNode$2(" 命中大奖后自动停止", -1))
        ]),
        (cfg.stop_on_prize)
          ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_25$1, [
              _createElementVNode$4("label", _hoisted_26$1, [
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.stop_on_vip) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox$2, cfg.stop_on_vip]
                ]),
                _cache[37] || (_cache[37] = _createTextVNode$2(" VIP", -1))
              ]),
              _createElementVNode$4("label", _hoisted_27$1, [
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.stop_on_invite) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox$2, cfg.stop_on_invite]
                ]),
                _cache[38] || (_cache[38] = _createTextVNode$2(" 邀请", -1))
              ]),
              _createElementVNode$4("label", _hoisted_28$1, [
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.stop_on_big_beans) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox$2, cfg.stop_on_big_beans]
                ]),
                _cache[39] || (_cache[39] = _createTextVNode$2(" 大额憨豆", -1))
              ]),
              _createElementVNode$4("label", null, [
                _cache[40] || (_cache[40] = _createElementVNode$4("span", null, "大额门槛", -1)),
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.big_bean_threshold) = $event)),
                  type: "number",
                  min: "1",
                  step: "10000"
                }, null, 512), [
                  [
                    _vModelText$3,
                    cfg.big_bean_threshold,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              _createElementVNode$4("label", null, [
                _cache[41] || (_cache[41] = _createElementVNode$4("span", null, "自定义关键词", -1)),
                _withDirectives$3(_createElementVNode$4("input", {
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.stop_prize_keywords) = $event)),
                  type: "text",
                  placeholder: "逗号分隔"
                }, null, 512), [
                  [_vModelText$3, cfg.stop_prize_keywords]
                ])
              ])
            ]))
          : _createCommentVNode$4("", true),
        _createElementVNode$4("label", _hoisted_29$1, [
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((cfg.notify_result) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.notify_result]
          ]),
          _cache[42] || (_cache[42] = _createTextVNode$2(" 完成后推送结果", -1))
        ]),
        _createElementVNode$4("label", _hoisted_30$1, [
          _withDirectives$3(_createElementVNode$4("input", {
            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((cfg.notify_cookie_error) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox$2, cfg.notify_cookie_error]
          ]),
          _cache[43] || (_cache[43] = _createTextVNode$2(" Cookie 异常时通知", -1))
        ]),
        _createElementVNode$4("button", {
          class: "secondary",
          disabled: saving.value,
          onClick: _cache[17] || (_cache[17] = $event => (save()))
        }, _toDisplayString$3(saving.value ? '保存中…' : '保存设置'), 9, _hoisted_31$1)
      ]),
      _createElementVNode$4("div", _hoisted_32$1, [
        _cache[45] || (_cache[45] = _createElementVNode$4("h3", null, "最近结果", -1)),
        _createElementVNode$4("pre", null, _toDisplayString$3(status.value.last_result || '还没有抽奖记录。'), 1)
      ])
    ]),
    _createElementVNode$4("footer", null, [
      _createElementVNode$4("button", {
        class: "primary",
        disabled: busy.value || status.value.running || !cfg.enabled,
        onClick: _cache[18] || (_cache[18] = $event => (action('run', '/lottery/run')))
      }, _toDisplayString$3(busy.value === 'run' ? '正在启动…' : '开始抽奖'), 9, _hoisted_33$1),
      _createElementVNode$4("button", {
        class: "danger",
        disabled: busy.value || !status.value.running,
        onClick: _cache[19] || (_cache[19] = $event => (action('stop', '/lottery/stop')))
      }, "停止抽奖", 8, _hoisted_34$1),
      _createElementVNode$4("button", {
        class: "secondary",
        disabled: busy.value,
        onClick: _cache[20] || (_cache[20] = $event => (action('cookie', '/lottery/cookie/check', 'GET')))
      }, "检查 Cookie 与余额", 8, _hoisted_35$1),
      _createElementVNode$4("button", {
        class: "secondary",
        disabled: busy.value || status.value.running,
        onClick: _cache[21] || (_cache[21] = $event => (action('mail', '/lottery/mail/clean')))
      }, "清理转盘通知", 8, _hoisted_36$1)
    ])
  ]))
}
}

};
const LotteryPanel = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-4c54ed44"]]);

const {createElementVNode:_createElementVNode$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$3,toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$1,normalizeClass:_normalizeClass$3,Fragment:_Fragment$2,normalizeStyle:_normalizeStyle,vModelCheckbox:_vModelCheckbox$1,withDirectives:_withDirectives$2,vModelText:_vModelText$2,renderList:_renderList} = await importShared('vue');


const _hoisted_1$3 = { class: "read-panel" };
const _hoisted_2$3 = {
  key: 0,
  class: "skeleton",
  "aria-label": "正在加载"
};
const _hoisted_3$2 = { class: "header" };
const _hoisted_4$2 = { class: "title-wrap" };
const _hoisted_5$2 = ["innerHTML"];
const _hoisted_6$2 = {
  class: "run-area",
  "aria-labelledby": "run-heading"
};
const _hoisted_7$2 = { class: "run-copy" };
const _hoisted_8$2 = { class: "meta" };
const _hoisted_9$2 = { class: "actions" };
const _hoisted_10$1 = ["disabled"];
const _hoisted_11$1 = ["innerHTML"];
const _hoisted_12$1 = ["disabled"];
const _hoisted_13$1 = ["innerHTML"];
const _hoisted_14 = ["disabled"];
const _hoisted_15 = ["innerHTML"];
const _hoisted_16 = ["disabled"];
const _hoisted_17 = ["innerHTML"];
const _hoisted_18 = ["aria-valuenow"];
const _hoisted_19 = { class: "content-grid" };
const _hoisted_20 = {
  class: "settings",
  "aria-labelledby": "settings-heading"
};
const _hoisted_21 = { class: "section-head" };
const _hoisted_22 = ["disabled"];
const _hoisted_23 = { class: "toggle-row" };
const _hoisted_24 = { class: "toggle-row" };
const _hoisted_25 = { class: "field-grid" };
const _hoisted_26 = { class: "input-unit" };
const _hoisted_27 = { class: "input-unit" };
const _hoisted_28 = {
  class: "history-area",
  "aria-labelledby": "history-heading"
};
const _hoisted_29 = { class: "section-head" };
const _hoisted_30 = { class: "head-actions" };
const _hoisted_31 = ["innerHTML"];
const _hoisted_32 = ["disabled"];
const _hoisted_33 = ["innerHTML"];
const _hoisted_34 = {
  key: 0,
  class: "empty"
};
const _hoisted_35 = ["innerHTML"];
const _hoisted_36 = {
  key: 1,
  class: "history-list"
};
const _hoisted_37 = { class: "history-meta" };

const {computed: computed$1,onBeforeUnmount,onMounted: onMounted$2,reactive: reactive$2,ref: ref$3} = await importShared('vue');



const _sfc_main$3 = {
  __name: 'ReadPanel',
  props: {
  pluginId: { type: String, required: true },
  host: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const cfg = reactive$2({ enabled: true, notify_result: true, page_delay: 1, max_pages: 200 });
const status = ref$3({
  running: false, phase: 'idle', message: '正在读取状态…', current_page: 0,
  total_pages: 0, processed: 0, started_at: '', finished_at: '', stop_requested: false,
});
const history = ref$3([]);
const loading = ref$3(true);
const saving = ref$3(false);
const starting = ref$3(false);
const deleting = ref$3(false);
const stopping = ref$3(false);
const checking = ref$3(false);
const clearing = ref$3(false);
let timer = null;

const phaseLabel = computed$1(() => ({
  idle: '待运行', checking: '检查登录', searching: '查找未读', processing: '处理中',
  completed: '已完成', stopped: '已停止', failed: '运行失败',
}[status.value.phase] || '待运行'));

const progress = computed$1(() => {
  const total = Number(status.value.total_pages || 0);
  const current = Number(status.value.current_page || 0);
  if (!total) return 0
  return Math.max(0, Math.min(100, Math.round(current / total * 100)))
});

const statusTone = computed$1(() => {
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
  try { status.value = await props.host.callApi('/read/status'); }
  catch (error) { /* 轮询失败不打断用户 */ }
}

async function loadHistory() {
  try { history.value = (await props.host.callApi('/read/history')).items || []; }
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
    const result = await props.host.callApi('/read/run', { method: 'POST', body: {} });
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
    await loadStatus();
  } catch (error) {
    props.host.toast.error('启动失败：' + (error.message || error));
  } finally { starting.value = false; }
}

async function runDelete() {
  if (!confirm('确定删除 HHanClub 收件箱中的全部消息吗？\n\n已读和未读消息都会被永久删除，此操作无法撤销。')) return
  deleting.value = true;
  try {
    await props.host.saveConfig({ ...cfg });
    const result = await props.host.callApi('/read/delete', { method: 'POST', body: {} });
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
    await loadStatus();
  } catch (error) {
    props.host.toast.error('启动删除失败：' + (error.message || error));
  } finally { deleting.value = false; }
}

async function stop() {
  stopping.value = true;
  try {
    const result = await props.host.callApi('/read/stop', { method: 'POST', body: {} });
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
    await loadStatus();
  } catch (error) {
    props.host.toast.error('停止失败：' + (error.message || error));
  } finally { stopping.value = false; }
}

async function checkCookie() {
  checking.value = true;
  try {
    const result = await props.host.callApi('/read/cookie/check');
    result.ok ? props.host.toast.success(result.message) : props.host.toast.error(result.message);
  } catch (error) {
    props.host.toast.error('检查失败：' + (error.message || error));
  } finally { checking.value = false; }
}

async function clearHistory() {
  if (!confirm('清空最近运行记录？')) return
  clearing.value = true;
  try {
    const result = await props.host.callApi('/read/history/clear', { method: 'POST', body: {} });
    history.value = [];
    props.host.toast.success(result.message);
  } catch (error) {
    props.host.toast.error('清空失败：' + (error.message || error));
  } finally { clearing.value = false; }
}

function historyStatus(item) {
  return ({ completed: '完成', stopped: '停止', failed: '失败' }[item.status] || item.status)
}

function operationLabel(item) { return item.operation === 'delete' ? '删除' : '已读' }

onMounted$2(async () => {
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
  return (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
    (loading.value)
      ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_2$3, [...(_cache[4] || (_cache[4] = [
          _createElementVNode$3("span", null, null, -1),
          _createElementVNode$3("span", null, null, -1),
          _createElementVNode$3("span", null, null, -1)
        ]))]))
      : (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 1 }, [
          _createElementVNode$3("header", _hoisted_3$2, [
            _createElementVNode$3("div", _hoisted_4$2, [
              (_openBlock$3(), _createElementBlock$3("svg", {
                class: "title-icon",
                viewBox: "0 0 24 24",
                "aria-hidden": "true",
                innerHTML: iconPath('inbox')
              }, null, 8, _hoisted_5$2)),
              _cache[5] || (_cache[5] = _createElementVNode$3("div", null, [
                _createElementVNode$3("h2", null, "消息管理"),
                _createElementVNode$3("p", null, "可以将未读消息批量设为已读，或删除收件箱全部消息。")
              ], -1))
            ]),
            _createElementVNode$3("span", {
              class: _normalizeClass$3(["state", statusTone.value])
            }, [
              _cache[6] || (_cache[6] = _createElementVNode$3("i", null, null, -1)),
              _createTextVNode$1(_toDisplayString$2(phaseLabel.value), 1)
            ], 2)
          ]),
          _createElementVNode$3("section", _hoisted_6$2, [
            _createElementVNode$3("div", _hoisted_7$2, [
              _cache[7] || (_cache[7] = _createElementVNode$3("span", {
                id: "run-heading",
                class: "section-label"
              }, "当前任务", -1)),
              _createElementVNode$3("strong", null, _toDisplayString$2(status.value.message), 1),
              _createElementVNode$3("span", _hoisted_8$2, [
                (status.value.total_pages)
                  ? (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 0 }, [
                      _createTextVNode$1("第 " + _toDisplayString$2(status.value.current_page) + "/" + _toDisplayString$2(status.value.total_pages) + " 页 · ", 1)
                    ], 64))
                  : _createCommentVNode$3("", true),
                _createTextVNode$1(" 已处理 " + _toDisplayString$2(status.value.processed) + " 条 ", 1)
              ])
            ]),
            _createElementVNode$3("div", _hoisted_9$2, [
              (!status.value.running)
                ? (_openBlock$3(), _createElementBlock$3("button", {
                    key: 0,
                    class: "button primary",
                    disabled: starting.value || !cfg.enabled,
                    onClick: run
                  }, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('play')
                    }, null, 8, _hoisted_11$1)),
                    _createTextVNode$1(" " + _toDisplayString$2(starting.value ? '启动中…' : '开始全部已读'), 1)
                  ], 8, _hoisted_10$1))
                : _createCommentVNode$3("", true),
              (!status.value.running)
                ? (_openBlock$3(), _createElementBlock$3("button", {
                    key: 1,
                    class: "button danger",
                    disabled: deleting.value || !cfg.enabled,
                    onClick: runDelete
                  }, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('trash')
                    }, null, 8, _hoisted_13$1)),
                    _createTextVNode$1(" " + _toDisplayString$2(deleting.value ? '启动中…' : '删除全部消息'), 1)
                  ], 8, _hoisted_12$1))
                : (_openBlock$3(), _createElementBlock$3("button", {
                    key: 2,
                    class: "button danger",
                    disabled: stopping.value || status.value.stop_requested,
                    onClick: stop
                  }, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('stop')
                    }, null, 8, _hoisted_15)),
                    _createTextVNode$1(" " + _toDisplayString$2(status.value.stop_requested ? '等待停止…' : stopping.value ? '提交中…' : '停止任务'), 1)
                  ], 8, _hoisted_14)),
              _createElementVNode$3("button", {
                class: "button",
                disabled: checking.value || status.value.running,
                onClick: checkCookie
              }, [
                (_openBlock$3(), _createElementBlock$3("svg", {
                  viewBox: "0 0 24 24",
                  "aria-hidden": "true",
                  innerHTML: iconPath('shield')
                }, null, 8, _hoisted_17)),
                _createTextVNode$1(" " + _toDisplayString$2(checking.value ? '检查中…' : '检查 Cookie'), 1)
              ], 8, _hoisted_16)
            ]),
            _createElementVNode$3("div", {
              class: "progress",
              role: "progressbar",
              "aria-valuenow": progress.value,
              "aria-valuemin": "0",
              "aria-valuemax": "100"
            }, [
              _createElementVNode$3("span", {
                style: _normalizeStyle({ transform: `scaleX(${progress.value / 100})` })
              }, null, 4)
            ], 8, _hoisted_18)
          ]),
          _createElementVNode$3("div", _hoisted_19, [
            _createElementVNode$3("section", _hoisted_20, [
              _createElementVNode$3("div", _hoisted_21, [
                _cache[8] || (_cache[8] = _createElementVNode$3("div", null, [
                  _createElementVNode$3("h3", { id: "settings-heading" }, "运行设置"),
                  _createElementVNode$3("p", null, "开始任务时会先自动保存这些设置。")
                ], -1)),
                _createElementVNode$3("button", {
                  class: "button compact",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString$2(saving.value ? '保存中…' : '保存'), 9, _hoisted_22)
              ]),
              _createElementVNode$3("label", _hoisted_23, [
                _cache[9] || (_cache[9] = _createElementVNode$3("span", null, [
                  _createElementVNode$3("b", null, "启用插件"),
                  _createElementVNode$3("small", null, "关闭后不能启动新任务")
                ], -1)),
                _withDirectives$2(_createElementVNode$3("input", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.enabled) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox$1, cfg.enabled]
                ])
              ]),
              _createElementVNode$3("label", _hoisted_24, [
                _cache[10] || (_cache[10] = _createElementVNode$3("span", null, [
                  _createElementVNode$3("b", null, "完成后推送结果"),
                  _createElementVNode$3("small", null, "通过平台通知渠道发送处理汇总")
                ], -1)),
                _withDirectives$2(_createElementVNode$3("input", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((cfg.notify_result) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox$1, cfg.notify_result]
                ])
              ]),
              _createElementVNode$3("div", _hoisted_25, [
                _createElementVNode$3("label", null, [
                  _cache[12] || (_cache[12] = _createElementVNode$3("span", null, "翻页间隔", -1)),
                  _createElementVNode$3("div", _hoisted_26, [
                    _withDirectives$2(_createElementVNode$3("input", {
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.page_delay) = $event)),
                      type: "number",
                      min: "0.2",
                      max: "10",
                      step: "0.1"
                    }, null, 512), [
                      [
                        _vModelText$2,
                        cfg.page_delay,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[11] || (_cache[11] = _createElementVNode$3("em", null, "秒", -1))
                  ])
                ]),
                _createElementVNode$3("label", null, [
                  _cache[14] || (_cache[14] = _createElementVNode$3("span", null, "最多扫描", -1)),
                  _createElementVNode$3("div", _hoisted_27, [
                    _withDirectives$2(_createElementVNode$3("input", {
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.max_pages) = $event)),
                      type: "number",
                      min: "1",
                      max: "1000"
                    }, null, 512), [
                      [
                        _vModelText$2,
                        cfg.max_pages,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[13] || (_cache[13] = _createElementVNode$3("em", null, "页", -1))
                  ])
                ])
              ]),
              _cache[15] || (_cache[15] = _createElementVNode$3("p", { class: "notice" }, [
                _createElementVNode$3("b", null, "全部已读"),
                _createTextVNode$1("只处理带 "),
                _createElementVNode$3("code", null, "icon-unread.svg"),
                _createTextVNode$1(" 标记的消息；"),
                _createElementVNode$3("b", null, "删除全部消息"),
                _createTextVNode$1("会清空当前收件箱中的已读和未读消息，且无法撤销。")
              ], -1))
            ]),
            _createElementVNode$3("section", _hoisted_28, [
              _createElementVNode$3("div", _hoisted_29, [
                _cache[16] || (_cache[16] = _createElementVNode$3("div", null, [
                  _createElementVNode$3("h3", { id: "history-heading" }, "最近运行"),
                  _createElementVNode$3("p", null, "保留最近 20 次处理结果。")
                ], -1)),
                _createElementVNode$3("div", _hoisted_30, [
                  _createElementVNode$3("button", {
                    class: "icon-button",
                    title: "刷新记录",
                    "aria-label": "刷新记录",
                    onClick: loadHistory
                  }, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('refresh')
                    }, null, 8, _hoisted_31))
                  ]),
                  _createElementVNode$3("button", {
                    class: "icon-button danger-text",
                    title: "清空记录",
                    "aria-label": "清空记录",
                    disabled: clearing.value || !history.value.length,
                    onClick: clearHistory
                  }, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('trash')
                    }, null, 8, _hoisted_33))
                  ], 8, _hoisted_32)
                ])
              ]),
              (!history.value.length)
                ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_34, [
                    (_openBlock$3(), _createElementBlock$3("svg", {
                      viewBox: "0 0 24 24",
                      "aria-hidden": "true",
                      innerHTML: iconPath('inbox')
                    }, null, 8, _hoisted_35)),
                    _cache[17] || (_cache[17] = _createElementVNode$3("b", null, "还没有运行记录", -1)),
                    _cache[18] || (_cache[18] = _createElementVNode$3("span", null, "首次执行后，处理数量和结果会显示在这里。", -1))
                  ]))
                : (_openBlock$3(), _createElementBlock$3("div", _hoisted_36, [
                    (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList(history.value, (item, index) => {
                      return (_openBlock$3(), _createElementBlock$3("article", {
                        key: item.time + index,
                        class: "history-item"
                      }, [
                        _createElementVNode$3("span", {
                          class: _normalizeClass$3(["history-status", item.status])
                        }, _toDisplayString$2(historyStatus(item)), 3),
                        _createElementVNode$3("div", null, [
                          _createElementVNode$3("b", null, _toDisplayString$2(operationLabel(item)) + " · " + _toDisplayString$2(item.processed) + " 条消息", 1),
                          _createElementVNode$3("span", null, _toDisplayString$2(item.detail), 1)
                        ]),
                        _createElementVNode$3("div", _hoisted_37, [
                          _createElementVNode$3("time", null, _toDisplayString$2(item.time), 1),
                          _createElementVNode$3("span", null, _toDisplayString$2(item.pages) + " 页", 1)
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
const ReadPanel = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-cda4d93d"]]);

const {openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass$2,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives$1,vModelText:_vModelText$1,Fragment:_Fragment$1} = await importShared('vue');


const _hoisted_1$2 = { class: "bonus-panel" };
const _hoisted_2$2 = {
  key: 0,
  class: "loading"
};
const _hoisted_3$1 = { class: "layout" };
const _hoisted_4$1 = { class: "card" };
const _hoisted_5$1 = { class: "section-head" };
const _hoisted_6$1 = ["disabled"];
const _hoisted_7$1 = { class: "switch-row" };
const _hoisted_8$1 = { class: "switch-row" };
const _hoisted_9$1 = { class: "fields" };
const _hoisted_10 = { class: "card guide" };
const _hoisted_11 = { class: "example" };
const _hoisted_12 = { class: "example" };
const _hoisted_13 = ["disabled"];

const {onMounted: onMounted$1,reactive: reactive$1,ref: ref$2} = await importShared('vue');



const _sfc_main$2 = {
  __name: 'BonusPanel',
  props: { pluginId: String, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const cfg = reactive$1({ bonus_enabled: true, notify_cookie_error: true, single_command: '.hh', batch_command: '.hhs', cooldown_seconds: 10, result_delete: 90 });
const loading = ref$2(true);
const saving = ref$2(false);
const checking = ref$2(false);

async function save() {
  saving.value = true;
  try {
    cfg.single_command = String(cfg.single_command || '.hh').trim() || '.hh';
    cfg.batch_command = String(cfg.batch_command || '.hhs').trim() || '.hhs';
    cfg.cooldown_seconds = Math.max(0, Math.min(Number(cfg.cooldown_seconds) || 0, 600));
    cfg.result_delete = Math.max(10, Math.min(Number(cfg.result_delete) || 90, 600));
    await props.host.saveConfig({ ...cfg });
    props.host.toast.success('赠豆配置已保存');
  } catch (error) { props.host.toast.error('保存失败：' + (error.message || error)); }
  finally { saving.value = false; }
}

async function checkCookie() {
  checking.value = true;
  try {
    const result = await props.host.callApi('/bonus/cookie/check')
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message);
  } catch (error) { props.host.toast.error('检查失败：' + (error.message || error)); }
  finally { checking.value = false; }
}

onMounted$1(async () => {
  try { Object.assign(cfg, await props.host.getConfig() || {}); }
  catch (error) { props.host.toast.error('读取配置失败：' + (error.message || error)); }
  finally { loading.value = false; }
});

return (_ctx, _cache) => {
  return (_openBlock$2(), _createElementBlock$2("section", _hoisted_1$2, [
    (loading.value)
      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_2$2, "正在读取配置…"))
      : (_openBlock$2(), _createElementBlock$2(_Fragment$1, { key: 1 }, [
          _createElementVNode$2("header", null, [
            _cache[7] || (_cache[7] = _createElementVNode$2("div", null, [
              _createElementVNode$2("p", { class: "eyebrow" }, "HHANCLUB"),
              _createElementVNode$2("h2", null, "赠豆助手"),
              _createElementVNode$2("p", null, "通过自己的用户账号发送命令，支持单人和批量赠送。")
            ], -1)),
            _createElementVNode$2("span", {
              class: _normalizeClass$2(["badge", { on: cfg.bonus_enabled }])
            }, [
              _cache[6] || (_cache[6] = _createElementVNode$2("i", null, null, -1)),
              _createTextVNode(_toDisplayString$1(cfg.bonus_enabled ? '命令已启用' : '命令已停用'), 1)
            ], 2)
          ]),
          _createElementVNode$2("div", _hoisted_3$1, [
            _createElementVNode$2("section", _hoisted_4$1, [
              _createElementVNode$2("div", _hoisted_5$1, [
                _cache[8] || (_cache[8] = _createElementVNode$2("div", null, [
                  _createElementVNode$2("h3", null, "命令设置"),
                  _createElementVNode$2("p", null, "修改后立即保存，下一条消息开始生效。")
                ], -1)),
                _createElementVNode$2("button", {
                  class: "primary",
                  disabled: saving.value,
                  onClick: save
                }, _toDisplayString$1(saving.value ? '保存中…' : '保存设置'), 9, _hoisted_6$1)
              ]),
              _createElementVNode$2("label", _hoisted_7$1, [
                _cache[9] || (_cache[9] = _createElementVNode$2("span", null, [
                  _createElementVNode$2("b", null, "启用赠豆命令"),
                  _createElementVNode$2("small", null, "监听用户账号发出的匹配命令")
                ], -1)),
                _withDirectives$1(_createElementVNode$2("input", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.bonus_enabled) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox, cfg.bonus_enabled]
                ])
              ]),
              _createElementVNode$2("label", _hoisted_8$1, [
                _cache[10] || (_cache[10] = _createElementVNode$2("span", null, [
                  _createElementVNode$2("b", null, "Cookie 异常时通知"),
                  _createElementVNode$2("small", null, "登录态失效时通过平台通知提醒")
                ], -1)),
                _withDirectives$1(_createElementVNode$2("input", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((cfg.notify_cookie_error) = $event)),
                  type: "checkbox",
                  role: "switch"
                }, null, 512), [
                  [_vModelCheckbox, cfg.notify_cookie_error]
                ])
              ]),
              _createElementVNode$2("div", _hoisted_9$1, [
                _createElementVNode$2("label", null, [
                  _cache[11] || (_cache[11] = _createElementVNode$2("span", null, "单人命令", -1)),
                  _withDirectives$1(_createElementVNode$2("input", {
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.single_command) = $event)),
                    type: "text",
                    placeholder: ".hh"
                  }, null, 512), [
                    [_vModelText$1, cfg.single_command]
                  ])
                ]),
                _createElementVNode$2("label", null, [
                  _cache[12] || (_cache[12] = _createElementVNode$2("span", null, "批量命令", -1)),
                  _withDirectives$1(_createElementVNode$2("input", {
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.batch_command) = $event)),
                    type: "text",
                    placeholder: ".hhs"
                  }, null, 512), [
                    [_vModelText$1, cfg.batch_command]
                  ])
                ]),
                _createElementVNode$2("label", null, [
                  _cache[14] || (_cache[14] = _createElementVNode$2("span", null, "赠送冷却", -1)),
                  _createElementVNode$2("div", null, [
                    _withDirectives$1(_createElementVNode$2("input", {
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.cooldown_seconds) = $event)),
                      type: "number",
                      min: "0",
                      max: "600"
                    }, null, 512), [
                      [
                        _vModelText$1,
                        cfg.cooldown_seconds,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[13] || (_cache[13] = _createElementVNode$2("em", null, "秒", -1))
                  ])
                ]),
                _createElementVNode$2("label", null, [
                  _cache[16] || (_cache[16] = _createElementVNode$2("span", null, "结果保留", -1)),
                  _createElementVNode$2("div", null, [
                    _withDirectives$1(_createElementVNode$2("input", {
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.result_delete) = $event)),
                      type: "number",
                      min: "10",
                      max: "600"
                    }, null, 512), [
                      [
                        _vModelText$1,
                        cfg.result_delete,
                        void 0,
                        { number: true }
                      ]
                    ]),
                    _cache[15] || (_cache[15] = _createElementVNode$2("em", null, "秒", -1))
                  ])
                ])
              ])
            ]),
            _createElementVNode$2("aside", _hoisted_10, [
              _cache[19] || (_cache[19] = _createElementVNode$2("h3", null, "命令格式", -1)),
              _createElementVNode$2("div", _hoisted_11, [
                _cache[17] || (_cache[17] = _createElementVNode$2("span", null, "单人赠送", -1)),
                _createElementVNode$2("code", null, _toDisplayString$1(cfg.single_command || '.hh') + " Alice 100 感谢分享", 1)
              ]),
              _createElementVNode$2("div", _hoisted_12, [
                _cache[18] || (_cache[18] = _createElementVNode$2("span", null, "批量赠送", -1)),
                _createElementVNode$2("code", null, _toDisplayString$1(cfg.batch_command || '.hhs') + " Alice Bob 100 感谢", 1)
              ]),
              _cache[20] || (_cache[20] = _createElementVNode$2("ul", null, [
                _createElementVNode$2("li", null, "站点最低赠送 100 憨豆"),
                _createElementVNode$2("li", null, "批量任务最多 50 位用户"),
                _createElementVNode$2("li", null, "接收方会按站点规则扣除税费"),
                _createElementVNode$2("li", null, "批量留言不能包含空格")
              ], -1)),
              _createElementVNode$2("button", {
                class: "secondary",
                disabled: checking.value,
                onClick: checkCookie
              }, _toDisplayString$1(checking.value ? '检查中…' : '检查平台 Cookie'), 9, _hoisted_13)
            ])
          ])
        ], 64))
  ]))
}
}

};
const BonusPanel = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-db48bb98"]]);

const {openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString,vModelRadio:_vModelRadio,withDirectives:_withDirectives,normalizeClass:_normalizeClass$1,vModelText:_vModelText,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1$1 = { class: "cookie-panel" };
const _hoisted_2$1 = {
  key: 0,
  class: "loading"
};
const _hoisted_3 = { class: "source-badge" };
const _hoisted_4 = {
  class: "source-grid",
  role: "radiogroup",
  "aria-label": "Cookie 来源"
};
const _hoisted_5 = { class: "card-head" };
const _hoisted_6 = ["disabled"];
const _hoisted_7 = ["disabled"];
const _hoisted_8 = ["disabled"];
const _hoisted_9 = ["disabled"];

const {computed,onMounted,reactive,ref: ref$1} = await importShared('vue');



const _sfc_main$1 = {
  __name: 'CookiePanel',
  props: { pluginId: String, host: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const cfg = reactive({ cookie_source: 'platform', manual_cookie: '' });
const loading = ref$1(true);
const saving = ref$1(false);
const checking = ref$1(false);
const checked = ref$1(null);
const hasManual = computed(() => Boolean(String(cfg.manual_cookie || '').trim()));

async function save(showToast = true) {
  saving.value = true;
  try {
    cfg.cookie_source = cfg.cookie_source === 'manual' ? 'manual' : 'platform';
    cfg.manual_cookie = String(cfg.manual_cookie || '').trim().replace(/^cookie:\s*/i, '');
    if (cfg.cookie_source === 'manual' && !cfg.manual_cookie) throw new Error('请先填写手动 Cookie')
    await props.host.saveConfig({ ...cfg });
    checked.value = null;
    if (showToast) props.host.toast.success('登录设置已保存');
    return true
  } catch (error) { props.host.toast.error('保存失败：' + (error.message || error)); return false }
  finally { saving.value = false; }
}

async function check() {
  checking.value = true;
  try {
    if (!await save(false)) return
    const result = await props.host.callApi('/auth/check');
    checked.value = result
    ;(result.ok ? props.host.toast.success : props.host.toast.error)(result.message);
  } catch (_) { checked.value = { ok: false, message: '登录设置未通过检查' }; }
  finally { checking.value = false; }
}

async function clearManual() {
  if (!confirm('清空已保存的手动 Cookie？')) return
  cfg.manual_cookie = '';
  if (cfg.cookie_source === 'manual') cfg.cookie_source = 'platform';
  try { await props.host.saveConfig({ ...cfg }); checked.value = null; props.host.toast.success('手动 Cookie 已清空，已切换到平台读取'); }
  catch (error) { props.host.toast.error('清空失败：' + (error.message || error)); }
}

onMounted(async () => {
  try { Object.assign(cfg, await props.host.getConfig() || {}); }
  catch (error) { props.host.toast.error('读取登录设置失败：' + (error.message || error)); }
  finally { loading.value = false; }
});

return (_ctx, _cache) => {
  return (_openBlock$1(), _createElementBlock$1("section", _hoisted_1$1, [
    (loading.value)
      ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, "正在读取登录设置…"))
      : (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 1 }, [
          _createElementVNode$1("header", null, [
            _cache[4] || (_cache[4] = _createElementVNode$1("div", null, [
              _createElementVNode$1("p", { class: "eyebrow" }, "ACCOUNT ACCESS"),
              _createElementVNode$1("h2", null, "登录设置"),
              _createElementVNode$1("p", null, "选择憨憨小助手访问 HHanClub 时使用的 Cookie 来源。")
            ], -1)),
            _createElementVNode$1("span", _hoisted_3, _toDisplayString(cfg.cookie_source === 'manual' ? '手动 Cookie' : '平台同步'), 1)
          ]),
          _createElementVNode$1("div", _hoisted_4, [
            _createElementVNode$1("label", {
              class: _normalizeClass$1({ selected: cfg.cookie_source === 'platform' })
            }, [
              _withDirectives(_createElementVNode$1("input", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((cfg.cookie_source) = $event)),
                type: "radio",
                value: "platform"
              }, null, 512), [
                [_vModelRadio, cfg.cookie_source]
              ]),
              _cache[5] || (_cache[5] = _createElementVNode$1("span", { class: "radio-dot" }, null, -1)),
              _cache[6] || (_cache[6] = _createElementVNode$1("span", null, [
                _createElementVNode$1("b", null, "从平台读取"),
                _createElementVNode$1("small", null, "使用 AWBotNest 已同步的 hhanclub.net Cookie")
              ], -1))
            ], 2),
            _createElementVNode$1("label", {
              class: _normalizeClass$1({ selected: cfg.cookie_source === 'manual' })
            }, [
              _withDirectives(_createElementVNode$1("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((cfg.cookie_source) = $event)),
                type: "radio",
                value: "manual"
              }, null, 512), [
                [_vModelRadio, cfg.cookie_source]
              ]),
              _cache[7] || (_cache[7] = _createElementVNode$1("span", { class: "radio-dot" }, null, -1)),
              _cache[8] || (_cache[8] = _createElementVNode$1("span", null, [
                _createElementVNode$1("b", null, "手动填写"),
                _createElementVNode$1("small", null, "使用下方保存的 Cookie，适合平台同步不可用时")
              ], -1))
            ], 2)
          ]),
          _createElementVNode$1("section", {
            class: _normalizeClass$1(["card", { inactive: cfg.cookie_source !== 'manual' }])
          }, [
            _createElementVNode$1("div", _hoisted_5, [
              _cache[9] || (_cache[9] = _createElementVNode$1("div", null, [
                _createElementVNode$1("h3", null, "手动 Cookie"),
                _createElementVNode$1("p", null, "从浏览器开发者工具复制完整 Cookie 值，不需要填写“Cookie:”前缀。")
              ], -1)),
              _createElementVNode$1("button", {
                class: "text-danger",
                disabled: !hasManual.value,
                onClick: clearManual
              }, "清空", 8, _hoisted_6)
            ]),
            _withDirectives(_createElementVNode$1("input", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((cfg.manual_cookie) = $event)),
              type: "password",
              autocomplete: "off",
              spellcheck: "false",
              placeholder: "name=value; name2=value2",
              disabled: cfg.cookie_source !== 'manual'
            }, null, 8, _hoisted_7), [
              [_vModelText, cfg.manual_cookie]
            ]),
            _cache[10] || (_cache[10] = _createElementVNode$1("p", { class: "security" }, "Cookie 相当于账号登录凭证。请勿发送给他人，建议定期更新。", -1))
          ], 2),
          (checked.value)
            ? (_openBlock$1(), _createElementBlock$1("div", {
                key: 0,
                class: _normalizeClass$1(["result", checked.value.ok ? 'success' : 'danger'])
              }, [
                _createElementVNode$1("b", null, _toDisplayString(checked.value.ok ? '连接正常' : '连接失败'), 1),
                _createElementVNode$1("span", null, _toDisplayString(checked.value.message), 1)
              ], 2))
            : _createCommentVNode$1("", true),
          _createElementVNode$1("footer", null, [
            _createElementVNode$1("button", {
              class: "primary",
              disabled: saving.value || checking.value,
              onClick: _cache[3] || (_cache[3] = $event => (save()))
            }, _toDisplayString(saving.value ? '保存中…' : '保存设置'), 9, _hoisted_8),
            _createElementVNode$1("button", {
              class: "secondary",
              disabled: saving.value || checking.value,
              onClick: check
            }, _toDisplayString(checking.value ? '检查中…' : '保存并检查连接'), 9, _hoisted_9)
          ])
        ], 64))
  ]))
}
}

};
const CookiePanel = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-298af4e7"]]);

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "plugin-shell" };
const _hoisted_2 = {
  class: "tabs",
  "aria-label": "插件功能"
};

const {ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: { pluginId: { type: String, required: true }, host: { type: Object, required: true } },
  setup(__props) {


const tab = ref('bonus');

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("nav", _hoisted_2, [
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'bonus' }),
        onClick: _cache[0] || (_cache[0] = $event => (tab.value = 'bonus'))
      }, "赠豆", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'lottery' }),
        onClick: _cache[1] || (_cache[1] = $event => (tab.value = 'lottery'))
      }, "幸运转盘", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'read' }),
        onClick: _cache[2] || (_cache[2] = $event => (tab.value = 'read'))
      }, "消息管理", 2),
      _createElementVNode("button", {
        class: _normalizeClass({ active: tab.value === 'auth' }),
        onClick: _cache[3] || (_cache[3] = $event => (tab.value = 'auth'))
      }, "登录设置", 2)
    ]),
    (tab.value === 'bonus')
      ? (_openBlock(), _createBlock(BonusPanel, {
          key: 0,
          "plugin-id": __props.pluginId,
          host: __props.host
        }, null, 8, ["plugin-id", "host"]))
      : (tab.value === 'lottery')
        ? (_openBlock(), _createBlock(LotteryPanel, {
            key: 1,
            "plugin-id": __props.pluginId,
            host: __props.host
          }, null, 8, ["plugin-id", "host"]))
        : (tab.value === 'read')
          ? (_openBlock(), _createBlock(ReadPanel, {
              key: 2,
              "plugin-id": __props.pluginId,
              host: __props.host
            }, null, 8, ["plugin-id", "host"]))
          : (_openBlock(), _createBlock(CookiePanel, {
              key: 3,
              "plugin-id": __props.pluginId,
              host: __props.host
            }, null, 8, ["plugin-id", "host"]))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-542a09dd"]]);

export { Config as default };
