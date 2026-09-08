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

__plugin__ = {'name': '憨憨小助手',
 'id': 'hhan_lottery',
 'version': '2.9.11',
 'author': 'AWdress',
 'description': 'HHanClub 综合助手：赠豆与自动确认、随机红包、幸运转盘及消息管理。',
 'icon': 'https://hhanclub.net/favicon.ico',
 'changelog': 'v2.9.11 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v2.9.10 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v2.9.9 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v2.9.7 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.9.0 新增 HHanClub 随机红包自动参与\n'
              '- 仅监听官方机器人 8780479105\n'
              '- 自动解析“发送口令「…」领取”并在原群发送\n'
              '- 支持配置最短与最长随机延迟\n'
              '- 按账号、群组和红包消息持久化去重\n'
              '\n'
              'v2.8.0 新增憨豆转赠自动确认',
 'scope': 'user',
 'cookie_domains': ['hhanclub.net', '*.hhanclub.net'],
 'resources': {'timeout_seconds': 3600,
               'max_concurrency': 2,
               'max_background_tasks': 24,
               'failure_threshold': 5,
               'recovery_seconds': 60},
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12', 'lxml>=5.0'],
 'config_schema': {'manual_cookie': {'title': 'manual cookie',
                                     'section': 'V2 配置',
                                     'order': 2,
                                     'type': 'password',
                                     'secret': True,
                                     'default': ''}},
 'v1_compatible_version': '2.9.0',
 'v2_adapter': 'telethon',
 'tags': ['幸运转盘', '赠豆', '消息管理'],
 'render_mode': 'vue'}
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
