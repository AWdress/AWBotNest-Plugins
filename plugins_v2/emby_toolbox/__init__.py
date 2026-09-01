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

__plugin__ = {'name': 'Emby 工具箱',
 'id': 'emby_toolbox',
 'version': '1.4.2',
 'author': 'AWdress',
 'description': '集成 Emby 剧集校验、Genre 清理/映射、季名刮削、国家语言 Tag、别名写入、STRM 刷新、元数据缺失检查等维护功能。支持定时执行与完整日志。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.4.1 重做 Vue 界面配色\n'
              '- 去除大面积墨绿色背景，改为与平台一致的深海军蓝中性层次\n'
              '- Emby 青蓝仅用于开关、主按钮和选中状态\n'
              '- 重新校正卡片、输入框、次要文字与边框对比度\n'
              '\n'
              'v1.4.0 迁移 Vue 媒体维护控制台\n'
              '- 新增实时任务状态、历史记录和后台 API',
 'scope': 'standalone',
 'requirements': ['requests>=2.28'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'emby_server': {'title': 'emby server',
                                   'section': 'V2 配置',
                                   'order': 1,
                                   'type': 'string',
                                   'default': ''},
                   'api_key': {'title': 'api key',
                               'section': 'V2 配置',
                               'order': 2,
                               'type': 'password',
                               'default': ''},
                   'user_id': {'title': 'user id',
                               'section': 'V2 配置',
                               'order': 3,
                               'type': 'string',
                               'default': ''},
                   'tmdb_key': {'title': 'tmdb key',
                                'section': 'V2 配置',
                                'order': 4,
                                'type': 'string',
                                'default': ''},
                   'library_names': {'title': 'library names',
                                     'section': 'V2 配置',
                                     'order': 5,
                                     'type': 'string',
                                     'default': ''},
                   'fix_lock_data': {'title': 'fix lock data',
                                     'section': 'V2 配置',
                                     'order': 6,
                                     'type': 'boolean',
                                     'default': True},
                   'max_output': {'title': 'max output',
                                  'section': 'V2 配置',
                                  'order': 7,
                                  'type': 'number',
                                  'default': 50},
                   'genre_mapping_json': {'title': 'genre mapping json',
                                          'section': 'V2 配置',
                                          'order': 8,
                                          'type': 'string',
                                          'default': '{\n'
                                                     '  "Sci-Fi & Fantasy": "科幻",\n'
                                                     '  "War & Politics": "战争"\n'
                                                     '}'},
                   'genre_remove_list': {'title': 'genre remove list',
                                         'section': 'V2 配置',
                                         'order': 9,
                                         'type': 'string',
                                         'default': ''},
                   'add_hant_title': {'title': 'add hant title',
                                      'section': 'V2 配置',
                                      'order': 10,
                                      'type': 'boolean',
                                      'default': True},
                   'strm_delay': {'title': 'strm delay',
                                  'section': 'V2 配置',
                                  'order': 11,
                                  'type': 'number',
                                  'default': 3},
                   'enable_episode_fix': {'title': 'enable episode fix',
                                          'section': 'V2 配置',
                                          'order': 12,
                                          'type': 'boolean',
                                          'default': True},
                   'enable_delete_episode_genre': {'title': 'enable delete episode genre',
                                                   'section': 'V2 配置',
                                                   'order': 13,
                                                   'type': 'boolean',
                                                   'default': False},
                   'enable_genre_mapper': {'title': 'enable genre mapper',
                                           'section': 'V2 配置',
                                           'order': 14,
                                           'type': 'boolean',
                                           'default': False},
                   'enable_season_renamer': {'title': 'enable season renamer',
                                             'section': 'V2 配置',
                                             'order': 15,
                                             'type': 'boolean',
                                             'default': False},
                   'enable_country_scraper': {'title': 'enable country scraper',
                                              'section': 'V2 配置',
                                              'order': 16,
                                              'type': 'boolean',
                                              'default': False},
                   'enable_alt_renamer': {'title': 'enable alt renamer',
                                          'section': 'V2 配置',
                                          'order': 17,
                                          'type': 'boolean',
                                          'default': False},
                   'enable_strm_mediainfo': {'title': 'enable strm mediainfo',
                                             'section': 'V2 配置',
                                             'order': 18,
                                             'type': 'boolean',
                                             'default': False},
                   'enable_damaged_check': {'title': 'enable damaged check',
                                            'section': 'V2 配置',
                                            'order': 19,
                                            'type': 'boolean',
                                            'default': False},
                   'enable_auto_schedule': {'title': 'enable auto schedule',
                                            'section': 'V2 配置',
                                            'order': 20,
                                            'type': 'boolean',
                                            'default': False},
                   'schedule_cron': {'title': 'schedule cron',
                                     'section': 'V2 配置',
                                     'order': 21,
                                     'type': 'string',
                                     'default': '0 3 * * *'},
                   'schedule_functions': {'title': 'schedule functions',
                                          'section': 'V2 配置',
                                          'order': 22,
                                          'type': 'text',
                                          'default': '',
                                          'help': '每行一项'},
                   'last_summary': {'type': 'string',
                                    'default': '',
                                    'title': 'last summary',
                                    'section': 'V2 兼容字段',
                                    'order': 9001}},
 'v1_compatible_version': '1.4.1',
 'v2_adapter': 'telethon',
 'tags': ['媒体'],
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
