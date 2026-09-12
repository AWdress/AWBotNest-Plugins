"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': '癫影积分红包',
 'id': 'dyp_redpacket',
 'version': '2.0.4',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'scope': 'user',
 'description': '监控癫影小助手发的混合积分红包，逐个点击未抢数字按钮；抽奖报名遇到限时算式验证时，仅在消息明确点名当前账号后自动回复。发包bot/群组内置写死。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/dyp_redpacket.jpg',
 'changelog': 'v2.0.4 支持抽奖报名验证\n'
              '- 识别癫影小助手发出的限时报名算式并回复验证消息\n'
              '- 仅在验证消息明确点名当前 Telegram 账号时作答，点名他人时忽略\n'
              '- 支持账号姓名、完整姓名和用户名匹配，并避免重复作答\n\n'
              'v2.0.3 修复多行通知显示\n'
              '- 抢包结果按状态、详情拆分为独立表格行\n'
              '- 避免完整正文挤入单个单元格导致裁切或显示不全\n\n'
              'v2.0.2 修复原生 Telethon 抢包链路\n'
              '- 修复机器人身份识别、按钮读取和点击参数，恢复自动抢包\n'
              '- 启动日志显示内部开关、固定群组和点击延迟\n\n'
              'v2.0.1 统一富文本表格通知\n- 红包结果改为平台结构化表格\n\n'
              'v1.2.10 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.2.9 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.2.8 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.2.7 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.2.5 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.2 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.2.1 更新插件 Logo\n'
              '- 使用癫影专属图片作为插件卡片与市场图标',
 'config_schema': {'dyp_enabled': {'type': 'boolean',
                                   'default': False,
                                   'label': '启用癫影积分红包',
                                   'cols': 3,
                                   'order': 1,
                                   'section': '功能开关',
                                   'help': '癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过）。现为混合红包（暗含 N 个雷包），照抢、赌不中雷。'},
                   'notify_owner': {'type': 'boolean',
                                    'default': True,
                                    'label': '抢到/踩雷时通知我',
                                    'cols': 3,
                                    'order': 2,
                                    'section': '功能开关',
                                    'help': '抢到红包或踩雷时用机器人通知平台主人；未抢到（都被别人抢完）仅记录日志不通知。'},
                   'dyp_delay': {'type': 'number',
                                 'default': 0,
                                 'label': '点击延迟-最小(秒)',
                                 'min': 0,
                                 'max': 60,
                                 'step': 1,
                                 'order': 10,
                                 'section': '延迟参数',
                                 'show_if': {'dyp_enabled': True},
                                 'help': '抢包前等待的最小秒数。与「点击延迟-最大」配合：最大>最小时在两者间取随机值，别太机械；相等或最大更小则固定等这么久。'},
                   'dyp_delay_max': {'type': 'number',
                                     'default': 0,
                                     'label': '点击延迟-最大(秒)',
                                     'min': 0,
                                     'max': 60,
                                     'step': 1,
                                     'order': 11,
                                     'section': '延迟参数',
                                     'show_if': {'dyp_enabled': True},
                                     'help': '抢包前等待的最大秒数。填得比「最小」大即启用随机延迟(每次在最小~最大间随机)；填 0 或不大于最小则退化为固定延迟。'}},
 'tags': ['红包领取', '动态口令', '自动抢包']}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
