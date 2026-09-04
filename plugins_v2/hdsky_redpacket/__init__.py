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

__plugin__ = {'name': '拼手气红包(HDSKY)',
 'id': 'hdsky_redpacket',
 'version': '1.0.9',
 'author': 'AWdress',
 'scope': 'user',
 'description': '监控天空(HDSKY)群拼手气红包，自动点击「抢红包」按钮。可选 /red 占位发言应对「限最近发言人」。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.5 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.4 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'config_schema': {'resolved_chat_names': {'type': 'info', 'label': '已识别群组名称', 'order': 9, 'section': '参数配置'},
                   'button_enabled': {'type': 'boolean',
                                      'default': False,
                                      'label': '启用拼手气红包',
                                      'cols': 3,
                                      'order': 1,
                                      'section': '功能开关',
                                      'help': '检测「拼手气红包」消息并自动点击「抢红包」内联按钮。'},
                   'button_pre_send': {'type': 'boolean',
                                       'default': False,
                                       'label': '发言占位（/red前）',
                                       'cols': 3,
                                       'order': 2,
                                       'section': '功能开关',
                                       'show_if': {'button_enabled': True},
                                       'help': '检测到 /red 发包命令时先发一条消息占位（随即删除），应对「限最近发言人」。'},
                   'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '抢包结果通知我',
                                    'cols': 3,
                                    'order': 3,
                                    'section': '功能开关',
                                    'help': '抢到/失败时用机器人通知平台主人。'},
                   'button_groups': {'type': 'chat',
                                     'default': '',
                                     'label': '监听群组ID',
                                     'order': 10,
                                     'section': '参数配置',
                                     'show_if': {'button_enabled': True},
                                     'help': '逗号分隔的群组ID，留空=所有群。',
                                     'chat_types': ['group', 'channel'],
                                     'session': True},
                   'button_delay': {'type': 'slider',
                                    'default': 0,
                                    'label': '点击延迟(秒)',
                                    'min': 0,
                                    'max': 60,
                                    'step': 1,
                                    'order': 11,
                                    'section': '参数配置',
                                    'show_if': {'button_enabled': True}},
                   'button_pre_send_text': {'type': 'string',
                                            'default': '.',
                                            'label': '占位消息内容',
                                            'order': 12,
                                            'section': '参数配置',
                                            'show_if': {'button_enabled': True}}},
 'v1_compatible_version': '1.0.6',
 'v2_adapter': 'telethon',
 'tags': ['天空红包', '自动领取', '动态密码']}
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

