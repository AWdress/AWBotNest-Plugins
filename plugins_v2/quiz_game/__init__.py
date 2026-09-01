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

__plugin__ = {'name': '趣味答题',
 'id': 'quiz_game',
 'version': '1.1.2',
 'author': 'AWdress',
 'description': '群内答题游戏：发「开启答题」出题，群友抢答，答对自动发魔力奖励，支持连胜加成。AI或天行出题。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/quiz_game.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.10 修复 Vue 配置保存\n'
              '- 保存配置改用新版平台 host.saveConfig，修复读取 undefined.post 失败\n'
              '- 答题记录和群组名称改用 host.callApi 读取\n'
              '- 读取、保存成功与失败统一使用平台提示\n'
              '\n'
              'v1.0.9 限制开局与答题消息来源\n'
              '- 只有插件所用的本人账号发送‘开启答题’或‘开始答题’才会开局\n'
              '- 结束命令同样只接受本人账号发送\n'
              '- 答案只接收其他群友的入站消息，开局账号不会参与抢答\n'
              '\n'
              'v1.0.7 前端移除自带 API 配置字段\n'
              '- 移除 AI 出题源的 ai_api_key/ai_base_url/ai_model 配置界面\n'
              '\n'
              'v1.0.6 改为仅使用平台统一 AI\n'
              '- 移除插件自带配置回退逻辑，仅调用平台统一 AI\n'
              '- 不再需要配置 ai_api_key/ai_base_url/ai_model\n'
              '\n'
              'v1.0.5 接入平台统一 AI 能力\n'
              '- AI 出题优先使用平台统一 AI（管理员在「系统设置→AI 服务」配置）\n'
              '- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置或天行数据\n'
              '\n'
              'v1.0.4 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'requirements': ['openai>=1.0'],
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'valid_groups': {'title': 'valid groups',
                                    'section': 'V2 配置',
                                    'order': 1,
                                    'type': 'chat',
                                    'default': '',
                                    'chat_types': ['group', 'channel'],
                                    'session': True},
                   'blacklist_users': {'title': 'blacklist users',
                                       'section': 'V2 配置',
                                       'order': 2,
                                       'type': 'string',
                                       'default': ''},
                   'source': {'title': 'source',
                              'section': 'V2 配置',
                              'order': 3,
                              'type': 'string',
                              'default': 'ai'},
                   'ai_api_key': {'title': 'ai api key',
                                  'section': 'V2 配置',
                                  'order': 4,
                                  'type': 'password',
                                  'default': ''},
                   'ai_base_url': {'title': 'ai base url',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'string',
                                   'default': ''},
                   'ai_model': {'title': 'ai model',
                                'section': 'V2 配置',
                                'order': 6,
                                'type': 'string',
                                'default': 'gpt-4o-mini'},
                   'tianapi_key': {'title': 'tianapi key',
                                   'section': 'V2 配置',
                                   'order': 7,
                                   'type': 'password',
                                   'default': ''},
                   'base_reward': {'title': 'base reward',
                                   'section': 'V2 配置',
                                   'order': 8,
                                   'type': 'number',
                                   'default': 500},
                   'streak_enabled': {'title': 'streak enabled',
                                      'section': 'V2 配置',
                                      'order': 9,
                                      'type': 'boolean',
                                      'default': True},
                   'streak_multiplier': {'title': 'streak multiplier',
                                         'section': 'V2 配置',
                                         'order': 10,
                                         'type': 'number',
                                         'default': 1.5},
                   'max_streak': {'title': 'max streak',
                                  'section': 'V2 配置',
                                  'order': 11,
                                  'type': 'number',
                                  'default': 5},
                   'timeout': {'title': 'timeout',
                               'section': 'V2 配置',
                               'order': 12,
                               'type': 'number',
                               'default': 60},
                   'question_count': {'title': 'question count',
                                      'section': 'V2 配置',
                                      'order': 13,
                                      'type': 'number',
                                      'default': 5},
                   'ai_image_enabled': {'title': 'ai image enabled',
                                        'section': 'V2 配置',
                                        'order': 14,
                                        'type': 'boolean',
                                        'default': False},
                   'ai_image_ratio': {'title': 'ai image ratio',
                                      'section': 'V2 配置',
                                      'order': 15,
                                      'type': 'number',
                                      'default': 30},
                   'auto_delete_delay': {'title': 'auto delete delay',
                                         'section': 'V2 配置',
                                         'order': 16,
                                         'type': 'number',
                                         'default': 30}},
 'v1_compatible_version': '1.1.2',
 'v2_adapter': 'telethon',
 'tags': ['消息处理']}
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
