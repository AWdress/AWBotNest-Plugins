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

__plugin__ = {'name': '小姐姐视频',
 'id': 'xjj',
 'version': '1.0.5',
 'author': 'AWdress',
 'description': '发送 /xjj 或 .xjj 获取一条随机短视频。',
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
 'config_schema': {'command': {'type': 'string',
                               'default': '.xjj',
                               'label': '触发命令',
                               'section': '命令',
                               'help': '自己发出、以此开头的消息会触发。/xjj 与 .xjj 等价。',
                               'order': 10},
                   'api_url': {'type': 'string',
                               'default': 'http://47.115.231.249/API/sjsp/api.php?msg=热舞',
                               'label': '视频接口地址',
                               'section': '接口',
                               'help': '返回 JSON 且含视频直链的接口。',
                               'order': 20},
                   'video_key': {'type': 'string',
                                 'default': 'url',
                                 'label': '直链字段名',
                                 'section': '接口',
                                 'help': '接口返回 JSON 中视频直链所在的字段（支持顶层或 data 下）。',
                                 'order': 21},
                   'timeout': {'type': 'slider',
                               'default': 15,
                               'label': '请求超时(秒)',
                               'min': 5,
                               'max': 60,
                               'step': 5,
                               'section': '接口',
                               'order': 22}},
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
