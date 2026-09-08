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

__plugin__ = {'name': '插件开发探针',
 'id': 'probe',
 'version': '1.0.9',
 'author': 'AWdress',
 'description': '开发插件时采集消息/会话/按钮/回调的完整信息：回复消息发 .probe 导出带访问路径的字段速查 + 原始结构；.cbprobe 抓 Bot 收到的回调。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png',
 'changelog': 'v1.0.9 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.8 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.6 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.3 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.2 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'both',
 'config_schema': {'delete_command': {'type': 'boolean',
                                      'default': True,
                                      'label': '删除命令消息',
                                      'cols': 3,
                                      'order': 1,
                                      'section': '功能开关',
                                      'help': '导出后是否删除你发出的命令本身。'},
                   'command': {'type': 'string',
                               'default': '.probe',
                               'label': '探测命令',
                               'order': 10,
                               'section': '命令配置',
                               'help': '自己发出、以此开头的消息会触发。/probe 与 .probe 等价。'},
                   'cb_command': {'type': 'string',
                                  'default': '.cbprobe',
                                  'label': '回调抓取开关命令',
                                  'order': 11,
                                  'section': '命令配置',
                                  'help': '「命令 on」开启、「命令 off」关闭抓取 Bot 收到的内联按钮回调。仅 Bot 账号生效。'},
                   'max_value_len': {'type': 'slider',
                                     'min': 50,
                                     'max': 1000,
                                     'default': 300,
                                     'label': '单字段截断长度',
                                     'order': 20,
                                     'section': '输出设置',
                                     'help': '速查区里文本类字段超过该长度会截断（原始结构区不截断）。'}},
 'v1_compatible_version': '1.0.3',
 'v2_adapter': 'telethon',
 'tags': ['网络探测', '延迟测试', '服务监控']}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults, __plugin__.get('config_schema'))
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
