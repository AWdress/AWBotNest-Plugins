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

__plugin__ = {'name': '自动抢红包',
 'id': 'red_packet_grab',
 'version': '1.2.7',
 'author': 'AWdress',
 'scope': 'user',
 'description': '自动参与口令红包：支持正文直接口令、图片财富密码、OCR 验证码识别及中奖确认复制兜底。可按发包人/群组限制范围，自带 Vue 配置界面与抢包记录。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.4 支持正文动态财富密码红包\n'
              '- 识别“财富密码：内容”并直接发送完整密码参与\n'
              '- 密码可包含中文、英文、数字、标点和空格\n'
              '- 红包剩余数量为 0 时自动跳过，避免发送失效密码\n'
              '\n'
              'v1.2.2 修复复制兜底漏响应\n'
              '- 支持群友回复红包消息发送口令，不再仅缓存独立文本\n'
              '- 缓存漏记时直接读取中奖确认所回复的原消息，必要时从 Telegram 回查\n'
              '- 同时监听新发与编辑后的中奖确认，兼容机器人编辑原消息返回结果\n'
              '- 扩展领取成功、获得、到账及内嵌金额确认识别\n'
              '- 记录候选口令所属红包，多红包并存时优先精确匹配并增加诊断日志\n'
              '\n'
              'v1.2.1 支持图片财富密码红包\n'
              '- 自动识别“财富密码见图片、发送财富密码即可领取”的拼手气红包\n'
              '- 监听红包图片编辑，前一次 OCR 未参与成功时会识别更新后的动态口令\n'
              '- 剩余数量为 0 时停止识别，避免红包结束后发送无效口令\n'
              '\n'
              'v1.2.0 支持正文拼手气红包\n'
              '- 自动识别“发送下方口令领取”后的完整口令并立即参与\n'
              '- 同时监听新消息与编辑消息，避免后补口令时漏抢\n'
              '- 按账号、群组和红包消息去重，结束状态不会重复发送\n'
              '\n'
              'v1.1.2 修复复制兜底选包\n'
              '- 修复多红包并存时按过期时间选包导致口令记错包，改为按确认者匹配对应红包\n'
              '\n'
              'v1.1.1 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
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
                   'trigger_keywords': {'title': 'trigger keywords',
                                        'section': 'V2 配置',
                                        'order': 2,
                                        'type': 'string',
                                        'default': '验证码,发送图中字符,识别上方,幸运红包'},
                   'target_senders': {'title': 'target senders',
                                      'section': 'V2 配置',
                                      'order': 3,
                                      'type': 'string',
                                      'default': ''},
                   'target_groups': {'title': 'target groups',
                                     'section': 'V2 配置',
                                     'order': 4,
                                     'type': 'text',
                                     'default': '',
                                     'help': '每行一项'},
                   'ocr_enabled': {'title': 'ocr enabled',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'boolean',
                                   'default': True},
                   'copy_fallback': {'title': 'copy fallback',
                                     'section': 'V2 配置',
                                     'order': 6,
                                     'type': 'boolean',
                                     'default': True},
                   'code_min_len': {'title': 'code min len',
                                    'section': 'V2 配置',
                                    'order': 7,
                                    'type': 'number',
                                    'default': 4},
                   'code_max_len': {'title': 'code max len',
                                    'section': 'V2 配置',
                                    'order': 8,
                                    'type': 'number',
                                    'default': 8},
                   'join_delay': {'title': 'join delay',
                                  'section': 'V2 配置',
                                  'order': 9,
                                  'type': 'number',
                                  'default': 2},
                   'success_markers': {'title': 'success markers',
                                       'section': 'V2 配置',
                                       'order': 10,
                                       'type': 'string',
                                       'default': '抢到,恭喜'},
                   'transfer_prefix': {'title': 'transfer prefix',
                                       'section': 'V2 配置',
                                       'order': 11,
                                       'type': 'string',
                                       'default': '+'},
                   'activity_ttl_minutes': {'title': 'activity ttl minutes',
                                            'section': 'V2 配置',
                                            'order': 12,
                                            'type': 'number',
                                            'default': 30},
                   'notify_owner': {'title': 'notify owner',
                                    'section': 'V2 配置',
                                    'order': 13,
                                    'type': 'boolean',
                                    'default': True}},
 'v1_compatible_version': '1.2.4',
 'v2_adapter': 'telethon',
 'tags': ['红包监控', '自动抢包', '群组通知'],
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

