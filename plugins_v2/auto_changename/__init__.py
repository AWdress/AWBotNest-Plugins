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

__plugin__ = {'name': '自动报时昵称',
 'id': 'auto_changename',
 $11.0.8',
 'author': 'AWdress',
 'description': '定时把你的账号昵称改成当前时间，支持自定义模板（时分秒/日期/星期/随机表情）。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cleanup.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.4 修复报时定时\n'
              '- 修复用 cron 分钟通配实现整点报时不准确，改为按分钟间隔调度\n'
              'v1.0.3 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.2 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'interval_min': {'type': 'slider',
                                    'default': 5,
                                    'label': '改名间隔(分钟)',
                                    'min': 1,
                                    'max': 60,
                                    'step': 1,
                                    'order': 10,
                                    'section': '更新计划',
                                    'help': '每隔多少分钟改一次。改这个值后需「重载」插件生效。'},
                   'name_format': {'type': 'string',
                                   'default': '{emoji}{H}:{M}',
                                   'label': '昵称模板',
                                   'order': 11,
                                   'section': '昵称规则',
                                   'help': '占位符：{emoji}随机表情 {H}时 {M}分 {S}秒 {date}年-月-日 {md}月-日 {week}星期几'},
                   'name_field': {'type': 'select',
                                  'default': 'last_name',
                                  'label': '改哪个名',
                                  'order': 12,
                                  'section': '昵称规则',
                                  'options': [{'value': 'last_name', 'label': '姓 (last name)'},
                                              {'value': 'first_name', 'label': '名 (first name)'},
                                              {'value': 'both', 'label': '姓和名都改'}]}},
 'v1_compatible_version': '1.0.4',
 'v2_adapter': 'telethon',
 'tags': ['昵称报时', '日期模板', '定时任务']}
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


