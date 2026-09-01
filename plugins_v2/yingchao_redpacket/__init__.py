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

__plugin__ = {'name': '影巢口令红包（测试）',
 'id': 'yingchao_redpacket',
 'version': '1.0.6',
 'author': 'AWdress',
 'scope': 'user',
 'description': '影巢口令红包（测试功能）：监控指定发包人发的口令红包，OCR识别图片口令或复制他人口令参与，含陷阱防护。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.4 修复内存与任务清理\n'
              '- 新增过期口令/回复缓存清理，避免长时间运行内存增长\n'
              '- 卸载时取消 OCR 超时任务\n'
              '\n'
              'v1.0.3 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.2 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'config_schema': {'token_enabled': {'type': 'boolean',
                                     'default': False,
                                     'label': '启用口令红包监控',
                                     'cols': 3,
                                     'order': 1,
                                     'section': '功能开关',
                                     'help': '监控指定发包人发的「口令红包」（图片/文档口令），OCR识别或复制他人口令参与。属影巢测试功能。'},
                   'token_ocr_enabled': {'type': 'boolean',
                                         'default': False,
                                         'label': '启用OCR识别图片口令',
                                         'cols': 3,
                                         'order': 2,
                                         'section': '功能开关',
                                         'show_if': {'token_enabled': True},
                                         'help': '开启则用 ddddocr '
                                                 '识别图片口令自动参与（识别率较低，失败自动退回复制模式）；关闭则只复制他人已确认的口令（更稳）。需安装 '
                                                 'ddddocr，未安装时自动降级为复制模式。'},
                   'token_trap_detection': {'type': 'boolean',
                                            'default': True,
                                            'label': '口令陷阱检测',
                                            'cols': 3,
                                            'order': 3,
                                            'section': '功能开关',
                                            'show_if': {'token_enabled': True},
                                            'help': '发送口令前检查危险/可疑关键词。命令前缀与注入字符始终拦截，不受此开关影响。'},
                   'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '抢包结果通知我',
                                    'cols': 3,
                                    'order': 4,
                                    'section': '功能开关',
                                    'help': '抢到/拦截/失败时用机器人通知平台主人。'},
                   'token_targets': {'type': 'text',
                                     'default': '',
                                     'label': '监控发包人',
                                     'order': 10,
                                     'section': '参数配置',
                                     'show_if': {'token_enabled': True},
                                     'help': '一行一个，格式 `用户ID 备注` 或 `用户ID`。只抢这些人发的口令红包。'},
                   'token_join_delay': {'type': 'slider',
                                        'default': 0,
                                        'label': '参与延迟(秒)',
                                        'min': 0,
                                        'max': 60,
                                        'step': 1,
                                        'order': 11,
                                        'section': '参数配置',
                                        'show_if': {'token_enabled': True},
                                        'help': '识别/复制到口令后等待多少秒再发送，0=立即。'},
                   'token_trap_keywords': {'type': 'text',
                                           'default': '脚本,挂,机器人,外挂,bot,自动,作弊,封禁,封号,ban,banned,封,禁,script,auto,cheat,hack,fake,test,block',
                                           'label': '陷阱关键词',
                                           'order': 12,
                                           'section': '参数配置',
                                           'show_if': {'token_enabled': True},
                                           'help': '逗号或换行分隔。口令命中其中任一关键词则拒绝发送。'}},
 'v1_compatible_version': '1.0.5',
 'v2_adapter': 'telethon',
 'tags': ['福利']}
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
