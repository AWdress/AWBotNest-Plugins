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

__plugin__ = {'name': 'PT站自动签到',
 'id': 'pt_multi_checkin',
 'version': '2.5.43',
 'author': 'AWdress',
 'description': '多 PT 站自动签到中心，统一使用平台 Cookie 与 CloakBrowser，提供 Vue 管理界面。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/pt_checkin_v2.svg',
 'changelog': 'v2.5.40 修复 V2 配置项声明\n'
              '- 补齐自动签到、重试、无头浏览器、结果通知与站点选择字段\n'
              '- 修复平台保存配置时报“包含未声明的配置项”\n\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.5.35 修复 Audiences Turnstile 点击可能落在外层容器的问题\n'
              '- 优先按 Cloudflare iframe 的真实边界点击复选框区域\n'
              '- 日志记录点击方式与 iframe 尺寸，便于确认真实交互\n'
              '\n'
              'v2.5.34 Docker 缺少 DISPLAY 时自动启动 Xvfb',
 'scope': 'standalone',
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12'],
 'cookie_domains': ['audiences.me',
                    '*.audiences.me',
                    'ourbits.club',
                    '*.ourbits.club',
                    'hhanclub.net',
                    '*.hhanclub.net',
                    'piggo.me',
                    '*.piggo.me',
                    'tjupt.org',
                    '*.tjupt.org',
                    '52pt.site',
                    '*.52pt.site',
                    'pt.btschool.club',
                    '*.pt.btschool.club',
                    'ptchdbits.co',
                    '*.ptchdbits.co',
                    'haidan.video',
                    '*.haidan.video',
                    'club.hares.top',
                    '*.club.hares.top',
                    'hdarea.club',
                    '*.hdarea.club',
                    'hdchina.org',
                    '*.hdchina.org',
                    'hdcity.city',
                    '*.hdcity.city',
                    'hdsky.me',
                    '*.hdsky.me',
                    'pt.hdupt.com',
                    '*.pt.hdupt.com',
                    'm-team.cc',
                    '*.m-team.cc',
                    'v6.nexushd.org',
                    '*.v6.nexushd.org',
                    'open.cd',
                    '*.open.cd',
                    'pterclub.net',
                    '*.pterclub.net',
                    'pttime.org',
                    '*.pttime.org',
                    'totheglory.im',
                    '*.totheglory.im',
                    'u2.dmhy.org',
                    '*.u2.dmhy.org',
                    'yemapt.org',
                    '*.yemapt.org',
                    'zhuque.in',
                    '*.zhuque.in'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 8,
               'max_background_tasks': 3,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'auto_checkin': {'type': 'boolean', 'default': True,
                                    'title': '启用自动签到', 'section': '签到计划', 'order': 1},
                   'checkin_hour': {'type': 'number', 'default': 8,
                                    'title': '签到小时', 'section': '签到计划', 'order': 2, 'min': 0, 'max': 23},
                   'checkin_minute': {'type': 'number', 'default': 10,
                                      'title': '签到分钟', 'section': '签到计划', 'order': 3, 'min': 0, 'max': 59},
                   'headless': {'type': 'boolean', 'default': True,
                                'title': '无头浏览器', 'section': '运行选项', 'order': 10},
                   'notify_result': {'type': 'boolean', 'default': True,
                                     'title': '推送签到结果', 'section': '运行选项', 'order': 11},
                   'retry_count': {'type': 'number', 'default': 2,
                                   'title': '失败重试次数', 'section': '运行选项', 'order': 12, 'min': 0, 'max': 5},
                   'retry_interval': {'type': 'number', 'default': 20,
                                      'title': '重试间隔（秒）', 'section': '运行选项', 'order': 13, 'min': 5, 'max': 300},
                   'selected_sites': {'type': 'array', 'default': ['audiences', 'ourbits', 'piggo', 'hhan', 'tjupt', 'pt52', 'btschool', 'chdbits', 'haidan', 'hares', 'hdarea', 'hdchina', 'hdcity', 'hdsky', 'hdupt', 'mteam', 'nexushd', 'opencd', 'pterclub', 'pttime', 'ttg', 'u2', 'yema', 'zhuque'],
                                      'title': '启用站点', 'section': '站点选择', 'order': 20},
                   'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'tjupt_ai_assist': {'type': 'boolean',
                                       'default': True,
                                       'title': 'tjupt ai assist',
                                       'section': 'V2 兼容字段',
                                       'order': 9000},
                   'tjupt_confirm_timeout': {'type': 'number',
                                             'default': 300,
                                             'title': 'tjupt confirm timeout',
                                             'section': 'V2 兼容字段',
                                             'order': 9001}},
 'v1_compatible_version': '2.5.35',
 'v2_adapter': 'telethon',
 'tags': ['PT站签到', '多站点', 'Cloudflare', 'Cookie'],
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
