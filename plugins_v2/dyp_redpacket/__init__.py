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

__plugin__ = {'name': '癫影积分红包',
 'id': 'dyp_redpacket',
 'version': '1.2.4',
 'author': 'AWdress',
 'scope': 'user',
 'description': '监控癫影小助手发的混合积分红包（暗含 N 个雷包），逐个点击未抢数字按钮，落地一格即停：抢到分或踩雷都算用掉唯一机会停手，只有「手慢了/已被抢」才试下一格。发包bot/群组内置写死。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/dyp_redpacket.jpg',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.2 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.2.1 更新插件 Logo\n'
              '- 使用癫影专属图片作为插件卡片与市场图标',
 'config_schema': {'dyp_enabled': {'type': 'boolean',
                                   'default': False,
                                   'label': '启用癫影积分红包',
                                   'cols': 3,
                                   'order': 1,
                                   'section': '功能开关',
                                   'help': '癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过）。现为混合红包（暗含 N 个雷包），照抢、赌不中雷。'},
                   'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '抢到/踩雷时通知我',
                                    'cols': 3,
                                    'order': 2,
                                    'section': '功能开关',
                                    'help': '抢到红包或踩雷时用机器人通知平台主人；未抢到（都被别人抢完）仅记录日志不通知。'},
                   'dyp_delay': {'type': 'slider',
                                 'default': 0,
                                 'label': '点击延迟-最小(秒)',
                                 'min': 0,
                                 'max': 60,
                                 'step': 1,
                                 'order': 10,
                                 'section': '延迟参数',
                                 'show_if': {'dyp_enabled': True},
                                 'help': '抢包前等待的最小秒数。与「点击延迟-最大」配合：最大>最小时在两者间取随机值，别太机械；相等或最大更小则固定等这么久。'},
                   'dyp_delay_max': {'type': 'slider',
                                     'default': 0,
                                     'label': '点击延迟-最大(秒)',
                                     'min': 0,
                                     'max': 60,
                                     'step': 1,
                                     'order': 11,
                                     'section': '延迟参数',
                                     'show_if': {'dyp_enabled': True},
                                     'help': '抢包前等待的最大秒数。填得比「最小」大即启用随机延迟(每次在最小~最大间随机)；填 0 或不大于最小则退化为固定延迟。'}},
 'v1_compatible_version': '1.2.2',
 'v2_adapter': 'telethon',
 'tags': ['红包领取', '动态口令', '自动抢包']}
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
