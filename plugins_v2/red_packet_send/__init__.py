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

__plugin__ = {'name': '发红包',
 'id': 'red_packet_send',
 'version': '1.0.15',
 'author': 'AWdress',
 'scope': 'user',
 'description': '用你的账号在群里发拼手气红包：口令（可自定义前缀）+随机防挂码渲染成验证码图片，群友识别并输入完整字符才算参与（防脚本）；可选每抢一个换码，命令消息秒删，按拼手气随机分配并自动发放魔力，每个红包带递增编号便于对照。自带 '
                'Vue 配置界面 + 红包监控。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.13 重复参与反馈\n'
              '- 用户再次发送当前有效参与口令时，回复重复参与无效提示\n'
              '- 提示 8 秒后自动删除，普通聊天不会被误判为重复参与\n'
              '\n'
              'v1.0.12 显示群组名称\n'
              '- 红包监控和历史记录显示群组名称并保留 UID\n'
              '- 创建、超时和结算日志显示群组名称\n'
              '\n'
              'v1.0.11 修复红包金额\n'
              '- 统一用整数魔力分配，避免按分切再取整导致小份额打成 0 或扣发不符\n'
              '- 总额不足以每个红包至少 1 魔力时拒绝创建',
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'enabled': {'title': 'enabled',
                               'section': 'V2 配置',
                               'order': 1,
                               'type': 'boolean',
                               'default': True},
                   'create_word': {'title': 'create word',
                                   'section': 'V2 配置',
                                   'order': 2,
                                   'type': 'string',
                                   'default': '创建红包'},
                   'status_word': {'title': 'status word',
                                   'section': 'V2 配置',
                                   'order': 3,
                                   'type': 'string',
                                   'default': '红包状态'},
                   'end_word': {'title': 'end word',
                                'section': 'V2 配置',
                                'order': 4,
                                'type': 'string',
                                'default': '结束红包'},
                   'code_length': {'title': 'code length',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'number',
                                   'default': 4},
                   'rotate_code': {'title': 'rotate code',
                                   'section': 'V2 配置',
                                   'order': 6,
                                   'type': 'boolean',
                                   'default': False},
                   'max_amount': {'title': 'max amount',
                                  'section': 'V2 配置',
                                  'order': 7,
                                  'type': 'number',
                                  'default': 0},
                   'max_count': {'title': 'max count',
                                 'section': 'V2 配置',
                                 'order': 8,
                                 'type': 'number',
                                 'default': 0},
                   'activity_timeout_minutes': {'title': 'activity timeout minutes',
                                                'section': 'V2 配置',
                                                'order': 9,
                                                'type': 'number',
                                                'default': 30},
                   'end_delete_delay': {'title': 'end delete delay',
                                        'section': 'V2 配置',
                                        'order': 10,
                                        'type': 'number',
                                        'default': 10},
                   'transfer_prefix': {'title': 'transfer prefix',
                                       'section': 'V2 配置',
                                       'order': 11,
                                       'type': 'string',
                                       'default': '+'},
                   'congrats_text': {'title': 'congrats text',
                                     'section': 'V2 配置',
                                     'order': 12,
                                     'type': 'string',
                                     'default': '恭喜 {name} 抢到 {amount} 魔力！'},
                   'blacklist_ids': {'title': 'blacklist ids',
                                     'section': 'V2 配置',
                                     'order': 13,
                                     'type': 'string',
                                     'default': ''}},
 'v1_compatible_version': '1.0.14',
 'v2_adapter': 'telethon',
 'tags': ['福利', 'Telegram'],
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
