"""AWBotNest V2 原生通用抽奖插件。"""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': '通用抽奖',
 'id': 'common_lottery',
 'version': '2.0.2',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'description': '自动参与 @Lottery8Bot 等通用抽奖：解析口令、按需自动加群、随机等待后发口令。任意群可用。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/common_lottery.jpg',
 'changelog': 'v2.0.2 统一富文本表格通知\n- 加群、参与和失败通知改为结构化表格\n\n'
              'v2.0.1 修复 Telethon 机器人识别\n'
              '- 使用 User.bot 字段识别抽奖机器人，恢复自动参与功能\n'
              '\n'
              'v1.0.15 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.14 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.0.13 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.12 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.10 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.7 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.6 更新插件 Logo\n'
              '- 使用通用抽奖专属图片作为插件卡片与市场图标',
 'scope': 'user',
 'config_schema': {'auto_join': {'type': 'boolean',
                                 'default': False,
                                 'label': '自动加入要求的群/频道',
                                 'cols': 3,
                                 'order': 1,
                                 'section': '功能开关',
                                 'help': '抽奖要求先加群时，是否自动加入。关闭则遇到加群要求就跳过。'},
                   'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '参与结果通知我',
                                    'cols': 3,
                                    'order': 2,
                                    'section': '功能开关'},
                   'groups': {'type': 'chat',
                              'default': [],
                              'label': '监听群组',
                              'multi': True,
                              'chat_types': ['group', 'channel'],
                              'order': 10,
                              'section': '参与范围',
                              'help': '勾选要参与抽奖的群/频道；留空 = 所有群都参与。'},
                   'wait_min': {'type': 'number',
                                'default': 25,
                                'label': '参与前最短等待(秒)',
                                'min': 0,
                                'max': 300,
                                'step': 5,
                                'order': 20,
                                'section': '等待策略'},
                   'wait_max': {'type': 'number',
                                'default': 65,
                                'label': '参与前最长等待(秒)',
                                'min': 5,
                                'max': 600,
                                'step': 5,
                                'order': 21,
                                'section': '等待策略'}},
 'tags': ['通用抽奖', 'Lottery8Bot', '群组管理']}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
