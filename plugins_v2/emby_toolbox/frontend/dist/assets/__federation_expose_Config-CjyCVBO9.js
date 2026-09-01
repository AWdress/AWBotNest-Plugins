import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,renderList:_renderList,Fragment:_Fragment,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,createCommentVNode:_createCommentVNode,vModelText:_vModelText,vModelDynamic:_vModelDynamic,createStaticVNode:_createStaticVNode} = await importShared('vue');


const _hoisted_1 = { class: "shell" };
const _hoisted_2 = { class: "hero" };
const _hoisted_3 = { class: "hero-actions" };
const _hoisted_4 = ["disabled"];
const _hoisted_5 = ["disabled"];
const _hoisted_6 = { class: "tabs" };
const _hoisted_7 = ["onClick"];
const _hoisted_8 = {
  key: 0,
  class: "console"
};
const _hoisted_9 = { class: "rail panel" };
const _hoisted_10 = { class: "section-head" };
const _hoisted_11 = ["onClick"];
const _hoisted_12 = { class: "workspace panel" };
const _hoisted_13 = { class: "workspace-top" };
const _hoisted_14 = { class: "switch" };
const _hoisted_15 = { class: "scope" };
const _hoisted_16 = { key: 0 };
const _hoisted_17 = {
  key: 0,
  class: "two"
};
const _hoisted_18 = {
  key: 1,
  class: "field"
};
const _hoisted_19 = { class: "range" };
const _hoisted_20 = {
  key: 2,
  class: "note"
};
const _hoisted_21 = { class: "workspace-bottom" };
const _hoisted_22 = { class: "check" };
const _hoisted_23 = ["checked"];
const _hoisted_24 = ["disabled"];
const _hoisted_25 = ["disabled"];
const _hoisted_26 = { class: "plan panel" };
const _hoisted_27 = { class: "switch-row" };
const _hoisted_28 = { class: "switch" };
const _hoisted_29 = { class: "field" };
const _hoisted_30 = { class: "queue" };
const _hoisted_31 = ["disabled"];
const _hoisted_32 = {
  key: 1,
  class: "settings panel"
};
const _hoisted_33 = { class: "form-grid" };
const _hoisted_34 = { class: "span2" };
const _hoisted_35 = { class: "secret" };
const _hoisted_36 = ["type"];
const _hoisted_37 = { class: "span2" };
const _hoisted_38 = { class: "strategy" };
const _hoisted_39 = { class: "check" };
const _hoisted_40 = { class: "check" };
const _hoisted_41 = {
  key: 2,
  class: "history panel"
};
const _hoisted_42 = { class: "section-head" };
const _hoisted_43 = {
  key: 0,
  class: "empty"
};
const _hoisted_44 = { class: "run" };

const {computed,onBeforeUnmount,onMounted,reactive,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {pluginId:{type:String,required:true},host:{type:Object,required:true}},
  setup(__props) {

const props=__props;
const FEATURES=[
  {key:'episode_fix',title:'剧集季集',desc:'扫描 SxxExx 文件名，校正 Emby 识别错误',tone:'mint'},
  {key:'delete_episode_genre',title:'单集 Genre',desc:'清理剧集单集上冗余的 Genre',tone:'amber',danger:true},
  {key:'genre_mapper',title:'Genre 映射',desc:'批量替换或删除指定类型',tone:'blue'},
  {key:'season_renamer',title:'季名刮削',desc:'从 TMDB 获取季名并写入 Emby',tone:'violet',tmdb:true},
  {key:'country_scraper',title:'国家与语言',desc:'从 TMDB 获取信息并转换为标签',tone:'cyan',tmdb:true},
  {key:'alt_renamer',title:'中文别名',desc:'将 TMDB 中文别名写入 SortName',tone:'rose',tmdb:true},
  {key:'strm_mediainfo',title:'STRM 刷新',desc:'重新提取 STRM 文件媒体信息',tone:'lime'},
  {key:'damaged_check',title:'健康检查',desc:'检测缺少简介、年份等关键元数据',tone:'slate'},
];
const DEFAULTS={emby_server:'',api_key:'',user_id:'',tmdb_key:'',library_names:'',fix_lock_data:true,max_output:50,genre_mapping_json:'{\n  "Sci-Fi & Fantasy": "科幻",\n  "War & Politics": "战争"\n}',genre_remove_list:'',add_hant_title:true,strm_delay:3,enable_episode_fix:true,enable_delete_episode_genre:false,enable_genre_mapper:false,enable_season_renamer:false,enable_country_scraper:false,enable_alt_renamer:false,enable_strm_mediainfo:false,enable_damaged_check:false,enable_auto_schedule:false,schedule_cron:'0 3 * * *',schedule_functions:[]};
const form=reactive({...DEFAULTS}),status=reactive({running:false,task:'',scheduled:false,schedule:'',history:[]});
const tab=ref('console'),selected=ref('episode_fix'),loading=ref(true),saving=ref(false),testing=ref(false),busy=ref(''),reveal=ref(false);
let timer;
const current=computed(()=>FEATURES.find(x=>x.key===selected.value)||FEATURES[0]);
const enabledCount=computed(()=>FEATURES.filter(x=>form['enable_'+x.key]).length);
const libraries=computed(()=>form.library_names.split(/[\n,]/).map(x=>x.trim()).filter(Boolean));
const notify=(type,msg)=>props.host.toast?.[type]?.(msg);
async function refresh(){try{Object.assign(status,await props.host.callApi('/status'));}catch{}finally{loading.value=false;}}
async function load(){try{Object.assign(form,DEFAULTS,await props.host.getConfig());}catch(e){notify('error','读取配置失败：'+e.message);}await refresh();timer=setInterval(refresh,2500);}
async function save(){saving.value=true;try{await props.host.saveConfig(JSON.parse(JSON.stringify(form)));notify('success','配置已保存并应用');}catch(e){notify('error','保存失败：'+e.message);}finally{saving.value=false;}}
async function test(){testing.value=true;try{const r=await props.host.callApi('/test',{method:'POST'});notify(r.ok?'success':'error',r.message);}catch(e){notify('error','测试失败：'+e.message);}finally{testing.value=false;}}
async function run(action){if(status.running)return;const f=FEATURES.find(x=>x.key===action);if(f?.danger&&!confirm(`“${f.title}”会修改 Emby 数据，确定继续？`))return;busy.value=action;try{const r=await props.host.callApi('/run',{method:'POST',body:{action}});notify(r.ok?'success':'error',r.message);await refresh();}catch(e){notify('error','启动失败：'+e.message);}finally{busy.value='';}}
function toggleSchedule(key){const i=form.schedule_functions.indexOf(key);i<0?form.schedule_functions.push(key):form.schedule_functions.splice(i,1);}
onMounted(load);onBeforeUnmount(()=>clearInterval(timer));

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _cache[20] || (_cache[20] = _createStaticVNode("<div class=\"brand\" data-v-ac2a94d3><div class=\"mark\" data-v-ac2a94d3><svg viewBox=\"0 0 32 32\" data-v-ac2a94d3><path d=\"M8 5h11a6 6 0 0 1 0 12H8zM8 17h13a5 5 0 0 1 0 10H8z\" data-v-ac2a94d3></path></svg></div><div data-v-ac2a94d3><span class=\"eyebrow\" data-v-ac2a94d3>MEDIA OPERATIONS</span><h1 data-v-ac2a94d3>Emby 工具箱</h1><p data-v-ac2a94d3>把扫描、修复和刮削收进一个可观测的维护工作台。</p></div></div>", 1)),
      _createElementVNode("div", _hoisted_3, [
        _createElementVNode("span", {
          class: _normalizeClass(["state", {live:status.running}])
        }, [
          _cache[19] || (_cache[19] = _createElementVNode("i", null, null, -1)),
          _createTextVNode(_toDisplayString(status.running?status.task:'就绪'), 1)
        ], 2),
        _createElementVNode("button", {
          class: "ghost",
          disabled: testing.value,
          onClick: test
        }, _toDisplayString(testing.value?'正在连接…':'测试 Emby'), 9, _hoisted_4),
        _createElementVNode("button", {
          class: "primary",
          disabled: saving.value,
          onClick: save
        }, _toDisplayString(saving.value?'保存中…':'保存并应用'), 9, _hoisted_5)
      ])
    ]),
    _createElementVNode("nav", _hoisted_6, [
      (_openBlock(), _createElementBlock(_Fragment, null, _renderList([['console','维护台'],['connection','连接与策略'],['history','运行记录']], (x) => {
        return _createElementVNode("button", {
          class: _normalizeClass({active:tab.value===x[0]}),
          onClick: $event => (tab.value=x[0])
        }, _toDisplayString(x[1]), 11, _hoisted_7)
      }), 64))
    ]),
    (tab.value==='console')
      ? (_openBlock(), _createElementBlock("main", _hoisted_8, [
          _createElementVNode("section", _hoisted_9, [
            _createElementVNode("div", _hoisted_10, [
              _cache[21] || (_cache[21] = _createElementVNode("div", null, [
                _createElementVNode("span", { class: "kicker" }, "MODULES"),
                _createElementVNode("h2", null, "维护模块")
              ], -1)),
              _createElementVNode("b", null, _toDisplayString(enabledCount.value) + " / 8", 1)
            ]),
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(FEATURES, (f) => {
              return _createElementVNode("button", {
                class: _normalizeClass(["feature", [{active:selected.value===f.key},f.tone]]),
                onClick: $event => (selected.value=f.key)
              }, [
                _cache[22] || (_cache[22] = _createElementVNode("i", null, null, -1)),
                _createElementVNode("span", null, [
                  _createElementVNode("strong", null, _toDisplayString(f.title), 1),
                  _createElementVNode("small", null, _toDisplayString(form['enable_'+f.key]?'已启用':'未启用'), 1)
                ]),
                _cache[23] || (_cache[23] = _createElementVNode("em", null, "›", -1))
              ], 10, _hoisted_11)
            }), 64))
          ]),
          _createElementVNode("section", _hoisted_12, [
            _createElementVNode("div", _hoisted_13, [
              _createElementVNode("div", null, [
                _cache[24] || (_cache[24] = _createElementVNode("span", { class: "kicker" }, "ACTIVE MODULE", -1)),
                _createElementVNode("h2", null, _toDisplayString(current.value.title), 1),
                _createElementVNode("p", null, _toDisplayString(current.value.desc), 1)
              ]),
              _createElementVNode("label", _hoisted_14, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form['enable_'+current.value.key]) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, form['enable_'+current.value.key]]
                ]),
                _cache[25] || (_cache[25] = _createElementVNode("span", null, null, -1))
              ])
            ]),
            _createElementVNode("div", _hoisted_15, [
              _cache[26] || (_cache[26] = _createElementVNode("span", null, "作用范围", -1)),
              _createElementVNode("strong", null, _toDisplayString(libraries.value.length?`${libraries.value.length} 个指定媒体库`:'全部媒体库'), 1),
              (current.value.tmdb)
                ? (_openBlock(), _createElementBlock("small", _hoisted_16, "TMDB 密钥必需"))
                : _createCommentVNode("", true)
            ]),
            (current.value.key==='genre_mapper')
              ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                  _createElementVNode("label", null, [
                    _cache[27] || (_cache[27] = _createTextVNode("Genre 映射 JSON", -1)),
                    _withDirectives(_createElementVNode("textarea", {
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.genre_mapping_json) = $event)),
                      rows: "7",
                      spellcheck: "false"
                    }, null, 512), [
                      [_vModelText, form.genre_mapping_json]
                    ])
                  ]),
                  _createElementVNode("label", null, [
                    _cache[28] || (_cache[28] = _createTextVNode("要删除的 Genre", -1)),
                    _withDirectives(_createElementVNode("textarea", {
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.genre_remove_list) = $event)),
                      rows: "7",
                      placeholder: "每行一个"
                    }, null, 512), [
                      [_vModelText, form.genre_remove_list]
                    ])
                  ])
                ]))
              : (current.value.key==='strm_mediainfo')
                ? (_openBlock(), _createElementBlock("div", _hoisted_18, [
                    _cache[29] || (_cache[29] = _createElementVNode("label", null, "STRM 请求间隔", -1)),
                    _createElementVNode("div", _hoisted_19, [
                      _withDirectives(_createElementVNode("input", {
                        "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.strm_delay) = $event)),
                        type: "range",
                        min: "0",
                        max: "30"
                      }, null, 512), [
                        [
                          _vModelText,
                          form.strm_delay,
                          void 0,
                          { number: true }
                        ]
                      ]),
                      _createElementVNode("output", null, _toDisplayString(form.strm_delay) + " 秒", 1)
                    ])
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_20, [
                    _cache[30] || (_cache[30] = _createElementVNode("svg", { viewBox: "0 0 24 24" }, [
                      _createElementVNode("path", { d: "M12 3v18M3 12h18" })
                    ], -1)),
                    _createElementVNode("p", null, _toDisplayString(current.value.key==='damaged_check'?'只读检查，不会修改媒体库。':'启用后可单独运行，也可纳入定时维护计划。'), 1)
                  ])),
            _createElementVNode("div", _hoisted_21, [
              _createElementVNode("label", _hoisted_22, [
                _createElementVNode("input", {
                  type: "checkbox",
                  checked: form.schedule_functions.includes(current.value.key),
                  onChange: _cache[4] || (_cache[4] = $event => (toggleSchedule(current.value.key)))
                }, null, 40, _hoisted_23),
                _cache[31] || (_cache[31] = _createElementVNode("span", null, "加入定时计划", -1))
              ]),
              _createElementVNode("div", null, [
                (current.value.key==='episode_fix')
                  ? (_openBlock(), _createElementBlock("button", {
                      key: 0,
                      class: "ghost",
                      disabled: status.running,
                      onClick: _cache[5] || (_cache[5] = $event => (run('scan_episode_mismatch')))
                    }, "先扫描", 8, _hoisted_24))
                  : _createCommentVNode("", true),
                _createElementVNode("button", {
                  class: "primary",
                  disabled: status.running||Boolean(busy.value),
                  onClick: _cache[6] || (_cache[6] = $event => (run(current.value.key)))
                }, _toDisplayString(busy.value===current.value.key?'启动中…':'立即执行'), 9, _hoisted_25)
              ])
            ])
          ]),
          _createElementVNode("aside", _hoisted_26, [
            _cache[36] || (_cache[36] = _createElementVNode("span", { class: "kicker" }, "AUTOMATION", -1)),
            _cache[37] || (_cache[37] = _createElementVNode("h2", null, "维护计划", -1)),
            _createElementVNode("label", _hoisted_27, [
              _createElementVNode("span", null, [
                _cache[32] || (_cache[32] = _createElementVNode("strong", null, "定时执行", -1)),
                _createElementVNode("small", null, _toDisplayString(status.scheduled?'已注册到平台':'未注册'), 1)
              ]),
              _createElementVNode("label", _hoisted_28, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.enable_auto_schedule) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, form.enable_auto_schedule]
                ]),
                _cache[33] || (_cache[33] = _createElementVNode("span", null, null, -1))
              ])
            ]),
            _createElementVNode("label", _hoisted_29, [
              _cache[34] || (_cache[34] = _createTextVNode("五段 Cron", -1)),
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.schedule_cron) = $event)),
                placeholder: "0 3 * * *"
              }, null, 512), [
                [_vModelText, form.schedule_cron]
              ])
            ]),
            _createElementVNode("div", _hoisted_30, [
              _cache[35] || (_cache[35] = _createElementVNode("span", null, "待执行模块", -1)),
              _createElementVNode("b", null, _toDisplayString(form.schedule_functions.length), 1)
            ]),
            _createElementVNode("button", {
              class: "wide",
              disabled: status.running||!form.schedule_functions.length,
              onClick: _cache[9] || (_cache[9] = $event => (run('scheduled')))
            }, "立即运行当前计划", 8, _hoisted_31)
          ])
        ]))
      : (tab.value==='connection')
        ? (_openBlock(), _createElementBlock("main", _hoisted_32, [
            _cache[46] || (_cache[46] = _createElementVNode("div", { class: "settings-title" }, [
              _createElementVNode("span", { class: "kicker" }, "CONNECTION"),
              _createElementVNode("h2", null, "Emby 与 TMDB"),
              _createElementVNode("p", null, "敏感数据仅保存在平台插件配置中。")
            ], -1)),
            _createElementVNode("div", _hoisted_33, [
              _createElementVNode("label", _hoisted_34, [
                _cache[38] || (_cache[38] = _createTextVNode("Emby 地址", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.emby_server) = $event)),
                  placeholder: "https://emby.example.com"
                }, null, 512), [
                  [
                    _vModelText,
                    form.emby_server,
                    void 0,
                    { trim: true }
                  ]
                ])
              ]),
              _createElementVNode("label", null, [
                _cache[39] || (_cache[39] = _createTextVNode("API Key", -1)),
                _createElementVNode("div", _hoisted_35, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.api_key) = $event)),
                    type: reveal.value?'text':'password'
                  }, null, 8, _hoisted_36), [
                    [_vModelDynamic, form.api_key]
                  ]),
                  _createElementVNode("button", {
                    onClick: _cache[12] || (_cache[12] = $event => (reveal.value=!reveal.value))
                  }, _toDisplayString(reveal.value?'隐藏':'显示'), 1)
                ])
              ]),
              _createElementVNode("label", null, [
                _cache[40] || (_cache[40] = _createTextVNode("用户 ID ", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.user_id) = $event)),
                  placeholder: "留空自动获取"
                }, null, 512), [
                  [
                    _vModelText,
                    form.user_id,
                    void 0,
                    { trim: true }
                  ]
                ])
              ]),
              _createElementVNode("label", null, [
                _cache[41] || (_cache[41] = _createTextVNode("TMDB API Key", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.tmdb_key) = $event)),
                  type: "password"
                }, null, 512), [
                  [_vModelText, form.tmdb_key]
                ])
              ]),
              _createElementVNode("label", _hoisted_37, [
                _cache[42] || (_cache[42] = _createTextVNode("媒体库名称", -1)),
                _withDirectives(_createElementVNode("textarea", {
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.library_names) = $event)),
                  rows: "5",
                  placeholder: "每行一个；留空处理全部"
                }, null, 512), [
                  [_vModelText, form.library_names]
                ])
              ])
            ]),
            _cache[47] || (_cache[47] = _createElementVNode("hr", null, null, -1)),
            _createElementVNode("div", _hoisted_38, [
              _createElementVNode("label", _hoisted_39, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.fix_lock_data) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, form.fix_lock_data]
                ]),
                _cache[43] || (_cache[43] = _createElementVNode("span", null, "修复后锁定条目数据", -1))
              ]),
              _createElementVNode("label", _hoisted_40, [
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.add_hant_title) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox, form.add_hant_title]
                ]),
                _cache[44] || (_cache[44] = _createElementVNode("span", null, "别名包含繁中标题", -1))
              ]),
              _createElementVNode("label", null, [
                _cache[45] || (_cache[45] = _createTextVNode("输出条目上限", -1)),
                _withDirectives(_createElementVNode("input", {
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.max_output) = $event)),
                  type: "number",
                  min: "5",
                  max: "200"
                }, null, 512), [
                  [
                    _vModelText,
                    form.max_output,
                    void 0,
                    { number: true }
                  ]
                ])
              ])
            ])
          ]))
        : (_openBlock(), _createElementBlock("main", _hoisted_41, [
            _createElementVNode("div", _hoisted_42, [
              _cache[49] || (_cache[49] = _createElementVNode("div", null, [
                _createElementVNode("span", { class: "kicker" }, "ACTIVITY"),
                _createElementVNode("h2", null, "运行记录")
              ], -1)),
              _createElementVNode("span", {
                class: _normalizeClass(["state", {live:status.running}])
              }, [
                _cache[48] || (_cache[48] = _createElementVNode("i", null, null, -1)),
                _createTextVNode(_toDisplayString(status.running?'运行中':'自动刷新'), 1)
              ], 2)
            ]),
            (!status.history?.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_43, "还没有维护记录。运行一次任务后，结果会留在这里。"))
              : _createCommentVNode("", true),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.history, (row) => {
              return (_openBlock(), _createElementBlock("article", _hoisted_44, [
                _createElementVNode("i", {
                  class: _normalizeClass(row.ok?'ok':'bad')
                }, null, 2),
                _createElementVNode("div", null, [
                  _createElementVNode("strong", null, _toDisplayString(row.task), 1),
                  _createElementVNode("span", null, _toDisplayString(row.source) + " · " + _toDisplayString(row.time), 1),
                  _createElementVNode("pre", null, _toDisplayString(row.summary), 1)
                ])
              ]))
            }), 256))
          ]))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ac2a94d3"]]);

export { Config as default };
