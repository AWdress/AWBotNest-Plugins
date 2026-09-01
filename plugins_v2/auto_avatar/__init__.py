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

__plugin__ = {'name': '自动换头像',
 'id': 'auto_avatar',
 'version': '1.0.4',
 'author': 'AWdress',
 'description': '定时把账号头像换成图片池里随机一张。回复图片发 .avataradd 加入池子，.avatarlist/.avatarclear 管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png',
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
 'config_schema': {'delete_old': {'type': 'boolean',
                                  'default': True,
                                  'label': '删除旧头像',
                                  'cols': 3,
                                  'order': 1,
                                  'section': '功能开关',
                                  'help': '换新头像后删掉本插件上次设的那张（不动你原有的真实头像）。'},
                   'interval_min': {'type': 'slider',
                                    'default': 60,
                                    'label': '换头像间隔(分钟)',
                                    'min': 10,
                                    'max': 1440,
                                    'step': 10,
                                    'order': 10,
                                    'section': '头像轮换',
                                    'help': '每隔多少分钟随机换一次。最小 10 分钟，防 Telegram 限流。改这个值后需「重载」插件生效。'},
                   'add_command': {'type': 'string',
                                   'default': '.avataradd',
                                   'label': '加图命令',
                                   'order': 20,
                                   'section': '图片池命令',
                                   'help': '回复图片或发图带此说明，把图存入池子。'},
                   'list_command': {'type': 'string',
                                    'default': '.avatarlist',
                                    'label': '查看命令',
                                    'order': 21,
                                    'section': '图片池命令'},
                   'clear_command': {'type': 'string',
                                     'default': '.avatarclear',
                                     'label': '清空命令',
                                     'order': 22,
                                     'section': '图片池命令'}},
 'v1_compatible_version': '1.0.4',
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
