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

__plugin__ = {'name': '幸运抽奖',
 'id': 'human_lottery',
 'version': '1.1.3',
 'author': 'AWdress',
 'scope': 'user',
 'description': '用用户账号在群里像真人一样发起抽奖：群友发送关键词参与，到时随机开奖，支持状态、提前开奖、取消和历史记录。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/lucky_lottery.svg',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.1.1 简化创建格式\n'
              '- 删除重复的“每人奖励”参数，奖品即为每位中奖者获得的奖励\n'
              '- 自动发奖金额统一从奖品名称中提取\n'
              '\n'
              'v1.1.0 优化抽奖交互与清理\n'
              '- 支持按时间或人数开奖、参与提示、昵称链接、原消息链接和结束清理\n'
              '\n'
              'v1.0.2 更名并启用原创 Logo\n'
              '- 插件名称调整为「幸运抽奖」并使用原创 Logo\n'
              '\n'
              'v1.0.1 新增自动发奖\n'
              '- 开奖后回复中奖者参与消息发送奖励命令\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 支持用户账号发起、参与、开奖、取消和历史记录',
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
                                   'default': '创建抽奖'},
                   'status_word': {'title': 'status word',
                                   'section': 'V2 配置',
                                   'order': 3,
                                   'type': 'string',
                                   'default': '抽奖状态'},
                   'draw_word': {'title': 'draw word',
                                 'section': 'V2 配置',
                                 'order': 4,
                                 'type': 'string',
                                 'default': '立即开奖'},
                   'cancel_word': {'title': 'cancel word',
                                   'section': 'V2 配置',
                                   'order': 5,
                                   'type': 'string',
                                   'default': '取消抽奖'},
                   'default_keyword': {'title': 'default keyword',
                                       'section': 'V2 配置',
                                       'order': 6,
                                       'type': 'string',
                                       'default': '参与抽奖'},
                   'default_duration': {'title': 'default duration',
                                        'section': 'V2 配置',
                                        'order': 7,
                                        'type': 'number',
                                        'default': 10},
                   'default_winners': {'title': 'default winners',
                                       'section': 'V2 配置',
                                       'order': 8,
                                       'type': 'number',
                                       'default': 1},
                   'min_participants': {'title': 'min participants',
                                        'section': 'V2 配置',
                                        'order': 9,
                                        'type': 'number',
                                        'default': 1},
                   'max_duration': {'title': 'max duration',
                                    'section': 'V2 配置',
                                    'order': 10,
                                    'type': 'number',
                                    'default': 1440},
                   'max_winners': {'title': 'max winners',
                                   'section': 'V2 配置',
                                   'order': 11,
                                   'type': 'number',
                                   'default': 100},
                   'allow_creator': {'title': 'allow creator',
                                     'section': 'V2 配置',
                                     'order': 12,
                                     'type': 'boolean',
                                     'default': False},
                   'require_reply': {'title': 'require reply',
                                     'section': 'V2 配置',
                                     'order': 13,
                                     'type': 'boolean',
                                     'default': False},
                   'delete_commands': {'title': 'delete commands',
                                       'section': 'V2 配置',
                                       'order': 14,
                                       'type': 'boolean',
                                       'default': True},
                   'announce_delay_min': {'title': 'announce delay min',
                                          'section': 'V2 配置',
                                          'order': 15,
                                          'type': 'number',
                                          'default': 1},
                   'announce_delay_max': {'title': 'announce delay max',
                                          'section': 'V2 配置',
                                          'order': 16,
                                          'type': 'number',
                                          'default': 3},
                   'draw_delay_min': {'title': 'draw delay min',
                                      'section': 'V2 配置',
                                      'order': 17,
                                      'type': 'number',
                                      'default': 2},
                   'draw_delay_max': {'title': 'draw delay max',
                                      'section': 'V2 配置',
                                      'order': 18,
                                      'type': 'number',
                                      'default': 8},
                   'progress_every': {'title': 'progress every',
                                      'section': 'V2 配置',
                                      'order': 19,
                                      'type': 'number',
                                      'default': 0},
                   'participation_reply': {'title': 'participation reply',
                                           'section': 'V2 配置',
                                           'order': 20,
                                           'type': 'boolean',
                                           'default': True},
                   'participation_reply_delete': {'title': 'participation reply delete',
                                                  'section': 'V2 配置',
                                                  'order': 21,
                                                  'type': 'number',
                                                  'default': 5},
                   'cleanup_delay': {'title': 'cleanup delay',
                                     'section': 'V2 配置',
                                     'order': 22,
                                     'type': 'number',
                                     'default': 30},
                   'blacklist_ids': {'title': 'blacklist ids',
                                     'section': 'V2 配置',
                                     'order': 23,
                                     'type': 'string',
                                     'default': ''},
                   'notify_owner': {'title': 'notify owner',
                                    'section': 'V2 配置',
                                    'order': 24,
                                    'type': 'boolean',
                                    'default': True},
                   'auto_award': {'title': 'auto award',
                                  'section': 'V2 配置',
                                  'order': 25,
                                  'type': 'boolean',
                                  'default': True},
                   'award_command': {'title': 'award command',
                                     'section': 'V2 配置',
                                     'order': 26,
                                     'type': 'string',
                                     'default': '+{amount}'},
                   'award_delay_min': {'title': 'award delay min',
                                       'section': 'V2 配置',
                                       'order': 27,
                                       'type': 'number',
                                       'default': 1},
                   'award_delay_max': {'title': 'award delay max',
                                       'section': 'V2 配置',
                                       'order': 28,
                                       'type': 'number',
                                       'default': 3},
                   'announce_template': {'title': 'announce template',
                                         'section': 'V2 配置',
                                         'order': 29,
                                         'type': 'string',
                                         'default': '🎁 <b>幸运抽奖 #{lottery_id}</b>\n'
                                                    '\n'
                                                    '✨ 奖品：<b>{prize}</b>\n'
                                                    '🏆 中奖名额：{winners} 人\n'
                                                    '{draw_rule}\n'
                                                    '\n'
                                                    '发送关键词参与：\n'
                                                    '<code>{keyword}</code>\n'
                                                    '\n'
                                                    '每人限参与一次，祝你好运 🍀'},
                   'result_template': {'title': 'result template',
                                       'section': 'V2 配置',
                                       'order': 30,
                                       'type': 'string',
                                       'default': '🎊 <b>幸运开奖 #{lottery_id}</b>\n'
                                                  '\n'
                                                  '🎁 奖品：<b>{prize}</b>\n'
                                                  '👥 参与人数：{participants} 人\n'
                                                  '🏆 中奖名单：\n'
                                                  '{winner_list}\n'
                                                  '\n'
                                                  '🔗 <a href="{announcement_link}">查看本次抽奖</a>\n'
                                                  '\n'
                                                  '恭喜中奖，感谢大家参与 ✨'},
                   'empty_template': {'title': 'empty template',
                                      'section': 'V2 配置',
                                      'order': 31,
                                      'type': 'string',
                                      'default': '这次抽奖参与人数不足（{participants}/{minimum}），先取消啦，下次再来～'}},
 'v1_compatible_version': '1.1.2',
 'v2_adapter': 'telethon',
 'tags': ['人工抽奖', '抽奖活动', '中奖记录'],
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
