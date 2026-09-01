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

__plugin__ = {'name': 'Emby 剧集季集校验',
 'id': 'emby_episode_fix',
 'version': '1.0.1',
 'author': 'AWdress',
 'description': '检查 Emby 剧集识别是否与文件名中的 SxxExx 一致，并可按文件名直接修正季集号。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 扫描 Emby Episode 与文件名中的 SxxExx 是否一致\n'
              '- 支持测试连接、扫描检查、按文件名自动修复\n'
              '- 自动修复后可再次校验确认结果',
 'scope': 'user',
 'requirements': ['requests>=2.28'],
 'config_schema': {'enabled': {'type': 'boolean',
                               'default': True,
                               'label': '启用插件',
                               'section': '功能开关',
                               'cols': 3,
                               'order': 1},
                   'auto_delete_command': {'type': 'boolean',
                                           'default': True,
                                           'label': '自动删除命令消息',
                                           'section': '功能开关',
                                           'cols': 3,
                                           'order': 2},
                   'emby_server': {'type': 'string',
                                   'default': '',
                                   'label': 'Emby 地址',
                                   'section': '基础配置',
                                   'order': 10,
                                   'help': '例如：https://v.awdys.cn/',
                                   'required': True},
                   'api_key': {'type': 'password',
                               'default': '',
                               'label': 'Emby API Key',
                               'section': '基础配置',
                               'order': 11,
                               'required': True},
                   'user_id': {'type': 'string',
                               'default': '',
                               'label': 'Emby 用户 ID（可选）',
                               'section': '基础配置',
                               'order': 12,
                               'help': '留空时插件会自动取第一个可用用户；如要稳定写入，建议填写固定用户 ID。'},
                   'fix_lock_data': {'type': 'boolean',
                                     'default': True,
                                     'label': '修复后锁定条目数据',
                                     'section': '修复策略',
                                     'cols': 4,
                                     'order': 20,
                                     'help': '开启后会把 LockData 设为 true，减少后续刷新把季集又刮回去。'},
                   'max_output': {'type': 'slider',
                                  'default': 50,
                                  'label': '输出条目上限',
                                  'min': 5,
                                  'max': 200,
                                  'step': 5,
                                  'section': '修复策略',
                                  'order': 21,
                                  'help': '扫描结果在消息里最多展示多少条；完整信息仍会写日志。'},
                   'test_connection': {'type': 'action',
                                       'label': '测试连接',
                                       'action': 'test_connection',
                                       'section': '操作',
                                       'order': 30},
                   'scan_now': {'type': 'action',
                                'label': '扫描检查',
                                'action': 'scan_now',
                                'section': '操作',
                                'order': 31},
                   'fix_now': {'type': 'action',
                               'label': '按文件名自动修复',
                               'action': 'fix_now',
                               'section': '操作',
                               'order': 32,
                               'danger': True},
                   'last_scan_summary': {'type': 'info',
                                         'label': '最近扫描结果',
                                         'section': '状态',
                                         'order': 40,
                                         'text': '尚未执行扫描'}},
 'v1_compatible_version': '1.0.0',
 'v2_adapter': 'telethon',
 'tags': ['Emby剧集', '文件名校正', '元数据修复']}
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
