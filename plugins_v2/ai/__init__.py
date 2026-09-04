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
 'version': '1.3.7',
 'author': 'AWdress',
 'description': '私聊/群@你时 AI 人形对话（带记忆）；支持主动搭话、/ai 图文解释，以及通过平台统一 AI 使用 /生图 或 /draw 生成图片。自带 Vue 配置界面。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/ai.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
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
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'enable_image_generation': {'title': 'enable image generation',
                                               'section': 'V2 配置',
                                               'order': 1,
                                               'type': 'boolean',
                                               'default': True},
                   'image_size': {'title': 'image size',
                                  'section': 'V2 配置',
                                  'order': 2,
                                  'type': 'string',
                                  'default': '1024x1024'},
                   'image_quality': {'title': 'image quality',
                                     'section': 'V2 配置',
                                     'order': 3,
                                     'type': 'string',
                                     'default': 'auto'},
                   'enable_private_chat': {'title': 'enable private chat',
                                           'section': 'V2 配置',
                                           'order': 4,
                                           'type': 'boolean',
                                           'default': True},
                   'enable_group_chat': {'title': 'enable group chat',
                                         'section': 'V2 配置',
                                         'order': 5,
                                         'type': 'boolean',
                                         'default': True},
                   'group_chat_ids': {'title': 'group chat ids',
                                      'section': 'V2 配置',
                                      'order': 6,
                                      'type': 'chat',
                                      'default': '',
                                      'chat_types': ['group', 'channel'],
                                      'session': True},
                   'system_prompt': {'title': 'system prompt',
                                     'section': 'V2 配置',
                                     'order': 7,
                                     'type': 'string',
                                     'default': '# Role\n'
                                                '你是一个相处了很久的普通网友。\n'
                                                '\n'
                                                '# Rules\n'
                                                '1. 语气口语化、随性、接地气，就像在微信或QQ上聊天。\n'
                                                '2. 每次回复必须精简，严禁长篇大论。\n'
                                                '3. 绝对不能超过 20 个字。\n'
                                                '4. 绝对不要在回复中模仿、复述或带入用户的动作动作。\n'
                                                '5. 偶尔可以在句末加一个合适的 emoji（如 😂、🤷\u200d♂️、👀），不要过多。'},
                   'max_history': {'title': 'max history',
                                   'section': 'V2 配置',
                                   'order': 8,
                                   'type': 'number',
                                   'default': 10},
                   'enable_proactive': {'title': 'enable proactive',
                                        'section': 'V2 配置',
                                        'order': 9,
                                        'type': 'boolean',
                                        'default': False},
                   'proactive_chat_ids': {'title': 'proactive chat ids',
                                          'section': 'V2 配置',
                                          'order': 10,
                                          'type': 'chat',
                                          'default': '',
                                          'chat_types': ['group', 'channel'],
                                          'session': True},
                   'proactive_min_minutes': {'title': 'proactive min minutes',
                                             'section': 'V2 配置',
                                             'order': 11,
                                             'type': 'number',
                                             'default': 60},
                   'proactive_max_minutes': {'title': 'proactive max minutes',
                                             'section': 'V2 配置',
                                             'order': 12,
                                             'type': 'number',
                                             'default': 180},
                   'enable_explain_command': {'title': 'enable explain command',
                                              'section': 'V2 配置',
                                              'order': 13,
                                              'type': 'boolean',
                                              'default': True},
                   'enable_explain_prompt': {'title': 'enable explain prompt',
                                             'section': 'V2 配置',
                                             'order': 14,
                                             'type': 'boolean',
                                             'default': False},
                   'explain_prompt': {'title': 'explain prompt',
                                      'section': 'V2 配置',
                                      'order': 15,
                                      'type': 'string',
                                      'default': '你是一个群聊消息解读助手。请根据用户【回复的消息内容】进行解释与答疑，简明清晰。\n'
                                                 '输出结构：\n'
                                                 '1) 这句话/这段话的主要意思\n'
                                                 '2) 语气/态度\n'
                                                 "3) 可能的隐含信息（没有就写'无'）\n"
                                                 '\n'
                                                 '需要解释的消息内容：{content}'},
                   'white_list_chats': {'title': 'white list chats',
                                        'section': 'V2 配置',
                                        'order': 16,
                                        'type': 'chat',
                                        'default': '',
                                        'chat_types': ['group', 'channel'],
                                        'session': True}},
 'v1_compatible_version': '1.3.4',
 'v2_adapter': 'telethon',
 'tags': ['AI对话', '智能回复', '主动搭话'],
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

