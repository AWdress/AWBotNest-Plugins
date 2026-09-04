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

__plugin__ = {'name': '插件开发调试',
 'id': 'custom_plugin',
 'version': '1.0.6',
 'author': 'AWdress',
 'scope': 'both',
 'description': '在管理员配置页编辑、检查并运行 Python 插件源码，显示运行状态与错误堆栈，适合开发和调试单文件插件。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/custom_plugin.svg',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.3 支持独立运行插件\n'
              '- 源码检查可以识别 standalone 范围\n'
              '- 独立运行插件不会自动挂载用户账号或机器人消息处理器\n'
              '\n'
              'v1.0.2 修复调试生命周期缺陷\n'
              '- 源码检查改用 AST 静态分析，不再执行顶层代码导致保存时重复副作用\n'
              '- 关闭运行开关时允许保存尚未完成或存在语法错误的草稿\n'
              '- 自定义 setup 完整成功前暂存消息、编辑、回调、API、Webhook、定时任务与清理注册\n'
              '- setup 失败时执行自定义清理并丢弃暂存注册，避免半成品监听器继续运行\n'
              '- 定时任务返回延迟绑定代理，兼容源码保存任务对象并读取运行状态\n'
              '- 按源码 __plugin__.scope 保持 user、bot、both 默认监听范围\n'
              '- 新增独立 JSON 运行配置并合并 config_schema 默认值，支持 ctx.config 与 ctx.update_config\n'
              '- 保留 /status 与 /validate 调试接口，防止自定义 API 覆盖后配置页失效\n'
              '\n'
              'v1.0.1 更名为插件开发调试\n'
              '- 展示名称调整为“插件开发调试”，更准确体现源码编辑、检查、运行和错误排查用途\n'
              '- 保留 custom_plugin 内部 ID，已安装用户可直接更新\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- Vue 配置页内置 Python 源码编辑器与示例模板\n'
              '- 保存配置后编译并运行自定义 setup(ctx)\n'
              '- 停用或重载时调用自定义 teardown(ctx)\n'
              '- 编译或运行失败时保留容器插件，便于直接修正源码\n'
              '- 仅管理员配置页可修改，不开放 Telegram 远程写代码',
 'webhook': True,
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100}},
 'v1_compatible_version': '1.0.3',
 'v2_adapter': 'telethon',
 'tags': ['自定义插件', '脚本执行', '扩展开发'],
 'render_mode': 'vue'}
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
