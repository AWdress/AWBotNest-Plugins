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

__plugin__ = {'name': '数字炸弹',
 'id': 'bomb_game',
 'version': '1.0.7',
 'author': 'AWdress',
 'description': '群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/bomb_game.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.6 修复 Vue 配置保存\n'
              '- 配置读取和保存迁移到新版平台 host 接口\n'
              '- 群组名称和游戏记录改用 host.callApi 读取\n'
              '- 重新构建并发布前端产物\n'
              '\n'
              'v1.0.4 修复核心接线错误\n'
              '- 修复处理函数调用了不存在的旧版 API 导致插件无法运行\n'
              '- 按真实游戏引擎接口重接开局/参与/猜数字/转账确认\n'
              '- 转账确认改为失败安全：无法唯一定位参与者时跳过，绝不错记金额\n'
              '\n'
              'v1.0.3 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n'
              '\n'
              'v1.0.2 修复配置界面缺失\n'
              '- 随插件发布 frontend/dist 前端构建产物',
 'scope': 'both',
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'valid_groups': {'title': 'valid groups',
                                    'section': 'V2 配置',
                                    'order': 1,
                                    'type': 'chat',
                                    'default': '',
                                    'chat_types': ['group', 'channel'],
                                    'session': True},
                   'entry_fee': {'title': 'entry fee',
                                 'section': 'V2 配置',
                                 'order': 2,
                                 'type': 'number',
                                 'default': 888},
                   'pool_ratio': {'title': 'pool ratio',
                                  'section': 'V2 配置',
                                  'order': 3,
                                  'type': 'number',
                                  'default': 50},
                   'wait_time': {'title': 'wait time',
                                 'section': 'V2 配置',
                                 'order': 4,
                                 'type': 'number',
                                 'default': 30},
                   'default_min': {'title': 'default min',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'number',
                                   'default': 1},
                   'default_max': {'title': 'default max',
                                   'section': 'V2 配置',
                                   'order': 6,
                                   'type': 'number',
                                   'default': 100},
                   'enable_range_shrink': {'title': 'enable range shrink',
                                           'section': 'V2 配置',
                                           'order': 7,
                                           'type': 'boolean',
                                           'default': True},
                   'shrink_1_5': {'title': 'shrink 1 5',
                                  'section': 'V2 配置',
                                  'order': 8,
                                  'type': 'number',
                                  'default': -10},
                   'shrink_6_15': {'title': 'shrink 6 15',
                                   'section': 'V2 配置',
                                   'order': 9,
                                   'type': 'number',
                                   'default': -4},
                   'shrink_16_30': {'title': 'shrink 16 30',
                                    'section': 'V2 配置',
                                    'order': 10,
                                    'type': 'number',
                                    'default': -2},
                   'shrink_31plus': {'title': 'shrink 31plus',
                                     'section': 'V2 配置',
                                     'order': 11,
                                     'type': 'number',
                                     'default': 2},
                   'instant_win_permille': {'title': 'instant win permille',
                                            'section': 'V2 配置',
                                            'order': 12,
                                            'type': 'number',
                                            'default': 5},
                   'auto_delete_enabled': {'title': 'auto delete enabled',
                                           'section': 'V2 配置',
                                           'order': 13,
                                           'type': 'boolean',
                                           'default': True},
                   'auto_delete_delay': {'title': 'auto delete delay',
                                         'section': 'V2 配置',
                                         'order': 14,
                                         'type': 'number',
                                         'default': 30},
                   'no_delete_groups': {'title': 'no delete groups',
                                        'section': 'V2 配置',
                                        'order': 15,
                                        'type': 'chat',
                                        'default': '',
                                        'chat_types': ['group', 'channel'],
                                        'session': True},
                   'monitor_disabled_groups': {'title': 'monitor disabled groups',
                                               'section': 'V2 配置',
                                               'order': 16,
                                               'type': 'chat',
                                               'default': '',
                                               'chat_types': ['group', 'channel'],
                                               'session': True},
                   'require_transfer_confirm': {'title': 'require transfer confirm',
                                                'section': 'V2 配置',
                                                'order': 17,
                                                'type': 'boolean',
                                                'default': False},
                   'transfer_bot_ids': {'title': 'transfer bot ids',
                                        'section': 'V2 配置',
                                        'order': 18,
                                        'type': 'string',
                                        'default': ''}},
 'v1_compatible_version': '1.0.6',
 'v2_adapter': 'telethon',
 'tags': ['炸弹游戏', '群组娱乐', '互动玩法'],
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
