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

__plugin__ = {'name': 'Emby 工具箱',
 'id': 'emby_toolbox',
 'version': '1.4.8',
 'author': 'AWdress',
 'description': '集成 Emby 剧集校验、Genre 清理/映射、季名刮削、国家语言 Tag、别名写入、STRM 刷新、元数据缺失检查等维护功能。支持定时执行与完整日志。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png',
 'changelog': 'v1.4.8 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.4.7 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.4.6 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.4.4 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.4.1 重做 Vue 界面配色\n'
              '- 去除大面积墨绿色背景，改为与平台一致的深海军蓝中性层次\n'
              '- Emby 青蓝仅用于开关、主按钮和选中状态\n'
              '- 重新校正卡片、输入框、次要文字与边框对比度\n'
              '\n'
              'v1.4.0 迁移 Vue 媒体维护控制台\n'
              '- 新增实时任务状态、历史记录和后台 API',
 'scope': 'standalone',
 'requirements': ['requests>=2.28'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'api_key': {'title': 'api key',
                               'section': 'V2 配置',
                               'order': 2,
                               'type': 'password',
                               'secret': True,
                               'default': ''}},
 'v1_compatible_version': '1.4.1',
 'v2_adapter': 'telethon',
 'tags': ['Emby维护', '媒体库清理', '元数据管理'],
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
