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

__plugin__ = {'name': '115频道监控',
 'id': 'movie_monitor_115',
 'version': '1.0.17',
 'author': 'AWdress',
 'description': '通用监控频道里的 115 分享，读取/识别 TMDB 后查 Emby 媒体库，缺失的转发给 CMS 入库机器人。可选电影/电视剧，默认全部。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cloud_media.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.16 修复 Vue 配置与测试接口\n'
              '- 配置读取和保存迁移到新版平台 host 接口\n'
              '- 状态、日志、群组名称和连接测试改用 host.callApi\n'
              '- 保留旧配置的监控开关兼容性\n'
              '\n'
              'v1.0.14 修复识别与配置缺陷\n'
              '- 修复保存配置接口误用 await req.json() 导致配置无法保存\n'
              '- 修复 TMDB 搜索调用了不存在的 multi_search（改为 search_all）\n'
              '- 修复 Emby 查重缺少 media_type 参数导致去重失效、重复入库\n'
              '\n'
              'v1.0.13 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'requirements': [],
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'shareswitch': {'title': 'shareswitch',
                                   'section': 'V2 配置',
                                   'order': 1,
                                   'type': 'boolean',
                                   'default': False},
                   'monitor_ids': {'title': 'monitor ids',
                                   'section': 'V2 配置',
                                   'order': 2,
                                   'type': 'string',
                                   'default': ''},
                   'media_types': {'title': 'media types',
                                   'section': 'V2 配置',
                                   'order': 3,
                                   'type': 'text',
                                   'default': 'movie\ntv',
                                   'help': '每行一项'},
                   'only_complete_series': {'title': 'only complete series',
                                            'section': 'V2 配置',
                                            'order': 4,
                                            'type': 'boolean',
                                            'default': False},
                   'tmdb_api_key': {'title': 'tmdb api key',
                                    'section': 'V2 配置',
                                    'order': 5,
                                    'type': 'password',
                                    'default': ''},
                   'tmdb_language': {'title': 'tmdb language',
                                     'section': 'V2 配置',
                                     'order': 6,
                                     'type': 'string',
                                     'default': 'zh-CN'},
                   'emby_url': {'title': 'emby url',
                                'section': 'V2 配置',
                                'order': 7,
                                'type': 'string',
                                'default': ''},
                   'emby_api_key': {'title': 'emby api key',
                                    'section': 'V2 配置',
                                    'order': 8,
                                    'type': 'password',
                                    'default': ''},
                   'skip_emby_check': {'title': 'skip emby check',
                                       'section': 'V2 配置',
                                       'order': 9,
                                       'type': 'boolean',
                                       'default': False},
                   'cms_bot_username': {'title': 'cms bot username',
                                        'section': 'V2 配置',
                                        'order': 10,
                                        'type': 'string',
                                        'default': ''},
                   'forward_label': {'title': 'forward label',
                                     'section': 'V2 配置',
                                     'order': 11,
                                     'type': 'string',
                                     'default': '115 网盘'},
                   'forward_to_saved': {'title': 'forward to saved',
                                        'section': 'V2 配置',
                                        'order': 12,
                                        'type': 'boolean',
                                        'default': False},
                   'pan115_cookie': {'title': 'pan115 cookie',
                                     'section': 'V2 配置',
                                     'order': 13,
                                     'type': 'password',
                                     'default': ''}},
 'v1_compatible_version': '1.0.16',
 'v2_adapter': 'telethon',
 'tags': ['媒体', 'Telegram'],
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
