"""pt_multi_checkin AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': 'PT站自动签到',
 'id': 'pt_multi_checkin',
 'version': '2.0.0',
 'author': 'AWdress',
 'description': '多 PT 站自动签到中心，统一使用平台 Cookie 与 CloakBrowser，提供 Vue 管理界面。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/pt_checkin_v2.svg',
 'changelog': 'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v2.5.51 修复 OurBits 新版签到回执识别\n'
              '- 兼容签到后跳转首页且不再显示文字回执的新页面流程\n'
              '- 仅在同域登录态首页且签到入口消失时确认完成，避免普通页面误报成功\n'
              '- 浏览器确认与轻量 HTTP 签到统一使用相同的严格判定\n'
              '\n'
              'v2.5.50 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v2.5.49 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v2.5.48 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v2.5.47 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v2.5.45 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'v2.5.40 修复 V2 配置项声明\n'
              '- 补齐自动签到、重试、无头浏览器、结果通知与站点选择字段\n'
              '- 修复平台保存配置时报“包含未声明的配置项”\n'
              '\n'
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
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12', 'opencv-python-headless>=4.8', 'numpy>=1.24'],
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
 'config_schema': {},
 'tags': ['PT站签到', '多站点', 'Cloudflare', 'Cookie'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = 'PT站自动签到'
