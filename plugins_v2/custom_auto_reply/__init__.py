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

__plugin__ = {'name': '定时自动回复',
 'id': 'custom_auto_reply',
 'version': '1.0.13',
 'author': 'AWdress',
 'description': '到点自动用你的账号往指定群/会话发消息。支持多个会话，每个会话可单独设时间和内容。时间支持每天定点、每隔几小时/几分钟、或 cron 表达式。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_reply.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.12 显示会话名称\n'
              '- 保存 UID 后在设置顶部显示群组/频道名称\n'
              '- 注册、发送和通知日志显示名称并保留 UID\n'
              '\n'
              'v1.0.11 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.10 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'notify_owner': {'type': 'boolean',
                                    'default': False,
                                    'label': '把结果通知给我',
                                    'section': '功能开关',
                                    'cols': 3,
                                    'order': 1,
                                    'help': '每次发送成功/失败后，平台用机器人私聊你（或发到你账号的收藏夹）报一条。无需填ID。'},
                   'resolved_chat_names': {'type': 'info', 'label': '已识别会话名称', 'section': '发送内容', 'order': 9},
                   'target_chat_id': {'type': 'list',
                                      'default': [],
                                      'label': '定时规则',
                                      'item_label': '规则',
                                      'section': '发送内容',
                                      'order': 10,
                                      'fields': {'chat': {'type': 'string',
                                                          'label': '会话',
                                                          'help': '群/频道ID(形如 -1001234567890)或 '
                                                                  '@用户名，不知道可用「查ID」插件'},
                                                 'time': {'type': 'string',
                                                          'label': '时间（可选）',
                                                          'help': '`09:30`每天定点 / `3h`每3小时 / `30m`每30分钟 / `0 '
                                                                  '9 * * 1-5`cron；留空=用下方默认时间'},
                                                 'content': {'type': 'string',
                                                             'label': '内容（可选）',
                                                             'help': '换行用 \\n；留空=用下方默认消息'}},
                                      'help': '逐条添加：发给谁、什么时间、发什么。时间/内容留空则用「默认时间」「默认消息」。'},
                   'message': {'type': 'text',
                               'default': '',
                               'label': '默认消息（可选）',
                               'section': '发送内容',
                               'order': 11,
                               'help': '对没单独写内容的会话使用这条。所有会话都各自写了内容时可留空。'},
                   'frequency': {'type': 'select',
                                 'default': 'daily',
                                 'label': '默认发送频率',
                                 'section': '默认时间',
                                 'order': 20,
                                 'options': [{'value': 'daily', 'label': '每天定点（每天一次）'},
                                             {'value': 'hours', 'label': '每隔几小时循环发'},
                                             {'value': 'minutes', 'label': '每隔几分钟循环发'},
                                             {'value': 'cron', 'label': '自定义 cron 表达式（高级）'}],
                                 'help': '仅对没在行内单独写时间的会话生效。注册后按规则反复发送。'},
                   'daily_hour': {'type': 'slider',
                                  'default': 9,
                                  'label': '每天几点',
                                  'min': 0,
                                  'max': 23,
                                  'step': 1,
                                  'section': '默认时间',
                                  'order': 21,
                                  'help': '24 小时制，0~23 点。',
                                  'show_if': {'frequency': 'daily'}},
                   'daily_minute': {'type': 'slider',
                                    'default': 0,
                                    'label': '几分',
                                    'min': 0,
                                    'max': 59,
                                    'step': 1,
                                    'section': '默认时间',
                                    'order': 22,
                                    'show_if': {'frequency': 'daily'}},
                   'every_hours': {'type': 'slider',
                                   'default': 3,
                                   'label': '每隔几小时',
                                   'min': 1,
                                   'max': 24,
                                   'step': 1,
                                   'section': '默认时间',
                                   'order': 23,
                                   'show_if': {'frequency': 'hours'}},
                   'every_minutes': {'type': 'slider',
                                     'default': 30,
                                     'label': '每隔几分钟',
                                     'min': 1,
                                     'max': 180,
                                     'step': 1,
                                     'section': '默认时间',
                                     'order': 24,
                                     'show_if': {'frequency': 'minutes'}},
                   'cron_expr': {'type': 'string',
                                 'default': '0 9 * * 1-5',
                                 'label': 'cron 表达式',
                                 'section': '默认时间',
                                 'order': 25,
                                 'show_if': {'frequency': 'cron'},
                                 'help': '标准 5 段格式：分 时 日 月 周。星期 0/7=周日，1=周一。\n'
                                         '例：`0 9 * * 1-5` 工作日每天 9:00；`*/15 9-18 * * *` 9~18 点每 15 分钟一次；`30 8 '
                                         '1 * *` 每月 1 号 8:30。'}},
 'v1_compatible_version': '1.0.12',
 'v2_adapter': 'telethon',
 'tags': ['自定义回复', '延迟发送', '定时规则']}
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
