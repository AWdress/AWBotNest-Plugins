"""digital_pet AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': '电子宠物',
 'id': 'digital_pet',
 'version': '2.0.1',
 'author': 'AWdress',
 'scope': 'user',
 'description': '在 Telegram 养成你的专属电子宠物！支持领养、喂食、玩耍、清洁、成长、进化、道具、随机事件和视觉表现。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/digital_pet/logo.png',
 'changelog': 'v2.0.1 适配平台正式调度接口\n- 宠物心跳统一改用 schedule_cron 注册并接受平台生命周期管理\n\nv2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v2.1.10 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v2.1.9 修复数值配置显示\n'
              '- 将滑块字段改为精确数值输入，确保当前值始终可见\n'
              '- 保留原有默认值、范围和步长校验\n'
              '\n'
              'v2.1.8 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v2.1.7 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v2.1.5 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.1.2 修复定时通知与卸载残留任务\n'
              '- 定时提醒改用新版平台 ctx.bot.send 接口\n'
              '- 卸载后残留的心跳回调会立即停止，不再发送通知或重复处理宠物状态\n'
              '- teardown 增加幂等保护，避免重复输出卸载日志\n'
              '\n'
              'v2.1.1 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              '\n'
              'v2.1.0 电子宠物终版增强更新\n'
              '- 新增全身像视觉系统、动作图、事件图、成长进化立绘\n'
              '- 支持三物种差异化成长：电子狗、像素猫、机械龙\n'
              '- 新增随机事件、升级奖励、周期播报、背包与道具体系\n'
              '- 新增 /档案、/背包、/使用 等命令\n'
              '- 新增命令冷却时间与冷却设置配置项\n'
              '- 全部命令彻底中文化，玩法说明和配置界面同步完善',
 'requirements': [],
 'config_schema': {'auto_reminder_enabled': {'type': 'boolean',
                                             'default': True,
                                             'label': '启用自动提醒',
                                             'cols': 3,
                                             'order': 1,
                                             'section': '功能开关'},
                   'auto_delete_replies': {'type': 'boolean',
                                           'default': True,
                                           'label': '自动删除插件回复',
                                           'cols': 3,
                                           'order': 2,
                                           'section': '功能开关'},
                   'show_pet_image': {'type': 'boolean',
                                      'default': True,
                                      'label': '状态时显示宠物图片',
                                      'cols': 3,
                                      'order': 3,
                                      'section': '功能开关'},
                   'use_fullbody_art': {'type': 'boolean',
                                        'default': True,
                                        'label': '启用全身像视觉系统',
                                        'cols': 3,
                                        'order': 4,
                                        'section': '功能开关'},
                   'random_events_enabled': {'type': 'boolean',
                                             'default': True,
                                             'label': '启用随机事件',
                                             'cols': 3,
                                             'order': 5,
                                             'section': '功能开关'},
                   'daily_brief_enabled': {'type': 'boolean',
                                           'default': True,
                                           'label': '启用周期状态播报',
                                           'cols': 3,
                                           'order': 6,
                                           'section': '功能开关'},
                   'heartbeat_interval_min': {'type': 'number',
                                              'default': 60,
                                              'label': '状态检查间隔（分钟）',
                                              'min': 10,
                                              'max': 360,
                                              'step': 10,
                                              'order': 10,
                                              'section': '运行设置'},
                   'decay_multiplier': {'type': 'number',
                                        'default': 100,
                                        'label': '状态衰减倍率（%）',
                                        'min': 50,
                                        'max': 300,
                                        'step': 10,
                                        'order': 11,
                                        'section': '运行设置'},
                   'delete_delay_seconds': {'type': 'number',
                                            'default': 30,
                                            'label': '回复消息保留时间（秒）',
                                            'min': 5,
                                            'max': 300,
                                            'step': 5,
                                            'order': 12,
                                            'section': '运行设置'},
                   'event_chance_percent': {'type': 'number',
                                            'default': 25,
                                            'label': '随机事件触发概率（%）',
                                            'min': 0,
                                            'max': 100,
                                            'step': 5,
                                            'order': 13,
                                            'section': '运行设置'},
                   'daily_brief_chance_percent': {'type': 'number',
                                                  'default': 20,
                                                  'label': '每轮播报概率（%）',
                                                  'min': 0,
                                                  'max': 100,
                                                  'step': 5,
                                                  'order': 14,
                                                  'section': '运行设置'},
                   'status_cooldown_seconds': {'type': 'number',
                                               'default': 10,
                                               'label': '状态命令冷却（秒）',
                                               'min': 0,
                                               'max': 120,
                                               'step': 5,
                                               'order': 20,
                                               'section': '冷却设置'},
                   'action_cooldown_seconds': {'type': 'number',
                                               'default': 20,
                                               'label': '互动命令冷却（秒）',
                                               'min': 0,
                                               'max': 180,
                                               'step': 5,
                                               'order': 21,
                                               'section': '冷却设置'},
                   'use_item_cooldown_seconds': {'type': 'number',
                                                 'default': 15,
                                                 'label': '使用道具冷却（秒）',
                                                 'min': 0,
                                                 'max': 180,
                                                 'step': 5,
                                                 'order': 22,
                                                 'section': '冷却设置'},
                   'info': {'type': 'info',
                            'label': '玩法说明',
                            'order': 30,
                            'section': '命令说明',
                            'text': '先发送 /领养 名字 或 .领养 名字 来领养宠物；领养后可用 /状态、/喂食、/玩耍、/清洁 与它互动。用 /档案 查看成长档案，用 /背包 查看道具，用 '
                                    '/使用 道具名 来使用道具。'}},
 'tags': ['电子宠物', '喂养互动', '随机事件'],
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = '电子宠物'
