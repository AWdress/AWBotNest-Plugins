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

__plugin__ = {'name': '电子宠物',
 'id': 'digital_pet',
 'version': '2.1.3',
 'author': 'AWdress',
 'scope': 'user',
 'description': '在 Telegram 养成你的专属电子宠物！支持领养、喂食、玩耍、清洁、成长、进化、道具、随机事件和视觉表现。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/digital_pet/logo.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.1.2 修复定时通知与卸载残留任务\n'
              '- 定时提醒改用新版平台 ctx.bot.send 接口\n'
              '- 卸载后残留的心跳回调会立即停止，不再发送通知或重复处理宠物状态\n'
              '- teardown 增加幂等保护，避免重复输出卸载日志\n'
              '\n'
              'v2.1.1 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              '\n'
              'v2.1.0 电子宠物终版增强更新\n'
              '- 新增全身像视觉系统、动作图、事件图、成长进化立绘\n'
              '- 支持三物种差异化成长：电子狗、像素猫、机械龙\n'
              '- 新增随机事件、升级奖励、周期播报、背包与道具体系\n'
              '- 新增 /档案、/背包、/使用 等命令\n'
              '- 新增命令冷却时间与冷却设置配置项\n'
              '- 全部命令彻底中文化，玩法说明和配置界面同步完善',
 'requirements': [],
 'config_schema': {'auto_reminder_enabled': {'type': 'boolean',
                                             'default': True,
                                             'label': '启用自动提醒',
                                             'cols': 3,
                                             'order': 1,
                                             'section': '功能开关'},
                   'auto_delete_replies': {'type': 'boolean',
                                           'default': True,
                                           'label': '自动删除插件回复',
                                           'cols': 3,
                                           'order': 2,
                                           'section': '功能开关'},
                   'show_pet_image': {'type': 'boolean',
                                      'default': True,
                                      'label': '状态时显示宠物图片',
                                      'cols': 3,
                                      'order': 3,
                                      'section': '功能开关'},
                   'use_fullbody_art': {'type': 'boolean',
                                        'default': True,
                                        'label': '启用全身像视觉系统',
                                        'cols': 3,
                                        'order': 4,
                                        'section': '功能开关'},
                   'random_events_enabled': {'type': 'boolean',
                                             'default': True,
                                             'label': '启用随机事件',
                                             'cols': 3,
                                             'order': 5,
                                             'section': '功能开关'},
                   'daily_brief_enabled': {'type': 'boolean',
                                           'default': True,
                                           'label': '启用周期状态播报',
                                           'cols': 3,
                                           'order': 6,
                                           'section': '功能开关'},
                   'heartbeat_interval_min': {'type': 'slider',
                                              'default': 60,
                                              'label': '状态检查间隔（分钟）',
                                              'min': 10,
                                              'max': 360,
                                              'step': 10,
                                              'order': 10,
                                              'section': '运行设置'},
                   'decay_multiplier': {'type': 'slider',
                                        'default': 100,
                                        'label': '状态衰减倍率（%）',
                                        'min': 50,
                                        'max': 300,
                                        'step': 10,
                                        'order': 11,
                                        'section': '运行设置'},
                   'delete_delay_seconds': {'type': 'slider',
                                            'default': 30,
                                            'label': '回复消息保留时间（秒）',
                                            'min': 5,
                                            'max': 300,
                                            'step': 5,
                                            'order': 12,
                                            'section': '运行设置'},
                   'event_chance_percent': {'type': 'slider',
                                            'default': 25,
                                            'label': '随机事件触发概率（%）',
                                            'min': 0,
                                            'max': 100,
                                            'step': 5,
                                            'order': 13,
                                            'section': '运行设置'},
                   'daily_brief_chance_percent': {'type': 'slider',
                                                  'default': 20,
                                                  'label': '每轮播报概率（%）',
                                                  'min': 0,
                                                  'max': 100,
                                                  'step': 5,
                                                  'order': 14,
                                                  'section': '运行设置'},
                   'status_cooldown_seconds': {'type': 'slider',
                                               'default': 10,
                                               'label': '状态命令冷却（秒）',
                                               'min': 0,
                                               'max': 120,
                                               'step': 5,
                                               'order': 20,
                                               'section': '冷却设置'},
                   'action_cooldown_seconds': {'type': 'slider',
                                               'default': 20,
                                               'label': '互动命令冷却（秒）',
                                               'min': 0,
                                               'max': 180,
                                               'step': 5,
                                               'order': 21,
                                               'section': '冷却设置'},
                   'use_item_cooldown_seconds': {'type': 'slider',
                                                 'default': 15,
                                                 'label': '使用道具冷却（秒）',
                                                 'min': 0,
                                                 'max': 180,
                                                 'step': 5,
                                                 'order': 22,
                                                 'section': '冷却设置'},
                   'info': {'type': 'info',
                            'label': '玩法说明',
                            'order': 30,
                            'section': '命令说明',
                            'text': '先发送 /领养 名字 或 .领养 名字 来领养宠物；领养后可用 /状态、/喂食、/玩耍、/清洁 与它互动。用 /档案 查看成长档案，用 /背包 '
                                    '查看道具，用 /使用 道具名 来使用道具。'}},
 'v1_compatible_version': '2.1.2',
 'v2_adapter': 'telethon',
 'tags': ['工具']}
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
