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
 'version': '1.0.10',
 'requirements': ['httpx>=0.27'],
 'author': 'AWdress',
 'description': '发送 /zpr [关键词] [数量] [r18] 获取二次元图片；/zp 同时附带原图文件。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png',
 'changelog': 'v1.0.10 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.0.9 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.8 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.6 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
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
                   'default_num': {'type': 'number',
                                   'default': 3,
                                   'label': '默认数量',
                                   'min': 1,
                                   'max': 10,
                                   'step': 1,
                                   'order': 10,
                                   'section': '数量限制',
                                   'help': '命令未带数量时取几张。'},
                   'max_num': {'type': 'number',
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
