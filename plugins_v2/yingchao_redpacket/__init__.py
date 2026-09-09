"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': '影巢口令红包（测试）',
 'id': 'yingchao_redpacket',
 'version': '2.0.1',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'scope': 'user',
 'requirements': ['Pillow>=10.0', 'ddddocr>=1.5'],
 'description': '影巢口令红包（测试功能）：监控指定发包人发的口令红包，OCR识别图片口令或复制他人口令参与，含陷阱防护。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg',
 'changelog': 'v2.0.1 修复 Telethon 消息字段与回复参数\n'
              '- 使用事件 sender/chat 和 Telethon reply_to、reply_to_msg_id\n'
              '- 修复口令红包监控、复制模式和历史记录在真实消息中的异常\n'
              '\n'
              'v1.0.13 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.12 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.0.11 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.10 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.8 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
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
                   'token_join_delay': {'type': 'number',
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
 'tags': ['应超红包', '自动领取', '口令解析']}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
