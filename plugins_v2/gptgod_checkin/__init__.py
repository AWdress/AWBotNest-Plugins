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

__plugin__ = {'name': 'GPT-GOD 自动签到',
 'id': 'gptgod_checkin',
 'version': '1.1.10',
 'author': 'AWdress',
 'description': '使用平台托管浏览器为多个 GPT-GOD 账号每日自动签到，支持独立会话复用、立即签到和汇总通知。',
 'changelog': 'AWBotNest 2 兼容发布\n'
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
                                'help': '逐个添加 GPT-GOD 账号。旧版单账号配置会自动继续使用。',
                                'section': '账号',
                                'cols': 12,
                                'order': 10,
                                'fields': {'email': {'type': 'string',
                                                     'label': '登录邮箱',
                                                     'help': 'GPT-GOD 注册邮箱。'},
                                           'password': {'type': 'password',
                                                        'label': '账户密码',
                                                        'help': 'GPT-GOD 账户密码，不是邮箱密码。'}}},
                   'checkin_hour': {'type': 'slider',
                                    'default': 8,
                                    'label': '签到小时',
                                    'min': 0,
                                    'max': 23,
                                    'step': 1,
                                    'section': '定时',
                                    'cols': 6,
                                    'order': 20},
                   'checkin_minute': {'type': 'slider',
                                      'default': 5,
                                      'label': '签到分钟',
                                      'min': 0,
                                      'max': 59,
                                      'step': 1,
                                      'section': '定时',
                                      'cols': 6,
                                      'order': 21},
                   'retry_count': {'type': 'slider',
                                   'default': 2,
                                   'label': '失败重试次数',
                                   'min': 0,
                                   'max': 5,
                                   'step': 1,
                                   'help': '单个账号首次失败后最多再次尝试的次数。',
                                   'section': '重试',
                                   'cols': 6,
                                   'order': 24},
                   'retry_interval': {'type': 'slider',
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
 'v1_compatible_version': '1.1.9',
 'v2_adapter': 'telethon',
 'tags': ['自动签到', '多账号', '网页自动化']}
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
