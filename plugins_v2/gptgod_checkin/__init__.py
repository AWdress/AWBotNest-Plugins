"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': 'GPT-GOD 自动签到',
 'id': 'gptgod_checkin',
 'version': '2.0.6',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'description': '使用平台托管浏览器为多个 GPT-GOD 账号定时自动签到，支持每日时分、Cron、独立会话复用、立即签到和汇总通知。',
 'changelog': 'v2.0.6 适配平台正式调度规范\n- Cron 配置声明为平台 cron 格式并复用统一 CronInput 组件\n- 定时任务只使用平台正式 schedule_cron 接口\n\n'
              'v2.0.5 复核密码独立显隐\n- 多账号密码继续逐行默认隐藏，每行提供独立眼睛按钮\n- 账号列表由平台受控读取真实值，避免显示脱敏占位符\n\n'
              'v2.0.4 恢复多账号列表配置\n- 恢复逐个添加、删除 GPT-GOD 账号的配置方式\n- 整个账号列表按敏感字段受控读取，每个密码默认隐藏并可单独显示\n- 自动将 2.0.3 单行账号配置还原为列表，不丢失已保存账号\n\n'
              'v2.0.3 适配平台敏感配置规范\n- 多账号凭据整体脱敏，避免嵌套列表密码经配置接口泄露\n\n'
              'v2.0.2 新增双定时方式\n- 可选择每天指定时分或标准五段 Cron 表达式\n- 非法 Cron 会记录明确错误且不影响插件启用和手动签到\n\n'
              'v2.0.1 统一富文本表格通知\n- 签到汇总与无账号结果统一使用结构化表格\n\n'
              'v1.1.18 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.1.17 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.1.16 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.1.15 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.1.13 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.1.9 修复定时签到完成后仍显示运行中\n'
              '- 定时触发改为投递平台托管后台任务，避免浏览器或通知收尾占住计划任务状态\n'
              '- 签到结果通知增加 30 秒超时，不再无限等待\n'
              '\n'
              'v1.1.8 修复新版福利页误点快捷入口\n'
              '- 严格匹配‘签到 领取 N 积分’按钮，不再误点‘签到 / 兑换码’快捷入口\n'
              '- 本地使用真实账号完成首次签到并取得服务端 success 回执\n'
              '- 二次运行正确识别今天已签到，不会重复提交\n'
              '\n'
              'v1.1.7 适配 GPT-GOD 新版签到回执\n'
              '- 兼容空 2xx、纯文本与 JSON 三类响应\n'
              '- 修复 JSON 解析失败时丢弃成功 HTTP 状态导致的误报失败',
 'icon': 'https://gptgod.online/favicon.ico',
 'scope': 'standalone',
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'auto_checkin': {'type': 'boolean',
                                    'default': True,
                                    'label': '启用自动签到',
                                    'section': '功能开关',
                                    'cols': 4,
                                    'order': 1},
                   'notify': {'type': 'boolean',
                              'default': True,
                              'label': '推送签到结果',
                              'section': '功能开关',
                              'cols': 4,
                              'order': 2},
                   'auto_retry': {'type': 'boolean',
                                  'default': True,
                                  'label': '失败后自动重试',
                                  'help': '仅重试浏览器启动、网络、页面加载和网站临时异常；明确的账号密码错误不会重试。',
                                  'section': '功能开关',
                                  'cols': 4,
                                  'order': 3},
                   'accounts': {'type': 'list',
                                'default': [],
                                'label': '签到账号',
                                'item_label': '账号',
                                'secret': True,
                                'help': '逐个添加 GPT-GOD 账号；账号列表整体受平台保护，密码默认隐藏。',
                                'section': '账号',
                                'cols': 12,
                                'order': 10,
                                'fields': {'email': {'type': 'string',
                                                     'label': '登录邮箱'},
                                           'password': {'type': 'password',
                                                        'label': '账户密码'}}},
                   'email': {'type': 'string',
                             'default': '',
                             'label': '旧版登录邮箱',
                             'show_if': {'legacy_account_visible': True},
                             'section': '兼容迁移',
                             'order': 90},
                   'password': {'type': 'password',
                                'default': '',
                                'label': '旧版账户密码',
                                'show_if': {'legacy_account_visible': True},
                                'section': '兼容迁移',
                                'order': 91},
                   'checkin_hour': {'type': 'number',
                                    'default': 8,
                                    'label': '签到小时',
                                    'min': 0,
                                    'max': 23,
                                    'step': 1,
                                    'section': '定时',
                                    'cols': 6,
                                    'order': 21,
                                    'show_if': {'schedule_mode': 'daily'}},
                   'checkin_minute': {'type': 'number',
                                      'default': 5,
                                      'label': '签到分钟',
                                      'min': 0,
                                      'max': 59,
                                      'step': 1,
                                      'section': '定时',
                                      'cols': 6,
                                      'order': 22,
                                      'show_if': {'schedule_mode': 'daily'}},
                   'schedule_mode': {'type': 'select',
                                     'default': 'daily',
                                     'label': '定时方式',
                                     'options': [{'value': 'daily', 'label': '每天指定时间'},
                                                 {'value': 'cron', 'label': 'Cron 表达式'}],
                                     'section': '定时',
                                     'cols': 12,
                                     'order': 20},
                   'cron_expression': {'type': 'string',
                                       'format': 'cron',
                                       'default': '5 8 * * *',
                                       'label': 'Cron 表达式',
                                       'help': '依次填写：分钟 小时 日 月 星期，例如 5 8 * * * 表示每天 08:05。',
                                       'section': '定时',
                                       'cols': 12,
                                       'order': 23,
                                       'show_if': {'schedule_mode': 'cron'}},
                   'retry_count': {'type': 'number',
                                   'default': 2,
                                   'label': '失败重试次数',
                                   'min': 0,
                                   'max': 5,
                                   'step': 1,
                                   'help': '单个账号首次失败后最多再次尝试的次数。',
                                   'section': '重试',
                                   'cols': 6,
                                   'order': 24},
                   'retry_interval': {'type': 'number',
                                      'default': 20,
                                      'label': '重试间隔（秒）',
                                      'min': 5,
                                      'max': 300,
                                      'step': 5,
                                      'help': '两次尝试之间的等待时间，建议至少 20 秒，避免网站限流。',
                                      'section': '重试',
                                      'cols': 6,
                                      'order': 25},
                   'run_now': {'type': 'action',
                               'label': '立即签到',
                               'action': 'run_now',
                               'section': '操作',
                               'cols': 6,
                               'order': 30},
                   'last_result': {'type': 'info',
                                   'default': '尚未运行',
                                   'label': '最近结果',
                                   'section': '运行状态',
                                   'cols': 12,
                                   'order': 40},
                   'checkin_history': {'type': 'info',
                                       'default': '暂无记录',
                                       'label': '最近签到记录',
                                       'section': '运行状态',
                                       'cols': 12,
                                       'order': 41}},
 'tags': ['GPT-GOD签到', '多账号', '网页自动化'],
 'render_mode': 'vue'}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
