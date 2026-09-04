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


 'version': '1.0.10','name': 'HDHive抽奖',
 'id': 'hdhive_lottery',
 'author': 'AWdress',
 'description': '自动参与 HDHive 抽奖：监听抽奖消息，随机等待后发口令参与，开奖检测中奖并通知。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.6 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.5 更新插件 Logo\n'
              '- 使用 HDHive（影巢）专属图片作为插件卡片与市场图标',
 'scope': 'user',
 'config_schema': {'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '参与/中奖通知我',
                                    'cols': 3,
                                    'order': 1,
                                    'section': '功能开关',
                                    'help': '参与成功、失败、中奖时用机器人通知平台主人。'},
                   'wait_min': {'type': 'slider',
                                'default': 25,
                                'label': '参与前最短等待(秒)',
                                'min': 0,
                                'max': 300,
                                'step': 5,
                                'order': 10,
                                'section': '等待策略',
                                'help': '收到抽奖后随机等待区间下限，避免秒回显得像机器人。'},
                   'wait_max': {'type': 'slider',
                                'default': 65,
                                'label': '参与前最长等待(秒)',
                                'min': 5,
                                'max': 600,
                                'step': 5,
                                'order': 11,
                                'section': '等待策略'}},
 'v1_compatible_version': '1.0.6',
 'v2_adapter': 'telethon',
 'tags': ['海胆抽奖', '积分抽奖', '奖品统计']}
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



