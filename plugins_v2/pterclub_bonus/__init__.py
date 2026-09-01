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

__plugin__ = {'name': '猫站赠粮',
 'id': 'pterclub_bonus',
 'version': '1.0.1',
 'author': 'AWdress',
 'description': '使用平台同步的 PTerClub Cookie，通过用户账号命令单人或批量赠送猫粮。',
 'icon': 'https://pterclub.net/favicon.ico',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 支持 .pm 单人赠粮与 .pms 批量赠粮\n'
              '- Cookie 统一从平台 Cookie 同步读取，不在插件配置中保存\n'
              '- 按猫站规则校验每份 25–50,000 猫粮并显示 10% 税后到账\n'
              '- 支持登录检查、持久化冷却、安全站内跳转和赠送结果解析',
 'scope': 'user',
 'cookie_domains': ['pterclub.net', '*.pterclub.net'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 2,
               'max_background_tasks': 16,
               'failure_threshold': 5,
               'recovery_seconds': 60},
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12', 'lxml>=5.0'],
 'config_schema': {'enabled': {'type': 'boolean',
                               'default': True,
                               'label': '启用赠粮命令',
                               'section': '功能开关',
                               'cols': 6,
                               'order': 1},
                   'notify_cookie_error': {'type': 'boolean',
                                           'default': True,
                                           'label': 'Cookie 异常时通知',
                                           'section': '功能开关',
                                           'cols': 6,
                                           'order': 2},
                   'single_command': {'type': 'string',
                                      'default': '.pm',
                                      'label': '单人赠粮命令',
                                      'help': '格式：.pm 用户名 数量 留言（留言可包含空格）。',
                                      'section': '命令',
                                      'cols': 6,
                                      'order': 10},
                   'batch_command': {'type': 'string',
                                     'default': '.pms',
                                     'label': '批量赠粮命令',
                                     'help': '格式：.pms 用户1 用户2 ... 数量 留言；批量留言请不要包含空格。',
                                     'section': '命令',
                                     'cols': 6,
                                     'order': 11},
                   'cooldown_seconds': {'type': 'slider',
                                        'default': 10,
                                        'label': '赠送冷却（秒）',
                                        'min': 0,
                                        'max': 600,
                                        'step': 5,
                                        'help': '每次向猫站提交赠送之间的最小间隔，批量任务同样生效。',
                                        'section': '限频与清理',
                                        'cols': 6,
                                        'order': 20},
                   'result_delete': {'type': 'slider',
                                     'default': 90,
                                     'label': '结果自动删除（秒）',
                                     'min': 10,
                                     'max': 600,
                                     'step': 10,
                                     'section': '限频与清理',
                                     'cols': 6,
                                     'order': 21},
                   'test_cookie': {'type': 'action',
                                   'label': '检查平台 Cookie',
                                   'action': 'test_cookie',
                                   'section': '检查',
                                   'cols': 6,
                                   'order': 30},
                   'command_help': {'type': 'info',
                                    'default': '单人：.pm 用户名 1000 留言内容\n'
                                               '批量：.pms 用户1 用户2 1000 留言\n'
                                               '每份最低 25、最高 50,000；接收者到账 90%。',
                                    'label': '命令说明',
                                    'section': '检查',
                                    'cols': 12,
                                    'order': 31}},
 'v1_compatible_version': '1.0.0',
 'v2_adapter': 'telethon',
 'tags': ['PterClub赠魔', '魔力转赠', 'Cookie登录']}
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
