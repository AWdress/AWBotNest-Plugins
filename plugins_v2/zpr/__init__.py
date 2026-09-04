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

__plugin__ = {'name': 'P站图片',
 'id': 'zpr',
 'version': '1.0.6',
 'requirements': ['httpx>=0.27'],
 'author': 'AWdress',
 'description': '发送 /zpr [关键词] [数量] [r18] 获取二次元图片；/zp 同时附带原图文件。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.3 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.2 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'allow_r18': {'type': 'boolean',
                                 'default': False,
                                 'label': '允许 R18',
                                 'cols': 3,
                                 'order': 1,
                                 'section': '功能开关',
                                 'help': '关闭时，命令里的 r18 参数会被强制按 0(非R18) 处理。'},
                   'spoiler': {'type': 'boolean',
                               'default': True,
                               'label': '图片加遮罩',
                               'cols': 3,
                               'order': 2,
                               'section': '功能开关',
                               'help': '以剧透遮罩形式发送图片，点开才显示。'},
                   'default_num': {'type': 'slider',
                                   'default': 3,
                                   'label': '默认数量',
                                   'min': 1,
                                   'max': 10,
                                   'step': 1,
                                   'order': 10,
                                   'section': '数量限制',
                                   'help': '命令未带数量时取几张。'},
                   'max_num': {'type': 'slider',
                               'default': 6,
                               'label': '最大数量',
                               'min': 1,
                               'max': 20,
                               'step': 1,
                               'order': 11,
                               'section': '数量限制',
                               'help': '单次最多取几张（防止刷屏/超时）。'}},
 'v1_compatible_version': '1.0.3',
 'v2_adapter': 'telethon',
 'tags': ['桌面提醒', '定时通知', '消息推送']}
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

