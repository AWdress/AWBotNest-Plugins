"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from ._compat import adapt
from ._legacy import setup as _legacy_setup
try:
    from ._legacy import DEFAULTS as _legacy_defaults
except ImportError:
    _legacy_defaults = {}
try:
    from ._legacy import teardown as _legacy_teardown
except ImportError:
    _legacy_teardown = None


 'version': '2.2.6','name': '聊天互动助手',
 'id': 'keyword_auto_reply',
 'author': 'AWdress',
 'description': '按可配置概率自动回复群消息，关键词可选，并支持追加回复、冷却、限群、自动删除及排行榜。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_reply.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.2.2 修正追加回复与随机数复用\n'
              '- 趣味文字命中时不再发送追加回复\n'
              '- 追加文案支持 {number}，复用标准回复生成的第一个随机数\n'
              '- 默认追加文案展示实际掉落茉莉数量\n'
              '\n'
              'v2.2.1 新增可选追加回复\n'
              '- 每条规则可在标准回复后再单独发送一条消息\n'
              '- 追加回复支持开关、自定义文案、模板变量和随机数\n'
              '- 追加消息沿用回复自动删除设置\n'
              '\n'
              'v2.2.0 支持无关键词概率触发\n'
              '- 关键词改为可选，留空时匹配任意群消息\n'
              '- 每条规则可独立设置触发概率\n'
              '- 插件更名为‘聊天互动助手’\n'
              '\n'
              'v2.1.1 支持多行趣味回复\n'
              '- 趣味文案按完整段落发送并保留原有换行\n'
              '- 多条随机文案改用单独一行 --- 分隔\n'
              '\n'
              'v2.1.0 新增逐规则榜单统计与趣味回复\n'
              '- 每条规则可独立选择是否计入薅羊毛排行榜\n'
              '- 支持设置趣味文字出现概率，并从多条文案中随机回复\n'
              '- 未命中趣味概率时继续发送原标准回复\n'
              '\n'
              'v2.0.2 恢复逐规则零点重置\n'
              '- 冷却计算方式移入每条规则，可选滚动小时或每日零点重置\n'
              '- 旧版全局零点重置设置自动迁移到已有规则\n'
              '\n'
              'v2.0.1 新增逐规则触发方式\n'
              '- 每条规则可选择普通关键词或仅在回复我的消息时触发\n'
              '- 旧规则默认保持普通关键词触发，不改变现有行为\n'
              '\n'
              'v2.0.0 Vue 规则编辑器与独立规则策略\n'
              '- 新增 Vue 配置页，规则支持展开编辑、排序和复制\n'
              '- 每条规则独立设置匹配方式、冷却时间和冷却提示\n'
              '- 旧版全局匹配与冷却配置自动迁移到已有规则\n'
              '- 完善空状态、保存校验、移动端布局与键盘焦点\n'
              '\n'
              'v1.1.1 调整插件定位与名称\n'
              '- 更名为‘关键词互动助手’，突出关键词自动回复核心能力\n'
              '- 薅羊毛排行榜保留为可选附加功能\n'
              '- 配置说明覆盖提示、互动和福利等用途\n'
              '\n'
              'v1.1.0 新增薅羊毛排行榜\n'
              '- 成功发放福利后按账号、群组和用户持久化累计次数\n'
              '- 群内发送可配置命令查看当前群薅羊毛排行榜\n'
              '\n'
              'v1.0.9 持久化关键词冷却\n'
              '- 冷却记录写入插件专属 ctx.kv，平台或容器重启后继续生效\n'
              '- 插件更新、停用重启后自动恢复有效记录，并清理过期数据\n'
              '\n'
              'v1.0.8 适配平台后台任务治理\n'
              '- 回复与冷却提示的延迟删除任务改由 ctx.create_task 托管\n'
              '- 插件停用或重载时不再遗留等待中的删除任务\n'
              '\n'
              'v1.0.6 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              '\n'
              'v1.0.5 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n'
              '\n'
              'v1.0.4 恢复冷却提示回复\n'
              '- 每条关键词规则重新提供“冷却时提示”开关，现有规则默认开启\n'
              '- 冷却命中时回复剩余小时、分钟或秒数，零点重置模式显示距零点时间\n'
              '- 冷却提示沿用回复自动删除时间\n'
              '\n'
              'v1.0.3 优化规则配置\n'
              '- 关键词规则改用列表控件，群组范围改用会话选择器',
 'scope': 'user',
 'config_schema': {'enabled': {'type': 'boolean',
                               'default': True,
                               'label': '启用聊天互动助手',
                               'cols': 3,
                               'order': 1,
                               'section': '功能开关'},
                   'midnight_reset': {'type': 'boolean',
                                      'default': False,
                                      'label': '冷却每天零点清零',
                                      'cols': 3,
                                      'order': 2,
                                      'section': '功能开关'},
                   'leaderboard_enabled': {'type': 'boolean',
                                           'default': True,
                                           'label': '启用薅羊毛排行榜',
                                           'cols': 3,
                                           'order': 3,
                                           'section': '功能开关'},
                   'rules_text': {'type': 'list',
                                  'default': [],
                                  'label': '互动规则',
                                  'item_label': '规则',
                                  'order': 10,
                                  'section': '规则',
                                  'fields': {'keyword': {'type': 'string', 'label': '关键词（可选）'},
                                             'reply': {'type': 'string', 'label': '回复内容'},
                                             'trigger_chance': {'type': 'number',
                                                                'label': '触发概率（%）',
                                                                'default': 100},
                                             'extra_reply_enabled': {'type': 'boolean',
                                                                     'label': '发送追加回复',
                                                                     'default': False},
                                             'extra_reply': {'type': 'string',
                                                             'label': '追加回复内容',
                                                             'default': '叮！恭喜你喜提特等奖掉落。掉落 {number} 茉莉'},
                                             'cooldown_notify': {'type': 'boolean',
                                                                 'label': '冷却时提示',
                                                                 'default': True}},
                                  'help': '关键词留空时任意消息均可参与概率判断。回复里可用 {uname}（对方昵称）、{uid}（对方ID）、a-b（a到b的随机数）。'},
                   'match_type': {'type': 'select',
                                  'default': 'contains',
                                  'label': '匹配方式',
                                  'order': 11,
                                  'section': '规则',
                                  'options': [{'value': 'contains', 'label': '包含关键词即触发'},
                                              {'value': 'exact', 'label': '消息完全等于关键词才触发'}]},
                   'chat_ids': {'type': 'chat',
                                'default': [],
                                'label': '只在这些群生效（可选）',
                                'multi': True,
                                'chat_types': ['group'],
                                'order': 20,
                                'section': '范围与冷却',
                                'help': '勾选生效的群；留空 = 所有群都生效。'},
                   'cooldown_hours': {'type': 'slider',
                                      'default': 24,
                                      'label': '同一个人冷却(小时)',
                                      'min': 0,
                                      'max': 72,
                                      'step': 1,
                                      'order': 21,
                                      'section': '范围与冷却',
                                      'help': '同一个人触发后多久内不再回复他。0 = 不限制。'},
                   'delete_after': {'type': 'slider',
                                    'default': 0,
                                    'label': '回复自动删除(秒)',
                                    'min': 0,
                                    'max': 600,
                                    'step': 10,
                                    'order': 22,
                                    'section': '范围与冷却',
                                    'help': '关键词回复和羊毛榜发出后多少秒自动撤回；0 = 不删除。'},
                   'blacklist_ids': {'type': 'text',
                                     'default': '',
                                     'label': '屏蔽用户ID',
                                     'order': 23,
                                     'section': '范围与冷却',
                                     'help': '这些用户的消息不触发回复。一行一个或逗号分隔的用户ID。'},
                   'leaderboard_command': {'type': 'string',
                                           'default': '.羊毛榜',
                                           'label': '排行榜命令',
                                           'order': 30,
                                           'section': '薅羊毛排行榜',
                                           'help': '群内发送该命令，查看当前群累计领取福利次数。'},
                   'leaderboard_size': {'type': 'slider',
                                        'default': 10,
                                        'label': '显示人数',
                                        'min': 3,
                                        'max': 30,
                                        'step': 1,
                                        'order': 31,
                                        'section': '薅羊毛排行榜'}},
 'v1_compatible_version': '2.2.2',
 'v2_adapter': 'telethon',
 'tags': ['关键词回复', '定时规则', '自动删除'],
 'render_mode': 'vue'}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults)
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()



