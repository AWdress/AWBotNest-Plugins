import { importShared } from './__federation_fn_import-GzAXfPDJ.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,vModelSelect:_vModelSelect,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "hdhive-quiz-config" };
const _hoisted_2 = { class: "tabs" };
const _hoisted_3 = { class: "tab-content" };
const _hoisted_4 = {
  key: 0,
  class: "settings"
};
const _hoisted_5 = { class: "section" };
const _hoisted_6 = { class: "row switch" };
const _hoisted_7 = { class: "row" };
const _hoisted_8 = { class: "row" };
const _hoisted_9 = { class: "row" };
const _hoisted_10 = { class: "section" };
const _hoisted_11 = { class: "row switch" };
const _hoisted_12 = { class: "row" };
const _hoisted_13 = ["disabled"];
const _hoisted_14 = { class: "row" };
const _hoisted_15 = ["disabled"];
const _hoisted_16 = { class: "row" };
const _hoisted_17 = ["disabled"];
const _hoisted_18 = { class: "section" };
const _hoisted_19 = { class: "row" };
const _hoisted_20 = { class: "row" };
const _hoisted_21 = { class: "row" };
const _hoisted_22 = { class: "row" };
const _hoisted_23 = ["disabled"];
const _hoisted_24 = {
  key: 1,
  class: "status"
};
const _hoisted_25 = { class: "card" };
const _hoisted_26 = { class: "kv" };
const _hoisted_27 = { class: "kv" };
const _hoisted_28 = { class: "kv" };
const _hoisted_29 = ["disabled"];
const _hoisted_30 = ["disabled"];
const _hoisted_31 = {
  key: 2,
  class: "history"
};
const _hoisted_32 = { class: "toolbar" };
const _hoisted_33 = { class: "muted" };
const _hoisted_34 = { class: "tbl" };
const _hoisted_35 = { class: "muted" };
const _hoisted_36 = { key: 0 };

const {ref,onMounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: { api: Object, config: Object },
  setup(__props) {

const props = __props;
const cfg = ref({
  enabled: false, bot_ids: '', chat_ids: '', reply_format: 'content',
  llm_enabled: false, llm_api_key: '', llm_base_url: '', llm_model: 'gpt-4o-mini',
  bank_repo: 'https://github.com/my-name-is-alan/hdhive-red-questions',
  bank_branch: 'main', bank_subdir: 'questions', bank_sync_hours: 12,
});
const tab = ref('settings');
const saving = ref(false);
const status = ref({});
const syncing = ref(false);
const testing = ref(false);
const testResult = ref(null);
const history = ref([]);

onMounted(() => {
  Object.assign(cfg.value, props.config || {});
  loadStatus();
  loadHistory();
  setInterval(loadStatus, 5000);
});

async function save() {
  saving.value = true;
  try {
    await props.api.post('/update_config', cfg.value);
    saving.value = false;
  } catch (e) {
    alert('保存失败：' + e.message);
    saving.value = false;
  }
}

async function loadStatus() {
  try {
    const r = await props.api.get('/status');
    status.value = r;
  } catch {}
}

async function syncBank() {
  syncing.value = true;
  try {
    const r = await props.api.post('/sync');
    alert(r.message || '同步完成');
    loadStatus();
  } catch (e) {
    alert('同步失败：' + e.message);
  } finally {
    syncing.value = false;
  }
}

async function testLLM() {
  testing.value = true;
  testResult.value = null;
  try {
    const r = await props.api.post('/test_llm');
    testResult.value = r;
  } catch (e) {
    testResult.value = { ok: false, message: '测试失败：' + e.message };
  } finally {
    testing.value = false;
  }
}

async function loadHistory() {
  try {
    const r = await props.api.get('/history');
    history.value = r.history || [];
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
        class: _normalizeClass({ active: tab.value === 'history' }),
        onClick: _cache[2] || (_cache[2] = $event => (tab.value = 'history'))
      }, "📝 答题记录", 2)
    ]),
    _createElementVNode("div", _hoisted_3, [
      (tab.value === 'settings')
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[20] || (_cache[20] = _createElementVNode("h3", null, "基本设置", -1)),
              _createElementVNode("label", _hoisted_6, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((cfg.value.enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.enabled]
                ]),
                _cache[15] || (_cache[15] = _createElementVNode("span", null, "启用自动答题", -1))
              ]),
              _createElementVNode("label", _hoisted_7, [
                _cache[16] || (_cache[16] = _createElementVNode("span", null, "发包 Bot ID", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((cfg.value.bot_ids) = $event)),
                  class: "inp",
                  placeholder: "留空=监听所有 bot，多个用逗号分隔"
                }, null, 512), [
                  [_vModelText, cfg.value.bot_ids]
                ])
              ]),
              _createElementVNode("label", _hoisted_8, [
                _cache[17] || (_cache[17] = _createElementVNode("span", null, "监听群组 ID", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((cfg.value.chat_ids) = $event)),
                  class: "inp",
                  placeholder: "留空=监听所有群，多个用逗号分隔"
                }, null, 512), [
                  [_vModelText, cfg.value.chat_ids]
                ])
              ]),
              _createElementVNode("label", _hoisted_9, [
                _cache[19] || (_cache[19] = _createElementVNode("span", null, "回复格式", -1)),
                _withDirectives(_createElementVNode("select", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((cfg.value.reply_format) = $event)),
                  class: "inp"
                }, [...(_cache[18] || (_cache[18] = [
                  _createElementVNode("option", { value: "content" }, "选项原文（如：蜜蜂）", -1),
                  _createElementVNode("option", { value: "letter" }, "选项字母（如：A）", -1),
                  _createElementVNode("option", { value: "full" }, "字母+原文（如：A. 蜜蜂）", -1)
                ]))], 512), [
                  [_vModelSelect, cfg.value.reply_format]
                ])
              ]),
              _cache[21] || (_cache[21] = _createElementVNode("p", { class: "tip" }, "回复答案的文本形式。判断题固定回复 对/错。", -1))
            ]),
            _createElementVNode("div", _hoisted_10, [
              _cache[26] || (_cache[26] = _createElementVNode("h3", null, "大模型兜底", -1)),
              _createElementVNode("label", _hoisted_11, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((cfg.value.llm_enabled) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, cfg.value.llm_enabled]
                ]),
                _cache[22] || (_cache[22] = _createElementVNode("span", null, "题库未命中时用大模型兜底", -1))
              ]),
              _createElementVNode("label", _hoisted_12, [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "API Key", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((cfg.value.llm_api_key) = $event)),
                  type: "password",
                  class: "inp",
                  disabled: !cfg.value.llm_enabled
                }, null, 8, _hoisted_13), [
                  [_vModelText, cfg.value.llm_api_key]
                ])
              ]),
              _createElementVNode("label", _hoisted_14, [
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "接口地址", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((cfg.value.llm_base_url) = $event)),
                  class: "inp",
                  placeholder: "如 https://api.openai.com/v1",
                  disabled: !cfg.value.llm_enabled
                }, null, 8, _hoisted_15), [
                  [_vModelText, cfg.value.llm_base_url]
                ])
              ]),
              _createElementVNode("label", _hoisted_16, [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "模型", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((cfg.value.llm_model) = $event)),
                  class: "inp",
                  placeholder: "gpt-4o-mini",
                  disabled: !cfg.value.llm_enabled
                }, null, 8, _hoisted_17), [
                  [_vModelText, cfg.value.llm_model]
                ])
              ])
            ]),
            _createElementVNode("div", _hoisted_18, [
              _cache[31] || (_cache[31] = _createElementVNode("h3", null, "题库设置", -1)),
              _createElementVNode("label", _hoisted_19, [
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "题库仓库", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((cfg.value.bank_repo) = $event)),
                  class: "inp",
                  placeholder: "GitHub 仓库地址"
                }, null, 512), [
                  [_vModelText, cfg.value.bank_repo]
                ])
              ]),
              _createElementVNode("label", _hoisted_20, [
                _cache[28] || (_cache[28] = _createElementVNode("span", null, "分支", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((cfg.value.bank_branch) = $event)),
                  class: "inp",
                  placeholder: "main"
                }, null, 512), [
                  [_vModelText, cfg.value.bank_branch]
                ])
              ]),
              _createElementVNode("label", _hoisted_21, [
                _cache[29] || (_cache[29] = _createElementVNode("span", null, "子目录", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((cfg.value.bank_subdir) = $event)),
                  class: "inp",
                  placeholder: "questions"
                }, null, 512), [
                  [_vModelText, cfg.value.bank_subdir]
                ])
              ]),
              _createElementVNode("label", _hoisted_22, [
                _cache[30] || (_cache[30] = _createElementVNode("span", null, "同步间隔(小时)", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((cfg.value.bank_sync_hours) = $event)),
                  type: "number",
                  class: "inp",
                  min: "1"
                }, null, 512), [
                  [
                    _vModelText,
                    cfg.value.bank_sync_hours,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ]),
            _createElementVNode("button", {
              onClick: save,
              class: "btn-primary",
              disabled: saving.value
            }, _toDisplayString(saving.value ? '保存中...' : '保存配置'), 9, _hoisted_23)
          ]))
        : (tab.value === 'status')
          ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
              _createElementVNode("div", _hoisted_25, [
                _cache[35] || (_cache[35] = _createElementVNode("h3", null, "题库状态", -1)),
                _createElementVNode("div", _hoisted_26, [
                  _cache[32] || (_cache[32] = _createElementVNode("span", null, "题目数量", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.bank_size || 0), 1)
                ]),
                _createElementVNode("div", _hoisted_27, [
                  _cache[33] || (_cache[33] = _createElementVNode("span", null, "最后同步", -1)),
                  _createElementVNode("b", null, _toDisplayString(status.value.last_sync || '从未同步'), 1)
                ]),
                _createElementVNode("div", _hoisted_28, [
                  _cache[34] || (_cache[34] = _createElementVNode("span", null, "同步状态", -1)),
                  _createElementVNode("b", {
                    class: _normalizeClass(status.value.sync_running ? 'running' : '')
                  }, _toDisplayString(status.value.sync_status || '空闲'), 3)
                ])
              ]),
              _createElementVNode("button", {
                onClick: syncBank,
                class: "btn",
                disabled: syncing.value
              }, _toDisplayString(syncing.value ? '同步中...' : '手动同步题库'), 9, _hoisted_29),
              _createElementVNode("button", {
                onClick: testLLM,
                class: "btn",
                disabled: testing.value || !cfg.value.llm_enabled
              }, _toDisplayString(testing.value ? '测试中...' : '测试大模型'), 9, _hoisted_30),
              (testResult.value)
                ? (_openBlock(), _createElementBlock("p", {
                    key: 0,
                    class: _normalizeClass(["test-result", testResult.value.ok ? 'ok' : 'err'])
                  }, _toDisplayString(testResult.value.message), 3))
                : _createCommentVNode("", true)
            ]))
          : (_openBlock(), _createElementBlock("div", _hoisted_31, [
              _createElementVNode("div", _hoisted_32, [
                _createElementVNode("button", {
                  onClick: loadHistory,
                  class: "btn-sm"
                }, "刷新"),
                _createElementVNode("span", _hoisted_33, "最近 " + _toDisplayString(history.value.length) + " 条", 1)
              ]),
              _createElementVNode("table", _hoisted_34, [
                _cache[37] || (_cache[37] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", null, "时间"),
                    _createElementVNode("th", null, "题目"),
                    _createElementVNode("th", null, "答案"),
                    _createElementVNode("th", null, "来源")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (h, i) => {
                    return (_openBlock(), _createElementBlock("tr", { key: i }, [
                      _createElementVNode("td", _hoisted_35, _toDisplayString(h.time), 1),
                      _createElementVNode("td", null, _toDisplayString(h.question), 1),
                      _createElementVNode("td", null, [
                        _createElementVNode("b", null, _toDisplayString(h.answer), 1)
                      ]),
                      _createElementVNode("td", null, [
                        _createElementVNode("span", {
                          class: _normalizeClass('src-' + h.source)
                        }, _toDisplayString(h.source === 'bank' ? '题库' : 'LLM'), 3)
                      ])
                    ]))
                  }), 128)),
                  (!history.value.length)
                    ? (_openBlock(), _createElementBlock("tr", _hoisted_36, [...(_cache[36] || (_cache[36] = [
                        _createElementVNode("td", {
                          colspan: "4",
                          class: "empty"
                        }, "暂无答题记录", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-168f45c5"]]);

export { Config as default };
