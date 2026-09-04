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

__plugin__ = {'name': '删除自己消息',
 'id': 'self_delete',
 'version': '1.0.6',
 'author': 'AWdress',
 'description': '发送 /dme 数字 或 .dme 数字，删除当前会话里自己最近发的若干条消息。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cleanup.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.4 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.3 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'command': {'type': 'string',
                               'default': '.dme',
                               'label': '触发命令',
                               'section': '基础配置',
                               'order': 10,
                               'help': '自己发出、以此开头的消息会触发。/dme 与 .dme 等价。'},
                   'tip_seconds': {'type': 'slider',
                                   'default': 2,
                                   'label': '提示停留(秒)',
                                   'min': 0,
                                   'max': 10,
                                   'step': 1,
                                   'section': '基础配置',
                                   'order': 11,
                                   'help': '删除完成后的「已删除 N 条」提示停留多少秒再消失。'}},
 'v1_compatible_version': '1.0.4',
 'v2_adapter': 'telethon',
 'tags': ['消息自删', '延时删除', '群组清理']}
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
