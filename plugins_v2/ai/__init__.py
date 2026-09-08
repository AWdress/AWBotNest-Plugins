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

__plugin__ = {'name': 'AI 助手',
 'id': 'ai',
 'version': '1.3.12',
 'author': 'AWdress',
 'description': '私聊/群@你时 AI 人形对话（带记忆）；支持主动搭话、/ai 图文解释，以及通过平台统一 AI 使用 /生图 或 /draw 生成图片。自带 Vue 配置界面。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/ai.png',
 'changelog': 'v1.3.12 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.3.11 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.3.10 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.3.8 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.3.3 修复平台 AI 调用\n'
              '- 清理遗留的插件 API Key 校验，不再误报未配置 API Key\n'
              '- 对话、解释、主动搭话和生图均按平台统一 AI 能力判断\n'
              '- 清理前端与后端遗留的旧接口配置字段\n'
              '\n'
              'v1.3.2 修复插件解析失败\n'
              '- 修复版本日志中的未转义引号导致 __init__.py 语法错误\n'
              '- 插件更新后可正常重新加载\n'
              '\n'
              'v1.3.1 前端移除自带 API 配置字段\n'
              '- 删除接口分组，移除 api_key/base_url/model 配置界面\n'
              '- 移除生图模型字段和测试连接功能\n'
              '- 配置界面仅保留功能开关和业务参数\n'
              '\n'
              'v1.3.0 改为仅使用平台统一 AI\n'
              '- 移除插件自带 OpenAI 配置的回退逻辑，仅调用平台统一 AI\n'
              '- 不再需要配置 api_key/base_url/model，统一由平台管理\n'
              '- 代码精简，去除 openai 库直接依赖\n'
              '\n'
              'v1.2.0 接入平台统一 AI 能力\n'
              '- 优先使用平台统一配置的 AI 服务（管理员在「系统设置→AI 服务」配置一次，所有插件共享）\n'
              '- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置\n'
              '- 无需为每个插件重复填写服务地址和密钥\n'
              '\n'
              'v1.1.0 新增 AI 生图\n'
              '- 新增独立生图模型、尺寸与质量配置，支持任意 OpenAI 兼容生图模型\n'
              '- 新增 /生图、.生图、/draw、.draw 命令，生成后直接发送图片到当前会话\n'
              '- 兼容接口返回 base64、data URL 或普通图片 URL\n'
              '\n'
              'v1.0.7 修复异常捕获\n'
              '- 修复解析回复时未捕获 ValueError 导致偶发报错中断\n'
              '\n'
              'v1.0.6 更新插件 Logo\n'
              '- 使用 AI 助手专属图片作为插件卡片与市场图标\n'
              '\n'
              'v1.0.5 修复主动搭话定时任务\n'
              '- 未启用主动搭话时不再注册每分钟检查任务',
 'scope': 'user',
 'config_schema': {},
 'v1_compatible_version': '1.3.4',
 'v2_adapter': 'telethon',
 'tags': ['AI对话', '智能回复', '主动搭话'],
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
