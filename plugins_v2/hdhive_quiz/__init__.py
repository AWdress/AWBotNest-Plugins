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

__plugin__ = {'name': '影巢答题红包',
 'id': 'hdhive_quiz',
 $11.0.13',
 'author': 'AWdress',
 'scope': 'user',
 'description': '自动回答影巢机器人发的答题红包：从社区题库查答案回复，题库没有时可选大模型兜底作答。发包bot/群组可配。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg',
 'changelog': 'AWBotNest 2 兼容发布\n'
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
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'enabled': {'title': 'enabled',
                               'section': 'V2 配置',
                               'order': 1,
                               'type': 'boolean',
                               'default': False},
                   'bot_ids': {'title': 'bot ids',
                               'section': 'V2 配置',
                               'order': 2,
                               'type': 'string',
                               'default': ''},
                   'chat_ids': {'title': 'chat ids',
                                'section': 'V2 配置',
                                'order': 3,
                                'type': 'chat',
                                'default': '',
                                'chat_types': ['group', 'channel'],
                                'session': True},
                   'reply_format': {'title': 'reply format',
                                    'section': 'V2 配置',
                                    'order': 4,
                                    'type': 'string',
                                    'default': 'content'},
                   'llm_enabled': {'title': 'llm enabled',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'boolean',
                                   'default': False},
                   'llm_api_key': {'title': 'llm api key',
                                   'section': 'V2 配置',
                                   'order': 6,
                                   'type': 'password',
                                   'default': ''},
                   'llm_base_url': {'title': 'llm base url',
                                    'section': 'V2 配置',
                                    'order': 7,
                                    'type': 'string',
                                    'default': ''},
                   'llm_model': {'title': 'llm model',
                                 'section': 'V2 配置',
                                 'order': 8,
                                 'type': 'string',
                                 'default': 'gpt-4o-mini'},
                   'bank_repo': {'title': 'bank repo',
                                 'section': 'V2 配置',
                                 'order': 9,
                                 'type': 'string',
                                 'default': 'https://github.com/my-name-is-alan/hdhive-red-questions'},
                   'bank_branch': {'title': 'bank branch',
                                   'section': 'V2 配置',
                                   'order': 10,
                                   'type': 'string',
                                   'default': 'main'},
                   'bank_subdir': {'title': 'bank subdir',
                                   'section': 'V2 配置',
                                   'order': 11,
                                   'type': 'string',
                                   'default': 'questions'},
                   'bank_sync_hours': {'title': 'bank sync hours',
                                       'section': 'V2 配置',
                                       'order': 12,
                                       'type': 'number',
                                       'default': 12}},
 'v1_compatible_version': '1.0.9',
 'v2_adapter': 'telethon',
 'tags': ['海胆答题', '题库管理', 'AI出题'],
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


