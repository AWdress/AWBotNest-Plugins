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

__plugin__ = {'name': 'AWEmbyPush',
 'id': 'awembypush',
 'version': '1.5.11',
 'scope': 'standalone',
 'author': 'AWdress',
 'description': '监听 Emby/Jellyfin 入库 Webhook，经 TMDB 增强/剧集合并/去重后，通过 Telegram/企业微信/Bark 推送精美媒体通知。（自 MoviePilot '
                '插件移植）自带 Vue 配置界面 + 最近推送/测试推送。',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.5.8 标明独立运行\n'
              '- 插件不依赖用户账号或机器人，安装后会显示“独立运行”\n'
              '- Webhook 和原有通知功能保持不变\n'
              '\n'
              'v1.5.7 修复去重记录竞态\n'
              '- 发送去重记录的读写加锁，避免多线程并发读写竞态\n'
              '\n'
              'v1.5.6 移植到 AWBotNest 平台\n'
              '- 自 MoviePilot 插件 AWEmbyPush v1.5.5 移植\n'
              '- 使用平台 Webhook 机制和 Vue 配置界面\n'
              '- 支持 Telegram/企业微信/Bark 三种推送渠道\n'
              '- 自动走平台代理，支持 TMDB 元数据增强\n'
              '- 剧集合并、去重、测试推送功能完整保留',
 'icon': 'https://raw.githubusercontent.com/AWdress/MoviePilot-Plugins/main/plugins/awembypush/logo.png',
 'webhook': True,
 'requirements': ['requests>=2.28'],
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'enable_tmdb': {'title': 'enable tmdb',
                                   'section': 'V2 配置',
                                   'order': 1,
                                   'type': 'boolean',
                                   'default': True},
                   'tmdb_api_key': {'title': 'tmdb api key',
                                    'section': 'V2 配置',
                                    'order': 2,
                                    'type': 'password',
                                    'default': ''},
                   'tmdb_api_domain': {'title': 'tmdb api domain',
                                       'section': 'V2 配置',
                                       'order': 3,
                                       'type': 'string',
                                       'default': 'api.themoviedb.org'},
                   'tmdb_image_domain': {'title': 'tmdb image domain',
                                         'section': 'V2 配置',
                                         'order': 4,
                                         'type': 'string',
                                         'default': 'image.tmdb.org'},
                   'emby_server_url': {'title': 'emby server url',
                                       'section': 'V2 配置',
                                       'order': 5,
                                       'type': 'string',
                                       'default': ''},
                   'dedup_window': {'title': 'dedup window',
                                    'section': 'V2 配置',
                                    'order': 6,
                                    'type': 'number',
                                    'default': 60},
                   'episode_cache_timeout': {'title': 'episode cache timeout',
                                             'section': 'V2 配置',
                                             'order': 7,
                                             'type': 'number',
                                             'default': 30},
                   'enable_watch_link': {'title': 'enable watch link',
                                         'section': 'V2 配置',
                                         'order': 8,
                                         'type': 'boolean',
                                         'default': False},
                   'watch_link_type': {'title': 'watch link type',
                                       'section': 'V2 配置',
                                       'order': 9,
                                       'type': 'string',
                                       'default': 'server'},
                   'link_redirect_prefix': {'title': 'link redirect prefix',
                                            'section': 'V2 配置',
                                            'order': 10,
                                            'type': 'string',
                                            'default': ''},
                   'tg_bot_token': {'title': 'tg bot token',
                                    'section': 'V2 配置',
                                    'order': 11,
                                    'type': 'password',
                                    'default': ''},
                   'tg_chat_id': {'title': 'tg chat id',
                                  'section': 'V2 配置',
                                  'order': 12,
                                  'type': 'chat',
                                  'default': '',
                                  'chat_types': ['group', 'channel'],
                                  'session': True},
                   'tg_api_host': {'title': 'tg api host',
                                   'section': 'V2 配置',
                                   'order': 13,
                                   'type': 'string',
                                   'default': ''},
                   'wx_corp_id': {'title': 'wx corp id',
                                  'section': 'V2 配置',
                                  'order': 14,
                                  'type': 'string',
                                  'default': ''},
                   'wx_corp_secret': {'title': 'wx corp secret',
                                      'section': 'V2 配置',
                                      'order': 15,
                                      'type': 'password',
                                      'default': ''},
                   'wx_agent_id': {'title': 'wx agent id',
                                   'section': 'V2 配置',
                                   'order': 16,
                                   'type': 'string',
                                   'default': ''},
                   'wx_user_id': {'title': 'wx user id',
                                  'section': 'V2 配置',
                                  'order': 17,
                                  'type': 'string',
                                  'default': '@all'},
                   'wx_msg_type': {'title': 'wx msg type',
                                   'section': 'V2 配置',
                                   'order': 18,
                                   'type': 'string',
                                   'default': 'news_notice'},
                   'wx_proxy_url': {'title': 'wx proxy url',
                                    'section': 'V2 配置',
                                    'order': 19,
                                    'type': 'string',
                                    'default': ''},
                   'wx_no_proxy': {'title': 'wx no proxy',
                                   'section': 'V2 配置',
                                   'order': 20,
                                   'type': 'boolean',
                                   'default': True},
                   'bark_server': {'title': 'bark server',
                                   'section': 'V2 配置',
                                   'order': 21,
                                   'type': 'string',
                                   'default': 'https://api.day.app'},
                   'bark_keys': {'title': 'bark keys',
                                 'section': 'V2 配置',
                                 'order': 22,
                                 'type': 'string',
                                 'default': ''},
                   'enable_custom_template': {'title': 'enable custom template',
                                              'section': 'V2 配置',
                                              'order': 23,
                                              'type': 'boolean',
                                              'default': False},
                   'tg_template': {'title': 'tg template',
                                   'section': 'V2 配置',
                                   'order': 24,
                                   'type': 'string',
                                   'default': ''},
                   'wx_title_template': {'title': 'wx title template',
                                         'section': 'V2 配置',
                                         'order': 25,
                                         'type': 'string',
                                         'default': ''},
                   'wx_body_template': {'title': 'wx body template',
                                        'section': 'V2 配置',
                                        'order': 26,
                                        'type': 'string',
                                        'default': ''},
                   'bark_title_template': {'title': 'bark title template',
                                           'section': 'V2 配置',
                                           'order': 27,
                                           'type': 'string',
                                           'default': ''},
                   'bark_body_template': {'title': 'bark body template',
                                          'section': 'V2 配置',
                                          'order': 28,
                                          'type': 'string',
                                          'default': ''}},
 'v1_compatible_version': '1.5.9',
 'v2_adapter': 'telethon',
 'tags': ['Emby推送', '媒体通知', 'TMDB匹配'],
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
