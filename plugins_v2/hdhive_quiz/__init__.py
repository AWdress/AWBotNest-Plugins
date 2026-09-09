"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown
try:
    from ._legacy import DEFAULTS as _legacy_defaults
except ImportError:
    _legacy_defaults = {}
try:
    from ._legacy import teardown as _legacy_teardown
except ImportError:
    _legacy_teardown = None

__plugin__ = {'name': '影巢答题红包',
 'id': 'hdhive_quiz',
 'version': '2.0.0',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'scope': 'user',
 'description': '自动回答影巢机器人发的答题红包：从社区题库查答案回复，题库没有时可选大模型兜底作答。发包bot/群组可配。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg',
 'changelog': 'v1.0.17 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.16 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.15 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.14 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.12 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.9 适配平台后台任务治理\n'
              '- 启动时题库同步改由 ctx.create_task 托管\n'
              '- 插件停用或重载时由平台统一取消未完成的同步任务\n'
              '\n'
              'v1.0.8 修复 Vue 配置与管理接口\n'
              '- 保存配置改用 host.saveConfig，修复 undefined.post 错误\n'
              '- 状态、题库同步、答题记录和群组名称改用 host.callApi\n'
              '- 配置页关闭时清理状态轮询定时器\n'
              '\n'
              'v1.0.6 前端移除自带 API 配置字段\n'
              '- 移除大模型兜底的 llm_api_key/llm_base_url/llm_model 配置界面\n'
              '- 移除测试大模型功能\n'
              '\n'
              'v1.0.5 改为仅使用平台统一 AI\n'
              '- 移除插件自带配置回退逻辑，仅调用平台统一 AI\n'
              '- 不再需要配置 llm_api_key/llm_base_url/llm_model\n'
              '\n'
              'v1.0.4 接入平台统一 AI 能力\n'
              '- 大模型兜底优先使用平台统一 AI（管理员在「系统设置→AI 服务」配置）\n'
              '- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置\n'
              '\n'
              'v1.0.3 修复后台任务泄漏\n'
              '- 修复初始同步任务未登记、卸载时未取消，现统一登记并在 teardown 取消\n'
              '\n'
              'v1.0.2 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'requirements': ['openai>=1.0'],
 'resources': {'timeout_seconds': 600,
               'max_concurrency': 4,
               'max_background_tasks': 8,
               'failure_threshold': 5,
               'recovery_seconds': 60},
 'config_schema': {'llm_api_key': {'title': 'llm api key',
                                   'section': 'V2 配置',
                                   'order': 6,
                                   'type': 'password',
                                   'secret': True,
                                   'default': ''}},
 'v1_compatible_version': '1.0.9',
 'v2_adapter': 'telethon',
 'tags': ['海胆答题', '题库管理', 'AI出题'],
 'render_mode': 'vue'}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
