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

__plugin__ = {'name': '消息转发',
 'id': 'msg_forward',
 'version': '1.0.3',
 'author': 'AWdress',
 'description': '把来源会话的消息按规则转发到目标会话，支持多规则、类型/关键词/发送者过滤、原生转发或复制搬运。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.3 显示群组/频道名称\n'
              '- 转发日志同时显示来源和目标会话名称，保留 ID 便于排查\n'
              '- 配置保存后自动解析已填写的会话 ID，在设置页显示名称\n'
              '\n'
              'v1.0.2 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.1 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'enable': {'type': 'boolean',
                              'default': False,
                              'label': '启用转发',
                              'cols': 3,
                              'order': 1,
                              'section': '功能开关',
                              'help': '总开关。关闭后不转发任何消息。'},
                   'forward_album': {'type': 'boolean',
                                     'default': True,
                                     'label': '整组转发相册',
                                     'cols': 3,
                                     'order': 2,
                                     'section': '功能开关',
                                     'help': '相册（多图/多视频）整组一起转；关闭则每个文件单独转。'},
                   'resolved_chat_names': {'type': 'info',
                                           'label': '已识别会话名称',
                                           'order': 9,
                                           'section': '规则',
                                           'help': '保存配置后自动从账号会话列表解析名称；解析失败时保留会话 ID。'},
                   'rules': {'type': 'list',
                             'default': [],
                             'label': '转发规则',
                             'item_label': '规则',
                             'order': 10,
                             'section': '规则',
                             'fields': {'source': {'type': 'string',
                                                   'label': '来源会话',
                                                   'help': '填 -100 开头的会话ID 或 @用户名'},
                                        'targets': {'type': 'string',
                                                    'label': '转发到',
                                                    'help': '目标会话ID / @用户名，逗号可填多个'},
                                        'types': {'type': 'multiselect',
                                                  'label': '消息类型',
                                                  'default': [],
                                                  'options': [{'value': 'text', 'label': '文本'},
                                                              {'value': 'link', 'label': '链接'},
                                                              {'value': 'photo', 'label': '图片'},
                                                              {'value': 'video', 'label': '视频'},
                                                              {'value': 'document', 'label': '文件'},
                                                              {'value': 'audio', 'label': '音频'}]},
                                        'kw': {'type': 'string', 'label': '关键词', 'help': '含任一才转，逗号分隔；留空=不限'},
                                        'nkw': {'type': 'string',
                                                'label': '排除词',
                                                'help': '含任一则不转，逗号分隔；留空=不排除'},
                                        'sender': {'type': 'string',
                                                   'label': '只转谁发的',
                                                   'help': '@用户名 / 数字ID / bot(只转机器人)，逗号多个；留空=所有人'},
                                        'copy': {'type': 'boolean',
                                                 'label': '复制搬运',
                                                 'default': False,
                                                 'help': '关=原生转发（带「转发自」）；开=复制搬运（不带来源标记）'}}}},
 'v1_compatible_version': '1.0.3',
 'v2_adapter': 'telethon'}
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
